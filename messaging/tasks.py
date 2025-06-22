from celery import shared_task
from django.utils import timezone
from .models import BroadcastMessage, MessageDelivery
from patients.models import Patient
from .services import WhatsAppService
import logging
from datetime import datetime, timedelta
from metrics.models import SystemMetric, PerformanceAlert


logger = logging.getLogger(__name__)

@shared_task
def send_broadcast_message_async(broadcast_id):
    """Envoyer un message diffusé à tous les patients ciblés"""
    try:
        broadcast = BroadcastMessage.objects.get(id=broadcast_id)
        whatsapp_service = WhatsAppService()
        
        # Récupérer les patients ciblés
        patients = get_targeted_patients(broadcast)
        
        # Créer les entrées de livraison
        deliveries = []
        for patient in patients:
            delivery, created = MessageDelivery.objects.get_or_create(
                broadcast_message=broadcast,
                patient=patient,
                defaults={'status': 'pending'}
            )
            deliveries.append(delivery)
        
        # Envoyer les messages
        sent_count = 0
        failed_count = 0
        
        for delivery in deliveries:
            try:
                success = whatsapp_service.send_message(
                    delivery.patient.phone,
                    broadcast.content
                )
                
                if success:
                    delivery.status = 'sent'
                    delivery.sent_at = timezone.now()
                    sent_count += 1
                else:
                    delivery.status = 'failed'
                    delivery.error_message = "Échec envoi WhatsApp"
                    failed_count += 1
                    
            except Exception as e:
                delivery.status = 'failed'
                delivery.error_message = str(e)
                failed_count += 1
                logger.error(f"Erreur envoi à {delivery.patient.phone}: {e}")
            
            delivery.save()
        
        # Mettre à jour le statut du broadcast
        broadcast.status = 'sent'
        broadcast.sent_at = timezone.now()
        broadcast.save()
        
        logger.info(f"Broadcast {broadcast_id} terminé: {sent_count} succès, {failed_count} échecs")
        
    except Exception as e:
        logger.error(f"Erreur broadcast {broadcast_id}: {e}")
        try:
            broadcast = BroadcastMessage.objects.get(id=broadcast_id)
            broadcast.status = 'failed'
            broadcast.save()
        except:
            pass

def get_targeted_patients(broadcast):
    """Récupérer les patients ciblés selon les filtres"""
    queryset = Patient.objects.filter(is_active=True)
    
    if not broadcast.target_all_patients:
        if broadcast.target_gender:
            queryset = queryset.filter(gender=broadcast.target_gender)
        
        if broadcast.target_age_min:
            # Calculer la date de naissance max pour l'âge min
            max_birth_date = timezone.now().date() - timedelta(days=broadcast.target_age_min * 365)
            queryset = queryset.filter(date_of_birth__lte=max_birth_date)
        
        if broadcast.target_age_max:
            # Calculer la date de naissance min pour l'âge max
            min_birth_date = timezone.now().date() - timedelta(days=broadcast.target_age_max * 365)
            queryset = queryset.filter(date_of_birth__gte=min_birth_date)
    
    return queryset

@shared_task
def process_scheduled_messages():
    """Traiter les messages programmés dont l'heure est arrivée"""
    now = timezone.now()
    scheduled_messages = BroadcastMessage.objects.filter(
        status='scheduled',
        scheduled_at__lte=now
    )
    
    for message in scheduled_messages:
        message.status = 'sending'
        message.save()
        send_broadcast_message_async.delay(message.id)

@shared_task
def analyze_message_engagement():
    """Analyse l'engagement des messages diffusés"""
    try:
        from .models import BroadcastMessage, MessageDelivery
        from datetime import timedelta
        
        # Analyser les messages des 7 derniers jours
        week_ago = timezone.now() - timedelta(days=7)
        
        recent_messages = BroadcastMessage.objects.filter(
            sent_at__gte=week_ago,
            status='sent'
        )
        
        engagement_data = []
        
        for message in recent_messages:
            deliveries = message.deliveries.all()
            total_sent = deliveries.filter(status='sent').count()
            total_delivered = deliveries.filter(status='delivered').count()
            
            engagement_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
            
            engagement_data.append({
                'message_id': message.id,
                'title': message.title,
                'category': message.category,
                'total_sent': total_sent,
                'total_delivered': total_delivered,
                'engagement_rate': round(engagement_rate, 2)
            })
        
        # Enregistrer comme métrique
        if engagement_data:
            avg_engagement = sum(item['engagement_rate'] for item in engagement_data) / len(engagement_data)
            SystemMetric.objects.create(
                metric_type='message_engagement',
                value=avg_engagement,
                metadata={'detailed_data': engagement_data}
            )
        
        return {"analyzed_messages": len(engagement_data)}
        
    except Exception as e:
        logger.error(f"Erreur analyse engagement: {e}")
        return {"error": str(e)}

@shared_task
def generate_content_suggestions():
    """Génère des suggestions de contenu basées sur les conversations"""
    try:
        from sessions.models import ConversationLog
        from collections import Counter
        import re
        
        # Analyser les conversations récentes
        recent_conversations = ConversationLog.objects.filter(
            timestamp__gte=timezone.now() - timedelta(days=7)
        )
        
        # Extraire les mots-clés des questions patients
        keywords = []
        for conv in recent_conversations:
            # Extraire les mots significatifs (plus de 3 caractères)
            words = re.findall(r'\b\w{4,}\b', conv.user_message.lower())
            keywords.extend(words)
        
        # Compter les mots les plus fréquents
        word_counts = Counter(keywords)
        most_common = word_counts.most_common(10)
        
        # Générer des suggestions de contenu
        suggestions = []
        for word, count in most_common:
            suggestions.append({
                'keyword': word,
                'frequency': count,
                'suggested_topic': f"Conseil santé sur: {word}"
            })
        
        # Sauvegarder les suggestions
        SystemMetric.objects.create(
            metric_type='content_suggestions',
            value=len(suggestions),
            metadata={'suggestions': suggestions}
        )
        
        return {"suggestions_generated": len(suggestions)}
        
    except Exception as e:
        logger.error(f"Erreur génération suggestions: {e}")
        return {"error": str(e)}
