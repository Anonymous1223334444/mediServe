# scripts/fix_phone_numbers.py
# Script pour nettoyer les numéros de téléphone avec espaces

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

def fix_phone_numbers():
    """Nettoie tous les numéros de téléphone en enlevant les espaces"""
    patients = Patient.objects.all()
    fixed_count = 0
    
    for patient in patients:
        old_phone = patient.phone
        # Enlever tous les espaces
        new_phone = old_phone.replace(' ', '')
        
        if old_phone != new_phone:
            print(f"Correction: {old_phone} → {new_phone}")
            patient.phone = new_phone
            patient.save()
            fixed_count += 1
    
    print(f"\n✅ {fixed_count} numéros corrigés")
    return fixed_count

if __name__ == "__main__":
    fix_phone_numbers()