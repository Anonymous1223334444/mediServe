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
from .n8n_manager import N8NWorkflowManager
from django.http import JsonResponse
import time


class PatientCreateAPIView(views.APIView):
    """
    POST /api/patients/
    1. Création du patient (avec activation_token).
    2. Lecture + interpolation du template patient_activation_template.json.
    3. create_workflow(...) → récupération du workflow_id.
    4. activate_workflow(...)
    5. trigger_webhook_activate(...) → envoi du JSON pour déclencher l’exécution.
    6. Sauvegarde workflow_id en base + renvoi de la réponse.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # 1) Création du Patient
        serializer = PatientCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        patient: Patient = serializer.save()
        token = str(patient.activation_token)

        # 2) Construction des variables
        activation_link = f"{settings.SITE_PUBLIC_URL}/activate/?token={token}"
        full_name = patient.full_name()
        phone_e164 = patient.phone  # e.g. "+221771234567"

        # 3) Lecture du template JSON
        template_path = os.path.join(settings.BASE_DIR,
                                    "patients", "workflows",
                                    "patient_activation_template.json")
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                raw_template = f.read()
        except FileNotFoundError:
            patient.delete()
            return Response(
                {"detail": "Workflow template not found."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 4) Interpolation des placeholders
        replaced = raw_template
        replaced = replaced.replace("{{ACTIVATION_TOKEN}}", token)
        replaced = replaced.replace("{{PHONE}}", phone_e164)
        replaced = replaced.replace("{{FULL_NAME}}", full_name)
        replaced = replaced.replace("{{ACTIVATION_LINK}}", activation_link)
        replaced = replaced.replace("{{TWILIO_ACCOUNT_SID}}", settings.TWILIO_ACCOUNT_SID)
        replaced = replaced.replace("{{TWILIO_WHATSAPP_NUMBER}}",
                                settings.TWILIO_WHATSAPP_NUMBER.lstrip("+"))
        replaced = replaced.replace("{{DJANGO_BASE_URL}}", settings.SITE_PUBLIC_URL)
        replaced = replaced.replace("{{WORKFLOW_ID}}", "ID sera défini après création")

        # Convertir en dict Python
        try:
            workflow_data = json.loads(replaced)
        except json.JSONDecodeError as e:
            patient.delete()
            return Response(
                {"detail": f"Invalid JSON after placeholder replacement: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 5) Création du workflow dans n8n
        manager = N8NWorkflowManager()
        manager.ensure_telegram_credentials_exist()
        workflow_name = f"Activate_{patient.first_name}_{token[:8]}"
        result = manager.create_workflow(workflow_data, workflow_name)

        # Handle workflow creation errors
        if "error" in result:
            patient.delete()
            return Response(
                {"detail": f"Failed to create workflow in n8n: {result['error']}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        workflow_id = result.get("id")
        if not workflow_id:
            patient.delete()
            return Response(
                {"detail": "Failed to get workflow ID from n8n."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 6) Sauvegarde du workflow_id dans le patient IMMÉDIATEMENT après création
        patient.n8n_workflow_id = str(workflow_id)
        patient.save()

        # 7) Traitement des documents téléchargés (si présents)
        uploaded_files = request.FILES.getlist('documents')
        if uploaded_files:
            from documents.models import DocumentUpload
            from documents.tasks import process_document_async
            
            for file in uploaded_files:
                document = DocumentUpload.objects.create(
                    patient=patient,
                    file=file,
                    original_filename=file.name,
                    file_size=file.size,
                    file_type=file.name.split('.')[-1].lower()
                )
                
                # Lancer l'indexation asynchrone
                process_document_async.delay(document.id)

        # 8) Activation du workflow avec tentatives
        max_retries_workflow_active = 10
        delay_seconds_workflow_active = 3
        workflow_is_ready = False

        # Première tentative d'activation
        activated_successfully = manager.activate_workflow(workflow_id)
        if not activated_successfully:
            print(f"⚠️ n8n workflow {workflow_id} failed to activate.")
            manager.delete_workflow(workflow_id)
            patient.delete()
            return Response(
                {"detail": "Failed to activate workflow in n8n."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Vérification que le workflow est bien actif
        print(f"Attente de l'activation du workflow {workflow_id}...")
        for i in range(max_retries_workflow_active):
            if manager.is_workflow_active(workflow_id):
                workflow_is_ready = True
                print(f"✅ Workflow {workflow_id} est actif après {i+1} tentatives")
                break
            print(f"Attente {delay_seconds_workflow_active}s avant vérification... ({i+1}/{max_retries_workflow_active})")
            time.sleep(delay_seconds_workflow_active)

        if not workflow_is_ready:
            print(f"❌ Le workflow {workflow_id} n'est pas devenu actif. Nettoyage...")
            manager.delete_workflow(workflow_id)
            patient.delete()
            return Response(
                {"detail": "Workflow did not become active in time."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # 9) Débogage des webhooks
        manager.debug_webhook_info(workflow_id)
        
        # 10) Construction de l'URL du webhook (pour information seulement)
        webhook_node_id = "webhookTrigger1"
        webhook_url = manager.get_webhook_production_url(workflow_id, webhook_node_id)
        print(f"✅ URL du webhook: {webhook_url}")

        # 11) Exécution directe du workflow
        workflow_data = {
            "fullName": full_name,
            "phone": phone_e164,
            "activation_link": activation_link
        }

        # Tentatives d'exécution du workflow
        max_retries_execution = 5
        delay_seconds_execution = 2
        execution_successful = False

        for i in range(max_retries_execution):
            print(f"Tentative d'exécution du workflow {i+1}/{max_retries_execution}...")
            if manager.execute_workflow_via_webhook(workflow_id, "webhookTrigger1", workflow_data):
                execution_successful = True
                print(f"✅ Workflow exécuté avec succès à la tentative {i+1}")
                break
            print(f"Échec de l'exécution. Attente {delay_seconds_execution}s avant nouvelle tentative...")
            time.sleep(delay_seconds_execution)

        if not execution_successful:
            print(f"❌ Impossible d'exécuter le workflow après {max_retries_execution} tentatives")
            # Le workflow reste créé pour une exécution manuelle ultérieure

        # 12) Construction de l'URL UI pour l'administration
        ui_base = settings.N8N_BASE_URL.rstrip("/").replace("/rest", "")
        workflow_ui_link = f"{ui_base}/workflow/{workflow_id}"

        # 13) Réponse finale
        return Response({
            "id": patient.id,
            "activation_link": activation_link,
            "n8n_workflow_id": workflow_id,
            "n8n_workflow_ui_link": workflow_ui_link,
            "webhook_url": webhook_url,
            "execution_status": "exécuté" if execution_successful else "non exécuté",
            "message": f"Patient créé, workflow n8n créé et {'exécuté' if execution_successful else 'non exécuté'}"
        }, status=status.HTTP_201_CREATED)

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
    Called by n8n when the patient’s WhatsApp reply is correct.
    Expects JSON: {"phone": "+221771234567", "valid": true}
    """

    def post(self, request, *args, **kwargs):
        phone = request.data.get("phone")
        valid = request.data.get("valid", False)

        if not phone or not isinstance(valid, bool):
            return Response(
                {"detail": "phone and valid (boolean) are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            patient = Patient.objects.get(phone=phone)
        except Patient.DoesNotExist:
            return Response({"detail": "Patient not found."}, status=status.HTTP_404_NOT_FOUND)

        if valid:
            patient.is_active = True
            patient.activated_at = timezone.now()
            patient.save()
            return Response({"detail": "Patient marked as active."}, status=status.HTTP_200_OK)
        else:
            return Response({"detail": "Confirmation invalid; no changes made."}, status=status.HTTP_200_OK)

class ActivateRedirectView(View):
    """
    GET /activate/?token=<uuid>
    Looks up the patient, then redirects to a WhatsApp chat link with pre-filled text.
    """

    def get(self, request, *args, **kwargs):
        token = request.GET.get("token")
        if not token:
            return HttpResponseBadRequest("Missing token parameter.")

        try:
            token_uuid = uuid.UUID(token)
        except ValueError:
            return HttpResponseBadRequest("Invalid token.")

        try:
            patient = Patient.objects.get(activation_token=token_uuid)
        except Patient.DoesNotExist:
            return HttpResponseBadRequest("No patient found with that activation link.")

        if patient.is_active:
            # If already active, you might show a “You’re already activated” page instead of redirect.
            return HttpResponseBadRequest("Your account is already active.")

        # Build the WhatsApp URL:
        # Twilio WhatsApp numbers typically look like “+1415XXXXXXX”.
        # Use https://api.whatsapp.com/send?phone=TWILIO_WHATSAPP_NUMBER&text=...
        base = "https://api.whatsapp.com/send"
        phone = settings.TWILIO_WHATSAPP_NUMBER  # e.g. "+1415XXXXXXX"
        # URL-encode the text exactly as n8n expects it
        message = "Je confirme l'accès à mon espace santé CARE."
        params = {
            "phone": phone.lstrip("+"),   # wa.me/<NO PLUS SIGN>
            "text": message
        }
        encoded = urllib.parse.urlencode(params, safe="!*'()")  # Encode properly, safe is for characters to NOT encode
        whatsapp_url = f"{base}?{encoded}"

        # Redirect patient’s browser to WhatsApp
        return HttpResponseRedirect(whatsapp_url)