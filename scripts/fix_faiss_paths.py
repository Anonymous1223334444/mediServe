#!/usr/bin/env python3
"""
Script pour corriger les chemins des fichiers FAISS
Usage: python fix_faiss_paths.py
"""
import os
import sys
import django
import shutil

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

def fix_faiss_paths():
    """Corrige les chemins des fichiers FAISS"""
    print("=== CORRECTION DES CHEMINS FAISS ===\n")
    
    vectors_root = os.path.join(settings.MEDIA_ROOT, 'vectors')
    
    if not os.path.exists(vectors_root):
        print(f"❌ Dossier vectors non trouvé: {vectors_root}")
        return
    
    corrections = []
    
    # Parcourir tous les dossiers de patients
    for patient_dir in os.listdir(vectors_root):
        if patient_dir.startswith('patient_'):
            patient_path = os.path.join(vectors_root, patient_dir)
            
            if os.path.isdir(patient_path):
                print(f"\n📁 Vérification: {patient_dir}")
                
                # Chemins possibles
                old_faiss = os.path.join(patient_path, 'vector_store.h5.faiss')
                new_faiss = os.path.join(patient_path, 'vector_store.faiss')
                hdf5_file = os.path.join(patient_path, 'vector_store.h5')
                
                # Afficher l'état actuel
                print(f"  - HDF5: {'✅ Existe' if os.path.exists(hdf5_file) else '❌ Manquant'}")
                print(f"  - FAISS (ancien): {'✅ Existe' if os.path.exists(old_faiss) else '❌ Manquant'}")
                print(f"  - FAISS (nouveau): {'✅ Existe' if os.path.exists(new_faiss) else '❌ Manquant'}")
                
                # Corriger si nécessaire
                if os.path.exists(old_faiss) and not os.path.exists(new_faiss):
                    corrections.append({
                        'patient_dir': patient_dir,
                        'old': old_faiss,
                        'new': new_faiss
                    })
                    print(f"  ⚠️ Correction nécessaire: renommer .h5.faiss → .faiss")
    
    # Appliquer les corrections
    if corrections:
        print(f"\n📊 Corrections à appliquer: {len(corrections)}")
        
        response = input("\nAppliquer les corrections ? (oui/non): ")
        if response.lower() in ['oui', 'o', 'yes', 'y']:
            for corr in corrections:
                try:
                    shutil.move(corr['old'], corr['new'])
                    print(f"✅ Renommé: {os.path.basename(corr['old'])} → {os.path.basename(corr['new'])}")
                except Exception as e:
                    print(f"❌ Erreur: {e}")
            print("\n✅ Corrections terminées!")
        else:
            print("\n❌ Corrections annulées.")
    else:
        print("\n✅ Aucune correction nécessaire, tous les fichiers sont corrects!")
    
    # Vérifier l'intégrité après correction
    print("\n🔍 VÉRIFICATION FINALE:")
    issues = []
    
    for patient_dir in os.listdir(vectors_root):
        if patient_dir.startswith('patient_'):
            patient_path = os.path.join(vectors_root, patient_dir)
            if os.path.isdir(patient_path):
                hdf5 = os.path.join(patient_path, 'vector_store.h5')
                faiss = os.path.join(patient_path, 'vector_store.faiss')
                
                if os.path.exists(hdf5) and not os.path.exists(faiss):
                    issues.append(f"  ⚠️ {patient_dir}: HDF5 présent mais FAISS manquant")
                elif not os.path.exists(hdf5) and os.path.exists(faiss):
                    issues.append(f"  ⚠️ {patient_dir}: FAISS présent mais HDF5 manquant")
    
    if issues:
        print("\n⚠️ Problèmes détectés:")
        for issue in issues:
            print(issue)
        print("\nConsidérez ré-indexer ces patients avec scripts/reindex_documents.py")
    else:
        print("\n✅ Tous les vector stores sont cohérents!")

if __name__ == "__main__":
    fix_faiss_paths()