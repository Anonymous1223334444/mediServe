import os
import io
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import pinecone
import google.generativeai as genai
from pinecone import Pinecone
import PyPDF2
from PIL import Image
import pytesseract
from django.conf import settings
from .models import Document, ConversationSession, Message

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Traite et extrait le texte des documents PDF et images"""
    
    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        """Extrait le texte d'un fichier PDF"""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text.strip()
        except Exception as e:
            logger.error(f"Erreur extraction PDF {file_path}: {e}")
            return ""
    
    @staticmethod
    def extract_text_from_image(file_path: str) -> str:
        """Extrait le texte d'une image via OCR"""
        try:
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image, lang='fra')
            return text.strip()
        except Exception as e:
            logger.error(f"Erreur OCR image {file_path}: {e}")
            return ""

class EmbeddingService:
    """Service pour générer des embeddings avec Gemini"""
    
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
    def generate_embedding(self, text: str) -> List[float]:
        """Génère un embedding pour un texte donné"""
        try:
            response = genai.embed_content(
                model="models/embedding-001",
                content=text,
                task_type="retrieval_document"
            )
            return response['embedding']
        except Exception as e:
            logger.error(f"Erreur génération embedding: {e}")
            return []

class PineconeService:
    """Service pour interagir avec Pinecone"""
    
    def __init__(self):
        self.pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        self.index_name = settings.PINECONE_INDEX_NAME
        self.index = self.pc.Index(self.index_name)
        
    def upsert_document(self, document_id: str, embedding: List[float], 
                       metadata: Dict[str, Any]) -> bool:
        """Insert ou update un document dans Pinecone"""
        try:
            self.index.upsert([{
                'id': document_id,
                'values': embedding,
                'metadata': metadata
            }])
            return True
        except Exception as e:
            logger.error(f"Erreur upsert Pinecone: {e}")
            return False
    
    def query_documents(self, query_embedding: List[float], 
                       patient_id: str, top_k: int = 5) -> List[Dict]:
        """Recherche de documents similaires pour un patient"""
        try:
            response = self.index.query(
                vector=query_embedding,
                filter={"patient_id": {"$eq": patient_id}},
                top_k=top_k,
                include_metadata=True
            )
            return response.matches
        except Exception as e:
            logger.error(f"Erreur query Pinecone: {e}")
            return []

class GeminiService:
    """Service pour interagir avec Gemini LLM"""
    
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-pro')
        
    def generate_response(self, query: str, context: str, 
                         patient_info: str) -> str:
        """Génère une réponse basée sur le contexte et la requête"""
        
        prompt = f"""
            Tu es un assistant médical AI spécialisé dans l'aide aux patients. 
            Réponds en français de manière claire et empathique.

            INFORMATIONS PATIENT:
            {patient_info}

            CONTEXTE MÉDICAL PERTINENT:
            {context}

            QUESTION DU PATIENT:
            {query}

            INSTRUCTIONS:
            - Base ta réponse uniquement sur les informations médicales fournies
            - Si tu n'as pas assez d'informations, demande de consulter le médecin
            - Sois rassurant mais prudent
            - N'invente jamais d'informations médicales
            - Limite ta réponse à 300 mots maximum

            RÉPONSE:
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Erreur Gemini: {e}")
            return "Désolé, je ne peux pas répondre pour le moment. Veuillez contacter votre médecin."

class RAGService:
    """Service principal pour le RAG (Retrieval-Augmented Generation)"""
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.pinecone_service = PineconeService()
        self.gemini_service = GeminiService()
        self.doc_processor = DocumentProcessor()
    
    def index_document(self, document: Document) -> bool:
        """Indexe un document dans Pinecone"""
        try:
            # 1. Extraire le texte
            if document.file_type == 'pdf':
                text = self.doc_processor.extract_text_from_pdf(document.file_path)
            else:
                text = self.doc_processor.extract_text_from_image(document.file_path)
            
            if not text:
                return False
            
            # 2. Sauvegarder le texte en base
            document.content_text = text
            
            # 3. Chunker le texte (par paragraphes)
            chunks = self._chunk_text(text)
            
            # 4. Pour chaque chunk, créer un embedding et indexer
            for i, chunk in enumerate(chunks):
                embedding = self.embedding_service.generate_embedding(chunk)
                if not embedding:
                    continue
                    
                metadata = {
                    'patient_id': str(document.patient.id),
                    'document_id': str(document.id),
                    'chunk_index': i,
                    'file_name': document.file_name,
                    'text': chunk,
                    'created_at': document.created_at.isoformat()
                }
                
                chunk_id = f"{document.id}_chunk_{i}"
                success = self.pinecone_service.upsert_document(
                    chunk_id, embedding, metadata
                )
                
                if not success:
                    return False
            
            # 5. Marquer comme indexé
            document.pinecone_indexed = True
            document.save()
            return True
            
        except Exception as e:
            logger.error(f"Erreur indexation document {document.id}: {e}")
            return False
    
    def _chunk_text(self, text: str, max_chars: int = 1000) -> List[str]:
        """Divise le texte en chunks plus petits"""
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            if len(current_chunk + paragraph) < max_chars:
                current_chunk += paragraph + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + "\n\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def query(self, patient_id: str, query: str, session_id: str) -> str:
        """Traite une requête patient et retourne une réponse"""
        start_time = datetime.now()
        
        try:
            # 1. Récupérer ou créer la session
            session, created = ConversationSession.objects.get_or_create(
                session_id=session_id,
                defaults={'patient_id': patient_id}
            )
            
            # 2. Générer embedding pour la query
            query_embedding = self.embedding_service.generate_embedding(query)
            if not query_embedding:
                return "Erreur technique. Veuillez réessayer."
            
            # 3. Rechercher documents pertinents
            relevant_docs = self.pinecone_service.query_documents(
                query_embedding, str(patient_id), top_k=5
            )
            
            # 4. Construire le contexte
            context = self._build_context(relevant_docs)
            
            # 5. Récupérer infos patient
            from patients.models import Patient
            patient = Patient.objects.get(id=patient_id)
            patient_info = self._build_patient_info(patient)
            
            # 6. Générer réponse avec Gemini
            response = self.gemini_service.generate_response(
                query, context, patient_info
            )
            
            # 7. Sauvegarder l'échange
            response_time = (datetime.now() - start_time).total_seconds()
            Message.objects.create(
                session=session,
                user_message=query,
                ai_response=response,
                response_time=response_time
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Erreur RAG query: {e}")
            return "Désolé, une erreur s'est produite. Contactez votre médecin."
    
    def _build_context(self, relevant_docs: List[Dict]) -> str:
        """Construit le contexte à partir des documents pertinents"""
        context_parts = []
        for doc in relevant_docs:
            metadata = doc.metadata
            text = metadata.get('text', '')
            file_name = metadata.get('file_name', '')
            context_parts.append(f"Document: {file_name}\n{text}\n")
        
        return '\n---\n'.join(context_parts)
    
    def _build_patient_info(self, patient) -> str:
        """Construit les informations patient pour le contexte"""
        return f"""
            Nom: {patient.full_name()}
            Âge: {patient.age()} ans
            Genre: {patient.gender}
            Téléphone: {patient.phone}
            Allergies: {patient.allergies or 'Aucune connue'}
            Médicaments actuels: {patient.current_medications or 'Aucun'}
            Historique médical: {patient.medical_history or 'Non renseigné'}
        """