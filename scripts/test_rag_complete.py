# scripts/test_rag_complete.py
# Test complet du système RAG avant utilisation en production

import os
import sys
import django
import time

script_dir = os.path.dirname(os.path.abspath(__file__))
# Aller deux niveaux plus haut pour atteindre le répertoire racine du projet Django
# (Exemple: si script est dans /project_root/scripts/, cela renvoie /project_root/)
project_root = os.path.join(script_dir, '..', '') # Ajout d'un '/' final pour s'assurer que c'est un chemin de répertoire
sys.path.insert(0, os.path.abspath(project_root))


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mediServe.settings')
django.setup()

from django.conf import settings
sys.path.append(os.path.join(settings.BASE_DIR, 'scripts'))

from patients.models import Patient
from documents.models import DocumentUpload
from rag.your_rag_module import (
    VectorStoreHDF5, EmbeddingGenerator, 
    HybridRetriever, GeminiLLM, RAG
)

def test_rag_for_all_patients():
    """Test le RAG pour tous les patients actifs"""
    
    print("\n" + "="*80)
    print("🧪 TEST COMPLET DU SYSTÈME RAG")
    print("="*80)
    
    # Récupérer tous les patients actifs avec documents
    patients = Patient.objects.filter(
        is_active=True,
        uploaded_documents__upload_status='indexed'
    ).distinct()
    
    if not patients.exists():
        print("❌ Aucun patient actif avec documents indexés trouvé.")
        print("\nActivez d'abord un patient avec :")
        print("python scripts/activate_patient.py --id 1")
        return
    
    print(f"\n📊 {patients.count()} patient(s) actif(s) trouvé(s)")
    
    # Questions de test variées
    test_questions = [
        "Bonjour, comment allez-vous ?",
        "Quels sont mes documents médicaux ?",
        "Résume mon dernier rapport médical",
        "Quels médicaments je prends actuellement ?",
        "Quels sont mes derniers résultats d'analyses ?",
        "Y a-t-il des anomalies dans mes examens ?",
    ]
    
    # Tester pour chaque patient
    for patient in patients:
        print(f"\n{'='*60}")
        print(f"👤 Patient: {patient.full_name()} (ID: {patient.id})")
        print(f"📱 Téléphone: {patient.phone}")
        
        # Vérifier les documents
        docs = DocumentUpload.objects.filter(patient=patient, upload_status='indexed')
        print(f"📄 Documents indexés: {docs.count()}")
        for doc in docs[:3]:
            print(f"   • {doc.original_filename}")
        
        # Vérifier l'existence des fichiers RAG
        vector_dir = os.path.join(settings.MEDIA_ROOT, 'vectors', f'patient_{patient.id}')
        hdf5_path = os.path.join(vector_dir, 'vector_store.h5')
        bm25_dir = os.path.join(settings.MEDIA_ROOT, 'indexes', f'patient_{patient.id}_bm25')
        
        print(f"\n🔍 Vérification des fichiers:")
        print(f"   HDF5: {'✅' if os.path.exists(hdf5_path) else '❌'} {hdf5_path}")
        print(f"   BM25: {'✅' if os.path.exists(bm25_dir) else '❌'} {bm25_dir}")
        
        if not os.path.exists(hdf5_path):
            print("   ⚠️  Pas de vector store, passage au patient suivant")
            continue
        
        try:
            # Initialiser le RAG
            print("\n⚙️  Initialisation du RAG...")
            start_init = time.time()
            
            # 1. Charger le vector store
            vector_store = VectorStoreHDF5(hdf5_path)
            vector_store.load_store()
            print(f"   ✅ Vector store chargé ({len(vector_store.meta)} chunks)")
            
            # 2. Embedder
            embedder = EmbeddingGenerator()
            print(f"   ✅ Embedder initialisé")
            
            # 3. Retriever
            if os.path.exists(bm25_dir):
                retriever = HybridRetriever(vector_store, embedder, bm25_dir)
                if settings.RAG_SETTINGS.get('USE_RERANKING', True):
                    retriever.enable_reranking('cross-encoder/ms-marco-MiniLM-L-6-v2')
                print(f"   ✅ Retriever hybride avec reranking")
            else:
                retriever = HybridRetriever(vector_store, embedder)
                print(f"   ✅ Retriever dense uniquement")
            
            # 4. LLM
            llm = GeminiLLM()
            print(f"   ✅ LLM Gemini initialisé")
            
            # 5. RAG
            rag = RAG(retriever, llm)
            init_time = time.time() - start_init
            print(f"   ✅ RAG prêt en {init_time:.2f}s")
            
            # Tester quelques questions
            print(f"\n💬 Test de questions:")
            for i, question in enumerate(test_questions[:3], 1):
                print(f"\n   Question {i}: {question}")
                
                try:
                    start_query = time.time()
                    response = rag.answer(question, top_k=3)
                    query_time = time.time() - start_query
                    
                    # Afficher la réponse (tronquée)
                    print(f"   Réponse ({query_time:.2f}s): {response[:150]}...")
                    
                except Exception as e:
                    print(f"   ❌ Erreur: {e}")
            
        except Exception as e:
            print(f"\n❌ Erreur initialisation RAG: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*80)
    print("✅ TEST TERMINÉ")
    print("="*80)


def test_specific_patient(patient_id, question=None):
    """Test le RAG pour un patient spécifique avec une question"""
    try:
        patient = Patient.objects.get(id=patient_id, is_active=True)
        print(f"\n👤 Test pour: {patient.full_name()}")
        
        # Si pas de question fournie, utiliser une question par défaut
        if not question:
            question = "Quels sont mes documents médicaux disponibles ?"
        
        print(f"❓ Question: {question}")
        
        # Chemins
        vector_dir = os.path.join(settings.MEDIA_ROOT, 'vectors', f'patient_{patient.id}')
        hdf5_path = os.path.join(vector_dir, 'vector_store.h5')
        bm25_dir = os.path.join(settings.MEDIA_ROOT, 'indexes', f'patient_{patient.id}_bm25')
        
        if not os.path.exists(hdf5_path):
            print("❌ Pas de vector store pour ce patient")
            return
        
        # Initialiser et tester
        vector_store = VectorStoreHDF5(hdf5_path)
        vector_store.load_store()
        
        embedder = EmbeddingGenerator()
        
        if os.path.exists(bm25_dir):
            retriever = HybridRetriever(vector_store, embedder, bm25_dir)
        else:
            retriever = HybridRetriever(vector_store, embedder)
        
        llm = GeminiLLM()
        rag = RAG(retriever, llm)
        
        # Poser la question
        start = time.time()
        response = rag.answer(question)
        duration = time.time() - start
        
        print(f"\n📝 Réponse ({duration:.2f}s):")
        print("-" * 60)
        print(response)
        print("-" * 60)
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--patient-id', type=int, help='Tester un patient spécifique')
    parser.add_argument('--question', help='Question à poser')
    parser.add_argument('--all', action='store_true', help='Tester tous les patients')
    
    args = parser.parse_args()
    
    if args.patient_id:
        test_specific_patient(args.patient_id, args.question)
    else:
        test_rag_for_all_patients()