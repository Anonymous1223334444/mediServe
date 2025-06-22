import functools
import logging
import time
from typing import Callable, Any
from .exceptions import MediRecordBaseException
from metrics.services import MetricsService

logger = logging.getLogger('medirecord')

def log_execution(func_name: str = None):
    """Décorateur pour logger l'exécution des fonctions"""
    def decorator(func: Callable) -> Callable:
        name = func_name or f"{func.__module__}.{func.__name__}"
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            logger.info(f"Début exécution: {name}")
            
            try:
                result = func(*args, **kwargs)
                execution_time = (time.time() - start_time) * 1000
                
                logger.info(f"Fin exécution: {name} ({execution_time:.2f}ms)")
                MetricsService.record_response_time(execution_time, name)
                
                return result
                
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                logger.error(f"Erreur dans {name} après {execution_time:.2f}ms: {str(e)}")
                raise
                
        return wrapper
    return decorator

def retry_on_failure(max_retries: int = 3, delay: float = 1.0, 
                    exceptions: tuple = (Exception,)):
    """Décorateur pour retry automatique"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        logger.warning(
                            f"Tentative {attempt + 1}/{max_retries} échouée "
                            f"pour {func.__name__}: {str(e)}. Retry dans {delay}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"Toutes les tentatives échouées pour {func.__name__}: {str(e)}"
                        )
            
            raise last_exception
                
        return wrapper
    return decorator

def validate_input(schema: Dict[str, Any]):
    """Décorateur pour valider les entrées"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Validation basique (peut être étendue avec jsonschema)
            for key, requirements in schema.items():
                if key in kwargs:
                    value = kwargs[key]
                    
                    # Vérifier le type
                    if 'type' in requirements:
                        expected_type = requirements['type']
                        if not isinstance(value, expected_type):
                            raise ValueError(f"{key} doit être de type {expected_type.__name__}")
                    
                    # Vérifier si requis
                    if requirements.get('required', False) and value is None:
                        raise ValueError(f"{key} est requis")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

