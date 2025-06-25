from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BroadcastMessageViewSet, TwilioWhatsAppWebhook

router = DefaultRouter()
router.register(r'broadcast', BroadcastMessageViewSet)

urlpatterns = [
    path('api/messaging/', include(router.urls)),
    path('api/webhook/twilio/whatsapp/', TwilioWhatsAppWebhook.as_view(), name='twilio-whatsapp-webhook'),
]