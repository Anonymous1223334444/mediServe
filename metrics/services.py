import time
from typing import Dict, Any
from .models import SystemMetric, PerformanceAlert
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class MetricsService:
    """Service pour enregistrer et analyser les métriques système"""
    
    @staticmethod
    def record_response_time(response_time_ms: float, endpoint: str = ""):
        """Enregistre le temps de réponse d'une API"""
        SystemMetric.objects.create(
            metric_type='response_time',
            value=response_time_ms,
            metadata={'endpoint': endpoint}
        )
        
        # Vérifier les seuils d'alerte
        if response_time_ms > 5000:  # Plus de 5 secondes
            MetricsService._create_alert(
                'response_time',
                'high' if response_time_ms < 10000 else 'critical',
                f"Temps de réponse élevé: {response_time_ms}ms sur {endpoint}",
                5000,
                response_time_ms
            )
    
    @staticmethod
    def record_rag_accuracy(accuracy_score: float, query: str = ""):
        """Enregistre la précision d'une réponse RAG"""
        SystemMetric.objects.create(
            metric_type='rag_accuracy',
            value=accuracy_score,
            metadata={'query_sample': query[:100]}
        )
    
    @staticmethod
    def record_document_indexing(success: bool, document_id: str, processing_time_ms: float):
        """Enregistre les métriques d'indexation de document"""
        SystemMetric.objects.create(
            metric_type='document_indexing',
            value=1.0 if success else 0.0,
            metadata={
                'document_id': document_id,
                'processing_time_ms': processing_time_ms,
                'success': success
            }
        )
    
    @staticmethod
    def record_message_delivery(success: bool, phone_number: str, message_type: str):
        """Enregistre les métriques de livraison de message"""
        SystemMetric.objects.create(
            metric_type='message_delivery',
            value=1.0 if success else 0.0,
            metadata={
                'phone_number': phone_number,
                'message_type': message_type,
                'success': success
            }
        )
    
    @staticmethod
    def _create_alert(metric_type: str, severity: str, message: str, 
                     threshold: float, actual_value: float):
        """Crée une alerte de performance"""
        PerformanceAlert.objects.create(
            metric_type=metric_type,
            severity=severity,
            message=message,
            threshold_value=threshold,
            actual_value=actual_value
        )
        
        # Log l'alerte
        logger.warning(f"ALERTE {severity.upper()}: {message}")

class PerformanceMonitor:
    """Décorateur pour monitorer les performances d'une fonction"""
    
    def __init__(self, metric_name: str, endpoint: str = ""):
        self.metric_name = metric_name
        self.endpoint = endpoint
    
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                success = True
            except Exception as e:
                success = False
                raise e
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                if self.metric_name == 'response_time':
                    MetricsService.record_response_time(duration_ms, self.endpoint)
                elif self.metric_name == 'document_indexing':
                    MetricsService.record_document_indexing(
                        success, 
                        kwargs.get('document_id', ''), 
                        duration_ms
                    )
            
            return result
        return wrapper

