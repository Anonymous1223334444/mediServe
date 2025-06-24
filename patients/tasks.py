# patients/tasks.py
from celery import shared_task
from django.utils import timezone
from .models import Patient
from .n8n_manager import N8NWorkflowManager
from metrics.services import MetricsService
import logging

logger = logging.getLogger(__name__)

@shared_task
def check_workflow_health():
    """Vérifie la santé des workflows N8N des patients actifs"""
    try:
        manager = N8NWorkflowManager()
        
        if not manager.test_connection():
            logger.error("Connexion N8N échouée")
            MetricsService._create_alert(
                'n8n_connection',
                'critical',
                "Impossible de se connecter à N8N",
                1.0,
                0.0
            )
            return {"error": "N8N connection failed"}
        
        # Vérifier quelques workflows récents
        recent_patients = Patient.objects.filter(
            is_active=True,
            workflow_id__isnull=False,
            activated_at__isnull=False
        ).order_by('-activated_at')[:10]
        
        healthy_workflows = 0
        unhealthy_workflows = 0
        
        for patient in recent_patients:
            if patient.workflow_id:
                is_active = manager.is_workflow_active(patient.workflow_id)
                if is_active:
                    healthy_workflows += 1
                else:
                    unhealthy_workflows += 1
                    logger.warning(f"Workflow inactif pour patient {patient.id}")
        
        return {
            "healthy_workflows": healthy_workflows,
            "unhealthy_workflows": unhealthy_workflows,
            "total_checked": healthy_workflows + unhealthy_workflows
        }
        
    except Exception as e:
        logger.error(f"Erreur vérification workflows: {e}")
        return {"error": str(e)}

@shared_task
def send_activation_reminder():
    """Envoie des rappels aux patients non activés après 24h"""
    try:
        from datetime import timedelta
        from messaging.services import WhatsAppService
        
        cutoff_time = timezone.now() - timedelta(hours=24)
        
        inactive_patients = Patient.objects.filter(
            is_active=False,
            created_at__lt=cutoff_time,
            created_at__gte=cutoff_time - timedelta(hours=24)  # Créés entre 24h et 48h
        )
        
        whatsapp_service = WhatsAppService()
        sent_count = 0
        
        for patient in inactive_patients:
            try:
                message = f"""
                    Bonjour {patient.first_name},

                    Votre espace santé MediRecord n'est pas encore activé. 

                    Pour activer votre compte et commencer à recevoir vos conseils santé personnalisés, veuillez cliquer sur le lien d'activation envoyé précédemment.

                    Si vous ne trouvez pas le message, contactez votre médecin.

                    L'équipe MediRecord
                    """
                
                success = whatsapp_service.send_message(patient.phone, message.strip())
                if success:
                    sent_count += 1
                    
            except Exception as e:
                logger.error(f"Erreur envoi rappel à {patient.phone}: {e}")
        
        return {"reminders_sent": sent_count}
        
    except Exception as e:
        logger.error(f"Erreur envoi rappels d'activation: {e}")
        return {"error": str(e)}
