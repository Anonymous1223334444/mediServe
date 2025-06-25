# messaging/webhook_debug_max.py
# Webhook avec MAXIMUM de debug

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from twilio.twiml.messaging_response import MessagingResponse
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook_debug_max(request):
    """Webhook qui log TOUT pour debug"""
    
    print("\n" + "🚨"*30)
    print("WEBHOOK TWILIO APPELÉ !!!")
    print("🚨"*30)
    
    # Log la méthode
    print(f"📌 Méthode: {request.method}")
    
    # Log tous les headers
    print("\n📋 HEADERS:")
    for header, value in request.headers.items():
        print(f"   {header}: {value}")
    
    # Log toutes les données POST
    print("\n📦 DONNÉES POST:")
    for key, value in request.POST.items():
        print(f"   {key}: {value}")
    
    # Log les données GET (au cas où)
    print("\n🔍 DONNÉES GET:")
    for key, value in request.GET.items():
        print(f"   {key}: {value}")
    
    # Log le body brut
    print(f"\n📄 BODY BRUT: {request.body[:200]}")
    
    # Réponse basique
    resp = MessagingResponse()
    
    if request.method == "POST":
        from_number = request.POST.get('From', 'Inconnu')
        body = request.POST.get('Body', 'Vide')
        
        resp.message(f"🤖 WEBHOOK OK! J'ai reçu: '{body}' de {from_number}")
    else:
        # Si c'est un GET (test navigateur)
        return HttpResponse("✅ Webhook actif! Utilisez POST pour envoyer des messages.", 
                          content_type="text/plain")
    
    print("\n✅ Réponse envoyée")
    print("🚨"*30 + "\n")
    
    return HttpResponse(str(resp), content_type='text/xml')