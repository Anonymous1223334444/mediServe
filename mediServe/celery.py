import os
import logging
from celery import Celery
from django.conf import settings

# Configuration du logging pour Celery
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set default Django settings module for 'celery' program
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mediServe.settings')

# Créer l'application Celery
app = Celery('mediServe')

# Configuration debug
app.conf.update(
    # Forcer l'exécution synchrone pour debug (désactiver en production!)
    task_always_eager=False,  # Mettre à True pour exécution synchrone pendant debug
    task_eager_propagates=True,
    
    # Logs détaillés
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
    
    # Autres configs
    result_backend=settings.CELERY_RESULT_BACKEND,
    broker_url=settings.CELERY_BROKER_URL,
    result_expires=3600,
    timezone='UTC',
    enable_utc=True,
)

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps
logger.info("Chargement des tâches Celery...")
app.autodiscover_tasks()

# Afficher toutes les tâches enregistrées
@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    logger.info("=== TÂCHES CELERY ENREGISTRÉES ===")
    for task_name in app.tasks:
        if not task_name.startswith('celery.'):
            logger.info(f"✅ Tâche: {task_name}")

# Test de connexion au démarrage
@app.task(bind=True)
def debug_task(self):
    logger.info(f'Request: {self.request!r}')
    return "Debug task executed successfully!"

# Configuration des tâches périodiques avec logs
app.conf.beat_schedule = {
    # Traiter les messages programmés toutes les 5 minutes
    'process-scheduled-messages': {
        'task': 'messaging.tasks.process_scheduled_messages',
        'schedule': 300.0,
        'options': {'expires': 200.0}
    },
    
    # Nettoyer les sessions expirées toutes les heures
    'cleanup-expired-sessions': {
        'task': 'sessions.tasks.cleanup_expired_sessions',
        'schedule': 3600.0,
    },
    
    # Vérifier la santé des workflows N8N toutes les 15 minutes
    'check-n8n-workflows': {
        'task': 'patients.tasks.check_workflow_health',
        'schedule': 900.0,
    },
}

logger.info(f"Celery configuré avec broker: {app.conf.broker_url}")
logger.info(f"Result backend: {app.conf.result_backend}")