#!/usr/bin/env python3
"""
Script de test du pipeline complet MediRecord
"""
import os
import sys
import time
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mediServe.settings')
django.setup()

from django.conf import settings
from patients.models import Patient
from documents.models import DocumentUpload
from documents.tasks import process_document_async
from rag.views import RAGQueryView
from celery.result import AsyncResult
import requests

def test_patient_creation():
    """Test 1: Création d'un patient"""
    print("\n🧪 TEST 1: Création d'un patient")
    
    # Créer un patient de test
    patient_data = {
        'first_name': 'Test',
        'last_name': 'Patient',
        'phone': '+221771234567',
        'email': 'test@example.com',
        'gender': 'M'
    }
    
    try:
        patient = Patient.objects.create(**patient_data)
        print(f"✅ Patient créé: {patient.full_name()} (ID: {patient.id})")
        return patient
    except Exception as e:
        print(f"❌ Erreur création patient: {e}")
        return None

def test_document_upload(patient):
    """Test 2: Upload de document"""
    print("\n🧪 TEST 2: Upload de document")
    
    # Créer un fichier de test
    test_file_path = os.path.join(settings.MEDIA_ROOT, 'test_document.pdf')
    
    # Créer un PDF simple (vous devrez avoir un PDF de test)
    if not os.path.exists(test_file_path):
        print("⚠️  Créez un fichier test_document.pdf dans le dossier media/")
        return None
    
    try:
        doc = DocumentUpload.objects.create(
            patient=patient,
            file='test_document.pdf',
            original_filename='test_document.pdf',
            file_type='pdf',
            file_size=os.path.getsize(test_file_path)
        )
        print(f"✅ Document créé: {doc.original_filename} (ID: {doc.id})")
        return doc
    except Exception as e:
        print(f"❌ Erreur upload document: {e}")
        return None

def test_celery_task(doc):
    """Test 3: Tâche Celery"""
    print("\n🧪 TEST 3: Traitement Celery")
    
    try:
        # Lancer la tâche
        task = process_document_async.delay(doc.id)
        print(f"📋 Tâche lancée: {task.id}")
        
        # Attendre et vérifier le statut
        for i in range(30):  # 30 secondes max
            result = AsyncResult(task.id)
            print(f"⏳ Status: {result.status} ({i+1}/30)")
            
            if result.ready():
                if result.successful():
                    print(f"✅ Tâche terminée avec succès!")
                    return True
                else:
                    print(f"❌ Tâche échouée: {result.info}")
                    return False
            
            time.sleep(1)
        
        print("⏱️  Timeout - la tâche prend trop de temps")
        return False
        
    except Exception as e:
        print(f"❌ Erreur Celery: {e}")
        return False

def test_vector_store(patient):
    """Test 4: Vérification du vector store"""
    print("\n🧪 TEST 4: Vérification du vector store")
    
    vector_path = os.path.join(settings.MEDIA_ROOT, 'vectors', f'patient_{patient.id}.h5')
    faiss_path = os.path.join(settings.MEDIA_ROOT, 'vectors', f'patient_{patient.id}.h5.faiss')
    
    if os.path.exists(vector_path):
        print(f"✅ Fichier HDF5 trouvé: {vector_path}")
        print(f"   Taille: {os.path.getsize(vector_path) / 1024:.2f} KB")
    else:
        print(f"❌ Fichier HDF5 non trouvé: {vector_path}")
        return False
    
    if os.path.exists(faiss_path):
        print(f"✅ Index FAISS trouvé: {faiss_path}")
        print(f"   Taille: {os.path.getsize(faiss_path) / 1024:.2f} KB")
    else:
        print(f"❌ Index FAISS non trouvé: {faiss_path}")
        return False
    
    return True

def test_rag_query(patient):
    """Test 5: Requête RAG"""
    print("\n🧪 TEST 5: Test requête RAG")
    
    # Simuler une requête RAG
    query_data = {
        'patient_phone': patient.phone,
        'query': 'Quel est le contenu de mes documents médicaux?',
        'session_id': f'test_session_{patient.id}'
    }
    
    try:
        # Appel API direct
        response = requests.post(
            'http://localhost:8000/api/rag/query/',
            json=query_data
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Réponse RAG reçue:")
            print(f"   Réponse: {data.get('response', '')[:100]}...")
            print(f"   Temps: {data.get('response_time_ms', 0)}ms")
            return True
        else:
            print(f"❌ Erreur API: {response.status_code}")
            print(f"   Réponse: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur requête RAG: {e}")
        return False

def test_whatsapp_activation(patient):
    """Test 6: Lien d'activation WhatsApp"""
    print("\n🧪 TEST 6: Lien d'activation WhatsApp")
    
    activation_url = f"{settings.SITE_PUBLIC_URL}/api/patients/activate/{patient.activation_token}/"
    print(f"🔗 Lien d'activation: {activation_url}")
    
    try:
        # Tester que le lien répond
        response = requests.get(activation_url, allow_redirects=False)
        
        if response.status_code in [301, 302]:
            print(f"✅ Redirection vers WhatsApp configurée")
            print(f"   Location: {response.headers.get('Location', 'N/A')}")
            return True
        else:
            print(f"❌ Status inattendu: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur test activation: {e}")
        return False

def cleanup(patient):
    """Nettoyer les données de test"""
    print("\n🧹 Nettoyage...")
    
    try:
        # Supprimer les fichiers vectoriels
        vector_files = [
            os.path.join(settings.MEDIA_ROOT, 'vectors', f'patient_{patient.id}.h5'),
            os.path.join(settings.MEDIA_ROOT, 'vectors', f'patient_{patient.id}.h5.faiss')
        ]
        
        for file in vector_files:
            if os.path.exists(file):
                os.remove(file)
                print(f"   Supprimé: {file}")
        
        # Supprimer le patient (cascade sur les documents)
        patient.delete()
        print("✅ Nettoyage terminé")
        
    except Exception as e:
        print(f"⚠️  Erreur nettoyage: {e}")

def main():
    """Exécuter tous les tests"""
    print("🚀 TEST DU PIPELINE MEDIRECORD")
    print("=" * 50)
    
    # Vérifications préliminaires
    print("\n📋 Vérifications préliminaires:")
    
    # Redis
    try:
        import redis
        r = redis.Redis()
        r.ping()
        print("✅ Redis: OK")
    except:
        print("❌ Redis: Non disponible")
        print("   Lancez: redis-server")
        return
    
    # Celery
    try:
        from mediServe.celery import app
        i = app.control.inspect()
        stats = i.stats()
        if stats:
            print("✅ Celery: OK")
        else:
            print("❌ Celery: Aucun worker actif")
            print("   Lancez: celery -A mediServe worker -l info")
            return
    except:
        print("❌ Celery: Erreur")
        return
    
    # Tests
    patient = test_patient_creation()
    if not patient:
        return
    
    doc = test_document_upload(patient)
    if not doc:
        cleanup(patient)
        return
    
    if test_celery_task(doc):
        time.sleep(2)  # Attendre que les fichiers soient écrits
        
        if test_vector_store(patient):
            test_rag_query(patient)
    
    test_whatsapp_activation(patient)
    
    # Nettoyage optionnel
    response = input("\n🗑️  Supprimer les données de test? (o/N): ")
    if response.lower() == 'o':
        cleanup(patient)
    
    print("\n✅ Tests terminés!")

if __name__ == "__main__":
    main()