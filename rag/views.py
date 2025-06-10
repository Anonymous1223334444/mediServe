from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .services import RAGService
from .models import Document
from patients.models import Patient
import logging

logger = logging.getLogger(__name__)

class RAGQueryView(views.APIView):
    """API endpoint pour les requêtes RAG depuis WhatsApp/N8N"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """
        POST /api/rag/query/
        Expected payload:
        {
            "patient_phone": "+221771234567",
            "query": "Quelle est ma dernière ordonnance ?",
            "session_id": "whatsapp_+221771234567_20241201"
        }
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
            # Trouver le patient
            patient = Patient.objects.get(phone=patient_phone, is_active=True)
            
            # Traiter la requête avec RAG
            rag_service = RAGService()
            response_text = rag_service.query(patient.id, query, session_id)
            
            return Response({
                "response": response_text,
                "patient_id": patient.id,
                "session_id": session_id
            })
            
        except Patient.DoesNotExist:
            return Response(
                {"error": "Patient non trouvé ou inactif"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Erreur RAG query: {e}")
            return Response(
                {"error": "Erreur interne du serveur"},
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
