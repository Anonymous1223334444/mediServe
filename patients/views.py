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


class PatientCreateAPIView(views.APIView):
    """
    POST /api/patients/
    Création du patient avec envoi SMS et traitement des documents
    """
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        try:
            logger.info(f"Création patient - Données reçues: {request.data}")
            logger.info(f"Fichiers reçus: {request.FILES.getlist('documents')}")
            
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
            
            # 3. Envoi du SMS d'activation
            sms_sent = False
            sms_error = None
            try:
                from messaging.services import SMSService
                sms_service = SMSService()
                sms_sent, sms_result = sms_service.send_activation_sms(patient)
                
                if sms_sent:
                    logger.info(f"✅ SMS d'activation envoyé à {patient.phone}")
                else:
                    logger.error(f"❌ Échec envoi SMS: {sms_result}")
                    sms_error = sms_result
                    
            except Exception as e:
                logger.error(f"❌ Erreur service SMS: {e}")
                sms_error = str(e)
            
            # 4. Traitement des documents uploadés
            documents_with_tasks = []
            if 'documents' in request.FILES:
                files = request.FILES.getlist('documents')
                logger.info(f"📄 {len(files)} documents à traiter")
                
                for file in files:
                    try:
                        # Créer l'entrée document
                        doc = DocumentUpload.objects.create(
                            patient=patient,
                            file=file,
                            original_filename=file.name,
                            file_size=file.size,
                            file_type=file.name.split('.')[-1].lower()
                        )
                        logger.info(f"✅ Document créé: ID={doc.id}, Nom={file.name}")
                        
                        # Import et exécution de la tâche Celery
                        try:
                            from documents.tasks import process_document_async
                            
                            # Vérifier si Celery est disponible
                            from kombu import Connection
                            try:
                                with Connection('redis://localhost:6379//') as conn:
                                    conn.ensure_connection(max_retries=1, timeout=2)
                                
                                # Celery est disponible, envoyer la tâche
                                task = process_document_async.delay(doc.id)
                                
                                # Sauvegarder le task_id
                                if hasattr(doc, 'celery_task_id'):
                                    doc.celery_task_id = task.id
                                    doc.save(update_fields=['celery_task_id'])
                                
                                logger.info(f"✅ Tâche Celery envoyée: task_id={task.id}")
                                
                                documents_with_tasks.append({
                                    'document_id': doc.id,
                                    'task_id': task.id,
                                    'filename': doc.original_filename
                                })
                                
                            except Exception as celery_error:
                                # Celery non disponible, exécution synchrone
                                logger.warning(f"⚠️ Celery non disponible: {celery_error}")
                                logger.info("🔄 Exécution synchrone du traitement")
                                
                                # Exécuter directement
                                result = process_document_async(doc.id)
                                logger.info(f"Résultat synchrone: {result}")
                                
                                documents_with_tasks.append({
                                    'document_id': doc.id,
                                    'task_id': None,
                                    'filename': doc.original_filename,
                                    'sync_result': result
                                })
                                
                        except ImportError as ie:
                            logger.error(f"❌ Import error: {ie}")
                            doc.upload_status = 'failed'
                            doc.error_message = f"Erreur d'import: {ie}"
                            doc.save()
                            
                    except Exception as e:
                        logger.error(f"❌ Erreur document {file.name}: {str(e)}", exc_info=True)
            
            # 5. Préparer la réponse
            response_data = {
                "patient_id": patient.id,
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "phone": patient.phone,
                "activation_token": str(patient.activation_token),
                "message": "Patient créé avec succès",
                "documents": documents_with_tasks,
                "indexing_status_url": f"/api/patients/{patient.id}/indexing-status/",
                "sms_sent": sms_sent
            }
            
            if not sms_sent:
                response_data["sms_error"] = sms_error
                response_data["activation_url"] = f"{settings.SITE_PUBLIC_URL}/api/patients/activate/{patient.activation_token}/"
            
            logger.info(f"✅ Réponse finale: {response_data}")
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.exception(f"❌ Erreur non gérée: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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
    Obtient le statut d'indexation des documents d'un patient
    """
    permission_classes = [AllowAny]
    
    def get(self, request, patient_id):
        try:
            # Vérifier que le patient existe
            try:
                patient = Patient.objects.get(id=patient_id)
            except Patient.DoesNotExist:
                return Response(
                    {'error': 'Patient non trouvé'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Récupérer tous les documents du patient
            documents = DocumentUpload.objects.filter(
                patient_id=patient_id
            ).order_by('-uploaded_at')
            
            # Calculer les statistiques
            total = documents.count()
            indexed = documents.filter(upload_status='indexed').count()
            processing = documents.filter(upload_status='processing').count()
            failed = documents.filter(upload_status='failed').count()
            pending = documents.filter(upload_status='pending').count()
            
            # Détails par document
            document_details = []
            for doc in documents:
                detail = {
                    'id': doc.id,
                    'filename': doc.original_filename,
                    'status': doc.upload_status,
                    'error': doc.error_message if doc.upload_status == 'failed' else None,
                    'uploaded_at': doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                    'processed_at': doc.processed_at.isoformat() if doc.processed_at else None
                }
                
                # Si un task_id est stocké, vérifier le statut Celery
                if hasattr(doc, 'celery_task_id') and doc.celery_task_id:
                    try:
                        result = AsyncResult(doc.celery_task_id)
                        detail['task_status'] = result.status
                        
                        # Obtenir les infos de progression si disponibles
                        if hasattr(result, 'info') and isinstance(result.info, dict):
                            detail['task_progress'] = result.info.get('current', 0)
                            detail['task_total'] = result.info.get('total', 100)
                            detail['task_message'] = result.info.get('status', '')
                        else:
                            detail['task_progress'] = 0
                    except Exception as e:
                        logger.warning(f"Erreur récupération statut Celery: {e}")
                        detail['task_status'] = 'UNKNOWN'
                        detail['task_progress'] = 0
                
                document_details.append(detail)
            
            # Calculer la progression globale
            if total > 0:
                progress = (indexed / total) * 100
            else:
                progress = 0
            
            return Response({
                'patient_id': patient_id,
                'patient_name': patient.full_name(),
                'total_documents': total,
                'indexed': indexed,
                'processing': processing,
                'failed': failed,
                'pending': pending,
                'progress': round(progress, 2),
                'is_complete': pending == 0 and processing == 0,
                'documents': document_details
            })
            
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

class ActivateRedirectView(View):
    """
    GET /api/patients/activate/uuid:token/
    Redirige vers WhatsApp avec message pré-rempli pour l'activation.
    """
    def get(self, request, token=None):
        try:
        # 1. Vérifier le token
            patient = Patient.objects.get(activation_token=token)
            if patient.is_active:
                return HttpResponseBadRequest("Votre compte est déjà activé.")
            
            # 2. Construire l'URL WhatsApp
            # Format: https://api.whatsapp.com/send?phone=NUMERO&text=MESSAGE
            whatsapp_number = settings.TWILIO_WHATSAPP_NUMBER.lstrip('+')
            message = "Je confirme l'accès à mon espace santé CARE."
            
            params = {
                "phone": whatsapp_number,
                "text": message
            }
            
            # Encoder les paramètres pour l'URL
            encoded_params = urllib.parse.urlencode(params)
            whatsapp_url = f"https://api.whatsapp.com/send?{encoded_params}"
            
            # 3. Rediriger vers WhatsApp
            return HttpResponseRedirect(whatsapp_url)
            
        except Patient.DoesNotExist:
            return HttpResponseBadRequest("Lien d'activation invalide ou expiré.")
        except Exception as e:
            return HttpResponseBadRequest(f"Erreur lors de l'activation: {str(e)}")