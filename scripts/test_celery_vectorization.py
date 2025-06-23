#!/usr/bin/env python3
"""
Script de test pour vérifier le système de vectorisation
"""
import os
import sys

# Ajouter le répertoire parent au PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mediServe.settings')

# Importer Django après avoir configuré le chemin
import django
django.setup()

from django.conf import settings
from documents.models import DocumentUpload
from patients.models import Patient
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_direct_vectorization(document_id):
    """Test de vectorisation directe sans Celery"""
    logger.info(f"=== TEST VECTORISATION DIRECTE - Document ID: {document_id} ===")
    
    try:
        # 1. Vérifier que le document existe
        doc = DocumentUpload.objects.get(id=document_id)
        logger.info(f"✅ Document trouvé: {doc.original_filename}")
        logger.info(f"   Patient: {doc.patient.full_name()}")
        logger.info(f"   Chemin: {doc.file.path}")
        logger.info(f"   Statut: {doc.upload_status}")
        
        # 2. Vérifier que le fichier existe
        if os.path.exists(doc.file.path):
            logger.info(f"✅ Fichier physique existe")
            file_size = os.path.getsize(doc.file.path)
            logger.info(f"   Taille: {file_size} bytes")
        else:
            logger.error(f"❌ Fichier physique introuvable!")
            return False
        
        # 3. Tester l'import du script de vectorisation
        logger.info("Test import vectorize_single_document...")
        sys.path.insert(0, os.path.join(settings.BASE_DIR, 'scripts'))
        from vectorize_single_document import DocumentVectorizer
        logger.info("✅ Import réussi")
        
        # 4. Tester la vectorisation
        logger.info("Création du vectorizer...")
        vectorizer = DocumentVectorizer()
        
        logger.info("Lancement de la vectorisation...")
        success = vectorizer.process_document(document_id)
        
        if success:
            logger.info("✅ VECTORISATION RÉUSSIE!")
            # Recharger le document pour voir les changements
            doc.refresh_from_db()
            logger.info(f"   Nouveau statut: {doc.upload_status}")
        else:
            logger.error("❌ VECTORISATION ÉCHOUÉE!")
            doc.refresh_from_db()
            logger.error(f"   Erreur: {doc.error_message}")
            
        return success
        
    except DocumentUpload.DoesNotExist:
        logger.error(f"❌ Document {document_id} non trouvé")
        return False
    except Exception as e:
        logger.error(f"❌ Erreur: {type(e).__name__}: {str(e)}")
        logger.error("Traceback:", exc_info=True)
        return False

def test_celery_connection():
    """Test de la connexion Celery"""
    logger.info("=== TEST CONNEXION CELERY ===")
    
    try:
        from kombu import Connection
        broker_url = settings.CELERY_BROKER_URL
        logger.info(f"Broker URL: {broker_url}")
        
        with Connection(broker_url) as conn:
            conn.ensure_connection(max_retries=3, timeout=5)
            logger.info("✅ Connexion au broker réussie")
            
        # Tester l'import des tâches
        from documents.tasks import process_document_async
        logger.info("✅ Import des tâches réussi")
        
        # Tester l'envoi d'une tâche simple
        from mediServe.celery import debug_task
        result = debug_task.delay()
        logger.info(f"✅ Tâche de test envoyée: {result.id}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur Celery: {type(e).__name__}: {str(e)}")
        return False

def test_celery_task(document_id):
    """Test de la tâche Celery de vectorisation"""
    logger.info(f"=== TEST TÂCHE CELERY - Document ID: {document_id} ===")
    
    try:
        from documents.tasks import process_document_async
        
        # Réinitialiser le statut du document
        doc = DocumentUpload.objects.get(id=document_id)
        doc.upload_status = 'pending'
        doc.error_message = ''
        doc.save()
        logger.info("Document réinitialisé à 'pending'")
        
        # Envoyer la tâche
        result = process_document_async.delay(document_id)
        logger.info(f"✅ Tâche envoyée: {result.id}")
        
        # Attendre un peu et vérifier
        import time
        logger.info("Attente 5 secondes...")
        time.sleep(5)
        
        # Vérifier le statut
        doc.refresh_from_db()
        logger.info(f"Statut après 5s: {doc.upload_status}")
        
        # Vérifier le résultat Celery
        if hasattr(result, 'state'):
            logger.info(f"État Celery: {result.state}")
            if hasattr(result, 'info'):
                logger.info(f"Info Celery: {result.info}")
                
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur: {type(e).__name__}: {str(e)}")
        return False

def main():
    """Point d'entrée principal"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_celery_vectorization.py celery        # Tester la connexion Celery")
        print("  python test_celery_vectorization.py direct <doc_id>  # Tester vectorisation directe")
        print("  python test_celery_vectorization.py task <doc_id>    # Tester tâche Celery")
        print("  python test_celery_vectorization.py all <doc_id>     # Tout tester")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "celery":
        test_celery_connection()
    elif command == "direct" and len(sys.argv) > 2:
        doc_id = int(sys.argv[2])
        test_direct_vectorization(doc_id)
    elif command == "task" and len(sys.argv) > 2:
        doc_id = int(sys.argv[2])
        test_celery_task(doc_id)
    elif command == "all" and len(sys.argv) > 2:
        doc_id = int(sys.argv[2])
        logger.info("=== TESTS COMPLETS ===")
        test_celery_connection()
        logger.info("")
        test_direct_vectorization(doc_id)
        logger.info("")
        test_celery_task(doc_id)
    else:
        print("Commande invalide")
        sys.exit(1)

if __name__ == "__main__":
    main()