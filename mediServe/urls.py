"""
URL configuration for mediServe project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from core.views import HealthCheckView

router = DefaultRouter()

# from patients.views import PatientViewSet
# from documents.views import DocumentViewSet
# from sessions.views import SessionViewSet
# from rag.views import RAGQueryView
# from metrics.views import PatientMetricViewSet

# router.register(r'patients', PatientViewSet, basename='patients')
# router.register(r'documents', DocumentViewSet, basename='documents')
# router.register(r'sessions', SessionViewSet, basename='sessions')
# router.register(r'metrics', PatientMetricViewSet, basename='metrics')
from django.conf import settings
import requests
from django.http import HttpResponse, HttpResponseServerError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.urls import path, include
from rag.views import RAGQueryView
from patients.views import PatientConfirmAPIView, ActivateRedirectView
from messaging.twilio_webhook import twilio_webhook



def n8n_proxy(request, path):
    """Enhanced proxy with proper header handling"""
    n8n_url = f"http://localhost:5678/{path}"
    
    # Forward headers but remove potential conflicts
    headers = {
        key: value 
        for key, value in request.headers.items()
        if key.lower() not in ['host', 'content-length']
    }
    
    # Add X-Forwarded headers for proper proxy identification
    if 'HTTP_X_FORWARDED_FOR' in request.META:
        headers['X-Forwarded-For'] = request.META['HTTP_X_FORWARDED_FOR']
    if 'HTTP_X_FORWARDED_PROTO' in request.META:
        headers['X-Forwarded-Proto'] = request.META['HTTP_X_FORWARDED_PROTO']
    
    if settings.N8N_API_KEY:
        headers['X-N8N-API-KEY'] = settings.N8N_API_KEY
    
    try:
        resp = requests.request(
            method=request.method,
            url=n8n_url,
            headers=headers,
            data=request.body,
            params=request.GET,
            verify=False,
            timeout=30
        )
        return HttpResponse(
            resp.content, 
            status=resp.status_code, 
            content_type=resp.headers.get('Content-Type')
        )
    except requests.exceptions.RequestException as e:
        return HttpResponseServerError(f"Proxy error: {str(e)}")

schema_view = get_schema_view(
    openapi.Info(
        title="MediRecord API",
        default_version='v1',
        description="API for MediRecord SIS",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)
from messaging.whatsapp_rag_webhook import whatsapp_rag_webhook

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("patients.urls")),
    path("documents", include("documents.urls")),
    path('api/', include(router.urls)),
    path('api/health/', HealthCheckView.as_view(), name='health-check'),
    # path('api/rag/query/', RAGQueryView.as_view(), name='rag-query'),
    # path('api/auth/', include('users.urls')),
    path('api/webhook/twilio/', include('messaging.urls')),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/webhook/twilio/', whatsapp_rag_webhook, name='twilio-webhook'),
    path('api/rag/query/', RAGQueryView.as_view(), name='rag-query'),

    # Endpoints pour WhatsApp et activation
    path('api/patients/confirm/', PatientConfirmAPIView.as_view(), name='patient-confirm'),
    path('api/patients/activate/<uuid:token>/', ActivateRedirectView.as_view(), name='patient-activate'),
]

