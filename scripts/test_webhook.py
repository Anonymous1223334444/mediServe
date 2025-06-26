#!/usr/bin/env python3
"""
Script pour tester le webhook localement
Usage: python test_webhook.py
"""
import requests
import sys

# Configuration
WEBHOOK_URL = "https://orca-eternal-specially.ngrok-free.app/api/webhook/twilio/"
PHONE_NUMBER = "+221778828376"  # Numéro du patient Lou
ACTIVATION_TOKEN = "879c306a-3931-4096-a432-8d1d6103342e"  # Token du patient Lou (ID: 2)

def test_webhook():
    """Test le webhook avec un message d'activation"""
    
    # Simuler les données que Twilio envoie
    data = {
        'MessageSid': 'SM1234567890abcdef',
        'SmsSid': 'SM1234567890abcdef',
        'AccountSid': 'AC1234567890abcdef',
        'MessagingServiceSid': '',
        'From': f'whatsapp:{PHONE_NUMBER}',
        'To': 'whatsapp:+14155238886',
        'Body': f'ACTIVER {ACTIVATION_TOKEN}',
        'NumMedia': '0'
    }
    
    print(f"🚀 Test du webhook: {WEBHOOK_URL}")
    print(f"📱 Numéro: {PHONE_NUMBER}")
    print(f"💬 Message: {data['Body']}")
    
    try:
        response = requests.post(WEBHOOK_URL, data=data)
        print(f"\n✅ Status Code: {response.status_code}")
        print(f"📄 Content-Type: {response.headers.get('Content-Type')}")
        print(f"\n📨 Réponse:\n{response.text}")
        
        # Vérifier si c'est une réponse TwiML valide
        if 'xml' in response.headers.get('Content-Type', ''):
            print("\n✅ Réponse TwiML valide détectée")
        else:
            print("\n⚠️ La réponse n'est pas du XML/TwiML")
            
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        
if __name__ == "__main__":
    test_webhook()