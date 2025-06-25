# messaging/webhook_simple.py
# Version la plus simple possible du webhook

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from twilio.twiml.messaging_response import MessagingResponse
from patients.models import Patient
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
def webhook_simple(request):
    """Webhook ultra-simple pour WhatsApp"""
    
    # Log TOUT pour debug
    print("\n" + "="*60)
    print("🔔 WEBHOOK APPELÉ !")
    print("="*60)
    
    # Récupérer les données
    from_raw = request.POST.get('From', '')
    body = request.POST.get('Body', '')
    
    # Nettoyer le numéro
    from_number = from_raw.replace('whatsapp:', '').replace(' ', '')
    
    print(f"📱 De: {from_number}")
    print(f"💬 Message: {body}")
    
    # Préparer la réponse
    resp = MessagingResponse()
    
    try:
        # Chercher le patient (avec ou sans espaces dans la DB)
        patient = None
        
        # Essayer d'abord avec le numéro exact
        try:
            patient = Patient.objects.get(phone=from_number)
        except Patient.DoesNotExist:
            # Essayer en cherchant avec des espaces
            for p in Patient.objects.all():
                if p.phone.replace(' ', '') == from_number:
                    patient = p
                    break
        
        if not patient:
            print("❌ Patient non trouvé")
            resp.message("❌ Numéro non reconnu. Contactez votre médecin.")
        else:
            print(f"✅ Patient trouvé: {patient.full_name()}")
            
            # Si le message contient ACTIVER et un token
            if "ACTIVER" in body.upper() and "184877e6" in body:
                if not patient.is_active:
                    patient.is_active = True
                    patient.activated_at = timezone.now()
                    patient.save()
                    resp.message(f"✅ Bienvenue {patient.first_name} ! Votre compte est maintenant actif.")
                else:
                    resp.message(f"✅ {patient.first_name}, votre compte est déjà actif !")
            
            # Sinon, réponse selon le statut
            elif patient.is_active:
                if "bonjour" in body.lower():
                    resp.message(f"👋 Bonjour {patient.first_name} ! Comment allez-vous ?")
                elif "document" in body.lower():
                    resp.message(f"📄 Vous avez des documents indexés. Que voulez-vous savoir ?")
                else:
                    resp.message(f"🤖 J'ai reçu: '{body}'. Je suis votre assistant médical.")
            else:
                resp.message(f"❌ Activez d'abord votre compte avec: ACTIVER {patient.activation_token}")
    
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        resp.message("⚠️ Erreur système. Réessayez svp.")
    
    print("📤 Réponse envoyée")
    print("="*60 + "\n")
    
    return HttpResponse(str(resp), content_type='text/xml')