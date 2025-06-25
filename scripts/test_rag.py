# scripts/test_rag.py
# Tester le RAG directement sans passer par WhatsApp

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
import requests

def test_rag_for_patient(patient_id=None, phone=None):
    """Test le RAG pour un patient spécifique"""
    
    # Trouver le patient
    if patient_id:
        patient = Patient.objects.get(id=patient_id)
    elif phone:
        patient = Patient.objects.get(phone=phone)
    else:
        # Prendre le premier patient actif avec des documents
        patient = Patient.objects.filter(
            is_active=True,
            uploaded_documents__upload_status='indexed'
        ).distinct().first()
    
    if not patient:
        print("❌ Aucun patient actif avec documents trouvé")
        return
    
    print(f"\n🧪 TEST RAG pour : {patient.full_name()} ({patient.phone})")
    print(f"   ID: {patient.id}")
    print(f"   Actif: {'Oui' if patient.is_active else 'Non'}")
    
    # Vérifier les documents
    docs = DocumentUpload.objects.filter(patient=patient, upload_status='indexed')
    print(f"   Documents indexés: {docs.count()}")
    for doc in docs:
        print(f"      📄 {doc.original_filename}")
    
    # Questions de test
    test_questions = [
        "Quels sont mes documents médicaux ?",
        "Résume mon dernier rapport",
        "Quels médicaments je prends ?",
    ]
    
    print("\n🔍 Test des questions RAG :")
    print("-" * 60)
    
    for question in test_questions:
        print(f"\n❓ Question: {question}")
        
        try:
            # Appeler l'API RAG
            response = requests.post(
                'http://localhost:8000/api/rag/query/',
                json={
                    'patient_phone': patient.phone,
                    'query': question,
                    'session_id': f'test_{patient.id}'
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get('response', 'Pas de réponse')
                print(f"✅ Réponse: {answer[:200]}...")
            else:
                print(f"❌ Erreur {response.status_code}: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print("❌ Impossible de se connecter à l'API RAG. Django est-il lancé ?")
        except requests.exceptions.Timeout:
            print("❌ Timeout - le RAG met trop de temps à répondre")
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--patient-id', type=int, help='ID du patient')
    parser.add_argument('--phone', help='Numéro de téléphone du patient')
    
    args = parser.parse_args()
    test_rag_for_patient(patient_id=args.patient_id, phone=args.phone)