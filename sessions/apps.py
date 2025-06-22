from django.apps import AppConfig

class WhatsAppSessionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sessions'
    label = 'whatsapp_sessions'  # Unique label to avoid conflict
    verbose_name = 'WhatsApp Sessions'