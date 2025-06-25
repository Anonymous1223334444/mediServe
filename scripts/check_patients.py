# scripts/check_patients.py
# Vérifier tous les patients et leurs statuts

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
from documents.models import DocumentUpload
from django.conf import settings

def check_all_patients():
    """Affiche tous les patients avec leurs infos"""
    
    print("\n" + "="*80)
    print("📋 ÉTAT DES PATIENTS DANS LE SYSTÈME")
    print("="*80)
    
    patients = Patient.objects.all().order_by('-created_at')
    
    if not patients:
        print("❌ Aucun patient trouvé dans la base de données")
        return
    
    for p in patients:
        # Status
        status = "✅ ACTIF" if p.is_active else "❌ INACTIF"
        
        # Infos principales
        print(f"\n{status} Patient #{p.id}: {p.full_name()}")
        print(f"   📱 Téléphone: {p.phone}")
        print(f"   📧 Email: {p.email or 'Non renseigné'}")
        print(f"   🔑 Token: {p.activation_token}")
        
        # Dates
        print(f"   📅 Créé le: {p.created_at.strftime('%d/%m/%Y %H:%M')}")
        if p.activated_at:
            print(f"   ✅ Activé le: {p.activated_at.strftime('%d/%m/%Y %H:%M')}")
        
        # Documents
        docs = DocumentUpload.objects.filter(patient=p)
        indexed = docs.filter(upload_status='indexed').count()
        total = docs.count()
        print(f"   📄 Documents: {indexed}/{total} indexés")
        
        if docs:
            print("      Fichiers:")
            for doc in docs[:3]:  # Afficher max 3 documents
                emoji = "✅" if doc.upload_status == 'indexed' else "⏳"
                print(f"      {emoji} {doc.original_filename} ({doc.upload_status})")
        
        # Lien d'activation
        activation_url = f"{settings.SITE_PUBLIC_URL}/api/patients/activate/{p.activation_token}/"
        print(f"   🔗 Lien: {activation_url}")
        
        # Message d'activation
        print(f"   💬 Message WhatsApp: ACTIVER {p.activation_token}")
        
        print("-" * 80)
    
    # Résumé
    total_patients = patients.count()
    active_patients = patients.filter(is_active=True).count()
    
    print(f"\n📊 RÉSUMÉ:")
    print(f"   Total patients: {total_patients}")
    print(f"   Actifs: {active_patients}")
    print(f"   Inactifs: {total_patients - active_patients}")
    
    # Patient le plus récent
    latest = patients.first()
    if latest:
        print(f"\n🆕 Dernier patient créé: {latest.full_name()} ({latest.created_at.strftime('%d/%m/%Y %H:%M')})")
        print(f"   Son token: {latest.activation_token}")

if __name__ == "__main__":
    check_all_patients()