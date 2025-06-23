#!/usr/bin/env python3
"""
Script pour créer un patient de test avec documents via l'API
"""
import os
import sys
import json
import requests
from datetime import datetime

def create_test_pdf(filename="test_document.pdf"):
    """Créer un PDF de test simple"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        c = canvas.Canvas(filename, pagesize=letter)
        c.drawString(100, 750, "Document Medical de Test")
        c.drawString(100, 700, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        c.drawString(100, 650, "Patient: Test Patient")
        c.drawString(100, 600, "Diagnostic: Test médical de routine")
        c.drawString(100, 550, "Traitement: Paracétamol 500mg, 3 fois par jour")
        c.save()
        
        print(f"✅ PDF de test créé: {filename}")
        return filename
    except ImportError:
        print("⚠️  reportlab non installé. Utilisation d'un fichier texte à la place.")
        with open("test_document.txt", "w") as f:
            f.write("Document médical de test\n")
            f.write(f"Date: {datetime.now()}\n")
            f.write("Patient: Test Patient\n")
            f.write("Diagnostic: Test médical\n")
        return "test_document.txt"

def create_test_patient(base_url="http://localhost:8000", with_documents=True):
    """Créer un patient de test via l'API"""
    
    # Données du patient
    patient_data = {
        "first_name": "Test",
        "last_name": f"Patient_{datetime.now().strftime('%H%M%S')}",
        "phone": f"+22177{datetime.now().strftime('%H%M%S')}",
        "email": f"test_{datetime.now().strftime('%H%M%S')}@example.com",
        "date_of_birth": "1990-01-01",
        "gender": "male",
        "address": "123 Rue de Test, Dakar",
        "medical_history": "Antécédents de test pour vérification du système",
        "allergies": "Aucune allergie connue",
        "current_medications": "Paracétamol 500mg"
    }
    
    print("📋 Création d'un patient de test...")
    print(f"   Nom: {patient_data['first_name']} {patient_data['last_name']}")
    print(f"   Téléphone: {patient_data['phone']}")
    
    # Préparer la requête
    url = f"{base_url}/api/patients/"
    files = []
    
    if with_documents:
        # Créer des documents de test
        doc1 = create_test_pdf("ordonnance_test.pdf")
        doc2 = create_test_pdf("analyse_test.pdf")
        
        files = [
            ('documents', (doc1, open(doc1, 'rb'), 'application/pdf')),
            ('documents', (doc2, open(doc2, 'rb'), 'application/pdf'))
        ]
        print(f"📄 Ajout de {len(files)} documents")
    
    try:
        # Envoyer la requête
        print(f"\n🚀 Envoi vers {url}...")
        
        if files:
            response = requests.post(url, data=patient_data, files=files)
            # Fermer les fichiers
            for _, (_, f, _) in files:
                f.close()
        else:
            response = requests.post(url, data=patient_data)
        
        print(f"📡 Status code: {response.status_code}")
        
        if response.ok:
            data = response.json()
            print("\n✅ Patient créé avec succès!")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            print(f"\n🔍 Informations importantes:")
            print(f"   Patient ID: {data.get('patient_id')}")
            print(f"   Nom complet: {data.get('first_name')} {data.get('last_name')}")
            
            if data.get('documents'):
                print(f"   Documents: {len(data['documents'])} uploadés")
                for doc in data['documents']:
                    print(f"     - {doc.get('filename')} [{doc.get('status')}]")
            
            print(f"\n📊 URL de suivi:")
            print(f"   {base_url}/api/patients/{data.get('patient_id')}/indexing-status/")
            
            return data
        else:
            print(f"\n❌ Erreur: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
    finally:
        # Nettoyer les fichiers de test
        for f in ["ordonnance_test.pdf", "analyse_test.pdf", "test_document.txt", "test_document.pdf"]:
            if os.path.exists(f):
                os.remove(f)

def main():
    """Point d'entrée principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Créer un patient de test")
    parser.add_argument("--url", default="http://localhost:8000", help="URL de base de l'API")
    parser.add_argument("--no-docs", action="store_true", help="Créer sans documents")
    parser.add_argument("--monitor", action="store_true", help="Monitorer l'indexation après création")
    
    args = parser.parse_args()
    
    # Créer le patient
    result = create_test_patient(args.url, not args.no_docs)
    
    # Monitorer si demandé
    if result and args.monitor and result.get('patient_id'):
        print("\n📊 Monitoring de l'indexation...")
        os.system(f"python scripts/test_indexing_status.py monitor {result['patient_id']}")

if __name__ == "__main__":
    main()