from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import WhatsAppSession, ConversationLog
from patients.models import Patient
from django.utils import timezone
import uuid

class ConversationLogAPIView(views.APIView):
    """
    POST /api/conversations/log/
    Enregistre une conversation WhatsApp pour analytics
    Appelé depuis N8N après chaque échange
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        phone = request.data.get('phone')
        user_message = request.data.get('user_message')
        ai_response = request.data.get('ai_response')
        session_id = request.data.get('session_id')
        response_time = request.data.get('response_time_ms')
        
        if not all([phone, user_message, ai_response, session_id]):
            return Response(
                {"error": "phone, user_message, ai_response et session_id requis"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Récupérer ou créer la session
            patient = Patient.objects.get(phone=phone, is_active=True)
            session, created = WhatsAppSession.objects.get_or_create(
                session_id=session_id,
                defaults={
                    'patient': patient,
                    'phone_number': phone,
                    'status': 'active'
                }
            )
            
            # Enregistrer la conversation
            conversation = ConversationLog.objects.create(
                session=session,
                user_message=user_message,
                ai_response=ai_response,
                response_time_ms=response_time,
                message_length=len(user_message),
                response_length=len(ai_response)
            )
            
            return Response({
                "success": True,
                "conversation_id": conversation.id,
                "session_id": session.session_id
            })
            
        except Patient.DoesNotExist:
            return Response(
                {"error": "Patient non trouvé ou inactif"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Erreur lors de l'enregistrement: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SessionStatsAPIView(views.APIView):
    """
    GET /api/sessions/stats/
    Statistiques des sessions WhatsApp
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        from django.db.models import Count, Avg, Sum
        from datetime import timedelta
        
        # Statistiques générales
        total_sessions = WhatsAppSession.objects.count()
        active_sessions = WhatsAppSession.objects.filter(status='active').count()
        
        # Dernières 24h
        yesterday = timezone.now() - timedelta(days=1)
        recent_conversations = ConversationLog.objects.filter(
            timestamp__gte=yesterday
        ).count()
        
        # Temps de réponse moyen
        avg_response_time = ConversationLog.objects.filter(
            response_time_ms__isnull=False
        ).aggregate(avg_time=Avg('response_time_ms'))['avg_time'] or 0
        
        # Patients les plus actifs
        active_patients = ConversationLog.objects.filter(
            timestamp__gte=yesterday
        ).values(
            'session__patient__first_name',
            'session__patient__last_name'
        ).annotate(
            message_count=Count('id')
        ).order_by('-message_count')[:5]
        
        return Response({
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "conversations_24h": recent_conversations,
            "avg_response_time_ms": round(avg_response_time, 2),
            "most_active_patients": list(active_patients)
        })
