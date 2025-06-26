#!/usr/bin/env python3
"""
Script pour vérifier quel patient correspond à un token
Usage: python check_token.py
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

def check_token():
    print("=== VÉRIFICATION TOKEN/NUMÉRO ===\n")
    
    # Token à vérifier
    token = "879c306a-3931-4096-a432-8d1d6103342e"
    phone = "+221778828376"
    
    print(f"🔍 Recherche du token: {token}")
    
    try:
        patient_by_token = Patient.objects.get(activation_token=token)
        print(f"\n✅ Patient trouvé par token:")
        print(f"  - ID: {patient_by_token.id}")
        print(f"  - Nom: {patient_by_token.full_name()}")
        print(f"  - Téléphone: {patient_by_token.phone}")
        print(f"  - Actif: {'Oui' if patient_by_token.is_active else 'Non'}")
    except Patient.DoesNotExist:
        print(f"❌ Aucun patient trouvé avec ce token")
    
    print(f"\n🔍 Recherche du numéro: {phone}")
    
    try:
        patient_by_phone = Patient.objects.get(phone=phone)
        print(f"\n✅ Patient trouvé par numéro:")
        print(f"  - ID: {patient_by_phone.id}")
        print(f"  - Nom: {patient_by_phone.full_name()}")
        print(f"  - Token: {patient_by_phone.activation_token}")
        print(f"  - Actif: {'Oui' if patient_by_phone.is_active else 'Non'}")
    except Patient.DoesNotExist:
        print(f"❌ Aucun patient trouvé avec ce numéro")
        
        # Recherche flexible
        print("\n🔍 Recherche flexible...")
        for p in Patient.objects.all():
            if phone.replace('+', '') in p.phone.replace('+', '').replace(' ', ''):
                print(f"  - Correspondance partielle: {p.full_name()} - {p.phone} (Token: {p.activation_token})")
    
    print("\n📋 TOUS LES PATIENTS:")
    print("-" * 100)
    print(f"{'ID':<5} {'Nom':<30} {'Téléphone':<20} {'Token':<40}")
    print("-" * 100)
    
    for patient in Patient.objects.all():
        print(f"{patient.id:<5} {patient.full_name():<30} {patient.phone:<20} {str(patient.activation_token):<40}")

if __name__ == "__main__":
    check_token()