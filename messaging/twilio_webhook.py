# messaging/twilio_webhook.py
# Webhook Twilio pour gérer l'activation avec token

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from twilio.twiml.messaging_response import MessagingResponse
from patients.models import Patient
from django.utils import timezone
import logging
import re

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def twilio_webhook(request):
    """Webhook pour recevoir et traiter les messages WhatsApp via Twilio"""
    try:
        # Extraire les données du message
        from_number = request.POST.get('From', '').replace('whatsapp:', '')
        message_body = request.POST.get('Body', '').strip()
        
        # Nettoyer le numéro (enlever les espaces)
        from_number = from_number.replace(' ', '')
        
        logger.info(f"📱 Message reçu de {from_number}: {message_body}")
        
        # Vérifier si c'est un message d'activation avec token
        if message_body.upper().startswith('ACTIVER '):
            # Extraire le token UUID
            token_match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', message_body, re.IGNORECASE)
            
            if token_match:
                token = token_match.group(0)
                logger.info(f"🔑 Token extrait: {token}")
                
                try:
                    # Chercher le patient par token ET vérifier le numéro
                    patient = Patient.objects.get(activation_token=token)
                    
                    # Vérifier que le numéro correspond
                    patient_phone_clean = patient.phone.replace(' ', '')
                    if patient_phone_clean != from_number:
                        reply = "❌ Ce lien d'activation ne correspond pas à votre numéro."
                    elif patient.is_active:
                        reply = f"✅ {patient.first_name}, votre compte est déjà activé ! Comment puis-je vous aider ?"
                    else:
                        # Activer le patient
                        patient.is_active = True
                        patient.activated_at = timezone.now()
                        patient.save()
                        
                        reply = f"""✅ Bienvenue {patient.first_name} !

Votre espace santé CARE est maintenant actif.

Je suis votre assistant médical personnel. Je peux répondre à vos questions sur :
📄 Vos documents médicaux
💊 Vos traitements
🔬 Vos résultats d'examens

Comment puis-je vous aider aujourd'hui ?"""
                        
                        logger.info(f"✅ Patient {patient.id} activé avec succès")
                        
                except Patient.DoesNotExist:
                    reply = "❌ Token d'activation invalide. Veuillez vérifier votre SMS."
            else:
                reply = "❌ Format invalide. Veuillez copier le message complet depuis votre SMS."
                
        # Vérifier si c'est le message de confirmation simple
        elif "confirme" in message_body.lower() and "care" in message_body.lower():
            try:
                patient = Patient.objects.get(phone=from_number)
                if patient.is_active:
                    reply = "✅ Votre compte est déjà actif ! Comment puis-je vous aider ?"
                else:
                    reply = f"📋 Pour activer votre compte, envoyez : ACTIVER {patient.activation_token}"
            except Patient.DoesNotExist:
                reply = "❌ Numéro non reconnu. Veuillez contacter votre médecin."
                
        else:
            # C'est une question - vérifier si le patient est actif
            try:
                patient = Patient.objects.get(phone=from_number, is_active=True)
                
                # Appeler le RAG pour répondre
                try:
                    import requests
                    response = requests.post(
                        'http://localhost:8000/api/rag/query/',
                        json={
                            'patient_phone': from_number,
                            'query': message_body,
                            'session_id': f'wa_{patient.id}'
                        },
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        reply = data.get('response', 'Désolé, je n\'ai pas compris votre question.')
                    else:
                        reply = "🤔 Je recherche dans vos documents... Un instant svp."
                        
                except Exception as e:
                    logger.error(f"Erreur RAG: {e}")
                    reply = f"🔍 Question reçue: '{message_body}'\n\nJe traite votre demande..."
                    
            except Patient.DoesNotExist:
                # Patient non trouvé ou inactif
                try:
                    patient = Patient.objects.get(phone=from_number)
                    reply = f"❌ Veuillez d'abord activer votre compte.\n\nEnvoyez : ACTIVER {patient.activation_token}"
                except Patient.DoesNotExist:
                    reply = "❌ Numéro non reconnu. Veuillez contacter votre médecin pour vous inscrire."
        
        # Créer la réponse TwiML
        resp = MessagingResponse()
        resp.message(reply)
        
        return HttpResponse(str(resp), content_type='text/xml')
        
    except Exception as e:
        logger.error(f"❌ Erreur webhook: {e}", exc_info=True)
        
        # Réponse d'erreur générique
        resp = MessagingResponse()
        resp.message("⚠️ Une erreur s'est produite. Veuillez réessayer ou contacter le support.")
        return HttpResponse(str(resp), content_type='text/xml')


# Dans mediServe/urls.py, remplacer l'import du webhook simple par :
# from messaging.twilio_webhook import twilio_webhook
# path('api/webhook/twilio/', twilio_webhook, name='twilio-webhook'),