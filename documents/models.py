from django.db import models
from patients.models import Patient
import os
from django.utils.text import slugify

def patient_document_path(instance, filename):
    """Génère le chemin de destination pour les documents des patients"""
    # Format : patient_documents/patient_ID_Prenom_Nom/filename
    patient = instance.patient
    # Nettoyer les noms pour éviter les caractères spéciaux
    first_name = slugify(patient.first_name)
    last_name = slugify(patient.last_name)
    folder_name = f"patient_{patient.id}_{first_name}_{last_name}"
    return os.path.join('patient_documents', folder_name, filename)

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