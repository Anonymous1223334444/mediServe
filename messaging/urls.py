from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BroadcastMessageViewSet

router = DefaultRouter()
router.register(r'broadcast', BroadcastMessageViewSet)

urlpatterns = [
    path('api/messaging/', include(router.urls)),
]