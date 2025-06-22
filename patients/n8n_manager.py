# patients/n8n_manager.py

import os
import json
import random
import requests
from typing import Dict, Any, Optional, List
from django.conf import settings
import time # Import time for retries
import urllib.parse # Import urllib.parse for URL encoding (used carefully)

names = ["Andre", "Benoit", "Céline", "David", "Elodie", "François", "Géraldine", "Hugo", "Isabelle", "Julien"]

class N8NWorkflowManager:
    def __init__(self, base_url=None):
        """Initialise le gestionnaire de workflows n8n"""
        self.base_url = base_url or os.getenv('N8N_BASE_URL', 'http://localhost:5678')
        print(f"[DEBUG n8n_manager] base_url utilisée = {self.base_url}")
        
        # Initialiser les headers pour les requêtes API
        self.headers = {
            'Content-Type': 'application/json',
            'X-N8N-API-KEY': os.getenv('N8N_API_KEY', '')
        }
        
        # Initialiser la session pour les requêtes
        self.session = requests.Session()
        self.session.headers.update(self.headers)

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
        """Vérifie que l'instance n8n est joignable."""
        try:
            response = self.session.get(f"{self.base_url}/api/v1/workflows")
            return response.status_code in [200, 401]
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection test failed: {e}")
            return False

    def create_workflow(self, name: str, nodes: List[Dict[str, Any]], connections: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Crée un nouveau workflow dans n8n.
        """
        try:
            # Préparer les données du workflow
            workflow_data = {
                "name": name,
                "nodes": nodes,
                "connections": connections,
                "settings": {}
            }
            
            print(f"📦 Données du workflow à créer: {workflow_data}")
            
            # Créer le workflow
            response = self.session.post(
                f"{self.base_url}/api/v1/workflows",
                json=workflow_data
            )
            response.raise_for_status()
            
            workflow = response.json()
            print(f"📦 Réponse de création du workflow: {workflow}")
            
            if not workflow.get('id'):
                print("❌ ID du workflow non trouvé dans la réponse")
                return None
            
            return workflow
            
        except Exception as e:
            print(f"❌ Erreur lors de la création du workflow: {str(e)}")
            return None

    def activate_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Active un workflow et attend que les URLs de webhook de production soient disponibles.
        Renvoie les données complètes du workflow si l'activation réussit, sinon None.
        """
        try:
            # 1. Activer le workflow
            activate_url = f"{self.base_url}/api/v1/workflows/{workflow_id}/activate"
            print(f"🚀 Tentative d'activation du workflow via POST {activate_url}")
            response = self.session.post(activate_url)
            print(f"🚦 Réponse de l'activation: {response.status_code} {response.text}")
            response.raise_for_status() # Lève une exception pour les codes 4xx/5xx

            # 2. Attendre/Poller pour que le workflow soit actif et que l'URL du webhook soit prête
            max_retries = 5
            delay_seconds = 2
            for attempt in range(max_retries):
                time.sleep(delay_seconds)
                workflow_url = f"{self.base_url}/api/v1/workflows/{workflow_id}"
                workflow_response = self.session.get(workflow_url)
                workflow_response.raise_for_status()
                workflow_data = workflow_response.json()

                if workflow_data.get('active'):
                    print(f"✅ Workflow {workflow_id} est maintenant marqué comme actif (tentative {attempt + 1}).")
                    return workflow_data
                
                print(f"⏳ Attente que le workflow {workflow_id} soit marqué comme actif (tentative {attempt + 1}/{max_retries})...")

            print(f"❌ Le workflow {workflow_id} n'a pas pu être activé ou l'URL du webhook n'est pas apparue après {max_retries * delay_seconds}s.")
            return None

        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur lors de l'activation du workflow {workflow_id}: {e}")
            return None

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
        """Liste tous les workflows existants dans l'instance n8n."""
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

    def get_webhook_production_url(self, webhook_node_id: str, workflow_data: Dict[str, Any]) -> Optional[str]:
        """
        Obtient l'URL de production du webhook pour un nœud donné.
        """
        try:
            workflow_id = workflow_data.get('id')
            if not workflow_id:
                print("❌ ID du workflow non trouvé dans les données")
                return None

            # Construire l'URL du webhook avec le format correct
            webhook_url = f"{self.base_url}/workflow/{workflow_id}/{webhook_node_id}"
            print(f"🔗 URL du webhook: {webhook_url}")
            return webhook_url
            
        except Exception as e:
            print(f"❌ Erreur lors de l'obtention de l'URL du webhook: {str(e)}")
            return None

    def trigger_webhook_activate(self, workflow_id: str, activation_token: str, full_name: str, phone: str, activation_link: str) -> bool:
        """
        Déclenche le webhook d'activation du workflow n8n.
        """
        try:
            # Récupérer les détails du workflow pour obtenir le chemin du webhook
            # C'est une bonne pratique de récupérer les détails pour s'assurer d'avoir le path correct.
            # Même si WebhookUrls est vide, le 'path' devrait être là.
            workflow_details_url = f"{self.base_url}/api/v1/workflows/{workflow_id}"
            resp_details = self.session.get(workflow_details_url, timeout=15)
            resp_details.raise_for_status() # Lève une exception pour les codes d'erreur HTTP
            workflow_details = resp_details.json()

            webhook_node_data = None
            for node in workflow_details.get('nodes', []):
                # Trouver le nœud 'Webhook Trigger (Activate)' par son nom et type
                if node.get('name') == 'Webhook Trigger (Activate)' and node.get('type') == 'n8n-nodes-base.webhook':
                    webhook_node_data = node
                    break

            if not webhook_node_data:
                print(f"❌ Le nœud 'Webhook Trigger (Activate)' n'a pas été trouvé dans le workflow {workflow_id}")
                return False

            # Récupérer le chemin (path) défini dans les paramètres du nœud webhook
            webhook_path_template = webhook_node_data.get('parameters', {}).get('path')
            if not webhook_path_template:
                print(f"❌ Le 'path' du webhook n'a pas été trouvé pour le nœud 'Webhook Trigger (Activate)' dans le workflow {workflow_id}")
                return False

            # Interpoler le token d'activation dans le chemin du webhook
            # Le chemin dans le template est "activate-{{ACTIVATION_TOKEN}}".
            # Nous devons remplacer le placeholder par le token réel.
            actual_webhook_path = webhook_path_template.replace("{{ACTIVATION_TOKEN}}", str(activation_token))

            # Construire l'URL du webhook de production
            # Depuis n8n v1, l'URL de production est au format :
            #     BASE_URL/webhook/<WORKFLOW_ID>/<PATH_DEFINI>
            # Exemple : http://localhost:5678/webhook/123abc/activate-XYZ
            # Certains anciens tutoriels ou versions <1.0 utilisaient `BASE_URL/webhook/<PATH_DEFINI>`.
            # Pour garantir la compatibilité, on essaie d'abord de récupérer l'URL directement exposée
            # par n8n dans `webhookUrls.production`, sinon on reconstruit en y incluant le `workflow_id`.
            webhook_url = None
            source_of_url = "inconnu"

            # 1️⃣  Essayer d'utiliser l'URL renvoyée par l'API (si présente)
            webhook_urls_from_api = webhook_node_data.get("webhookUrls")
            print(f"🔍 Webhook URLs from API: {webhook_urls_from_api}") # DEBUG
            if webhook_urls_from_api:
                # Selon la version de n8n, `webhookUrls` peut être :
                #   • une liste de chaînes (URLs)  ➜ on prend la 1re
                #   • un dict sous la forme {"production": [...], "test": [...]}  ➜ on prend production[0]
                if isinstance(webhook_urls_from_api, list) and webhook_urls_from_api:
                    webhook_url = webhook_urls_from_api[0]
                    source_of_url = "API (liste)"
                elif isinstance(webhook_urls_from_api, dict):
                    prod_urls = webhook_urls_from_api.get("production") or webhook_urls_from_api.get("prod")
                    if prod_urls and isinstance(prod_urls, list):
                        webhook_url = prod_urls[0]
                        source_of_url = "API (dict.production)"

            # 2️⃣  Fallback : reconstruire manuellement avec WORKFLOW_ID dans le chemin
            if not webhook_url:
                webhook_url = f"{self.base_url}/webhook/{workflow_id}/{actual_webhook_path}"
                source_of_url = "Fallback (manuel)"

            print(f"✅ URL du webhook construite ({source_of_url}): {webhook_url}")

            # Préparer les données pour le déclenchement (si c'est un GET, elles seront encodées dans l'URL)
            data_to_send = {
                "fullName": full_name,
                "phone": phone,
                "activation_link": activation_link
            }

            # Déterminer la méthode HTTP du webhook (du template, c'est GET pour l'activation)
            http_method = webhook_node_data.get('parameters', {}).get('httpMethod', 'GET').upper()

            print(f"→ Déclenchement du webhook ({http_method}): {webhook_url}")

            def _send_once():
                if http_method == "GET":
                    query_params = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in data_to_send.items()])
                    url_with_params = f"{webhook_url}?{query_params}" if query_params else webhook_url
                    return requests.get(
                        url_with_params,
                        headers={"Content-Type": "application/json"},
                        timeout=15
                    )
                else:
                    return requests.post(
                        webhook_url,
                        json=data_to_send,
                        headers={"Content-Type": "application/json"},
                        timeout=15
                    )

            max_retries = 5
            retry_delay_seconds = 3
            resp = None

            for attempt in range(max_retries):
                resp = _send_once()
                if resp.status_code != 404:
                    # Succès ou erreur autre que 404, on sort de la boucle
                    break
                
                print(f"⏳ Webhook non reconnu (404). Tentative {attempt + 1}/{max_retries}. Attente {retry_delay_seconds}s...")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay_seconds)

            if resp.status_code in [200, 201]:
                print(f"✅ Webhook déclenché avec succès: {resp.status_code}")
                print(f"✅ Réponse: {resp.text[:100]}...")
                return True
            else:
                print(f"❌ Échec du déclenchement du webhook: {resp.status_code} - {resp.text}")
                return False

        except requests.exceptions.RequestException as req_e:
            print(f"❌ Erreur de requête HTTP lors du déclenchement du webhook: {req_e}")
            return False
        except Exception as e:
            print(f"❌ Erreur lors du déclenchement du webhook: {e}")
            return False

    def execute_workflow_directly(self, workflow_id: str, data: Dict[str, Any]) -> bool:
        """Exécute un workflow en déclenchant son webhook directement"""
        try:
            # D'abord, obtenir l'URL du webhook
            webhook_node_id = "webhookTrigger1"
            webhook_url = self.get_webhook_production_url(webhook_node_id, data)
            
            if not webhook_url:
                print(f"❌ Impossible d'obtenir l'URL du webhook pour le workflow {workflow_id}")
                return False
            
            print(f"→ Déclenchement du webhook: {webhook_url}")
            resp = requests.get(
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
        
    def execute_workflow_via_webhook(self, webhook_node_id: str, data: Dict[str, Any], workflow_id: str) -> Optional[requests.Response]:
        """
        Exécute un workflow via son webhook.
        
        Args:
            webhook_node_id: ID du nœud webhook
            data: Données à envoyer au webhook
            workflow_id: ID du workflow
            
        Returns:
            Response de la requête ou None en cas d'erreur
        """
        try:
            # Extraire le token d'activation des données
            activation_token = data.get('patient', {}).get('activation_token')
            if not activation_token:
                print("❌ Token d'activation non trouvé dans les données")
                return None
                
            # Construire l'URL du webhook avec le chemin complet
            webhook_url = f"{self.base_url}/webhook/{webhook_node_id}/activate-{activation_token}"
            print(f"🔗 URL du webhook: {webhook_url}")
            print(f"📦 Données envoyées: {data}")
            
            # Envoyer les données au webhook
            response = requests.post(webhook_url, json=data)
            response.raise_for_status()
            return response
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Erreur lors de l'exécution du webhook: {str(e)}")
            return None