# patients/views.py

import urllib.parse
from django.shortcuts import redirect
from django.conf import settings
from rest_framework import status, views
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
import uuid
from django.urls import reverse
from django.views import View
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from .serializers import PatientCreateSerializer
from .models import Patient
from .n8n_client import trigger_n8n_activation # This might be unused, depending on final structure
from django.utils import timezone
import os
import json
from django.db import models
import uuid
import logging
from .n8n_manager import N8NWorkflowManager
from django.http import JsonResponse
import time
from documents.models import DocumentUpload
from documents.tasks import process_document_async
from messaging.services import WhatsAppService
from rest_framework.decorators import api_view
from rest_framework.response import Response
from celery.result import AsyncResult
logger = logging.getLogger(__name__)
from documents.serializers import DocumentUploadSerializer # Corrected typo here

class PatientCreateAPIView(views.APIView):
    """
    POST /api/patients/
    Création du patient avec envoi SMS et traitement des documents
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try: # Outer try block starts here
            logger.info(f"=== CRÉATION PATIENT ===")
            logger.info(f"Données reçues: {request.data}")
            logger.info(f"Fichiers reçus: {len(request.FILES.getlist('documents'))} documents")

            # 1. Validation des données patient
            serializer = PatientCreateSerializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"Erreurs de validation: {serializer.errors}")
                return Response(
                    {"error": "Validation failed", "details": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 2. Création du patient
            patient = serializer.save()
            logger.info(f"✅ Patient créé: ID={patient.id}, Nom={patient.full_name()}")

            # 3. Envoi du SMS d'activation (non bloquant)
            sms_sent = False
            sms_error = None
            try:
                from messaging.services import SMSService
                sms_service = SMSService()
                sms_sent, sms_result = sms_service.send_activation_sms(patient)

                if sms_sent:
                    logger.info(f"✅ SMS d'activation envoyé à {patient.phone}")
                else:
                    logger.warning(f"⚠️ SMS non envoyé: {sms_result}")
                    sms_error = sms_result
            except Exception as e:
                logger.warning(f"⚠️ Service SMS indisponible: {e}")
                sms_error = str(e)

            # 4. Traitement des documents
            documents_results = []
            celery_available = self._check_celery_availability()

            if 'documents' in request.FILES:
                files = request.FILES.getlist('documents')
                logger.info(f"📄 {len(files)} documents à traiter")

                for file in files:
                    try:
                        # Créer l'entrée document directement
                        doc = DocumentUpload.objects.create(
                            patient=patient,
                            file=file,
                            original_filename=file.name,
                            file_size=file.size,
                            file_type=file.name.split('.')[-1].lower()
                        )
                        logger.info(f"📄 Document créé: ID={doc.id}, Nom={file.name}")

                        # Lancer le traitement asynchrone
                        from documents.tasks import process_document_async
                        task = process_document_async.delay(doc.id)
                        doc.celery_task_id = task.id
                        doc.save(update_fields=['celery_task_id'])
                        logger.info(f"✅ Tâche Celery envoyée: {task.id}")

                        documents_results.append({
                            'document_id': doc.id,
                            'filename': doc.original_filename,
                            'status': 'pending',
                            'task_id': task.id
                        })

                    except Exception as e:
                        logger.error(f"❌ Erreur document {file.name}: {e}")
                        documents_results.append({
                            'filename': file.name,
                            'status': 'error',
                            'error': str(e)
                        })

            # 5. Préparer la réponse COMPATIBLE avec le frontend
            # This block is now outside the document processing loop
            response_data = {
                # Champs attendus par le frontend
                "patient_id": patient.id,
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "phone": patient.phone,
                "activation_token": str(patient.activation_token),

                # Documents dans le format attendu
                "documents": documents_results,  # Le frontend vérifie data.documents.length

                # Infos supplémentaires
                "sms_sent": sms_sent,
                "sms_error": sms_error,
                "activation_url": f"{settings.SITE_PUBLIC_URL}/api/patients/activate/{patient.activation_token}/",
                "indexing_status_url": f"/api/patients/{patient.id}/indexing-status/",

                # Message de succès
                "message": "Patient créé avec succès",
                "status": "success"
            }

            logger.info(f"✅ Patient créé avec succès")
            logger.info(f"📤 Réponse envoyée: patient_id={patient.id}, documents={len(documents_results)}")

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e: # This is the outer catch-all for the entire post method
            logger.exception(f"❌ Erreur non gérée: {e}")
            return Response(
                {"error": "Erreur serveur", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _check_celery_availability(self):
        """Vérifier si Celery est disponible"""
        try:
            from kombu import Connection
            with Connection(settings.CELERY_BROKER_URL) as conn:
                conn.ensure_connection(max_retries=1, timeout=2)
            logger.info("✅ Celery disponible")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Celery non disponible: {e}")
            return False

    def _process_document_sync(self, document_id):
        """Traiter un document de manière synchrone"""
        try:
            # Importer le script de vectorisation
            import subprocess
            script_path = os.path.join(settings.BASE_DIR, 'scripts', 'vectorize_single_document.py')

            if not os.path.exists(script_path):
                # Essayer l'import direct
                logger.info("Import direct du module de vectorisation")
                import sys
                sys.path.insert(0, os.path.join(settings.BASE_DIR, 'scripts'))
                from vectorize_single_document import DocumentVectorizer

                vectorizer = DocumentVectorizer()
                return vectorizer.process_document(document_id)
            else:
                # Exécuter via subprocess
                logger.info(f"Exécution du script: {script_path}")
                result = subprocess.run(
                    ['python', script_path, str(document_id)],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0

        except Exception as e:
            logger.error(f"Erreur traitement synchrone: {e}")
            # Marquer le document comme échoué
            try:
                doc = DocumentUpload.objects.get(id=document_id)
                doc.upload_status = 'failed'
                doc.error_message = str(e)
                doc.save()
            except:
                pass
            return False

class DocumentRetryView(views.APIView):
    """
    POST /api/documents/{document_id}/retry/
    Relance le traitement d'un document échoué
    """
    permission_classes = [AllowAny]

    def post(self, request, document_id):
        try:
            doc = DocumentUpload.objects.get(id=document_id)

            if doc.upload_status not in ['failed', 'pending']:
                return Response(
                    {'error': 'Le document ne peut pas être relancé'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Réinitialiser le statut
            doc.upload_status = 'pending'
            doc.error_message = ''
            doc.save()

            # Relancer la tâche
            from documents.tasks import process_document_async
            task = process_document_async.delay(doc.id)

            # Sauvegarder le nouveau task_id
            doc.celery_task_id = task.id
            doc.save(update_fields=['celery_task_id'])

            return Response({
                'message': 'Document relancé',
                'task_id': task.id,
                'document_id': doc.id
            })

        except DocumentUpload.DoesNotExist:
            return Response(
                {'error': 'Document non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )


class PatientCheckActiveAPIView(views.APIView):
    """
    POST /api/patients/check-active/
    Vérifie si un patient est actif basé sur son numéro de téléphone
    Utilisé par N8N pour valider les sessions WhatsApp
    """
    permission_classes = [AllowAny]

    def post(self, request):
        phone = request.data.get('phone')

        if not phone:
            return Response(
                {"error": "Numéro de téléphone requis"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            patient = Patient.objects.get(phone=phone)
            return Response({
                "is_active": patient.is_active,
                "patient_id": patient.id,
                "full_name": patient.full_name(),
                "activated_at": patient.activated_at
            })
        except Patient.DoesNotExist:
            return Response({
                "is_active": False,
                "patient_id": None,
                "error": "Patient non trouvé"
            })

class PatientListAPIView(views.APIView):
    """
    GET /api/patients/
    Liste des patients avec pagination et filtres
    """
    permission_classes = [AllowAny]

    def get(self, request):
        patients = Patient.objects.all().order_by('-created_at')

        # Filtres
        is_active = request.GET.get('is_active')
        if is_active is not None:
            patients = patients.filter(is_active=is_active.lower() == 'true')

        search = request.GET.get('search')
        if search:
            patients = patients.filter(
                models.Q(first_name__icontains=search) |
                models.Q(last_name__icontains=search) |
                models.Q(phone__icontains=search)
            )

        # Pagination simple
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        start = (page - 1) * page_size
        end = start + page_size

        total_count = patients.count()
        patients_page = patients[start:end]

        # Sérialiser les données
        data = []
        for patient in patients_page:
            data.append({
                'id': patient.id,
                'full_name': patient.full_name(),
                'phone': patient.phone,
                'email': patient.email,
                'is_active': patient.is_active,
                'created_at': patient.created_at,
                'activated_at': patient.activated_at,
                'documents_count': patient.documents.count() if hasattr(patient, 'documents') else 0
            })

        return Response({
            'results': data,
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'has_next': end < total_count,
            'has_previous': page > 1
        })

class PatientConfirmAPIView(views.APIView):
    """
    POST /api/patients/confirm/
    Appelée par N8N quand le patient répond correctement sur WhatsApp.
    """
    permission_classes = [AllowAny]
    def post(self, request, *args, **kwargs):
        phone = request.data.get("phone")
        valid = request.data.get("valid", False)

        if not phone or not isinstance(valid, bool):
            return Response(
                {"detail": "phone et valid (boolean) sont requis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Trouver le patient par son numéro de téléphone
            patient = Patient.objects.get(phone=phone)

            if valid:
                # Activer le patient
                patient.is_active = True
                patient.activated_at = timezone.now()
                patient.save()

                # Envoyer un message de bienvenue
                try:
                    whatsapp_service = WhatsAppService()
                    message = f"Bienvenue {patient.first_name} ! Votre espace santé est maintenant activé. "
                    message += f"Vous pouvez me poser des questions sur vos documents médicaux à tout moment."
                    whatsapp_service.send_message(patient.phone, message)
                except Exception as e:
                    # Ignorer les erreurs d'envoi de message de bienvenue
                    pass

                return Response({"detail": "Patient activé avec succès."}, status=status.HTTP_200_OK)
            else:
                return Response({"detail": "Confirmation invalide."}, status=status.HTTP_200_OK)

        except Patient.DoesNotExist:
            return Response({"detail": "Patient non trouvé."}, status=status.HTTP_404_NOT_FOUND)


class PatientIndexingStatusView(views.APIView):
    """
    GET /api/patients/{patient_id}/indexing-status/
    Obtient le statut d'indexation des documents d'un patient avec plus de détails
    """
    permission_classes = [AllowAny]

    def get(self, request, patient_id):
        try:
            patient = Patient.objects.get(id=patient_id)
            documents = DocumentUpload.objects.filter(patient=patient).select_related('patient')
            
            # Calculer les stats
            total = documents.count()
            indexed = documents.filter(upload_status='indexed').count()
            processing = documents.filter(upload_status='processing').count()
            failed = documents.filter(upload_status='failed').count()
            pending = documents.filter(upload_status='pending').count()
            
            progress = int((indexed / total) * 100) if total > 0 else 0
            is_complete = (indexed + failed) == total and total > 0
            
            # Détails des documents avec progression Celery
            documents_data = []
            for doc in documents:
                doc_data = {
                    'id': doc.id,
                    'filename': doc.original_filename,
                    'status': doc.upload_status,
                    'error': doc.error_message if doc.error_message else None,
                    'uploaded_at': doc.uploaded_at.isoformat(),
                    'processed_at': doc.processed_at.isoformat() if doc.processed_at else None,
                }
                
                # Ajouter la progression Celery si disponible
                if hasattr(doc, 'celery_task_id') and doc.celery_task_id:
                    try:
                        from celery.result import AsyncResult
                        result = AsyncResult(doc.celery_task_id)
                        
                        if result.state == 'PROGRESS' and isinstance(result.info, dict):
                            doc_data['progress'] = result.info.get('current', 0)
                            doc_data['task_status'] = result.info.get('status', '')
                        elif result.state in ['SUCCESS', 'FAILURE']:
                            doc_data['task_status'] = result.state
                            
                    except Exception as e:
                        logger.warning(f"Erreur récupération statut Celery pour doc {doc.id}: {e}")
                
                documents_data.append(doc_data)

            return Response({
                'patient_id': patient_id,
                'patient_name': patient.full_name(),
                'total_documents': total,
                'indexed': indexed,
                'processing': processing,
                'failed': failed,
                'pending': pending,
                'progress': progress,
                'is_complete': is_complete,
                'documents': documents_data,
                'last_updated': timezone.now().isoformat()
            })
            
        except Patient.DoesNotExist:
            return Response(
                {'error': 'Patient non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Erreur dans PatientIndexingStatusView: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Erreur serveur: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DocumentIndexingStatusView(views.APIView):
    """
    GET /api/documents/{document_id}/status/
    Obtient le statut détaillé d'un document spécifique
    """
    permission_classes = [AllowAny]

    def get(self, request, document_id):
        try:
            doc = DocumentUpload.objects.get(id=document_id)

            response_data = {
                'id': doc.id,
                'filename': doc.original_filename,
                'status': doc.upload_status,
                'file_size': doc.file_size,
                'uploaded_at': doc.uploaded_at,
                'processed_at': doc.processed_at,
                'error_message': doc.error_message
            }

            # Vérifier le statut Celery si disponible
            if hasattr(doc, 'celery_task_id') and doc.celery_task_id:
                result = AsyncResult(doc.celery_task_id)
                response_data['task_status'] = result.status
                response_data['task_info'] = result.info

            return Response(response_data)

        except DocumentUpload.DoesNotExist:
            return Response(
                {'error': 'Document non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )

from django.shortcuts import render
from django.template.response import TemplateResponse

class ActivateRedirectView(View):
    """
    GET /api/patients/activate/<uuid:token>/
    Affiche un guide d'activation en deux étapes
    """
    def get(self, request, token=None):
        try:
            # 1. Vérifier le token
            patient = Patient.objects.get(activation_token=token)
            
            # 2. Marquer que le lien a été cliqué
            if hasattr(patient, 'activation_link_clicked'):
                patient.activation_link_clicked = True
                patient.save(update_fields=['activation_link_clicked'])
            
            # 3. Préparer les données pour le template
            whatsapp_number = settings.TWILIO_WHATSAPP_NUMBER.replace('whatsapp:', '').lstrip('+')
            
            # URLs WhatsApp
            sandbox_message = "join fur-asleep"
            activation_message = f"ACTIVER {token}"
            
            sandbox_url = f"https://api.whatsapp.com/send?phone={whatsapp_number}&text={urllib.parse.quote(sandbox_message)}"
            activation_url = f"https://api.whatsapp.com/send?phone={whatsapp_number}&text={urllib.parse.quote(activation_message)}"
            
            context = {
                'patient_name': patient.first_name,
                'token': str(token),
                'sandbox_url': sandbox_url,
                'activation_url': activation_url,
                'health_structure_name': settings.HEALTH_STRUCTURE_NAME,
                'whatsapp_number': whatsapp_number
            }
            
            logger.info(f"Affichage du guide d'activation pour patient {patient.id}")
            
            # 4. Retourner le template HTML
            return render(request, 'activation_guide.html', context)
            
        except Patient.DoesNotExist:
            # Template d'erreur simple
            return render(request, 'activation_error.html', {
                'error': "Lien d'activation invalide ou expiré."
            }, status=404)
        except Exception as e:
            logger.error(f"Erreur activation: {e}")
            return render(request, 'activation_error.html', {
                'error': f"Erreur lors de l'activation: {str(e)}"
            }, status=500)