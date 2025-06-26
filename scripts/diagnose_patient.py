#!/usr/bin/env python3
"""
Script de diagnostic pour vérifier les patients et leurs tokens
Usage: python diagnose_patient.py
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
from documents.models import DocumentUpload

def diagnose():
    print("=== DIAGNOSTIC PATIENTS ===\n")
    
    # 1. Lister tous les patients
    patients = Patient.objects.all()
    print(f"📊 Total patients: {patients.count()}")
    print("\n📋 Liste des patients:")
    print("-" * 100)
    print(f"{'ID':<5} {'Nom':<30} {'Téléphone':<20} {'Actif':<10} {'Token':<40}")
    print("-" * 100)
    
    for patient in patients:
        print(f"{patient.id:<5} {patient.full_name():<30} {patient.phone:<20} "
              f"{'✅' if patient.is_active else '❌':<10} {str(patient.activation_token):<40}")
    
    # 2. Rechercher par numéro de téléphone
    phone = input("\n📱 Entrez un numéro de téléphone à rechercher (ou appuyez sur Entrée pour passer): ")
    if phone:
        # Nettoyer le numéro
        phone_clean = phone.replace(' ', '').replace('+', '')
        
        # Rechercher avec différentes variations
        patients_found = Patient.objects.filter(phone__icontains=phone_clean)
        
        if patients_found.exists():
            print(f"\n✅ Patient(s) trouvé(s) pour {phone}:")
            for p in patients_found:
                print(f"  - {p.full_name()} (ID: {p.id})")
                print(f"    Phone: {p.phone}")
                print(f"    Token: {p.activation_token}")
                print(f"    Actif: {'Oui' if p.is_active else 'Non'}")
                
                # Vérifier les documents
                docs = DocumentUpload.objects.filter(patient=p)
                print(f"    Documents: {docs.count()}")
                if docs.exists():
                    for doc in docs:
                        print(f"      - {doc.original_filename} ({doc.upload_status})")
        else:
            print(f"\n❌ Aucun patient trouvé pour {phone}")
            
            # Recherche plus large
            print("\n🔍 Recherche élargie:")
            all_phones = Patient.objects.values_list('phone', flat=True)
            for db_phone in all_phones:
                if phone_clean in db_phone or db_phone in phone_clean:
                    p = Patient.objects.get(phone=db_phone)
                    print(f"  - Correspondance partielle: {p.full_name()} - {db_phone}")
    
    # 3. Rechercher par token
    token = input("\n🔑 Entrez un token d'activation à rechercher (ou appuyez sur Entrée pour passer): ")
    if token:
        try:
            patient = Patient.objects.get(activation_token=token)
            print(f"\n✅ Patient trouvé pour le token:")
            print(f"  - Nom: {patient.full_name()}")
            print(f"  - ID: {patient.id}")
            print(f"  - Phone: {patient.phone}")
            print(f"  - Actif: {'Oui' if patient.is_active else 'Non'}")
            print(f"  - Créé le: {patient.created_at}")
            if patient.activated_at:
                print(f"  - Activé le: {patient.activated_at}")
        except Patient.DoesNotExist:
            print(f"\n❌ Aucun patient trouvé pour le token: {token}")
    
    # 4. Statistiques
    print("\n📊 STATISTIQUES:")
    print(f"  - Patients actifs: {Patient.objects.filter(is_active=True).count()}")
    print(f"  - Patients inactifs: {Patient.objects.filter(is_active=False).count()}")
    print(f"  - Documents totaux: {DocumentUpload.objects.count()}")
    print(f"  - Documents indexés: {DocumentUpload.objects.filter(upload_status='indexed').count()}")
    
    # 5. Derniers patients créés
    print("\n🆕 5 derniers patients créés:")
    recent = Patient.objects.order_by('-created_at')[:5]
    for p in recent:
        print(f"  - {p.full_name()} ({p.phone}) - Créé: {p.created_at.strftime('%Y-%m-%d %H:%M')}")

if __name__ == "__main__":
    diagnose()