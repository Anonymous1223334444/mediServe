from django.db import models
from django.contrib.auth.models import User
from patients.models import Patient

class BroadcastMessage(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('scheduled', 'Programmé'),
        ('sending', 'En cours d\'envoi'),
        ('sent', 'Envoyé'),
        ('failed', 'Échec'),
    ]
    
    CATEGORY_CHOICES = [
        ('health_tip', 'Conseil santé'),
        ('reminder', 'Rappel'),
        ('alert', 'Alerte'),
        ('info', 'Information'),
        ('prevention', 'Prévention'),
    ]
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Filtres de ciblage
    target_all_patients = models.BooleanField(default=True)
    target_gender = models.CharField(max_length=10, blank=True, choices=[('M', 'Homme'), ('F', 'Femme')])
    target_age_min = models.IntegerField(null=True, blank=True)
    target_age_max = models.IntegerField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"

class MessageDelivery(models.Model):
    DELIVERY_STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('sent', 'Envoyé'),
        ('delivered', 'Livré'),
        ('failed', 'Échec'),
    ]
    
    broadcast_message = models.ForeignKey(BroadcastMessage, on_delete=models.CASCADE, related_name='deliveries')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=DELIVERY_STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['broadcast_message', 'patient']

