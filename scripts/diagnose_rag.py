#!/usr/bin/env python3
"""
Script de diagnostic du système RAG
Usage: python diagnose_rag.py
"""
import os
import sys
import django


script_dir = os.path.dirname(os.path.abspath(__file__))
# Aller deux niveaux plus haut pour atteindre le répertoire racine du projet Django
# (Exemple: si script est dans /project_root/scripts/, cela renvoie /project_root/)
project_root = os.path.join(script_dir, '..', '') # Ajout d'un '/' final pour s'assurer que c'est un chemin de répertoire
sys.path.insert(0, os.path.abspath(project_root))

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mediServe.settings')
django.setup()

from django.conf import settings
from patients.models import Patient
from documents.models import DocumentUpload
from messaging.utils import normalize_phone_number
import h5py

def check_patient_rag_setup(patient_id=None, phone=None):
    """Vérifie la configuration RAG pour un patient"""
    print("=== DIAGNOSTIC SYSTÈME RAG ===\n")
    
    # Trouver le patient
    patient = None
    if patient_id:
        try:
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            print(f"❌ Patient avec ID {patient_id} non trouvé")
            return
    elif phone:
        # Normaliser le numéro
        normalized = normalize_phone_number(phone)
        print(f"📱 Recherche avec numéro: {phone} → {normalized}")
        
        # Recherche flexible
        for p in Patient.objects.all():
            if normalized in normalize_phone_number(p.phone) or normalize_phone_number(p.phone) in normalized:
                patient = p
                break
        
        if not patient:
            print(f"❌ Aucun patient trouvé pour le numéro {phone}")
            return
    else:
        # Prendre le dernier patient actif
        patient = Patient.objects.filter(is_active=True).order_by('-activated_at').first()
        if not patient:
            print("❌ Aucun patient actif trouvé")
            return
    
    print(f"\n👤 PATIENT: {patient.full_name()}")
    print(f"  - ID: {patient.id}")
    print(f"  - Téléphone: {patient.phone}")
    print(f"  - Actif: {'✅ Oui' if patient.is_active else '❌ Non'}")
    print(f"  - Token: {patient.activation_token}")
    if patient.activated_at:
        print(f"  - Activé le: {patient.activated_at}")
    
    # Vérifier les documents
    print(f"\n📄 DOCUMENTS:")
    documents = DocumentUpload.objects.filter(patient=patient)
    print(f"  - Total: {documents.count()}")
    
    for status in ['pending', 'processing', 'indexed', 'failed']:
        count = documents.filter(upload_status=status).count()
        if count > 0:
            print(f"  - {status}: {count}")
    
    print(f"\n📚 Documents détaillés:")
    for doc in documents:
        print(f"  - {doc.original_filename}")
        print(f"    • Status: {doc.upload_status}")
        print(f"    • Uploadé: {doc.uploaded_at}")
        if doc.processed_at:
            print(f"    • Traité: {doc.processed_at}")
        if doc.error_message:
            print(f"    • ❌ Erreur: {doc.error_message}")
        
        # Vérifier le fichier physique
        if doc.file:
            exists = os.path.exists(doc.file.path)
            print(f"    • Fichier: {'✅ Existe' if exists else '❌ Manquant'}")
            if exists:
                print(f"    • Chemin: {doc.file.path}")
    
    # Vérifier les vector stores
    print(f"\n🔍 VECTOR STORES:")
    vector_dir = os.path.join(settings.MEDIA_ROOT, 'vectors', f'patient_{patient.id}')
    hdf5_path = os.path.join(vector_dir, 'vector_store.h5')
    faiss_path = os.path.join(vector_dir, 'vector_store.faiss')
    bm25_dir = os.path.join(settings.MEDIA_ROOT, 'indexes', f'patient_{patient.id}_bm25')
    
    print(f"  - Dossier vectors: {'✅ Existe' if os.path.exists(vector_dir) else '❌ Manquant'}")
    print(f"  - HDF5: {'✅ Existe' if os.path.exists(hdf5_path) else '❌ Manquant'}")
    print(f"  - FAISS: {'✅ Existe' if os.path.exists(faiss_path) else '❌ Manquant'}")
    print(f"  - BM25: {'✅ Existe' if os.path.exists(bm25_dir) else '❌ Manquant'}")
    
    # Analyser le contenu HDF5
    if os.path.exists(hdf5_path):
        try:
            with h5py.File(hdf5_path, 'r') as hf:
                if 'vectors' in hf:
                    vectors_shape = hf['vectors'].shape
                    print(f"\n  📊 Contenu HDF5:")
                    print(f"    • Vecteurs: {vectors_shape[0]}")
                    print(f"    • Dimensions: {vectors_shape[1]}")
                
                if 'metadata' in hf:
                    meta_count = len(hf['metadata'])
                    print(f"    • Métadonnées: {meta_count}")
                    
                    # Afficher quelques métadonnées
                    if meta_count > 0:
                        print(f"\n    📝 Exemples de métadonnées:")
                        import json
                        for i in range(min(3, meta_count)):
                            meta = json.loads(hf['metadata'][i].decode('utf-8'))
                            print(f"      [{i}] Document: {meta.get('file_name', 'N/A')}")
                            print(f"          Type: {meta.get('type', 'N/A')}")
                            print(f"          Page: {meta.get('page', 'N/A')}")
        except Exception as e:
            print(f"  ❌ Erreur lecture HDF5: {e}")
    
    # Vérifier la configuration
    print(f"\n⚙️ CONFIGURATION:")
    print(f"  - GEMINI_API_KEY: {'✅ Configurée' if settings.GEMINI_API_KEY else '❌ Manquante'}")
    print(f"  - Modèle embedding: {settings.RAG_SETTINGS.get('EMBEDDING_MODEL', 'Non configuré')}")
    print(f"  - Modèle LLM: {settings.RAG_SETTINGS.get('LLM_MODEL', 'Non configuré')}")
    print(f"  - BM25 activé: {'✅ Oui' if settings.RAG_SETTINGS.get('USE_BM25', False) else '❌ Non'}")
    print(f"  - Reranking activé: {'✅ Oui' if settings.RAG_SETTINGS.get('USE_RERANKING', False) else '❌ Non'}")
    
    # Test rapide du RAG
    print(f"\n🧪 TEST RAG:")
    if os.path.exists(hdf5_path) and patient.is_active:
        try:
            # Importer et tester
            sys.path.append(os.path.join(settings.BASE_DIR, 'scripts'))
            from rag.your_rag_module import VectorStoreHDF5, EmbeddingGenerator
            
            # Charger le store
            store = VectorStoreHDF5(hdf5_path)
            store.load_store()
            print(f"  ✅ Vector store chargé avec succès")
            print(f"  - Nombre de documents: {len(store.meta)}")
            
            # Tester l'embedder
            embedder = EmbeddingGenerator()
            test_vec = embedder.embed_text("test")
            print(f"  ✅ Embedder fonctionne")
            print(f"  - Dimension des vecteurs: {len(test_vec)}")
            
        except Exception as e:
            print(f"  ❌ Erreur test RAG: {e}")
    else:
        print(f"  ⚠️ Test ignoré (pas de vector store ou patient inactif)")

def main():
    print("Options de diagnostic:")
    print("1. Diagnostiquer par ID patient")
    print("2. Diagnostiquer par numéro de téléphone")
    print("3. Diagnostiquer le dernier patient actif")
    
    choice = input("\nVotre choix (1-3): ")
    
    if choice == "1":
        patient_id = input("ID du patient: ")
        check_patient_rag_setup(patient_id=int(patient_id))
    elif choice == "2":
        phone = input("Numéro de téléphone: ")
        check_patient_rag_setup(phone=phone)
    else:
        check_patient_rag_setup()

if __name__ == "__main__":
    main()