# scripts/test_whatsapp_integration.py

import os
import sys
import django

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
from messaging.services import SMSService, WhatsAppService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_whatsapp_setup():
    """Test complet de l'intégration WhatsApp"""
    
    print("🔍 Test de l'intégration WhatsApp MediRecord\n")
    
    # 1. Vérifier les configurations
    print("1️⃣ Vérification des configurations...")
    
    required_settings = [
        'TWILIO_ACCOUNT_SID',
        'TWILIO_AUTH_TOKEN', 
        'TWILIO_WHATSAPP_NUMBER',
        'SITE_PUBLIC_URL',
        'HEALTH_STRUCTURE_NAME'
    ]
    
    missing = []
    for setting in required_settings:
        value = getattr(settings, setting, None)
        if not value:
            missing.append(setting)
        else:
            masked_value = value[:5] + '...' if len(value) > 5 else value
            print(f"   ✅ {setting}: {masked_value}")
    
    if missing:
        print(f"   ❌ Manquant: {', '.join(missing)}")
        return False
    
    # 2. Tester la connexion Twilio
    print("\n2️⃣ Test de connexion Twilio...")
    try:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        account = client.api.accounts(settings.TWILIO_ACCOUNT_SID).fetch()
        print(f"   ✅ Compte Twilio actif: {account.friendly_name}")
    except Exception as e:
        print(f"   ❌ Erreur Twilio: {e}")
        return False
    
    # 3. Vérifier un patient test
    print("\n3️⃣ Recherche d'un patient test...")
    try:
        patient = Patient.objects.filter(is_active=False).first()
        if patient:
            print(f"   ✅ Patient trouvé: {patient.full_name()} ({patient.phone})")
            print(f"      Token: {patient.activation_token}")
            print(f"      Lien cliqué: {'Oui' if patient.activation_link_clicked else 'Non'}")
        else:
            print("   ⚠️  Aucun patient inactif trouvé")
            # Créer un patient test
            print("   📝 Création d'un patient test...")
            patient = Patient.objects.create(
                first_name="Test",
                last_name="Patient",
                phone="+221770000000",  # Numéro test
                email="test@example.com"
            )
            print(f"   ✅ Patient test créé: {patient.full_name()}")
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return False
    
    # 4. Vérifier les documents indexés
    print("\n4️⃣ Vérification de l'indexation...")
    try:
        docs = DocumentUpload.objects.filter(patient=patient)
        if docs.exists():
            print(f"   📄 {docs.count()} document(s) trouvé(s)")
            for doc in docs:
                print(f"      - {doc.original_filename}: {doc.upload_status}")
        
        # Vérifier les vector stores
        vector_path = os.path.join(settings.MEDIA_ROOT, 'vectors', f'patient_{patient.id}')
        if os.path.exists(vector_path):
            files = os.listdir(vector_path)
            print(f"   ✅ Vector store trouvé: {len(files)} fichier(s)")
        else:
            print("   ⚠️  Pas de vector store pour ce patient")
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
    
    # 5. Générer le lien d'activation
    print("\n5️⃣ Génération du lien d'activation...")
    activation_url = f"{settings.SITE_PUBLIC_URL}/api/patients/activate/{patient.activation_token}/"
    print(f"   🔗 {activation_url}")
    
    # 6. Tester l'envoi WhatsApp (optionnel)
    print("\n6️⃣ Test d'envoi WhatsApp...")
    response = input("   Voulez-vous envoyer un message test ? (o/n): ")
    
    if response.lower() == 'o':
        try:
            whatsapp = WhatsAppService()
            success = whatsapp.send_message(
                patient.phone,
                f"Test MediRecord: Votre lien d'activation est {activation_url}"
            )
            if success:
                print("   ✅ Message envoyé avec succès")
            else:
                print("   ❌ Échec de l'envoi")
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
    
    print("\n✨ Test terminé!")
    print("\n📋 Prochaines étapes:")
    print("1. Cliquer sur le lien d'activation")
    print("2. Envoyer le message ACTIVER [token] sur WhatsApp")
    print("3. Tester des questions médicales")
    
    return True

if __name__ == "__main__":
    test_whatsapp_setup()