# messaging/twilio_webhook_debug.py
# Version de debug du webhook avec réponses simulées

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
def twilio_webhook_debug(request):
    """Webhook Twilio avec réponses de test pour débugger"""
    try:
        # Extraire les données
        from_number = request.POST.get('From', '').replace('whatsapp:', '').replace(' ', '')
        message_body = request.POST.get('Body', '').strip()
        
        logger.info(f"📱 Message reçu de {from_number}: {message_body}")
        print(f"\n🔔 WEBHOOK APPELÉ - De: {from_number} - Message: {message_body}\n")
        
        # Gestion de l'activation avec token
        if message_body.upper().startswith('ACTIVER '):
            token_match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', message_body, re.IGNORECASE)
            
            if token_match:
                token = token_match.group(0)
                logger.info(f"🔑 Token extrait: {token}")
                
                try:
                    patient = Patient.objects.get(activation_token=token)
                    patient_phone_clean = patient.phone.replace(' ', '')
                    
                    if patient_phone_clean != from_number:
                        reply = "❌ Ce lien d'activation ne correspond pas à votre numéro."
                    elif patient.is_active:
                        reply = f"✅ {patient.first_name}, votre compte est déjà activé !"
                    else:
                        patient.is_active = True
                        patient.activated_at = timezone.now()
                        patient.save()
                        reply = f"""✅ Bienvenue {patient.first_name} !

Votre espace santé CARE est maintenant actif.

Je suis votre assistant médical. Posez vos questions !"""
                        
                except Patient.DoesNotExist:
                    reply = "❌ Token d'activation invalide."
            else:
                reply = "❌ Format invalide. Copiez le message complet du SMS."
                
        else:
            # Pour toute autre question
            try:
                patient = Patient.objects.get(phone=from_number)
                
                if not patient.is_active:
                    reply = f"❌ Activez d'abord votre compte.\n\nEnvoyez : ACTIVER {patient.activation_token}"
                else:
                    # RÉPONSES DE TEST selon les mots-clés
                    message_lower = message_body.lower()
                    
                    if any(word in message_lower for word in ['document', 'fichier', 'pdf']):
                        # Vérifier les documents du patient
                        from documents.models import DocumentUpload
                        docs = DocumentUpload.objects.filter(patient=patient, upload_status='indexed')
                        
                        if docs.exists():
                            doc_list = "\n".join([f"📄 {doc.original_filename}" for doc in docs[:3]])
                            reply = f"📚 Vos documents indexés :\n{doc_list}\n\nQue voulez-vous savoir ?"
                        else:
                            reply = "📭 Aucun document trouvé. Contactez votre médecin."
                            
                    elif any(word in message_lower for word in ['résultat', 'analyse', 'examen']):
                        reply = "🔬 D'après vos documents, vos derniers résultats datent du mois dernier. Tous les paramètres sont dans les normes."
                        
                    elif any(word in message_lower for word in ['médicament', 'traitement', 'posologie']):
                        reply = "💊 Selon votre dossier, vous prenez actuellement :\n- Paracétamol 1g : 3x/jour\n- Vitamine D : 1x/jour"
                        
                    elif any(word in message_lower for word in ['bonjour', 'salut', 'hello']):
                        reply = f"👋 Bonjour {patient.first_name} ! Comment puis-je vous aider aujourd'hui ?"
                        
                    elif any(word in message_lower for word in ['aide', 'help', 'comment']):
                        reply = """🤝 Je peux vous aider avec :
- Vos documents médicaux
- Vos résultats d'analyses
- Vos médicaments
- Vos rendez-vous

Posez votre question !"""
                        
                    else:
                        # Réponse générique avec info de debug
                        reply = f"""🤖 J'ai bien reçu : "{message_body}"

[MODE DEBUG - RAG désactivé]

Pour tester, essayez :
- "Mes documents"
- "Mes résultats"
- "Mes médicaments"

Patient ID: {patient.id}
Docs indexés: {DocumentUpload.objects.filter(patient=patient, upload_status='indexed').count()}"""
                        
            except Patient.DoesNotExist:
                reply = "❌ Numéro non reconnu. Contactez votre médecin pour vous inscrire."
        
        # Envoyer la réponse
        resp = MessagingResponse()
        resp.message(reply)
        
        logger.info(f"📤 Réponse envoyée: {reply[:50]}...")
        return HttpResponse(str(resp), content_type='text/xml')
        
    except Exception as e:
        logger.error(f"❌ Erreur webhook: {e}", exc_info=True)
        resp = MessagingResponse()
        resp.message(f"⚠️ Erreur : {str(e)}")
        return HttpResponse(str(resp), content_type='text/xml')


# Vérifier les tokens de tous les patients
def check_all_tokens():
    """Fonction utilitaire pour voir tous les tokens"""
    from patients.models import Patient
    
    print("\n📋 LISTE DES PATIENTS ET TOKENS :")
    print("-" * 60)
    
    for p in Patient.objects.all():
        status = "✅ ACTIF" if p.is_active else "❌ INACTIF"
        print(f"{status} {p.full_name()} ({p.phone})")
        print(f"   Token: {p.activation_token}")
        print(f"   Lien: https://orca-eternal-specially.ngrok-free.app/api/patients/activate/{p.activation_token}/")
        print("-" * 60)


# Dans urls.py, temporairement remplacer par :
# from messaging.twilio_webhook_debug import twilio_webhook_debug
# path('api/webhook/twilio/', twilio_webhook_debug, name='twilio-webhook'),