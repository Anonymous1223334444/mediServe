# patients/n8n_manager.py

import os
import json
import random
import requests
from typing import Dict, Any, Optional
from django.conf import settings
import time # Import time for retries
import urllib.parse # Import urllib.parse for URL encoding (used carefully)

names = ["Andre", "Benoit", "Céline", "David", "Elodie", "François", "Géraldine", "Hugo", "Isabelle", "Julien"]

class N8NWorkflowManager:
    def __init__(self,
                 base_url: Optional[str] = None,
                 api_key: Optional[str] = None):
        """
        Initialise le manager n8n.
        On récupère settings.N8N_BASE_URL (ex. "http://localhost:5678/rest")
        et settings.N8N_API_KEY si besoin d'authentification.
        """
        self.base_url = (base_url or settings.N8N_BASE_URL).rstrip('/')
        print(f"[DEBUG n8n_manager] base_url utilisée = {self.base_url}")
        self.api_key  = api_key or settings.N8N_API_KEY
        self.session = requests.Session()

        # Si on a une API Key, on l'ajoute dans l’en-tête
        if self.api_key:
            self.session.headers.update({
                'X-N8N-API-KEY': self.api_key,
                'Content-Type': 'application/json'
            })
        else:
            self.session.headers.update({
                'Content-Type': 'application/json'
            })

    def is_workflow_active(self, workflow_id: str) -> bool:
        """Check if a workflow is active and ready to receive webhooks"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/workflows/{workflow_id}"
            )
            # Raise HTTPError for bad responses (4xx or 5xx)
            response.raise_for_status()
            workflow_data = response.json()
            # n8n's API for getting a single workflow returns { "item": { ...workflow_data... } }
            # Or directly the workflow data depending on API version/endpoint
            # Let's try to handle both, prioritizing "item" key if present.
            active_status = workflow_data.get("item", {}).get("active", False) if "item" in workflow_data else workflow_data.get("active", False)
            return active_status
        except requests.exceptions.RequestException as e:
            print(f"❌ Échec de la vérification de l'état du workflow '{workflow_id}' : {e}")
            return False
        except Exception as e:
            print(f"❌ Erreur inattendue lors de la vérification de l'état du workflow : {e}")
            return False

    def debug_webhook_info(self, workflow_id: str) -> None:
        """
        Debug method to inspect webhook node information and URLs.
        """
        try:
            response = self.session.get(f"{self.base_url}/api/v1/workflows/{workflow_id}")
            response.raise_for_status()
            workflow_data = response.json()
            workflow_details = workflow_data.get("item", workflow_data)
            
            print(f"🔍 Debugging webhook info for workflow {workflow_id}")
            print(f"   Workflow active: {workflow_details.get('active', False)}")
            
            for node in workflow_details.get("nodes", []):
                if node.get("type") == "n8n-nodes-base.webhook":
                    print(f"\n📌 Webhook Node: {node.get('name')} (ID: {node.get('id')})")
                    print(f"   Parameters: {json.dumps(node.get('parameters', {}), indent=4)}")
                    print(f"   WebhookUrls: {json.dumps(node.get('webhookUrls', {}), indent=4)}")
                    
        except Exception as e:
            print(f"❌ Debug failed: {e}")

    def test_connection(self) -> bool:
        """Vérifie que l’instance n8n est joignable."""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/workflows")
            return response.status_code in [200, 401]
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection test failed: {e}")
            return False

    def create_workflow(self,
                        workflow_data: Dict[str, Any],
                        workflow_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Crée un nouveau workflow dans n8n.
        On n'envoie que : name, nodes, connections, settings (et staticData si présent).
        """
        if workflow_name is None:
            workflow_name = f"Patient Activation Workflow_{names[random.randint(0, len(names)-1)]}"

        payload: Dict[str, Any] = {
            "name": workflow_name,
            "nodes": workflow_data["nodes"],
            "connections": workflow_data["connections"],
            "settings": workflow_data.get("settings", {})
        }
        if "staticData" in workflow_data:
            payload["staticData"] = workflow_data["staticData"]

        try:
            print(f"🚀 Creating workflow in n8n: {workflow_name}")
            response = self.session.post(
                f"{self.base_url}/api/v1/workflows",
                json=payload
            )
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            if response.status_code in [200, 201]:
                wf_info = response.json()
                print("✅ Workflow created successfully!")
                print(f"   • ID:   {wf_info.get('id')}")
                print(f"   • Name: {wf_info.get('name')}")
                return wf_info
            else: # This block might be redundant due to raise_for_status, but kept for clarity
                print(f"❌ Failed to create workflow. Status: {response.status_code}")
                print(f"   › Response: {response.text}")
                return {"error": response.text, "status_code": response.status_code}
        except requests.exceptions.RequestException as e:
            print(f"❌ Request to create workflow failed: {e}")
            return {"error": str(e)}
        except Exception as e:
            print(f"❌ Erreur inattendue lors de la création du workflow : {e}")
            return {"error": str(e)}


    def activate_workflow(self, workflow_id: str) -> bool:
        """
        Active un workflow par son ID pour que le Webhook Trigger soit exposé.
        """
        try:
            # À partir de n8n v0.185+, on utilise /api/v1/workflows/{id}/activate
            response = self.session.post(
                f"{self.base_url}/api/v1/workflows/{workflow_id}/activate",
                json={"workflowId": workflow_id}
            )
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            print(f"✅ Workflow {workflow_id} activated successfully!")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to activate workflow {workflow_id}: {e}")
            return False
        except Exception as e:
            print(f"❌ Erreur inattendue lors de l'activation du workflow : {e}")
            return False

    def delete_workflow(self, workflow_id: str) -> bool:
        """
        Supprime un workflow n8n spécifique.
        """
        try:
            delete_url = f"{self.base_url}/api/v1/workflows/{workflow_id}"
            resp = self.session.delete(delete_url)
            resp.raise_for_status()
            print(f"Workflow {workflow_id} deleted successfully!")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Échec de la suppression du workflow '{workflow_id}' : {e}")
            return False
        except Exception as e:
            print(f"❌ Erreur inattendue lors de la suppression du workflow : {e}")
            return False

    def list_workflows(self) -> list:
        """Liste tous les workflows existants dans l’instance n8n."""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/workflows")
            if response.status_code == 200:
                data = response.json()
                workflows = data.get("data", data) if isinstance(data, dict) else data
                print(f"📋 Found {len(workflows)} workflows:")
                for wf in workflows:
                    if isinstance(wf, dict):
                        status = "🟢 Active" if wf.get("active") else "🔴 Inactive"
                        print(f"   • {wf.get('name','<no name>')} "
                              f"(ID: {wf.get('id')}) – {status}")
                    else:
                        print(f"   • {wf}")
                return workflows
            else:
                print(f"❌ Failed to list workflows. Status: {response.status_code}")
                print(f"   › Response: {response.text}")
                return []
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to list workflows: {e}")
            return []
        except Exception as e:
            print(f"❌ Unexpected error while listing workflows: {e}")
            return []

    def get_webhook_production_url(self, workflow_id: str, webhook_node_id: str) -> Optional[str]:
        try:
            # Fetch the full workflow definition
            response = self.session.get(f"{self.base_url}/api/v1/workflows/{workflow_id}")
            response.raise_for_status()
            workflow_data = response.json()
            workflow_details = workflow_data.get("item", workflow_data)

            for node in workflow_details.get("nodes", []):
                if node.get("id") == webhook_node_id and node.get("type") == "n8n-nodes-base.webhook":
                    
                    # Get the webhook path from parameters
                    parameters = node.get("parameters", {})
                    webhook_path = parameters.get("path", "")
                    
                    if webhook_path:
                        # Format correct pour n8n v1.93.0
                        n8n_public_base_url = self.base_url.rstrip('/')
                        if n8n_public_base_url.endswith('/rest'):
                            n8n_public_base_url = n8n_public_base_url[:-5]
                        
                        # L'URL correcte est simplement: base_url/webhook/path
                        full_url = f"{n8n_public_base_url}/webhook/{webhook_path}"
                        
                        print(f"✅ Constructed webhook URL: {full_url}")
                        return full_url
                        
            return None
            
        except Exception as e:
            print(f"❌ Unexpected error getting webhook production URL: {e}")
            return None

    def trigger_webhook_activate(self, webhook_full_url: str, payload: Dict[str, Any]) -> bool:
        try:
            print(f"→ Sending POST to Webhook Activate: {webhook_full_url}")
            resp = self.session.post(  # Vérifiez bien que c'est une requête POST
                url=webhook_full_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            resp.raise_for_status()
            print(f"→ WEBHOOK Trigger Activate reçu (status {resp.status_code})")
            return True
        except Exception as e:
            print(f"❌ Échec du POST vers '{webhook_full_url}' : {e}")
            return False
        
    def execute_workflow_directly(self, workflow_id: str, data: Dict[str, Any]) -> bool:
        """Exécute un workflow en déclenchant son webhook directement"""
        try:
            # D'abord, obtenir l'URL du webhook
            webhook_node_id = "webhookTrigger1"
            webhook_url = self.get_webhook_production_url(workflow_id, webhook_node_id)
            
            if not webhook_url:
                print(f"❌ Impossible d'obtenir l'URL du webhook pour le workflow {workflow_id}")
                return False
            
            print(f"→ Déclenchement du webhook: {webhook_url}")
            resp = requests.post(
                url=webhook_url,
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=15
            )
            
            if resp.status_code in [200, 201]:
                print(f"✅ Webhook déclenché avec succès: {resp.status_code}")
                print(f"✅ Réponse: {resp.text[:100]}...")
                return True
            else:
                print(f"❌ Échec du déclenchement du webhook: {resp.status_code} - {resp.text}")
                return False
                
        except Exception as e:
            print(f"❌ Erreur lors du déclenchement du webhook: {e}")
            return False
        
    def discover_workflow_execution_api(self, workflow_id: str):
        """Découvre l'API correcte pour exécuter un workflow"""
        possible_endpoints = [
            f"/api/v1/workflows/{workflow_id}/activate",
            f"/api/v1/executions/{workflow_id}",
            f"/api/v1/workflows/{workflow_id}/trigger",
            f"/api/v1/workflows/{workflow_id}/run"
        ]
        
        print("Recherche de l'API d'exécution correcte...")
        for endpoint in possible_endpoints:
            try:
                resp = self.session.post(f"{self.base_url}{endpoint}")
                print(f"Endpoint {endpoint}: {resp.status_code}")
                if resp.status_code not in [404, 405]:
                    print(f"✅ Endpoint potentiellement utilisable: {endpoint}")
            except Exception as e:
                print(f"Erreur pour {endpoint}: {e}")
        
    def ensure_telegram_credentials_exist(self) -> bool:
        """S'assure que les identifiants Telegram existent dans n8n"""
        try:
            # Vérifier si les identifiants existent déjà
            response = self.session.get(f"{self.base_url}/api/v1/credentials")
            response.raise_for_status()
            credentials = response.json()
            
            # Rechercher les identifiants Telegram
            telegram_credentials_exist = False
            for cred in credentials:
                if cred.get("name") == "Telegram API" and cred.get("type") == "telegramApi":
                    telegram_credentials_exist = True
                    break
                    
            # Si les identifiants n'existent pas, les créer
            if not telegram_credentials_exist:
                telegram_cred_data = {
                    "name": "Telegram API",
                    "type": "telegramApi",
                    "data": {
                        "accessToken": "8143834291:AAFVQaQ-7tGEXP3CYQ-bgKD-mu46x5AGK4g  "
                    }
                }
                
                create_response = self.session.post(
                    f"{self.base_url}/api/v1/credentials",
                    json=telegram_cred_data
                )
                create_response.raise_for_status()
                print("✅ Identifiants Telegram créés avec succès!")
                
            return True
        except Exception as e:
            print(f"❌ Erreur lors de la vérification/création des identifiants Telegram: {e}")
            return False
        
    def execute_workflow_via_webhook(self, workflow_id: str, webhook_node_id: str, data: Dict[str, Any]) -> bool:
        """Exécute un workflow en déclenchant son webhook"""
        try:
            # Obtenir d'abord les détails du webhook pour connaître la méthode HTTP configurée
            response = self.session.get(f"{self.base_url}/api/v1/workflows/{workflow_id}")
            response.raise_for_status()
            workflow_data = response.json()
            workflow_details = workflow_data.get("item", workflow_data)
            
            # Déterminer la méthode HTTP configurée
            http_method = "POST"  # Par défaut
            for node in workflow_details.get("nodes", []):
                if node.get("id") == webhook_node_id and node.get("type") == "n8n-nodes-base.webhook":
                    parameters = node.get("parameters", {})
                    http_method = parameters.get("httpMethod", "POST")
                    break
            
            # Obtenir l'URL du webhook
            webhook_url = self.get_webhook_production_url(workflow_id, webhook_node_id)
            
            if not webhook_url:
                print(f"❌ Impossible d'obtenir l'URL du webhook pour le workflow {workflow_id}")
                return False
            
            print(f"→ Déclenchement du webhook ({http_method}): {webhook_url}")
            
            # Utiliser la méthode HTTP configurée
            if http_method == "GET":
                # Convertir les données en paramètres de requête pour GET
                query_params = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in data.items()])
                url_with_params = f"{webhook_url}?{query_params}" if query_params else webhook_url
                resp = requests.get(
                    url=url_with_params,
                    headers={"Content-Type": "application/json"},
                    timeout=15
                )
            else:  # POST ou autres méthodes
                resp = requests.post(
                    url=webhook_url,
                    json=data,
                    headers={"Content-Type": "application/json"},
                    timeout=15
                )
            
            if resp.status_code in [200, 201]:
                print(f"✅ Webhook déclenché avec succès: {resp.status_code}")
                print(f"✅ Réponse: {resp.text[:100]}...")
                return True
            else:
                print(f"❌ Échec du déclenchement du webhook: {resp.status_code} - {resp.text}")
                return False
                
        except Exception as e:
            print(f"❌ Erreur lors du déclenchement du webhook: {e}")
            return False
        