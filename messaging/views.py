from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.utils import timezone
from .models import BroadcastMessage, MessageDelivery
from .serializers import BroadcastMessageSerializer
from .tasks import send_broadcast_message_async
from patients.models import Patient

class BroadcastMessageViewSet(viewsets.ModelViewSet):
    queryset = BroadcastMessage.objects.all().order_by('-created_at')
    serializer_class = BroadcastMessageSerializer
    permission_classes = [AllowAny]
    
    @action(detail=True, methods=['post'])
    def send_now(self, request, pk=None):
        """Envoyer un message immédiatement"""
        message = self.get_object()
        
        if message.status != 'draft':
            return Response(
                {"error": "Seuls les messages en brouillon peuvent être envoyés"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Marquer comme en cours d'envoi
        message.status = 'sending'
        message.save()
        
        # Lancer l'envoi asynchrone
        send_broadcast_message_async.delay(message.id)
        
        return Response({
            "message": "Envoi démarré",
            "status": message.status
        })
    
    @action(detail=True, methods=['post'])
    def schedule(self, request, pk=None):
        """Programmer un message pour plus tard"""
        message = self.get_object()
        scheduled_at = request.data.get('scheduled_at')
        
        if not scheduled_at:
            return Response(
                {"error": "scheduled_at requis"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        message.scheduled_at = scheduled_at
        message.status = 'scheduled'
        message.save()
        
        return Response({
            "message": "Message programmé",
            "scheduled_at": message.scheduled_at
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques des messages"""
        total_messages = BroadcastMessage.objects.count()
        sent_messages = BroadcastMessage.objects.filter(status='sent').count()
        pending_messages = BroadcastMessage.objects.filter(status__in=['draft', 'scheduled']).count()
        
        return Response({
            "total_messages": total_messages,
            "sent_messages": sent_messages,
            "pending_messages": pending_messages,
            "success_rate": (sent_messages / total_messages * 100) if total_messages > 0 else 0
        })
