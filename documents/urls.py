from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DocumentUploadViewSet

router = DefaultRouter()
router.register(r'documents', DocumentUploadViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
]
