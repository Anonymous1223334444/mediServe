from django.db import models
from patients.models import Patient

class Document(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='documents')
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_type = models.CharField(max_length=10, choices=[('pdf', 'PDF'), ('image', 'Image')])
    content_text = models.TextField(blank=True)
    pinecone_indexed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.patient.full_name()} - {self.file_name}"

class ConversationSession(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

class Message(models.Model):
    session = models.ForeignKey(ConversationSession, on_delete=models.CASCADE, related_name='messages')
    user_message = models.TextField()
    ai_response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    response_time = models.FloatField(null=True)  # For metrics
