import logging
import traceback
from typing import Dict, Any, Optional
from django.http import JsonResponse
from django.conf import settings
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from .exceptions import MediRecordBaseException
from metrics.services import MetricsService

logger = logging.getLogger('medirecord.errors')

def custom_exception_handler(exc, context):
    """Gestionnaire d'exceptions personnalisé pour DRF"""
    
    # Appeler le gestionnaire par défaut
    response = exception_handler(exc, context)
    
    # Log l'erreur
    log_error(exc, context)
    
    # Personnaliser la réponse pour nos exceptions
    if isinstance(exc, MediRecordBaseException):
        custom_response_data = {
            'error': {
                'message': exc.message,
                'code': exc.error_code,
                'details': exc.details,
                'type': exc.__class__.__name__
            }
        }
        
        # Déterminer le status code
        status_code = getattr(exc, 'status_code', status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(custom_response_data, status=status_code)
    
    # Améliorer les réponses d'erreur standard
    if response is not None:
        custom_response_data = {
            'error': {
                'message': get_error_message(exc),
                'details': response.data if hasattr(response, 'data') else {},
                'type': exc.__class__.__name__
            }
        }
        response.data = custom_response_data
    
    return response

def log_error(exc, context):
    """Log détaillé des erreurs"""
    request = context.get('request')
    view = context.get('view')
    
    error_info = {
        'exception_type': exc.__class__.__name__,
        'exception_message': str(exc),
        'request_path': request.path if request else 'N/A',
        'request_method': request.method if request else 'N/A',
        'user': str(request.user) if request and hasattr(request, 'user') else 'Anonymous',
        'view': str(view) if view else 'N/A',
        'traceback': traceback.format_exc()
    }
    
    # Log avec niveau approprié
    if isinstance(exc, MediRecordBaseException):
        logger.error(f"MediRecord Exception: {error_info}")
    else:
        logger.error(f"Unhandled Exception: {error_info}")
    
    # Enregistrer comme métrique
    MetricsService.record_error_metric(exc.__class__.__name__, str(exc))

def get_error_message(exc):
    """Extrait un message d'erreur approprié"""
    if hasattr(exc, 'message'):
        return exc.message
    elif hasattr(exc, 'detail'):
        return str(exc.detail)
    else:
        return str(exc)

