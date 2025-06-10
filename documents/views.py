from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import DocumentUpload
from .serializers import DocumentUploadSerializer
from .tasks import process_document_async
from patients.models import Patient
import logging

logger = logging.getLogger(__name__)

class DocumentUploadViewSet(viewsets.ModelViewSet):
    queryset = DocumentUpload.objects.all()
    serializer_class = DocumentUploadSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        """Upload d'un document pour un patient"""
        patient_id = request.data.get('patient_id')
        
        if not patient_id:
            return Response(
                {"error": "patient_id requis"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            return Response(
                {"error": "Patient non trouvé"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Sauvegarder le document
            document = serializer.save(patient=patient)
            
            # Lancer le traitement asynchrone
            process_document_async.delay(document.id)
            
            return Response({
                "id": document.id,
                "message": "Document uploadé, traitement en cours",
                "status": document.upload_status
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def bulk_upload(self, request):
        """Upload multiple documents pour un patient"""
        patient_id = request.data.get('patient_id')
        files = request.FILES.getlist('files')
        
        if not patient_id or not files:
            return Response(
                {"error": "patient_id et files requis"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            return Response(
                {"error": "Patient non trouvé"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        created_documents = []
        
        for file in files:
            document_data = {
                'file': file,
                'original_filename': file.name,
                'file_size': file.size,
                'file_type': file.name.split('.')[-1].lower()
            }
            
            document = DocumentUpload.objects.create(
                patient=patient,
                **document_data
            )
            
            # Lancer le traitement asynchrone
            process_document_async.delay(document.id)
            created_documents.append(document.id)
        
        return Response({
            "uploaded_documents": created_documents,
            "message": f"{len(created_documents)} documents uploadés, traitement en cours"
        }, status=status.HTTP_201_CREATED)
