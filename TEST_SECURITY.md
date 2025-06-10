# Guide de Troubleshooting Avancé - MediRecord SIS

## 🔍 Diagnostic Rapide

### Commandes de Diagnostic Immédiat

```bash
# Status général complet
sudo /home/medirecord/medirecord-sis/scripts/admin.sh status

# Vérification API Health Check
curl -s http://localhost:8000/api/health/ | jq '.'

# Logs des 5 dernières minutes
sudo journalctl --since "5 minutes ago" -u medirecord -u medirecord-celery

# Utilisation des ressources
htop
df -h
free -h
```

### Indicateurs de Problèmes

| Symptôme | Cause Probable | Action Immédiate |
|----------|----------------|------------------|
| API ne répond pas | Django/Gunicorn down | `systemctl restart medirecord` |
| Messages WhatsApp non envoyés | N8N ou Twilio | Vérifier workflows N8N |
| RAG lent/échoue | Gemini ou Pinecone | Tester les APIs externes |
| Documents non indexés | Celery worker down | `systemctl restart medirecord-celery` |
| Erreurs 500 fréquentes | Base de données | Vérifier PostgreSQL |

---

## 🚨 Problèmes Critiques et Solutions

### 1. Base de Données Inaccessible

**Symptômes :**
- Erreurs "connection refused" dans les logs Django
- API Health Check échoue
- Impossible de créer des patients

**Diagnostic :**
```bash
# Vérifier PostgreSQL
sudo systemctl status postgresql
sudo -u postgres psql -c "SELECT version();"

# Vérifier les connexions
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"

# Vérifier l'espace disque
df -h /var/lib/postgresql/
```

**Solutions :**
```bash
# Redémarrer PostgreSQL
sudo systemctl restart postgresql

# Si problème de corruption
sudo -u postgres pg_resetwal /var/lib/postgresql/14/main/

# Si manque d'espace
sudo find /var/lib/postgresql/ -name "*.log" -mtime +7 -delete
sudo -u postgres psql -c "VACUUM FULL;"

# Restaurer depuis backup si nécessaire
sudo /home/medirecord/medirecord-sis/scripts/admin.sh restore /backup/medirecord/full_backup_YYYYMMDD_HHMMSS.tar.gz
```

### 2. N8N Workflows Non Fonctionnels

**Symptômes :**
- Patients créés mais pas de message WhatsApp
- Messages diffusés non envoyés
- Webhooks qui échouent

**Diagnostic :**
```bash
# Vérifier N8N container
docker ps | grep n8n
docker logs medirecord_n8n

# Tester connectivity
curl -f https://orca-eternal-specially.ngrok-free.app/healthz

# Vérifier workflows actifs
curl -H "X-N8N-API-KEY: $N8N_API_KEY" \
     https://orca-eternal-specially.ngrok-free.app/api/v1/workflows
```

**Solutions :**
```bash
# Redémarrer N8N
docker restart medirecord_n8n

# Réactiver les workflows
python manage.py shell -c "
from patients.n8n_manager import N8NWorkflowManager
manager = N8NWorkflowManager()
workflows = manager.list_workflows()
for wf in workflows:
    if not wf.get('active'):
        manager.activate_workflow(wf['id'])
        print(f'Reactivated workflow {wf[\"id\"]}')
"

# Recréer les credentials Twilio dans N8N
# Via l'interface N8N: Settings > Credentials > Twilio
```

### 3. Gemini API Rate Limiting

**Symptômes :**
- Erreurs "quota exceeded" dans les logs
- RAG queries échouent
- Indexation de documents lente

**Diagnostic :**
```bash
# Vérifier les métriques RAG
curl -s http://localhost:8000/api/metrics/dashboard/ | jq '.rag_metrics'

# Tester directement Gemini
python manage.py shell -c "
from rag.services import EmbeddingService
service = EmbeddingService()
try:
    result = service.generate_embedding('test')
    print('Gemini OK:', len(result))
except Exception as e:
    print('Gemini Error:', e)
"
```

**Solutions :**
```bash
# Implémenter un cache pour les embeddings
python manage.py shell -c "
# Ajouter à rag/services.py
from django.core.cache import cache
import hashlib

class EmbeddingService:
    def generate_embedding(self, text):
        # Cache key basé sur le hash du texte
        cache_key = f'embedding_{hashlib.md5(text.encode()).hexdigest()}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # Générer et cache pour 24h
        embedding = self._generate_embedding_api(text)
        cache.set(cache_key, embedding, 86400)
        return embedding
"

# Réduire la fréquence des appels
# Modifier CELERY_BEAT_SCHEDULE dans settings.py
```

