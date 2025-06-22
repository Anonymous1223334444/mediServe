from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .services import RAGService
from .models import Document
from patients.models import Patient
import logging
import time
import os
from django.conf import settings
import sys
sys.path.append(os.path.join(settings.BASE_DIR, 'scripts'))
from rag.your_rag_module import VectorStoreHDF5, EmbeddingGenerator, HybridRetriever, GeminiLLM, RAG

logger = logging.getLogger(__name__)

class RAGQueryView(views.APIView):
    """API endpoint pour les requêtes RAG depuis WhatsApp via N8N"""
    permission_classes = [AllowAny]
    def post(self, request):
        """
        POST /api/rag/query/
        Requête RAG basée sur le téléphone du patient
        """
        patient_phone = request.data.get('patient_phone')
        query = request.data.get('query')
        session_id = request.data.get('session_id')
        
        if not all([patient_phone, query, session_id]):
            return Response(
                {"error": "patient_phone, query et session_id requis"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Mesurer le temps de réponse
            start_time = time.time()
            
            # Trouver le patient
            patient = Patient.objects.get(phone=patient_phone, is_active=True)
            
            # Chemins des fichiers vector store pour ce patient
            hdf5_path = os.path.join(settings.MEDIA_ROOT, 'vectors', f'patient_{patient.id}.h5')
            
            # Vérifier l'existence des fichiers
            if not os.path.exists(hdf5_path):
                return Response(
                    {"error": "Aucun document indexé trouvé pour ce patient"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # 1. Charger le vector store
            vector_store = VectorStoreHDF5(hdf5_path)
            vector_store.load_store()
            
            # 2. Initialiser le générateur d'embeddings
            embedder = EmbeddingGenerator()
            
            # 3. Construire le retriever (hybride si BM25 disponible)
            bm25_index_dir = os.path.join(settings.MEDIA_ROOT, 'indexes', f'patient_{patient.id}_bm25')
            if os.path.exists(bm25_index_dir):
                retriever = HybridRetriever(vector_store, embedder, bm25_index_dir)
                # Activer le reranking si configuré
                if getattr(settings, 'USE_RERANKING', True):
                    retriever.enable_reranking('cross-encoder/ms-marco-MiniLM-L-6-v2')
            else:
                # Retriever dense seulement
                retriever = HybridRetriever(vector_store, embedder)
            
            # 4. Initialiser le LLM
            llm = GeminiLLM()
            
            # 5. Créer le pipeline RAG
            rag = RAG(retriever, llm)
            
            # 6. Générer la réponse
            response_text = rag.answer(query, top_k=5)
            
            # Calculer le temps de réponse
            response_time = (time.time() - start_time) * 1000  # en ms
            
            # Sauvegarder les métriques (optionnel)
            try:
                from metrics.services import MetricsService
                MetricsService.record_response_time(response_time, 'rag_query')
            except Exception as e:
                logger.warning(f"Erreur lors de l'enregistrement des métriques: {e}")
            
            # Sauvegarder la conversation (optionnel)
            try:
                from sessions.models import WhatsAppSession, ConversationLog
                
                # Récupérer ou créer la session
                session, created = WhatsAppSession.objects.get_or_create(
                    session_id=session_id,
                    defaults={
                        'patient': patient,
                        'phone_number': patient_phone,
                        'status': 'active'
                    }
                )
                
                # Enregistrer la conversation
                ConversationLog.objects.create(
                    session=session,
                    user_message=query,
                    ai_response=response_text,
                    response_time_ms=response_time,
                    message_length=len(query),
                    response_length=len(response_text)
                )
            except Exception as e:
                logger.warning(f"Erreur lors de l'enregistrement de la conversation: {e}")
            
            return Response({
                "response": response_text,
                "patient_id": patient.id,
                "session_id": session_id,
                "response_time_ms": response_time
            })
            
        except Patient.DoesNotExist:
            return Response(
                {"error": "Patient non trouvé ou inactif"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Erreur RAG query: {e}")
            return Response(
                {"error": f"Erreur lors du traitement de la requête: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DocumentIndexView(views.APIView):
    """API pour forcer l'indexation d'un document"""
    permission_classes = [AllowAny]
    
    def post(self, request, document_id):
        """
        POST /api/rag/index-document/<document_id>/
        """
        try:
            document = Document.objects.get(id=document_id)
            rag_service = RAGService()
            success = rag_service.index_document(document)
            
            return Response({
                "success": success,
                "document_id": document_id,
                "indexed": document.pinecone_indexed
            })
            
        except Document.DoesNotExist:
            return Response(
                {"error": "Document non trouvé"},
                status=status.HTTP_404_NOT_FOUND
            )
