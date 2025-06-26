#!/usr/bin/env python3
"""
Script pour corriger le numéro de téléphone d'un patient
Usage: python fix_patient_phone.py
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

def fix_patient_phone():
    print("=== CORRECTION NUMÉRO DE TÉLÉPHONE ===\n")
    
    # D'abord, afficher l'état actuel
    token = "879c306a-3931-4096-a432-8d1d6103342e"
    target_phone = "+221778828376"
    
    print(f"🔍 Token cible: {token}")
    print(f"📱 Numéro cible: {target_phone}\n")
    
    # Trouver le patient avec ce token
    try:
        patient = Patient.objects.get(activation_token=token)
        print(f"✅ Patient trouvé:")
        print(f"  - ID: {patient.id}")
        print(f"  - Nom: {patient.full_name()}")
        print(f"  - Numéro actuel: {patient.phone}")
        print(f"  - Actif: {'Oui' if patient.is_active else 'Non'}")
        
        if patient.phone == target_phone:
            print("\n✅ Le numéro est déjà correct!")
            return
        
        # Vérifier si un autre patient a ce numéro
        try:
            other_patient = Patient.objects.get(phone=target_phone)
            if other_patient.id != patient.id:
                print(f"\n⚠️ ATTENTION: Un autre patient a déjà ce numéro:")
                print(f"  - ID: {other_patient.id}")
                print(f"  - Nom: {other_patient.full_name()}")
                print(f"  - Token: {other_patient.activation_token}")
                
                print("\n🤔 Que voulez-vous faire?")
                print("1. Échanger les numéros entre les deux patients")
                print("2. Forcer le changement (l'autre patient perdra ce numéro)")
                print("3. Annuler")
                
                choice = input("\nVotre choix (1-3): ")
                
                if choice == "1":
                    # Échanger les numéros
                    old_phone = patient.phone
                    patient.phone = target_phone
                    other_patient.phone = old_phone
                    patient.save()
                    other_patient.save()
                    print(f"\n✅ Numéros échangés!")
                    print(f"  - {patient.full_name()}: {patient.phone}")
                    print(f"  - {other_patient.full_name()}: {other_patient.phone}")
                elif choice == "2":
                    # Forcer le changement
                    other_patient.phone = f"{other_patient.phone}_old"
                    other_patient.save()
                    patient.phone = target_phone
                    patient.save()
                    print(f"\n✅ Numéro mis à jour pour {patient.full_name()}")
                else:
                    print("\n❌ Opération annulée")
                    return
                    
        except Patient.DoesNotExist:
            # Pas de conflit, on peut changer directement
            print(f"\n📝 Changement du numéro:")
            print(f"  - Ancien: {patient.phone}")
            print(f"  - Nouveau: {target_phone}")
            
            response = input("\nConfirmer le changement? (oui/non): ")
            if response.lower() in ['oui', 'o', 'yes', 'y']:
                patient.phone = normalize_phone_number(target_phone)
                patient.save()
                print("\n✅ Numéro mis à jour avec succès!")
            else:
                print("\n❌ Changement annulé")
                
    except Patient.DoesNotExist:
        print(f"❌ Aucun patient trouvé avec le token: {token}")
        
        # Proposer de créer un nouveau patient
        print("\n🆕 Voulez-vous créer un nouveau patient avec ces informations?")
        response = input("(oui/non): ")
        
        if response.lower() in ['oui', 'o', 'yes', 'y']:
            first_name = input("Prénom: ")
            last_name = input("Nom: ")
            
            patient = Patient.objects.create(
                first_name=first_name,
                last_name=last_name,
                phone=normalize_phone_number(target_phone),
                activation_token=token
            )
            print(f"\n✅ Patient créé: {patient.full_name()} (ID: {patient.id})")

if __name__ == "__main__":
    fix_patient_phone()