### 4. Pinecone Indisponible

**Symptômes :**
- RAG queries retournent des réponses vides
- Indexation de documents échoue
- Health check Pinecone en erreur

**Diagnostic :**
```bash
# Test connection Pinecone
python manage.py shell -c "
from rag.services import PineconeService
service = PineconeService()
try:
    stats = service.index.describe_index_stats()
    print('Pinecone Stats:', stats)
except Exception as e:
    print('Pinecone Error:', e)
"
```

**Solutions :**
```bash
# Fallback vers recherche textuelle simple
# Créer un service de fallback dans rag/services.py

class FallbackRAGService:
    def query(self, patient_id, query, session_id):
        from rag.models import Document
        from django.db.models import Q
        
        # Recherche textuelle dans les documents
        documents = Document.objects.filter(
            patient_id=patient_id,
            content_text__icontains=query[:50]
        )[:3]
        
        if documents:
            context = '\n'.join([doc.content_text[:500] for doc in documents])
            return f"Basé sur vos documents: {context[:200]}..."
        
        return "Désolé, je ne trouve pas d'informations pertinentes dans vos documents."
```

---

## ⚡ Optimisations de Performance

### 1. Optimisation Base de Données

#### Configuration PostgreSQL
```sql
-- postgresql.conf optimizations
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
```

#### Index Optimaux
```sql
-- Indexes pour les requêtes fréquentes
CREATE INDEX CONCURRENTLY idx_patients_phone ON patients_patient(phone);
CREATE INDEX CONCURRENTLY idx_patients_active ON patients_patient(is_active) WHERE is_active = true;
CREATE INDEX CONCURRENTLY idx_documents_patient_indexed ON rag_document(patient_id, pinecone_indexed);
CREATE INDEX CONCURRENTLY idx_conversations_session_timestamp ON sessions_conversationlog(session_id, timestamp DESC);
CREATE INDEX CONCURRENTLY idx_metrics_type_timestamp ON metrics_systemmetric(metric_type, timestamp DESC);

-- Index composites
CREATE INDEX CONCURRENTLY idx_messages_status_created ON messaging_broadcastmessage(status, created_at DESC);
CREATE INDEX CONCURRENTLY idx_deliveries_message_status ON messaging_messagedelivery(broadcast_message_id, status);
```

#### Requêtes Optimisées
```python
# patients/views.py - Optimisation des requêtes
class PatientListAPIView(views.APIView):
    def get(self, request):
        # Utiliser select_related et prefetch_related
        patients = Patient.objects.select_related().prefetch_related(
            'documents', 
            'whatsapp_sessions'
        ).filter(
            is_active=True
        ).only(
            'id', 'first_name', 'last_name', 'phone', 
            'email', 'is_active', 'created_at'
        )
        
        # Pagination efficace
        paginator = Paginator(patients, 50)
        page = paginator.get_page(request.GET.get('page', 1))
        
        return Response({
            'results': [self.serialize_patient(p) for p in page],
            'has_next': page.has_next(),
            'total_pages': paginator.num_pages
        })
```

### 2. Optimisation Redis et Cache

#### Configuration Redis
```bash
# redis.conf optimizations
maxmemory 512mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

#### Cache Strategy Django
```python
# settings.py - Cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
        },
        'KEY_PREFIX': 'medirecord',
        'TIMEOUT': 3600,  # 1 hour default
    }
}

# Cache pour les sessions
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
```

#### Mise en Cache Intelligente
```python
# rag/services.py - Cache pour RAG
from django.core.cache import cache
from django.utils.encoding import force_str
import hashlib

class RAGService:
    def query(self, patient_id, query, session_id):
        # Cache key unique
        cache_key = f"rag_{patient_id}_{hashlib.md5(query.encode()).hexdigest()}"
        
        # Vérifier le cache (5 minutes)
        cached_response = cache.get(cache_key)
        if cached_response:
            return cached_response
        
        # Générer la réponse
        response = self._generate_response(patient_id, query, session_id)
        
        # Mettre en cache
        cache.set(cache_key, response, 300)
        return response
