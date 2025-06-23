from django.db import models
from patients.models import Patient
import os

def patient_document_path(instance, filename):
    """Génère le chemin de destination pour les documents des patients"""
    # Format : patient_documents/patient_ID_NAME/filename
    # patient_folder = f"patient_{instance.patient.id}_{instance.patient.first_name}{instance.patient.last_name}"
    # return os.path.join('patient_documents', patient_folder, filename)
    return f"patient_documents/patient_{instance.patient.id}/{filename}"

class DocumentUpload(models.Model):
    STATUS_CHOICES = [
    ('pending', 'En attente'),
    ('processing', 'En traitement'),
    ('indexed', 'Indexé'),
    ('failed', 'Échec'),
    ]
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='uploaded_documents')
    # Modifier cette ligne pour utiliser la fonction personnalisée
    file = models.FileField(upload_to=patient_document_path)
    celery_task_id = models.CharField(max_length=255, blank=True, null=True, 
                                  help_text="ID de la tâche Celery pour le suivi")
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20)
    file_size = models.IntegerField()
    upload_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.patient.full_name()} - {self.original_filename}"