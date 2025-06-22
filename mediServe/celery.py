import os
from celery import Celery
from django.conf import settings

# Set default Django settings module for 'celery' program
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mediServe.settings')

app = Celery('mediServe')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps
app.autodiscover_tasks()

# Configuration des tâches périodiques
app.conf.beat_schedule = {
    # Traiter les messages programmés toutes les minutes
    'process-scheduled-messages': {
        'task': 'messaging.tasks.process_scheduled_messages',
        'schedule': 300.0,  # Toutes les 60 secondes
    },
    
    # Nettoyer les sessions expirées toutes les heures
    'cleanup-expired-sessions': {
        'task': 'sessions.tasks.cleanup_expired_sessions',
        'schedule': 3600.0,  # Toutes les heures
    },
    
    # Indexer les documents en attente toutes les 5 minutes
    'process-pending-documents': {
        'task': 'documents.tasks.process_pending_documents',
        'schedule': 300.0,  # Toutes les 5 minutes
    },
    
    # Générer un rapport de métriques quotidien
    'daily-metrics-report': {
        'task': 'metrics.tasks.generate_daily_report',
        'schedule': 86400.0,  # Toutes les 24 heures
        'options': {'kwargs': {'send_email': True}}
    },
    
    # Sauvegarder les métriques toutes les 10 minutes
    'collect-system-metrics': {
        'task': 'metrics.tasks.collect_system_metrics',
        'schedule': 600.0,  # Toutes les 10 minutes
    },
    
    # Vérifier la santé des workflows N8N toutes les 15 minutes
    'check-n8n-workflows': {
        'task': 'patients.tasks.check_workflow_health',
        'schedule': 900.0,  # Toutes les 15 minutes
    },
}

app.conf.timezone = 'UTC'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


# mediServe/__init__.py
from .celery import app as celery_app

__all__ = ('celery_app',)