```

### 3. Optimisation Celery

#### Configuration Optimisée
```python
# settings.py - Celery optimizations
CELERY_WORKER_CONCURRENCY = 4
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Queue routing optimisé
CELERY_TASK_ROUTES = {
    'documents.tasks.process_document_async': {'queue': 'documents'},
    'messaging.tasks.send_broadcast_message_async': {'queue': 'messaging'},
    'rag.tasks.*': {'queue': 'rag'},
    'metrics.tasks.*': {'queue': 'metrics'},
}

# Retry configuration
CELERY_TASK_RETRY_BACKOFF = True
CELERY_TASK_RETRY_BACKOFF_MAX = 700
CELERY_TASK_RETRY_JITTER = False
```

#### Tâches Optimisées
```python
# documents/tasks.py - Optimisation traitement batch
@shared_task(bind=True)
def process_documents_batch(self, document_ids):
    """Traiter plusieurs documents en batch pour réduire l'overhead"""
    from .models import DocumentUpload
    from rag.services import RAGService
    
    rag_service = RAGService()
    results = []
    
    # Traitement par batch de 5
    for i in range(0, len(document_ids), 5):
        batch = document_ids[i:i+5]
        
        for doc_id in batch:
            try:
                doc = DocumentUpload.objects.get(id=doc_id)
                success = rag_service.index_document(doc)
                results.append({'doc_id': doc_id, 'success': success})
            except Exception as e:
                results.append({'doc_id': doc_id, 'success': False, 'error': str(e)})
        
        # Petite pause entre les batches
        time.sleep(1)
    
    return results
```

### 4. Optimisation N8N et WhatsApp

#### Rate Limiting Intelligent
```json
// N8N workflow optimization - Add rate limiting
{
  "id": "rateLimitNode",
  "name": "Rate Limit Control",
  "type": "n8n-nodes-base.code",
  "parameters": {
    "jsCode": "// Rate limiting pour WhatsApp (1 message/seconde)\nconst lastSent = $workflow.lastMessageTime || 0;\nconst now = Date.now();\nconst minInterval = 1000; // 1 seconde\n\nconst waitTime = Math.max(0, minInterval - (now - lastSent));\n\nif (waitTime > 0) {\n  await new Promise(resolve => setTimeout(resolve, waitTime));\n}\n\n$workflow.lastMessageTime = Date.now();\nreturn $input.all();"
  }
}
```

#### Batch Processing pour Messages Diffusés
```python
# messaging/tasks.py - Optimisation envoi en batch
@shared_task
def send_broadcast_batch(message_id, patient_batch):
    """Envoyer des messages par batch avec rate limiting"""
    from .models import BroadcastMessage, MessageDelivery
    from .services import WhatsAppService
    
    message = BroadcastMessage.objects.get(id=message_id)
    whatsapp_service = WhatsAppService()
    
    results = []
    
    for patient_data in patient_batch:
        try:
            # Rate limiting: 1 message/seconde
            time.sleep(1)
            
            success = whatsapp_service.send_message(
                patient_data['phone'],
                message.content
            )
            
            # Mise à jour en batch
            results.append({
                'patient_id': patient_data['id'],
                'status': 'sent' if success else 'failed'
            })
            
        except Exception as e:
            results.append({
                'patient_id': patient_data['id'],
                'status': 'failed',
                'error': str(e)
            })
    
    # Mise à jour en batch
    for result in results:
        MessageDelivery.objects.filter(
            broadcast_message=message,
            patient_id=result['patient_id']
        ).update(status=result['status'])
    
    return results
```

---

## 🚀 Monitoring et Alertes Avancées

### 1. Métriques de Performance Personnalisées

```python
# metrics/advanced_metrics.py
import time
import psutil
from django.core.management.base import BaseCommand
from metrics.services import MetricsService

