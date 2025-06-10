from django.db import models
from patients.models import Patient
from django.core.files.storage import default_storage
import os

class DocumentUpload(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En traitement'),
        ('indexed', 'Indexé'),
        ('failed', 'Échec'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='uploaded_documents')
    file = models.FileField(upload_to='patient_documents/')
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20)
    file_size = models.IntegerField()
    upload_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.patient.full_name()} - {self.original_filename}"
