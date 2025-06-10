from django.db import models

class SystemMetric(models.Model):
    METRIC_TYPES = [
        ('response_time', 'Temps de réponse'),
        ('rag_accuracy', 'Précision RAG'),
        ('user_satisfaction', 'Satisfaction utilisateur'),
        ('message_delivery', 'Livraison message'),
        ('document_indexing', 'Indexation document'),
    ]
    
    metric_type = models.CharField(max_length=30, choices=METRIC_TYPES)
    value = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['metric_type', 'timestamp']),
        ]

class PerformanceAlert(models.Model):
    SEVERITY_CHOICES = [
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé'),
        ('critical', 'Critique'),
    ]
    
    metric_type = models.CharField(max_length=30)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    message = models.TextField()
    threshold_value = models.FloatField()
    actual_value = models.FloatField()
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
