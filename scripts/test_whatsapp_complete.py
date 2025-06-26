#!/usr/bin/env python3
"""
Script de test complet pour WhatsApp
Usage: python test_whatsapp_complete.py
"""
import os
import sys
import django
import requests

script_dir = os.path.dirname(os.path.abspath(__file__))
# Aller deux niveaux plus haut pour atteindre le répertoire racine du projet Django
# (Exemple: si script est dans /project_root/scripts/, cela renvoie /project_root/)
project_root = os.path.join(script_dir, '..', '') # Ajout d'un '/' final pour s'assurer que c'est un chemin de répertoire
sys.path.insert(0, os.path.abspath(project_root))

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mediServe.settings')
django.setup()

from django.conf import settings
from patients.models import Patient
from documents.models import DocumentUpload

def test_whatsapp():
    print("=== TEST COMPLET WHATSAPP ===\n")
    
    # 1. Sélectionner le patient
    print("📋 Patients disponibles:")
    patients = Patient.objects.all()
    for p in patients:
        docs = DocumentUpload.objects.filter(patient=p, upload_status='indexed').count()
        print(f"  {p.id}. {p.full_name()} - {p.phone} ({'✅ Actif' if p.is_active else '❌ Inactif'}) - {docs} docs")
    
    patient_id = input("\nChoisir un patient (ID): ")
    try:
        patient = Patient.objects.get(id=int(patient_id))
    except:
        print("❌ Patient non trouvé")
        return
    
    print(f"\n✅ Patient sélectionné: {patient.full_name()}")
    print(f"  - Téléphone: {patient.phone}")
    print(f"  - Token: {patient.activation_token}")
    print(f"  - Actif: {'Oui' if patient.is_active else 'Non'}")
    
    # 2. Tester différents messages
    webhook_url = f"{settings.SITE_PUBLIC_URL}/api/webhook/twilio/"
    
    test_messages = [
        f"ACTIVER {patient.activation_token}",
        "Bonjour",
        "Documents",
        "Résume mes documents",
        "Quels sont mes médicaments ?",
    ]
    
    print(f"\n🚀 Tests sur: {webhook_url}")
    
    for msg in test_messages:
        print(f"\n📱 Test: '{msg}'")
        
        data = {
            'MessageSid': f'TEST_{int(os.urandom(4).hex(), 16)}',
            'SmsSid': f'TEST_{int(os.urandom(4).hex(), 16)}',
            'AccountSid': 'ACtest',
            'MessagingServiceSid': '',
            'From': f'whatsapp:{patient.phone}',
            'To': f'whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}',
            'Body': msg,
            'NumMedia': '0'
        }
        
        try:
            response = requests.post(webhook_url, data=data)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                # Extraire le message de la réponse XML
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.text)
                message = root.find('.//Message')
                if message is not None:
                    response_text = message.text
                    # Limiter l'affichage
                    if len(response_text) > 200:
                        response_text = response_text[:200] + "..."
                    print(f"  Réponse: {response_text}")
                else:
                    print(f"  Réponse XML: {response.text[:200]}...")
            else:
                print(f"  ❌ Erreur: {response.text[:200]}...")
                
        except Exception as e:
            print(f"  ❌ Exception: {e}")
    
    # 3. Vérifier l'état des vector stores
    print("\n🔍 VÉRIFICATION VECTOR STORES:")
    vector_dir = os.path.join(settings.MEDIA_ROOT, 'vectors', f'patient_{patient.id}')
    
    if os.path.exists(vector_dir):
        files = os.listdir(vector_dir)
        print(f"  ✅ Dossier existe: {vector_dir}")
        print(f"  📁 Fichiers: {', '.join(files)}")
    else:
        print(f"  ❌ Dossier manquant: {vector_dir}")

if __name__ == "__main__":
    test_whatsapp()