class Command(BaseCommand):
    help = 'Collecte des métriques avancées'
    
    def handle(self, *args, **options):
        # Métriques PostgreSQL
        db_metrics = self.get_database_metrics()
        for metric, value in db_metrics.items():
            MetricsService.record_custom_metric(f'db_{metric}', value)
        
        # Métriques Redis
        redis_metrics = self.get_redis_metrics()
        for metric, value in redis_metrics.items():
            MetricsService.record_custom_metric(f'redis_{metric}', value)
        
        # Métriques application
        app_metrics = self.get_application_metrics()
        for metric, value in app_metrics.items():
            MetricsService.record_custom_metric(f'app_{metric}', value)
    
    def get_database_metrics(self):
        from django.db import connection
        
        with connection.cursor() as cursor:
            # Connexions actives
            cursor.execute("SELECT count(*) FROM pg_stat_activity")
            active_connections = cursor.fetchone()[0]
            
            # Taille de la base
            cursor.execute("""
                SELECT pg_size_pretty(pg_database_size('medirecord_prod'))
            """)
            db_size = cursor.fetchone()[0]
            
            # Requêtes lentes
            cursor.execute("""
                SELECT count(*) FROM pg_stat_statements 
                WHERE mean_time > 1000
            """)
            slow_queries = cursor.fetchone()[0] if cursor.fetchone() else 0
            
            return {
                'active_connections': active_connections,
                'slow_queries': slow_queries,
                'size_mb': self.parse_size(db_size)
            }
    
    def get_redis_metrics(self):
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        
        info = r.info()
        return {
            'used_memory_mb': info['used_memory'] / 1024 / 1024,
            'connected_clients': info['connected_clients'],
            'keyspace_hits': info['keyspace_hits'],
            'keyspace_misses': info['keyspace_misses']
        }
    
    def get_application_metrics(self):
        from patients.models import Patient
        from rag.models import Document
        from sessions.models import ConversationLog
        from datetime import datetime, timedelta
        
        now = datetime.now()
        today = now.date()
        hour_ago = now - timedelta(hours=1)
        
        return {
            'active_patients': Patient.objects.filter(is_active=True).count(),
            'documents_indexed_today': Document.objects.filter(
                created_at__date=today,
                pinecone_indexed=True
            ).count(),
            'conversations_last_hour': ConversationLog.objects.filter(
                timestamp__gte=hour_ago
            ).count()
        }
```

### 2. Alertes Intelligentes

```python
# metrics/alert_rules.py
from datetime import datetime, timedelta
from .models import SystemMetric, PerformanceAlert

class SmartAlertSystem:
    def __init__(self):
        self.rules = {
            'response_time_spike': self.check_response_time_spike,
            'error_rate_increase': self.check_error_rate_increase,
            'resource_exhaustion': self.check_resource_exhaustion,
            'service_degradation': self.check_service_degradation
        }
    
    def check_all_rules(self):
        """Exécuter toutes les règles d'alerte"""
        for rule_name, rule_func in self.rules.items():
            try:
                rule_func()
            except Exception as e:
                print(f"Erreur dans la règle {rule_name}: {e}")
    
    def check_response_time_spike(self):
        """Détecter les pics de temps de réponse"""
        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        last_24h = now - timedelta(days=1)
        
        # Moyenne dernière heure vs 24h
        recent_avg = SystemMetric.objects.filter(
            metric_type='response_time',
            timestamp__gte=last_hour
        ).aggregate(avg=models.Avg('value'))['avg'] or 0
        
        baseline_avg = SystemMetric.objects.filter(
            metric_type='response_time',
            timestamp__gte=last_24h,
            timestamp__lt=last_hour
        ).aggregate(avg=models.Avg('value'))['avg'] or 0
        
        if baseline_avg > 0 and recent_avg > baseline_avg * 2:
            self.create_alert(
                'response_time_spike',
                'high',
                f'Temps de réponse x2: {recent_avg:.0f}ms vs {baseline_avg:.0f}ms baseline',
                baseline_avg * 2,
                recent_avg
            )
    
    def check_error_rate_increase(self):
        """Détecter l'augmentation du taux d'erreur"""
        # Compter les erreurs dans les logs
        from django.contrib.admin.models import LogEntry
        
        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        
        error_count = LogEntry.objects.filter(
            action_time__gte=last_hour,
            content_type__model__in=['patient', 'document', 'broadcastmessage']
        ).count()
        
        if error_count > 10:  # Plus de 10 erreurs par heure
            self.create_alert(
                'error_rate_increase',
                'medium',
                f'Taux d\'erreur élevé: {error_count} erreurs dans la dernière heure',
                10,
                error_count
            )
    
    def create_alert(self, alert_type, severity, message, threshold, actual_value):
        """Créer une alerte si elle n'existe pas déjà"""
        existing = PerformanceAlert.objects.filter(
            metric_type=alert_type,
            resolved=False,
            created_at__gte=datetime.now() - timedelta(hours=1)
        ).exists()
        
        if not existing:
            PerformanceAlert.objects.create(
                metric_type=alert_type,
                severity=severity,
                message=message,
                threshold_value=threshold,
                actual_value=actual_value
            )
