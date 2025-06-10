from rest_framework import views
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .health_checks import HealthChecker

class HealthCheckView(views.APIView):
    """
    GET /api/health/
    Endpoint de vérification de santé du système
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        health_status = HealthChecker.run_all_checks()
        
        # Status HTTP basé sur la santé globale
        status_code = 200 if health_status['overall_status'] == 'healthy' else 503
        
        return Response(health_status, status=status_code)
