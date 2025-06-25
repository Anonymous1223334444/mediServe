# patients/models.py

import uuid
from django.db import models
from django.utils import timezone
from datetime import date

class Patient(models.Model):
    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64)
    phone = models.CharField(max_length=32, unique=True)
    email = models.EmailField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=16, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    emergency_contact = models.CharField(max_length=128, blank=True, null=True)
    emergency_phone = models.CharField(max_length=32, blank=True, null=True)
    medical_history = models.TextField(blank=True, null=True)
    allergies = models.TextField(blank=True, null=True)
    current_medications = models.TextField(blank=True, null=True)

    # Automatically generate a UUID activation token
    activation_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    activation_link_clicked = models.BooleanField(
        default=False, 
        help_text="Indique si le patient a cliqué sur le lien d'activation"
    )
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(blank=True, null=True)

    # NEW: store the workflow ID that n8n returns when dynamically creating a workflow
    n8n_workflow_id = models.CharField(max_length=128, null=True, blank=True, help_text="ID du workflow n8n associé")

    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return f"{self.full_name()} ({self.phone})"
        
    def age(self):
        """Calcule l'âge du patient"""
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )