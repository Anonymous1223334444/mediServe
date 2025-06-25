# messaging/webhook.py
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def twilio_webhook(request):
    """Webhook simple pour recevoir les messages WhatsApp"""
    try:
        # Extraire les données du message
        from_number = request.POST.get('From', '').replace('whatsapp:', '')
        message_body = request.POST.get('Body', '')
        
        logger.info(f"Message reçu de {from_number}: {message_body}")
        
        # Importer les services nécessaires
        from patients.models import Patient
        from messaging.services import WhatsAppService
        from django.utils import timezone
        
        # Vérifier si c'est un message de confirmation
        if "confirme" in message_body.lower() and "care" in message_body.lower():
            try:
                # Trouver le patient par numéro
                patient = Patient.objects.get(phone=from_number)
                
                if not patient.is_active:
                    # Activer le patient
                    patient.is_active = True
                    patient.activated_at = timezone.now()
                    patient.save()
                    
                    response_message = f"""✅ Bienvenue {patient.first_name} !

Votre espace santé CARE est maintenant actif.

Je suis votre assistant médical personnel. Je peux répondre à vos questions sur :
📄 Vos documents médicaux
💊 Vos traitements
🔬 Vos résultats d'examens

Comment puis-je vous aider aujourd'hui ?"""
                else:
                    response_message = "Votre compte est déjà actif ! Comment puis-je vous aider ?"
                    
            except Patient.DoesNotExist:
                response_message = "❌ Numéro non reconnu. Veuillez contacter votre médecin."
        else:
            # C'est une question - utiliser le RAG
            try:
                patient = Patient.objects.get(phone=from_number, is_active=True)
                
                # Appeler le RAG
                from rag.views import RAGQueryView
                import json
                
                # Simuler une requête RAG
                response = requests.post(
                    'http://localhost:8000/api/rag/query/',
                    json={
                        'patient_phone': from_number,
                        'query': message_body,
                        'session_id': f'wa_{patient.id}'
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    response_message = data.get('response', 'Désolé, je n\'ai pas compris.')
                else:
                    response_message = "Désolé, une erreur s'est produite. Veuillez réessayer."
                    
            except Patient.DoesNotExist:
                response_message = "❌ Veuillez d'abord activer votre compte en envoyant le message de confirmation."
            except Exception as e:
                logger.error(f"Erreur RAG: {e}")
                response_message = "Désolé, je ne peux pas répondre pour le moment."
        
        # Retourner la réponse TwiML
        from twilio.twiml.messaging_response import MessagingResponse
        resp = MessagingResponse()
        resp.message(response_message)
        
        return HttpResponse(str(resp), content_type='text/xml')
        
    except Exception as e:
        logger.error(f"Erreur webhook: {e}")
        return HttpResponse(status=500)