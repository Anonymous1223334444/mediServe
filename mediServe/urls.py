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
from django.conf import settings
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rag.views import RAGQueryView
from patients.views import PatientConfirmAPIView, ActivateRedirectView
from messaging.whatsapp_rag_webhook import whatsapp_rag_webhook

router = DefaultRouter()

schema_view = get_schema_view(
    openapi.Info(
        title="MediRecord API",
        default_version='v1',
        description="API for MediRecord SIS",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("patients.urls")),
    path("documents/", include("documents.urls")),
    path('api/', include(router.urls)),
    path('api/health/', HealthCheckView.as_view(), name='health-check'),
    
    # Authentication
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # RAG endpoint
    path('api/rag/query/', RAGQueryView.as_view(), name='rag-query'),
    
    # Patient activation
    path('api/patients/confirm/', PatientConfirmAPIView.as_view(), name='patient-confirm'),
    path('api/patients/activate/<uuid:token>/', ActivateRedirectView.as_view(), name='patient-activate'),
    
    # WEBHOOK TWILIO - Une seule route claire
    path('api/webhook/twilio/', whatsapp_rag_webhook, name='twilio-webhook'),
    
    # Autres endpoints messaging (sans conflit)
    path('api/messaging/', include('messaging.urls')),
    
    # Swagger
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
]