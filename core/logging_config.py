import os
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from django.conf import settings

def setup_logging():
    """Configuration centralisée du logging pour MediRecord"""
    
    # Créer le dossier de logs
    log_dir = os.path.join(settings.BASE_DIR, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Configuration du format
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s '
        '[%(filename)s:%(lineno)d] [PID:%(process)d]'
    )
    
    # Logger principal MediRecord
    logger = logging.getLogger('medirecord')
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    # Handler pour fichier général (rotation par taille)
    general_handler = RotatingFileHandler(
        os.path.join(log_dir, 'medirecord.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    general_handler.setFormatter(formatter)
    general_handler.setLevel(logging.INFO)
    logger.addHandler(general_handler)
    
    # Handler pour erreurs (rotation quotidienne)
    error_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, 'errors.log'),
        when='midnight',
        interval=1,
        backupCount=30
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    logger.addHandler(error_handler)
    
    # Logger spécialisés
    setup_specialized_loggers(log_dir, formatter)
    
    # Console handler pour le développement
    if settings.DEBUG:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG)
        logger.addHandler(console_handler)

def setup_specialized_loggers(log_dir, formatter):
    """Configuration des loggers spécialisés"""
    
    # Logger RAG
    rag_logger = logging.getLogger('medirecord.rag')
    rag_handler = RotatingFileHandler(
        os.path.join(log_dir, 'rag.log'),
        maxBytes=5*1024*1024,
        backupCount=3
    )
    rag_handler.setFormatter(formatter)
    rag_logger.addHandler(rag_handler)
    
    # Logger WhatsApp
    whatsapp_logger = logging.getLogger('medirecord.whatsapp')
    whatsapp_handler = RotatingFileHandler(
        os.path.join(log_dir, 'whatsapp.log'),
        maxBytes=5*1024*1024,
        backupCount=3
    )
    whatsapp_handler.setFormatter(formatter)
    whatsapp_logger.addHandler(whatsapp_handler)
    
    # Logger N8N
    n8n_logger = logging.getLogger('medirecord.n8n')
    n8n_handler = RotatingFileHandler(
        os.path.join(log_dir, 'n8n.log'),
        maxBytes=5*1024*1024,
        backupCount=3
    )
    n8n_handler.setFormatter(formatter)
    n8n_logger.addHandler(n8n_handler)
    
    # Logger Celery
    celery_logger = logging.getLogger('medirecord.celery')
    celery_handler = RotatingFileHandler(
        os.path.join(log_dir, 'celery.log'),
        maxBytes=5*1024*1024,
        backupCount=3
    )
    celery_handler.setFormatter(formatter)
    celery_logger.addHandler(celery_handler)
