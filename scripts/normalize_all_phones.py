#!/usr/bin/env python3
"""
Script pour normaliser tous les numéros de téléphone dans la base de données
Usage: python normalize_all_phones.py
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
from messaging.utils import normalize_phone_number

def normalize_all():
    """Normalise tous les numéros de téléphone"""
    print("=== NORMALISATION DES NUMÉROS DE TÉLÉPHONE ===\n")
    
    patients = Patient.objects.all()
    print(f"📊 Patients à traiter: {patients.count()}\n")
    
    normalized_count = 0
    errors = []
    
    for patient in patients:
        old_phone = patient.phone
        
        try:
            # Normaliser le numéro
            new_phone = normalize_phone_number(old_phone)
            
            # Enlever tous les espaces pour uniformiser
            new_phone = new_phone.replace(' ', '')
            
            if old_phone != new_phone:
                print(f"📱 {patient.full_name()}")
                print(f"   Avant: {old_phone}")
                print(f"   Après: {new_phone}")
                
                patient.phone = new_phone
                patient.save()
                normalized_count += 1
                print(f"   ✅ Mis à jour\n")
            
        except Exception as e:
            errors.append({
                'patient': patient,
                'error': str(e)
            })
            print(f"❌ Erreur pour {patient.full_name()}: {e}\n")
    
    # Résumé
    print(f"\n📊 RÉSUMÉ:")
    print(f"  - Total traités: {patients.count()}")
    print(f"  - Numéros normalisés: {normalized_count}")
    print(f"  - Erreurs: {len(errors)}")
    
    if errors:
        print(f"\n❌ Erreurs détaillées:")
        for err in errors:
            print(f"  - {err['patient'].full_name()}: {err['error']}")

if __name__ == "__main__":
    print("⚠️ Ce script va normaliser TOUS les numéros de téléphone dans la base de données.")
    response = input("Continuer ? (oui/non): ")
    
    if response.lower() in ['oui', 'o', 'yes', 'y']:
        normalize_all()
        print("\n✅ Normalisation terminée!")
    else:
        print("\n❌ Opération annulée.")