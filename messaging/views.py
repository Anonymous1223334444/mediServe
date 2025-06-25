from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import views
from django.utils import timezone
from .models import BroadcastMessage, MessageDelivery
from .serializers import BroadcastMessageSerializer
from .tasks import send_broadcast_message_async
from patients.models import Patient
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging

logger = logging.getLogger(__name__)

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

@method_decorator(csrf_exempt, name='dispatch')
class TwilioWhatsAppWebhook(views.APIView):
    """
    POST /api/webhook/twilio/whatsapp/
    Webhook pour recevoir les messages WhatsApp via Twilio
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Traite les messages WhatsApp entrants"""
        try:
            # Extraire les données Twilio
            from_number = request.data.get('From', '').replace('whatsapp:', '')
            to_number = request.data.get('To', '').replace('whatsapp:', '')
            message_body = request.data.get('Body', '').strip()
            message_sid = request.data.get('MessageSid')
            
            logger.info(f"Message WhatsApp reçu de {from_number}: {message_body}")
            
            # Vérifier si c'est un message d'activation
            if message_body.startswith('ACTIVER '):
                return self.handle_activation(from_number, message_body)
            
            # Vérifier si le patient est actif
            try:
                patient = Patient.objects.get(phone=from_number, is_active=True)
                return self.handle_patient_query(patient, message_body)
            except Patient.DoesNotExist:
                return self.send_whatsapp_response(
                    from_number,
                    "❌ Votre compte n'est pas encore activé. Veuillez cliquer sur le lien d'activation envoyé par SMS."
                )
                
        except Exception as e:
            logger.error(f"Erreur webhook WhatsApp: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def handle_activation(self, phone_number, message):
        """Gère l'activation du patient"""
        try:
            # Extraire le token
            parts = message.split(' ')
            if len(parts) != 2:
                return self.send_whatsapp_response(
                    phone_number,
                    "❌ Format invalide. Veuillez utiliser le lien d'activation envoyé par SMS."
                )
            
            token = parts[1]
            
            # Trouver et activer le patient
            patient = Patient.objects.get(activation_token=token, phone=phone_number)
            
            if patient.is_active:
                return self.send_whatsapp_response(
                    phone_number,
                    "✅ Votre compte est déjà activé ! Comment puis-je vous aider ?"
                )
            
            # Activer le patient
            patient.is_active = True
            patient.activated_at = timezone.now()
            patient.save()
            
            # Obtenir le nom de la structure
            structure_name = settings.HEALTH_STRUCTURE_NAME  # À définir dans settings
            
            # Envoyer le message de bienvenue personnalisé
            welcome_message = f"""✅ Bienvenue {patient.first_name} !

Votre espace santé {structure_name} est maintenant actif.

Je suis votre assistant médical personnel et je peux répondre à vos questions sur :
📄 Vos documents médicaux
💊 Vos traitements
🔬 Vos résultats d'examens
📋 Votre historique médical

Comment puis-je vous aider aujourd'hui ?"""
            
            return self.send_whatsapp_response(phone_number, welcome_message)
            
        except Patient.DoesNotExist:
            return self.send_whatsapp_response(
                phone_number,
                "❌ Token d'activation invalide. Veuillez vérifier votre SMS."
            )
    
    def handle_patient_query(self, patient, query):
        """Traite une requête patient via RAG"""
        try:
            from rag.services import RAGService
            from sessions.models import WhatsAppSession
            import uuid
            
            # Créer ou récupérer la session
            session_id = f"wa_{patient.id}_{uuid.uuid4().hex[:8]}"
            session, created = WhatsAppSession.objects.get_or_create(
                patient=patient,
                phone_number=patient.phone,
                defaults={'session_id': session_id, 'status': 'active'}
            )
            
            # Utiliser le service RAG
            rag_service = RAGService()
            response = rag_service.query(
                patient_id=patient.id,
                query=query,
                session_id=session.session_id
            )
            
            return self.send_whatsapp_response(patient.phone, response)
            
        except Exception as e:
            logger.error(f"Erreur RAG pour patient {patient.id}: {e}")
            return self.send_whatsapp_response(
                patient.phone,
                "Désolé, une erreur s'est produite. Veuillez réessayer ou contacter votre médecin."
            )
    
    def send_whatsapp_response(self, to_number, message):
        """Envoie une réponse WhatsApp"""
        try:
            from messaging.services import WhatsAppService
            whatsapp = WhatsAppService()
            whatsapp.send_message(to_number, message)
            
            return Response({"status": "sent"}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Erreur envoi WhatsApp: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
