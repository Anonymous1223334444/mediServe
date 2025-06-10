import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class WhatsAppService:
    """Service pour envoyer des messages WhatsApp via Twilio"""
    
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.whatsapp_number = settings.TWILIO_WHATSAPP_NUMBER
        
    def send_message(self, to_number: str, message: str) -> bool:
        """Envoyer un message WhatsApp"""
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        
        data = {
            'From': f'whatsapp:{self.whatsapp_number}',
            'To': f'whatsapp:{to_number}',
            'Body': message
        }
        
        try:
            response = requests.post(
                url,
                data=data,
                auth=(self.account_sid, self.auth_token)
            )
            
            if response.status_code == 201:
                logger.info(f"Message envoyé à {to_number}")
                return True
            else:
                logger.error(f"Échec envoi à {to_number}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur envoi WhatsApp à {to_number}: {e}")
            return False
