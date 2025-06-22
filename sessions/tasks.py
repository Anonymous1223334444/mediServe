from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import WhatsAppSession
import logging

logger = logging.getLogger(__name__)

@shared_task
def cleanup_expired_sessions():
    """Nettoie les sessions WhatsApp expirées (plus de 24h d'inactivité)"""
    try:
        cutoff_time = timezone.now() - timedelta(hours=24)
        
        expired_sessions = WhatsAppSession.objects.filter(
            last_activity__lt=cutoff_time,
            status='active'
        )
        
        count = expired_sessions.count()
        expired_sessions.update(status='expired')
        
        logger.info(f"Nettoyage sessions: {count} sessions expirées")
        return {"expired_sessions": count}
        
    except Exception as e:
        logger.error(f"Erreur nettoyage sessions: {e}")
        return {"error": str(e)}

@shared_task
def archive_old_conversations():
    """Archive les conversations de plus de 30 jours"""
    try:
        from .models import ConversationLog
        
        cutoff_date = timezone.now() - timedelta(days=30)
        
        old_conversations = ConversationLog.objects.filter(
            timestamp__lt=cutoff_date
        )
        
        count = old_conversations.count()
        
        # Ici vous pourriez exporter vers un système d'archivage
        # Pour l'instant, on garde juste un compteur
        
        logger.info(f"Conversations à archiver: {count}")
        return {"conversations_to_archive": count}
        
    except Exception as e:
        logger.error(f"Erreur archivage conversations: {e}")
        return {"error": str(e)}
