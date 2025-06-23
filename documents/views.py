from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import DocumentUpload
from .serializers import DocumentUploadSerializer
from patients.models import Patient
import logging
import os
from django.conf import settings
from kombu import Connection

logger = logging.getLogger(__name__)

class DocumentUploadViewSet(viewsets.ModelViewSet):
    queryset = DocumentUpload.objects.all()
    serializer_class = DocumentUploadSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        """Upload d'un document pour un patient"""
        logger.info("=== DÉBUT UPLOAD DOCUMENT ===")
        patient_id = request.data.get('patient_id')
        
        if not patient_id:
            logger.error("patient_id manquant dans la requête")
            return Response(
                {"error": "patient_id requis"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            patient = Patient.objects.get(id=patient_id)
            logger.info(f"Patient trouvé: {patient.full_name()} (ID: {patient_id})")
        except Patient.DoesNotExist:
            logger.error(f"Patient non trouvé avec ID: {patient_id}")
            return Response(
                {"error": "Patient non trouvé"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Sauvegarder le document
            document = serializer.save(patient=patient)
            logger.info(f"Document sauvegardé: ID={document.id}, Fichier={document.original_filename}")
            logger.info(f"Chemin du fichier: {document.file.path}")
            
            # Vérifier que le fichier existe physiquement
            if os.path.exists(document.file.path):
                logger.info(f"✅ Fichier physique confirmé: {document.file.path}")
            else:
                logger.error(f"❌ FICHIER PHYSIQUE INTROUVABLE: {document.file.path}")
            
            # Tester la connexion Celery/Redis
            try:
                logger.info("Test de la connexion Celery/Redis...")
                broker_url = settings.CELERY_BROKER_URL
                logger.info(f"Broker URL: {broker_url}")
                
                with Connection(broker_url) as conn:
                    conn.ensure_connection(max_retries=3, timeout=5)
                    logger.info("✅ Connexion Celery/Redis OK")
                    
                # Importer et lancer la tâche
                logger.info("Import de la tâche Celery...")
                from .tasks import process_document_async
                
                logger.info(f"Envoi de la tâche pour document ID: {document.id}")
                result = process_document_async.delay(document.id)
                logger.info(f"✅ Tâche envoyée avec ID: {result.id}")
                
                # Sauvegarder le task_id
                document.celery_task_id = result.id
                document.save(update_fields=['celery_task_id'])
                logger.info(f"Task ID sauvegardé dans le document")
                
            except Exception as e:
                logger.error(f"❌ ERREUR Celery: {type(e).__name__}: {str(e)}")
                logger.error(f"Détails: {e}", exc_info=True)
                
                # Essayer d'exécuter le script directement
                logger.info("⚠️ Tentative d'exécution directe du script de vectorisation...")
                try:
                    import subprocess
                    script_path = os.path.join(settings.BASE_DIR, 'scripts', 'vectorize_document.sh')
                    
                    if os.path.exists(script_path):
                        logger.info(f"Script trouvé: {script_path}")
                        os.chmod(script_path, 0o755)  # S'assurer qu'il est exécutable
                        
                        process = subprocess.Popen(
                            [script_path, str(document.id)],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        stdout, stderr = process.communicate()
                        
                        logger.info(f"Script stdout: {stdout}")
                        if stderr:
                            logger.error(f"Script stderr: {stderr}")
                        logger.info(f"Script return code: {process.returncode}")
                    else:
                        logger.error(f"❌ Script non trouvé: {script_path}")
                        
                except Exception as script_error:
                    logger.error(f"❌ Erreur exécution script: {script_error}")
            
            return Response({
                "id": document.id,
                "message": "Document uploadé, traitement en cours",
                "status": document.upload_status,
                "file_path": document.file.path,
                "patient_id": patient.id
            }, status=status.HTTP_201_CREATED)
        
        logger.error(f"Erreurs de validation: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def bulk_upload(self, request):
        """Upload multiple documents pour un patient"""
        return Response({"error": "Cette méthode est obsolète"}, status=410)
        # logger.info("=== DÉBUT BULK UPLOAD ===")
        # patient_id = request.data.get('patient_id')
        # files = request.FILES.getlist('files')
        
        # logger.info(f"Patient ID: {patient_id}")
        # logger.info(f"Nombre de fichiers: {len(files)}")
        
        # if not patient_id or not files:
        #     return Response(
        #         {"error": "patient_id et files requis"},
        #         status=status.HTTP_400_BAD_REQUEST
        #     )
        
        # try:
        #     patient = Patient.objects.get(id=patient_id)
        #     logger.info(f"Patient trouvé: {patient.full_name()}")
        # except Patient.DoesNotExist:
        #     return Response(
        #         {"error": "Patient non trouvé"},
        #         status=status.HTTP_404_NOT_FOUND
        #     )
        
        # created_documents = []
        
        # for file in files:
        #     logger.info(f"Traitement du fichier: {file.name}")
        #     document_data = {
        #         'file': file,
        #         'original_filename': file.name,
        #         'file_size': file.size,
        #         'file_type': file.name.split('.')[-1].lower()
        #     }
            
        #     document = DocumentUpload.objects.create(
        #         patient=patient,
        #         **document_data
        #     )
        #     logger.info(f"Document créé: ID={document.id}")
            
        #     # Lancer le traitement asynchrone
        #     try:
        #         from .tasks import process_document_async
        #         result = process_document_async.delay(document.id)
        #         document.celery_task_id = result.id
        #         document.save(update_fields=['celery_task_id'])
        #         logger.info(f"✅ Tâche Celery envoyée: {result.id}")
        #     except Exception as e:
        #         logger.error(f"❌ Erreur envoi tâche pour document {document.id}: {e}")
        #         document.upload_status = 'failed'
        #         document.error_message = str(e)
        #         document.save()
            
        #     created_documents.append(document.id)
        
        # logger.info(f"=== FIN BULK UPLOAD: {len(created_documents)} documents créés ===")
        
        # return Response({
        #     "uploaded_documents": created_documents,
        #     "message": f"{len(created_documents)} documents uploadés, traitement en cours"
        # }, status=status.HTTP_201_CREATED)