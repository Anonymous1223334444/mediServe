import requests
from django.conf import settings
import logging
from twilio.rest import Client

logger = logging.getLogger(__name__)

class SMSService:
    """Service pour envoyer des SMS via Twilio"""
    
    def __init__(self):
        self.client = Client(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN
        )
        # Utiliser le numéro SMS, pas le numéro WhatsApp !
        self.from_number = settings.TWILIO_SMS_NUMBER
    
    def send_activation_sms(self, patient):
        """Envoie un SMS d'activation au patient"""
        try:
            # Construire le lien d'activation
            activation_url = f"{settings.SITE_PUBLIC_URL}/api/patients/activate/{patient.activation_token}/"
            
            # Message en français avec instructions claires
            message = f"""Bonjour {patient.first_name},activez votre accès WhatsApp santé ici:{activation_url}
{settings.HEALTH_STRUCTURE_NAME}"""
            
            # Envoyer le SMS
            sms = self.client.messages.create(
                body=message,
                from_=self.from_number,  # Numéro SMS
                to=patient.phone
            )
            
            logger.info(f"SMS envoyé à {patient.phone}: {sms.sid}")
            return True, sms.sid
            
        except Exception as e:
            logger.error(f"Erreur envoi SMS à {patient.phone}: {e}")
            return False, str(e)

    
    def send_indexing_complete_sms(self, patient, doc_count):
        """Envoie un SMS quand l'indexation est terminée"""
        try:
            message = f"""Bonjour {patient.first_name},

Vos {doc_count} documents médicaux ont été traités avec succès.

Vous pouvez maintenant poser des questions sur vos documents via WhatsApp.

Si vous n'avez pas encore activé votre compte, utilisez le lien d'activation envoyé précédemment.

Cordialement,
{settings.HEALTH_STRUCTURE_NAME}"""
            
            sms = self.client.messages.create(
                body=message,
                from_=self.from_number,  # Numéro SMS
                to=patient.phone
            )
            
            logger.info(f"SMS de confirmation envoyé à {patient.phone}: {sms.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur envoi SMS de confirmation: {e}")
            return False

class WhatsAppService:
    """Service pour envoyer des messages WhatsApp via Twilio"""
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        # Utiliser le numéro WhatsApp Sandbox
        self.whatsapp_number = settings.TWILIO_WHATSAPP_NUMBER
        
    def send_message(self, to_number: str, message: str) -> bool:
        """Envoyer un message WhatsApp"""
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        
        # S'assurer que le numéro est au format E.164
        if not to_number.startswith('+'):
            to_number = f"+{to_number}"
        
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
                logger.info(f"Message WhatsApp envoyé à {to_number}")
                return True
            else:
                logger.error(f"Échec envoi WhatsApp à {to_number}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur envoi WhatsApp à {to_number}: {e}")
            return False