import os
import django

# Configurez l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mediServe.settings')
django.setup()

from patients.n8n_manager import N8NWorkflowManager

def test_discover_api():
    """Test la découverte des API n8n disponibles"""
    # Remplacez par un ID de workflow existant dans votre instance n8n
    workflow_id = "7156xvL7XECFhBTm"  # Utilisez l'ID du dernier workflow créé
    
    manager = N8NWorkflowManager()
    manager.discover_workflow_execution_api(workflow_id)
    
    print("Test terminé!")

if __name__ == "__main__":
    test_discover_api()