```

### 3. Dashboard de Performance Temps Réel

```python
# metrics/views.py - API pour dashboard temps réel
class RealTimeMetricsView(views.APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Métriques en temps réel pour le dashboard"""
        
        # Métriques des 5 dernières minutes
        five_min_ago = timezone.now() - timedelta(minutes=5)
        
        metrics = {
            'timestamp': timezone.now().isoformat(),
            'system': self.get_system_metrics(),
            'application': self.get_application_metrics(five_min_ago),
            'database': self.get_database_metrics(),
            'external_services': self.get_external_services_status()
        }
        
        return Response(metrics)
    
    def get_system_metrics(self):
        """Métriques système instantanées"""
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'load_average': psutil.getloadavg()[0]
        }
    
    def get_application_metrics(self, since):
        """Métriques application récentes"""
        recent_response_times = SystemMetric.objects.filter(
            metric_type='response_time',
            timestamp__gte=since
        ).values_list('value', flat=True)
        
        return {
            'avg_response_time': sum(recent_response_times) / len(recent_response_times) if recent_response_times else 0,
            'max_response_time': max(recent_response_times) if recent_response_times else 0,
            'total_requests': len(recent_response_times),
            'active_sessions': self.get_active_sessions_count()
        }
    
    def get_active_sessions_count(self):
        """Compter les sessions WhatsApp actives"""
        from sessions.models import WhatsAppSession
        
        return WhatsAppSession.objects.filter(
            status='active',
            last_activity__gte=timezone.now() - timedelta(minutes=30)
        ).count()
```

---

## 🔒 Sécurité et Conformité

### 1. Audit Trail Complet

```python
# core/audit.py
from django.db import models
from django.contrib.auth.models import User
import json

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Création'),
        ('UPDATE', 'Modification'),
        ('DELETE', 'Suppression'),
        ('VIEW', 'Consultation'),
        ('LOGIN', 'Connexion'),
        ('LOGOUT', 'Déconnexion'),
    ]
    
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True)
    changes = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp', 'user']),
            models.Index(fields=['model_name', 'action']),
        ]

def log_audit(user, action, model_name, object_id=None, changes=None, request=None):
    """Enregistrer une action d'audit"""
    AuditLog.objects.create(
        user=user,
        action=action,
        model_name=model_name,
        object_id=str(object_id) if object_id else '',
        changes=changes or {},
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else ''
    )

def get_client_ip(request):
    """Obtenir l'IP réelle du client"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
```

### 2. Chiffrement des Données Sensibles

```python
# core/encryption.py
from cryptography.fernet import Fernet
from django.conf import settings
import base64

class DataEncryption:
    def __init__(self):
        self.key = settings.ENCRYPTION_KEY.encode()
        self.cipher = Fernet(self.key)
    
    def encrypt(self, data):
        """Chiffrer des données sensibles"""
        if isinstance(data, str):
            data = data.encode()
        encrypted = self.cipher.encrypt(data)
        return base64.b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data):
        """Déchiffrer des données"""
        encrypted_bytes = base64.b64decode(encrypted_data.encode())
        decrypted = self.cipher.decrypt(encrypted_bytes)
        return decrypted.decode()

# patients/models.py - Champs chiffrés
class Patient(models.Model):
    # Champs normaux
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    
    # Champs sensibles chiffrés
    _encrypted_ssn = models.TextField(blank=True)  # Numéro sécurité sociale
    _encrypted_medical_notes = models.TextField(blank=True)
    
    @property
    def ssn(self):
        if self._encrypted_ssn:
            encryption = DataEncryption()
            return encryption.decrypt(self._encrypted_ssn)
        return ""
    
    @ssn.setter
    def ssn(self, value):
        if value:
            encryption = DataEncryption()
            self._encrypted_ssn = encryption.encrypt(value)
        else:
            self._encrypted_ssn = ""
```

Cette documentation complète couvre maintenant tous les aspects critiques du système MediRecord SIS, de l'installation à la maintenance en production, en passant par le troubleshooting avancé et les optimisations de performance. Le système est maintenant prêt pour un déploiement professionnel avec une surveillance complète et des mécanismes de récupération robustes.
