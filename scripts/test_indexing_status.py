#!/usr/bin/env python3
"""
Script pour tester l'endpoint d'indexation status
"""
import os
import sys
import time
import requests

# Configuration
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mediServe.settings')
import django
django.setup()

from patients.models import Patient
from documents.models import DocumentUpload

def test_indexing_endpoint(patient_id):
    """Tester l'endpoint d'indexation status"""
    base_url = "http://localhost:8000"
    url = f"{base_url}/api/patients/{patient_id}/indexing-status/"
    
    print(f"🔍 Test de l'endpoint: {url}")
    
    try:
        response = requests.get(url)
        print(f"📡 Status code: {response.status_code}")
        
        if response.ok:
            data = response.json()
            print("\n✅ Réponse reçue:")
            print(f"   Patient: {data.get('patient_name')}")
            print(f"   Total documents: {data.get('total_documents')}")
            print(f"   Indexés: {data.get('indexed')}")
            print(f"   En cours: {data.get('processing')}")
            print(f"   Échoués: {data.get('failed')}")
            print(f"   En attente: {data.get('pending')}")
            print(f"   Progression: {data.get('progress')}%")
            print(f"   Terminé: {data.get('is_complete')}")
            
            if 'documents' in data:
                print(f"\n📄 Documents ({len(data['documents'])}):")
                for doc in data['documents'][:5]:  # Afficher max 5 documents
                    print(f"   - {doc.get('filename')} [{doc.get('status')}]")
                    if doc.get('error'):
                        print(f"     Erreur: {doc['error']}")
            
            return data
        else:
            print(f"❌ Erreur API: {response.status_code}")
            print(f"   Réponse: {response.text}")
            
    except Exception as e:
        print(f"❌ Erreur: {e}")

def test_with_mock_data():
    """Créer des données de test et tester l'endpoint"""
    print("\n🧪 Test avec données mockées...")
    
    try:
        # Trouver ou créer un patient de test
        patient = Patient.objects.filter(first_name="Test").first()
        if not patient:
            print("Création d'un patient de test...")
            patient = Patient.objects.create(
                first_name="Test",
                last_name="Patient",
                phone="+221771234567"
            )
            print(f"✅ Patient créé: ID={patient.id}")
        else:
            print(f"✅ Patient existant: ID={patient.id}")
        
        # Vérifier les documents
        docs = DocumentUpload.objects.filter(patient=patient)
        print(f"📄 Documents existants: {docs.count()}")
        
        if docs.count() == 0:
            print("⚠️  Aucun document trouvé. Créez des documents pour ce patient.")
        else:
            # Afficher le statut de chaque document
            for doc in docs[:5]:
                print(f"   - {doc.original_filename}: {doc.upload_status}")
        
        # Tester l'endpoint
        return test_indexing_endpoint(patient.id)
        
    except Exception as e:
        print(f"❌ Erreur: {e}")

def monitor_indexing(patient_id, duration=30):
    """Monitorer l'indexation pendant une durée donnée"""
    print(f"\n📊 Monitoring de l'indexation pour {duration} secondes...")
    
    start_time = time.time()
    iteration = 0
    
    while time.time() - start_time < duration:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---")
        
        data = test_indexing_endpoint(patient_id)
        
        if data and data.get('is_complete'):
            print("\n✅ Indexation terminée!")
            break
        
        time.sleep(3)  # Attendre 3 secondes entre chaque check
    
    print("\n📊 Fin du monitoring")

def main():
    """Point d'entrée principal"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_indexing_status.py <patient_id>")
        print("  python test_indexing_status.py test")
        print("  python test_indexing_status.py monitor <patient_id>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "test":
        test_with_mock_data()
    elif command == "monitor" and len(sys.argv) > 2:
        patient_id = int(sys.argv[2])
        monitor_indexing(patient_id)
    else:
        try:
            patient_id = int(command)
            test_indexing_endpoint(patient_id)
        except ValueError:
            print("❌ ID patient invalide")
            sys.exit(1)

if __name__ == "__main__":
    main()