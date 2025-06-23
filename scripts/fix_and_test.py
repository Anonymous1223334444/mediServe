#!/usr/bin/env python3
"""
Script de correction rapide pour résoudre les problèmes de chemin
et tester le système
"""
import os
import sys
import subprocess

def setup_environment():
    """Configurer l'environnement Python correctement"""
    # Trouver la racine du projet
    current_file = os.path.abspath(__file__)
    current_dir = os.path.dirname(current_file)
    
    # Si on est dans scripts/, remonter d'un niveau
    if os.path.basename(current_dir) == 'scripts':
        project_root = os.path.dirname(current_dir)
    else:
        project_root = current_dir
    
    # Vérifier qu'on est au bon endroit
    manage_py = os.path.join(project_root, 'manage.py')
    if not os.path.exists(manage_py):
        print(f"❌ Erreur: manage.py non trouvé dans {project_root}")
        print("   Exécutez ce script depuis la racine du projet ou le dossier scripts/")
        sys.exit(1)
    
    # Configurer le PYTHONPATH
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Configurer Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mediServe.settings')
    
    print(f"✅ Environnement configuré")
    print(f"   Racine du projet: {project_root}")
    print(f"   PYTHONPATH: {sys.path[0]}")
    
    return project_root

def check_redis():
    """Vérifier si Redis est actif"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✅ Redis est actif")
        return True
    except:
        print("❌ Redis n'est pas actif!")
        print("\n📋 Pour démarrer Redis:")
        print("   sudo systemctl start redis")
        print("   # ou")
        print("   redis-server")
        return False

def test_celery_import():
    """Tester l'import de Celery et des tâches"""
    try:
        import django
        django.setup()
        
        from documents.tasks import process_document_async
        from celery import current_app
        
        print("✅ Import des tâches réussi")
        
        # Lister les tâches
        tasks = [t for t in current_app.tasks if 'documents' in t]
        print(f"📋 Tâches documents trouvées: {len(tasks)}")
        for task in tasks:
            print(f"   - {task}")
        
        return True
    except Exception as e:
        print(f"❌ Erreur import: {e}")
        return False

def test_direct_vectorization(doc_id):
    """Tester la vectorisation directe"""
    try:
        import django
        django.setup()
        
        from documents.models import DocumentUpload
        from scripts.vectorize_single_document import DocumentVectorizer
        
        # Vérifier que le document existe
        doc = DocumentUpload.objects.get(id=doc_id)
        print(f"✅ Document trouvé: {doc.original_filename}")
        
        # Tester la vectorisation
        vectorizer = DocumentVectorizer()
        success = vectorizer.process_document(doc_id)
        
        if success:
            print("✅ Vectorisation réussie!")
        else:
            print("❌ Vectorisation échouée")
            
        return success
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def find_pending_documents():
    """Trouver des documents en attente"""
    try:
        import django
        django.setup()
        
        from documents.models import DocumentUpload
        
        pending = DocumentUpload.objects.filter(upload_status='pending')
        failed = DocumentUpload.objects.filter(upload_status='failed')
        
        print(f"\n📄 Documents trouvés:")
        print(f"   En attente: {pending.count()}")
        print(f"   Échoués: {failed.count()}")
        
        if pending.exists():
            print("\n📋 Documents en attente:")
            for doc in pending[:5]:
                print(f"   ID {doc.id}: {doc.original_filename} (Patient: {doc.patient.full_name()})")
            return pending.first().id
        elif failed.exists():
            print("\n📋 Documents échoués:")
            for doc in failed[:5]:
                print(f"   ID {doc.id}: {doc.original_filename} - {doc.error_message[:50]}...")
            return failed.first().id
        else:
            print("\n⚠️  Aucun document à traiter")
            return None
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None

def main():
    print("🔧 === CORRECTION ET TEST RAPIDE ===\n")
    
    # 1. Configurer l'environnement
    project_root = setup_environment()
    
    # 2. Vérifier Redis
    redis_ok = check_redis()
    
    # 3. Tester les imports
    print("\n📦 Test des imports...")
    imports_ok = test_celery_import()
    
    if not redis_ok or not imports_ok:
        print("\n❌ Corrections nécessaires avant de continuer")
        return
    
    # 4. Trouver un document à tester
    doc_id = find_pending_documents()
    
    if doc_id:
        print(f"\n🧪 Test de vectorisation sur le document {doc_id}...")
        
        # Demander confirmation
        response = input("\nVoulez-vous tester la vectorisation? (y/n): ")
        if response.lower() == 'y':
            test_direct_vectorization(doc_id)
    
    print("\n📋 Commandes utiles:")
    print(f"   cd {project_root}")
    print("   python scripts/check_redis.py")
    print("   python scripts/test_celery_vectorization.py celery")
    if doc_id:
        print(f"   python scripts/test_celery_vectorization.py direct {doc_id}")

if __name__ == "__main__":
    main()