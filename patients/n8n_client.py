import requests
from django.conf import settings
from typing import Dict

def trigger_n8n_activation(patient_payload: Dict) -> None:
    """
    Calls the generic 'activate-patient' webhook in n8n with this payload.
    We assume:
      - The n8n Webhook Trigger node listens on /webhook-test/activate-patient (POST)
      - settings.N8N_BASE_URL is e.g. "http://localhost:5678"
    """
    webhook_url = f"{settings.N8N_BASE_URL}/activate-patient"
    headers = {"Content-Type": "application/json"}
    if settings.N8N_API_KEY:
        # If your n8n has API key auth, pass it here. But Webhook Trigger may not require it.
        headers["Authorization"] = f"Bearer {settings.N8N_API_KEY}"

    try:
        response = requests.post(webhook_url, json=patient_payload, headers=headers, timeout=5)
        response.raise_for_status()
    except requests.RequestException as e:
        # You can log or re-raise. For now, we will just print.
        print(f"❌ Failed to trigger n8n activation webhook: {e}")
        # Optionally, raise e so it bubbles up to the view:
        raise
