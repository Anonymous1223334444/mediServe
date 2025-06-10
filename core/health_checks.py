import logging
from typing import Dict, Any
from django.db import connection
from django.core.cache import cache
from django.conf import settings
import redis
import requests
from patients.n8n_manager import N8NWorkflowManager
import time

logger = logging.getLogger('medirecord.health')

class HealthChecker:
    """Vérificateur de santé des services"""
    
    @staticmethod
    def check_database() -> Dict[str, Any]:
        """Vérifier la connexion à la base de données"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
            
            return {
                'status': 'healthy',
                'message': 'Database connection OK',
                'details': {'result': result[0] if result else None}
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'unhealthy',
                'message': f'Database connection failed: {str(e)}',
                'details': {}
            }
    
    @staticmethod
    def check_redis() -> Dict[str, Any]:
        """Vérifier la connexion à Redis"""
        try:
            cache.set('health_check', 'test', 30)
            value = cache.get('health_check')
            
            if value == 'test':
                return {
                    'status': 'healthy',
                    'message': 'Redis connection OK',
                    'details': {}
                }
            else:
                raise Exception("Redis test value mismatch")
                
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                'status': 'unhealthy',
                'message': f'Redis connection failed: {str(e)}',
                'details': {}
            }
    
    @staticmethod
    def check_n8n() -> Dict[str, Any]:
        """Vérifier la connexion à N8N"""
        try:
            manager = N8NWorkflowManager()
            is_connected = manager.test_connection()
            
            if is_connected:
                return {
                    'status': 'healthy',
                    'message': 'N8N connection OK',
                    'details': {'base_url': manager.base_url}
                }
            else:
                raise Exception("N8N connection test failed")
                
        except Exception as e:
            logger.error(f"N8N health check failed: {e}")
            return {
                'status': 'unhealthy',
                'message': f'N8N connection failed: {str(e)}',
                'details': {}
            }
    
    @staticmethod
    def check_twilio() -> Dict[str, Any]:
        """Vérifier la connexion à Twilio"""
        try:
            from messaging.services import WhatsAppService
            
            # Test simple de connexion (sans envoyer de message)
            service = WhatsAppService()
            
            # Vérifier que les credentials sont configurés
            if not all([service.account_sid, service.auth_token, service.whatsapp_number]):
                raise Exception("Twilio credentials not configured")
            
            return {
                'status': 'healthy',
                'message': 'Twilio configuration OK',
                'details': {'account_sid': service.account_sid[:8] + '...'}
            }
            
        except Exception as e:
            logger.error(f"Twilio health check failed: {e}")
            return {
                'status': 'unhealthy',
                'message': f'Twilio check failed: {str(e)}',
                'details': {}
            }
    
    @staticmethod
    def check_pinecone() -> Dict[str, Any]:
        """Vérifier la connexion à Pinecone"""
        try:
            from rag.services import PineconeService
            
            service = PineconeService()
            # Test simple de connexion
            stats = service.index.describe_index_stats()
            
            return {
                'status': 'healthy',
                'message': 'Pinecone connection OK',
                'details': {
                    'total_vector_count': stats.total_vector_count,
                    'index_name': service.index_name
                }
            }
            
        except Exception as e:
            logger.error(f"Pinecone health check failed: {e}")
            return {
                'status': 'unhealthy',
                'message': f'Pinecone connection failed: {str(e)}',
                'details': {}
            }
    
    @staticmethod
    def check_gemini() -> Dict[str, Any]:
        """Vérifier la connexion à Gemini"""
        try:
            from rag.services import EmbeddingService
            
            service = EmbeddingService()
            # Test avec un texte court
            embedding = service.generate_embedding("test")
            
            if embedding and len(embedding) > 0:
                return {
                    'status': 'healthy',
                    'message': 'Gemini API OK',
                    'details': {'embedding_size': len(embedding)}
                }
            else:
                raise Exception("Empty embedding returned")
                
        except Exception as e:
            logger.error(f"Gemini health check failed: {e}")
            return {
                'status': 'unhealthy',
                'message': f'Gemini API failed: {str(e)}',
                'details': {}
            }
    
    @classmethod
    def run_all_checks(cls) -> Dict[str, Any]:
        """Exécuter toutes les vérifications de santé"""
        checks = {
            'database': cls.check_database(),
            'redis': cls.check_redis(),
            'n8n': cls.check_n8n(),
            'twilio': cls.check_twilio(),
            'pinecone': cls.check_pinecone(),
            'gemini': cls.check_gemini(),
        }
        
        # Déterminer la santé globale
        all_healthy = all(check['status'] == 'healthy' for check in checks.values())
        
        return {
            'overall_status': 'healthy' if all_healthy else 'unhealthy',
            'timestamp': time.time(),
            'checks': checks
        }