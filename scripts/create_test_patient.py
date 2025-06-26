#!/usr/bin/env python3
"""
Script pour créer un patient de test
Usage: python create_test_patient.py
"""
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

from patients.models import Patient
from messaging.services import SMSService
import uuid

def create_test_patient():
    print("=== CRÉATION D'UN PATIENT DE TEST ===\n")
    
    # Demander les informations
    first_name = input("Prénom: ") or "Test"
    last_name = input("Nom: ") or "Patient"
    phone = input("Numéro de téléphone (format: +221778828376): ")
    
    if not phone:
        print("❌ Le numéro de téléphone est obligatoire!")
        return
    
    # Vérifier si le patient existe déjà
    existing = Patient.objects.filter(phone=phone).first()
    if existing:
        print(f"\n⚠️ Un patient existe déjà avec ce numéro:")
        print(f"  - Nom: {existing.full_name()}")
        print(f"  - Token: {existing.activation_token}")
        print(f"  - Actif: {'Oui' if existing.is_active else 'Non'}")
        
        response = input("\nVoulez-vous réinitialiser ce patient ? (oui/non): ")
        if response.lower() in ['oui', 'o', 'yes', 'y']:
            # Réinitialiser
            existing.is_active = False
            existing.activation_token = uuid.uuid4()
            existing.activated_at = None
            existing.save()
            patient = existing
            print("✅ Patient réinitialisé!")
        else:
            return
    else:
        # Créer un nouveau patient
        patient = Patient.objects.create(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            gender='M'  # Par défaut
        )
        print("✅ Patient créé!")
    
    print(f"\n📋 Informations du patient:")
    print(f"  - ID: {patient.id}")
    print(f"  - Nom: {patient.full_name()}")
    print(f"  - Téléphone: {patient.phone}")
    print(f"  - Token: {patient.activation_token}")
    print(f"  - Actif: {'Oui' if patient.is_active else 'Non'}")
    
    # Proposer d'envoyer le SMS
    response = input("\n📱 Voulez-vous envoyer le SMS d'activation ? (oui/non): ")
    if response.lower() in ['oui', 'o', 'yes', 'y']:
        try:
            sms_service = SMSService()
            success, result = sms_service.send_activation_sms(patient)
            if success:
                print("✅ SMS envoyé avec succès!")
            else:
                print(f"❌ Erreur envoi SMS: {result}")
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    # Message de test pour WhatsApp
    print(f"\n💬 Message de test pour WhatsApp:")
    print(f"ACTIVER {patient.activation_token}")
    
    print(f"\n🔗 Lien d'activation:")
    from django.conf import settings
    print(f"{settings.SITE_PUBLIC_URL}/api/patients/activate/{patient.activation_token}/")

if __name__ == "__main__":
    create_test_patient()