# scripts/activate_patient.py
# Activer manuellement un patient pour tester

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
from django.utils import timezone

def activate_patient(patient_id=None, phone=None, token=None):
    """Active manuellement un patient"""
    
    try:
        if patient_id:
            patient = Patient.objects.get(id=patient_id)
        elif phone:
            patient = Patient.objects.get(phone=phone)
        elif token:
            patient = Patient.objects.get(activation_token=token)
        else:
            # Prendre le dernier patient créé
            patient = Patient.objects.order_by('-created_at').first()
        
        if not patient:
            print("❌ Aucun patient trouvé")
            return
        
        print(f"\n🔍 Patient trouvé: {patient.full_name()}")
        print(f"   📱 Téléphone: {patient.phone}")
        print(f"   🔑 Token: {patient.activation_token}")
        print(f"   📊 Statut actuel: {'ACTIF' if patient.is_active else 'INACTIF'}")
        
        if patient.is_active:
            print("\n✅ Ce patient est déjà actif !")
            return
        
        # Demander confirmation
        response = input("\n❓ Voulez-vous activer ce patient ? (o/n): ")
        
        if response.lower() == 'o':
            patient.is_active = True
            patient.activated_at = timezone.now()
            patient.save()
            
            print(f"\n✅ Patient {patient.full_name()} activé avec succès !")
            print(f"   Activé le: {patient.activated_at.strftime('%d/%m/%Y %H:%M')}")
            
            # Message à envoyer sur WhatsApp
            print(f"\n💬 Maintenant, testez sur WhatsApp avec ce numéro:")
            print(f"   {patient.phone}")
            print(f"\n   Envoyez n'importe quelle question, par exemple:")
            print(f"   - Bonjour")
            print(f"   - Mes documents")
            print(f"   - Quels sont mes résultats ?")
        else:
            print("\n❌ Activation annulée")
            
    except Patient.DoesNotExist:
        print("❌ Patient non trouvé")
    except Exception as e:
        print(f"❌ Erreur: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', type=int, help='ID du patient')
    parser.add_argument('--phone', help='Numéro de téléphone')
    parser.add_argument('--token', help='Token d\'activation')
    
    args = parser.parse_args()
    activate_patient(patient_id=args.id, phone=args.phone, token=args.token)