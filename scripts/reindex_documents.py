#!/usr/bin/env python3
"""
Script pour ré-indexer les documents d'un patient
Usage: python reindex_documents.py
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

from django.conf import settings
from patients.models import Patient
from documents.models import DocumentUpload
from documents.tasks import process_document_async
from messaging.utils import normalize_phone_number
import shutil

def reindex_patient_documents(patient):
    """Ré-indexe tous les documents d'un patient"""
    print(f"\n🔄 RÉ-INDEXATION DES DOCUMENTS DE {patient.full_name()}")
    
    # 1. Supprimer les anciens index
    vector_dir = os.path.join(settings.MEDIA_ROOT, 'vectors', f'patient_{patient.id}')
    bm25_dir = os.path.join(settings.MEDIA_ROOT, 'indexes', f'patient_{patient.id}_bm25')
    
    if os.path.exists(vector_dir):
        print(f"🗑️ Suppression de l'ancien vector store...")
        shutil.rmtree(vector_dir)
    
    if os.path.exists(bm25_dir):
        print(f"🗑️ Suppression de l'ancien index BM25...")
        shutil.rmtree(bm25_dir)
    
    # 2. Récupérer tous les documents
    documents = DocumentUpload.objects.filter(patient=patient)
    print(f"\n📄 Documents à ré-indexer: {documents.count()}")
    
    # 3. Réinitialiser le statut
    for doc in documents:
        print(f"\n  📄 {doc.original_filename}")
        
        # Vérifier que le fichier existe
        if not doc.file or not os.path.exists(doc.file.path):
            print(f"    ❌ Fichier manquant!")
            doc.upload_status = 'failed'
            doc.error_message = 'Fichier physique introuvable'
            doc.save()
            continue
        
        # Réinitialiser le statut
        doc.upload_status = 'pending'
        doc.error_message = ''
        doc.processed_at = None
        doc.save()
        
        # Lancer la tâche de traitement
        try:
            # Essayer avec Celery
            task = process_document_async.delay(doc.id)
            doc.celery_task_id = task.id
            doc.save(update_fields=['celery_task_id'])
            print(f"    ✅ Tâche Celery lancée: {task.id}")
        except Exception as e:
            print(f"    ⚠️ Celery non disponible, traitement synchrone...")
            
            # Traitement synchrone
            try:
                sys.path.append(os.path.join(settings.BASE_DIR, 'scripts'))
                from vectorize_single_document import DocumentVectorizer
                
                vectorizer = DocumentVectorizer()
                success = vectorizer.process_document(doc.id)
                
                if success:
                    print(f"    ✅ Document indexé avec succès")
                else:
                    print(f"    ❌ Échec de l'indexation")
            except Exception as ve:
                print(f"    ❌ Erreur: {ve}")
                doc.upload_status = 'failed'
                doc.error_message = str(ve)
                doc.save()
    
    # 4. Résumé
    print(f"\n📊 RÉSUMÉ:")
    documents_after = DocumentUpload.objects.filter(patient=patient)
    for status in ['pending', 'processing', 'indexed', 'failed']:
        count = documents_after.filter(upload_status=status).count()
        if count > 0:
            print(f"  - {status}: {count}")

def main():
    print("=== RÉ-INDEXATION DES DOCUMENTS ===\n")
    
    print("Options:")
    print("1. Ré-indexer par ID patient")
    print("2. Ré-indexer par numéro de téléphone")
    print("3. Ré-indexer le dernier patient actif")
    
    choice = input("\nVotre choix (1-3): ")
    
    patient = None
    
    if choice == "1":
        patient_id = input("ID du patient: ")
        try:
            patient = Patient.objects.get(id=int(patient_id))
        except Patient.DoesNotExist:
            print(f"❌ Patient avec ID {patient_id} non trouvé")
            return
    
    elif choice == "2":
        phone = input("Numéro de téléphone: ")
        normalized = normalize_phone_number(phone)
        
        # Recherche flexible
        for p in Patient.objects.all():
            if normalized in normalize_phone_number(p.phone) or normalize_phone_number(p.phone) in normalized:
                patient = p
                break
        
        if not patient:
            print(f"❌ Aucun patient trouvé pour le numéro {phone}")
            return
    
    else:
        patient = Patient.objects.filter(is_active=True).order_by('-activated_at').first()
        if not patient:
            print("❌ Aucun patient actif trouvé")
            return
    
    print(f"\n👤 Patient sélectionné: {patient.full_name()} ({patient.phone})")
    
    # Demander confirmation
    response = input("\n⚠️ Cette action va ré-indexer tous les documents. Continuer ? (oui/non): ")
    
    if response.lower() in ['oui', 'o', 'yes', 'y']:
        reindex_patient_documents(patient)
        print("\n✅ Ré-indexation terminée!")
    else:
        print("\n❌ Ré-indexation annulée.")

if __name__ == "__main__":
    main()