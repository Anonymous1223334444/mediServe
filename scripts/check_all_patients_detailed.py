# scripts/check_all_patients_detailed.py

import os
import sys
import django

script_dir = os.path.dirname(os.path.abspath(__file__))
# Aller deux niveaux plus haut pour atteindre le répertoire racine du projet Django
# (Exemple: si script est dans /project_root/scripts/, cela renvoie /project_root/)
project_root = os.path.join(script_dir, '..', '') # Ajout d'un '/' final pour s'assurer que c'est un chemin de répertoire
sys.path.insert(0, os.path.abspath(project_root))


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mediServe.settings')
django.setup()

from patients.models import Patient

def check_all_patients_detailed():
    """Affiche TOUS les détails de TOUS les patients"""
    
    print("\n" + "="*80)
    print("🔍 ANALYSE COMPLÈTE DE TOUS LES PATIENTS")
    print("="*80)
    
    # Chercher par différents critères
    all_patients = Patient.objects.all().order_by('id')
    
    print(f"\n📊 Total : {all_patients.count()} patient(s)\n")
    
    # Afficher chaque patient
    for p in all_patients:
        print(f"{'='*40}")
        print(f"ID: {p.id}")
        print(f"Nom: {p.full_name()}")
        print(f"Téléphone: {p.phone}")
        print(f"Email: {p.email}")
        print(f"Token: {p.activation_token}")
        print(f"Actif: {'✅ OUI' if p.is_active else '❌ NON'}")
        print(f"Créé: {p.created_at}")
        if p.activated_at:
            print(f"Activé: {p.activated_at}")
        print(f"{'='*40}\n")
    
    # Rechercher le token mystère
    mystery_token = "dfae34f8-d904-4a20-a24f-981fbbf9f8a5"
    try:
        mystery_patient = Patient.objects.get(activation_token=mystery_token)
        print(f"\n🔍 TOKEN MYSTÈRE TROUVÉ !")
        print(f"   Patient: {mystery_patient.full_name()}")
        print(f"   ID: {mystery_patient.id}")
        print(f"   Téléphone: {mystery_patient.phone}")
    except Patient.DoesNotExist:
        print(f"\n❓ Token mystère '{mystery_token}' non trouvé dans la base")
    
    # Afficher les numéros uniques
    print("\n📱 TOUS LES NUMÉROS :")
    for p in all_patients:
        status = "✅" if p.is_active else "❌"
        print(f"   {status} {p.phone} - {p.full_name()}")

if __name__ == "__main__":
    check_all_patients_detailed()