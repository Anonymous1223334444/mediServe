from django.db import models
from patients.models import Patient

class WhatsAppSession(models.Model):
    SESSION_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('expired', 'Expirée'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='whatsapp_sessions')
    session_id = models.CharField(max_length=100, unique=True)
    phone_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=SESSION_STATUS_CHOICES, default='active')
    last_activity = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)  # Pour stocker des infos additionnelles
    
    class Meta:
        unique_together = ['patient', 'session_id']
    
    def __str__(self):
        return f"{self.patient.full_name()} - {self.session_id}"

class ConversationLog(models.Model):
    session = models.ForeignKey(WhatsAppSession, on_delete=models.CASCADE, related_name='conversations')
    user_message = models.TextField()
    ai_response = models.TextField()
    response_time_ms = models.IntegerField(null=True)  # Temps de réponse en millisecondes
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Métadonnées pour analytics
    message_length = models.IntegerField(default=0)
    response_length = models.IntegerField(default=0)
    context_documents_used = models.IntegerField(default=0)
