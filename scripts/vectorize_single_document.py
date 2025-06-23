#!/usr/bin/env python3
"""
Script pour vectoriser un seul document uploadé
"""
import os
import sys
import json
import logging
from pathlib import Path

# Configuration Django
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mediServe.settings')
django.setup()

from django.conf import settings
from documents.models import DocumentUpload
from patients.models import Patient
import numpy as np
import h5py
import faiss
import pdfplumber
import camelot
from PIL import Image
import pytesseract
from sentence_transformers import SentenceTransformer
from whoosh import index as whoosh_index
from whoosh.fields import Schema, TEXT, ID
from whoosh.analysis import RegexTokenizer, LowercaseFilter
import nltk

# Configuration logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Télécharger les modèles NLTK si nécessaire
try:
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)
except Exception: # noqa
    pass

# Analyseur pour le français
FR_ANALYZER = RegexTokenizer(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+") | LowercaseFilter()

class DocumentVectorizer:
    def __init__(self, embedder_name=None):
        if embedder_name is None:
            embedder_name = settings.RAG_SETTINGS.get('EMBEDDING_MODEL', 'all-mpnet-base-v2')
        logger.info(f"Initialisation de DocumentVectorizer avec le modèle: {embedder_name}")
        self.embedder = SentenceTransformer(embedder_name)
        self.dim = self.embedder.get_sentence_embedding_dimension()
        self.embedder_name = embedder_name # Sauvegarder pour les métadonnées
        
    def process_document(self, document_upload_id: int):
        """Traite et vectorise un document"""
        doc_upload = None # Définir au cas où le premier try échoue
        try:
            # 1. Récupérer le document
            doc_upload = DocumentUpload.objects.get(id=document_upload_id)
            patient = doc_upload.patient
            
            logger.info(f"Traitement du document {doc_upload.original_filename} pour {patient.full_name()}")
            
            # 2. Vérifier que le fichier existe
            if not doc_upload.file or not os.path.exists(doc_upload.file.path):
                raise FileNotFoundError(f"Fichier physique introuvable: {doc_upload.file.path}")
            
            # 3. Extraire le texte selon le type
            file_path = doc_upload.file.path
            file_ext = doc_upload.file_type.lower()
            
            if file_ext == 'pdf':
                passages = self.extract_text_from_pdf(file_path)
            elif file_ext in ['jpg', 'jpeg', 'png', 'tiff', 'bmp']:
                passages = self.extract_text_from_image(file_path)
            else:
                raise ValueError(f"Type de fichier non supporté: {file_ext}")
            
            if not passages:
                raise ValueError("Aucun texte extrait du document")
            
            logger.info(f"Extrait {len(passages)} passages du document")
            
            # 4. Préparer les chemins de stockage pour ce patient
            # Utiliser RAG_SETTINGS pour la robustesse
            vector_dir = settings.RAG_SETTINGS['VECTOR_STORE_DIR']
            index_dir = settings.RAG_SETTINGS['BM25_INDEX_DIR']
            
            # Créer les dossiers de base s'ils n'existent pas (déjà fait dans settings.py mais redondance ok)
            os.makedirs(vector_dir, exist_ok=True)
            os.makedirs(index_dir, exist_ok=True)
            
            patient_vector_dir = os.path.join(vector_dir, f'patient_{patient.id}')
            patient_bm25_dir = os.path.join(index_dir, f'patient_{patient.id}_bm25')
            
            os.makedirs(patient_vector_dir, exist_ok=True)
            os.makedirs(patient_bm25_dir, exist_ok=True)

            hdf5_path = os.path.join(patient_vector_dir, 'vector_store.h5')
            faiss_path = os.path.join(patient_vector_dir, 'vector_store.faiss')
            
            # 5. Charger ou créer les stores existants
            if os.path.exists(hdf5_path):
                logger.info(f"Chargement du vector store existant: {hdf5_path}")
                vectors, metadata = self.load_existing_store(hdf5_path)
            else:
                logger.info(f"Création d'un nouveau vector store: {hdf5_path}")
                vectors = []
                metadata = []
            
            # 6. Vectoriser les nouveaux passages
            new_vectors = []
            new_metadata = []
            
            for i, passage in enumerate(passages):
                # Créer l'embedding
                vec = self.embedder.encode(passage['text'], convert_to_numpy=True)
                # S'assurer que vec est un array 1D avant reshape
                if vec.ndim == 1:
                    vec_norm = vec.reshape(1, -1)
                else:
                    vec_norm = vec
                faiss.normalize_L2(vec_norm)
                
                # Créer les métadonnées
                meta = {
                    'id': f"doc{doc_upload.id}_patient{patient.id}_{passage['source']}_p{passage['page']}_c{i}",
                    'patient_id': str(patient.id),
                    'document_id': str(doc_upload.id),
                    'source': passage['source'],
                    'type': passage['source'], # 'type' est souvent utilisé, 'source' peut être plus spécifique
                    'page': passage['page'],
                    'text': passage['text'],
                    'file_name': doc_upload.original_filename,
                    'embedder': self.embedder_name # Utiliser la variable d'instance
                }
                
                new_vectors.append(vec_norm[0]) # Stocker le vecteur 1D
                new_metadata.append(meta)
            
            # 7. Combiner avec les vecteurs existants
            all_vectors = vectors + new_vectors
            all_metadata = metadata + new_metadata
            
            # 8. Sauvegarder dans HDF5
            self.save_to_hdf5(hdf5_path, all_vectors, all_metadata)
            
            # 9. Créer/Mettre à jour l'index FAISS
            self.update_faiss_index(faiss_path, all_vectors)
            
            # 10. Mettre à jour l'index BM25
            if settings.RAG_SETTINGS.get('USE_BM25', True):
                self.update_bm25_index(patient_bm25_dir, new_metadata) # Utiliser patient_bm25_dir
            
            # 11. Mettre à jour le statut du document
            doc_upload.upload_status = 'indexed'
            doc_upload.processed_at = django.utils.timezone.now()
            doc_upload.error_message = '' # Effacer les erreurs précédentes
            doc_upload.save()
            
            logger.info(f"✅ Document {document_upload_id} vectorisé avec succès pour patient {patient.id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la vectorisation du document {document_upload_id}: {str(e)}", exc_info=True)
            
            if doc_upload:
                doc_upload.upload_status = 'failed'
                doc_upload.error_message = str(e)
                doc_upload.save()
            
            return False
    
    def extract_text_from_pdf(self, pdf_path: str) -> list:
        """Extrait le texte d'un PDF page par page"""
        passages = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    if text.strip():
                        passages.append({
                            'source': 'pdf_page', # Plus spécifique
                            'page': page_idx + 1, # Pages habituellement 1-indexed pour l'utilisateur
                            'text': text.strip()
                        })
        except Exception as e:
            logger.error(f"Erreur extraction PDF: {e}", exc_info=True)
        
        try:
            tables = camelot.read_pdf(pdf_path, pages="all", flavor='stream', suppress_stdout=True)
            for tbl in tables:
                # Convertir le dataframe en une représentation textuelle simple
                # ou HTML si c'est mieux pour le RAG
                table_text = tbl.df.to_string(index=False)
                passages.append({
                    'source': 'pdf_table', # Plus spécifique
                    'page': int(tbl.page), # Page 1-indexed
                    'text': table_text
                })
        except Exception as e:
            logger.warning(f"Extraction de table Camelot échouée ou aucune table trouvée: {e}")
        
        return passages
    
    def extract_text_from_image(self, image_path: str) -> list:
        """Extrait le texte d'une image via OCR"""
        passages = []
        
        try:
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img, lang='fra') # Préciser la langue si possible
            
            if text.strip():
                passages.append({
                    'source': 'image_ocr', # Plus spécifique
                    'page': 0, # Pas de notion de page pour une image simple
                    'text': text.strip()
                })
        except Exception as e:
            logger.error(f"Erreur OCR: {e}", exc_info=True)
        
        return passages
    
    def load_existing_store(self, hdf5_path: str) -> tuple:
        """Charge un store HDF5 existant"""
        vectors = []
        metadata = []
        
        try:
            with h5py.File(hdf5_path, 'r') as hf:
                if 'vectors' in hf:
                    vectors = list(hf['vectors'][:])
                if 'metadata' in hf:
                    # Gérer le cas où metadata est vide ou n'est pas un tableau de bytes encodés
                    raw_meta = hf['metadata'][:]
                    for item in raw_meta:
                        if isinstance(item, bytes):
                            metadata.append(json.loads(item.decode('utf-8')))
                        elif isinstance(item, str): # Au cas où ce serait déjà des strings JSON
                             metadata.append(json.loads(item))
                        # Si c'est autre chose, on pourrait logger une erreur ou l'ignorer
        except FileNotFoundError:
            logger.info(f"Fichier HDF5 non trouvé ({hdf5_path}), nouveau store sera créé.")
        except Exception as e:
            logger.error(f"Erreur chargement store HDF5 ({hdf5_path}): {e}", exc_info=True)
        return vectors, metadata
    
    def save_to_hdf5(self, hdf5_path: str, vectors: list, metadata: list):
        """Sauvegarde les vecteurs et métadonnées dans HDF5"""
        try:
            with h5py.File(hdf5_path, 'w') as hf:
                if vectors:
                    vectors_array = np.array(vectors, dtype='float32')
                    if vectors_array.ndim == 1: # S'il n'y a qu'un seul vecteur
                        vectors_array = vectors_array.reshape(1, -1)
                    hf.create_dataset('vectors', data=vectors_array)
                
                if metadata:
                    dt = h5py.special_dtype(vlen=bytes)
                    meta_dataset = hf.create_dataset('metadata', (len(metadata),), dtype=dt)
                    for i, meta_item in enumerate(metadata):
                        meta_dataset[i] = json.dumps(meta_item).encode('utf-8')
            logger.info(f"Store HDF5 sauvegardé: {hdf5_path}")
        except Exception as e:
            logger.error(f"Erreur sauvegarde HDF5 ({hdf5_path}): {e}", exc_info=True)
    
    def update_faiss_index(self, faiss_path: str, vectors: list):
        """Met à jour l'index FAISS"""
        if not vectors:
            logger.info("Aucun vecteur à ajouter à l'index FAISS.")
            # Supprimer l'ancien index s'il n'y a plus de vecteurs ? Ou le laisser vide ?
            # Pour l'instant, on ne fait rien si vectors est vide.
            # Si un index vide doit être créé, cela doit être géré explicitement.
            if os.path.exists(faiss_path): # Si pas de vecteurs mais un vieil index existe
                try:
                    os.remove(faiss_path)
                    logger.info(f"Ancien index FAISS supprimé car plus de vecteurs: {faiss_path}")
                except OSError as e:
                    logger.error(f"Impossible de supprimer l'ancien index FAISS {faiss_path}: {e}", exc_info=True)
            return

        try:
            vectors_array = np.array(vectors, dtype='float32')
            if vectors_array.ndim == 1: # S'il n'y a qu'un seul vecteur
                vectors_array = vectors_array.reshape(1, -1)

            faiss.normalize_L2(vectors_array) # Normaliser avant d'ajouter
            
            index = faiss.IndexFlatIP(self.dim) # Utiliser IndexFlatIP pour similarité cosinus après normalisation L2
            index.add(vectors_array)
            
            faiss.write_index(index, faiss_path)
            logger.info(f"Index FAISS mis à jour/créé: {faiss_path} avec {index.ntotal} vecteurs")
        except Exception as e:
            logger.error(f"Erreur mise à jour FAISS ({faiss_path}): {e}", exc_info=True)
    
    def update_bm25_index(self, bm25_dir: str, new_metadata: list):
        """Met à jour l'index BM25. Ajoute seulement les nouveaux documents."""
        if not new_metadata: # Seulement traiter s'il y a de nouvelles métadonnées à ajouter
            logger.info("Aucune nouvelle métadonnée pour l'index BM25.")
            return

        try:
            if not os.path.exists(bm25_dir):
                os.makedirs(bm25_dir)
                schema = Schema(id=ID(stored=True, unique=True), content=TEXT(analyzer=FR_ANALYZER))
                idx = whoosh_index.create_in(bm25_dir, schema)
                logger.info(f"Index BM25 créé: {bm25_dir}")
            else:
                try:
                    idx = whoosh_index.open_dir(bm25_dir)
                    logger.info(f"Index BM25 ouvert: {bm25_dir}")
                except whoosh_index.EmptyIndexError: # Si le dossier existe mais est vide/corrompu
                    logger.warning(f"Index BM25 existant à {bm25_dir} est vide ou corrompu. Recréation.")
                    schema = Schema(id=ID(stored=True, unique=True), content=TEXT(analyzer=FR_ANALYZER))
                    idx = whoosh_index.create_in(bm25_dir, schema)


            # Utiliser un writer avec modification pour ajouter ou mettre à jour
            writer = idx.writer()
            for meta in new_metadata:
                # id est unique, donc update=True va remplacer si l'id existe déjà.
                # C'est utile si on re-vectorise un document.
                writer.update_document(
                    id=meta['id'], 
                    content=meta['text']
                )
            writer.commit()
            
            logger.info(f"Index BM25 mis à jour: {len(new_metadata)} documents traités dans {bm25_dir}")
            
        except Exception as e:
            logger.warning(f"Erreur mise à jour BM25 ({bm25_dir}): {e}", exc_info=True)

def main():
    """Point d'entrée principal"""
    if len(sys.argv) != 2:
        print("Usage: python vectorize_single_document.py <document_upload_id>")
        sys.exit(1)
    
    try:
        document_id = int(sys.argv[1])
    except ValueError:
        print("L'ID du document doit être un nombre entier.")
        sys.exit(1)
    
    vectorizer = DocumentVectorizer()
    success = vectorizer.process_document(document_id)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    # S'assurer que le script est exécuté dans le contexte du projet Django
    # pour que les imports relatifs et les settings soient disponibles.
    # Normalement, django.setup() s'en occupe.
    main()
