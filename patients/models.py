# patients/models.py

import uuid
from django.db import models

class Patient(models.Model):
    # —Existing fields—
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
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(blank=True, null=True)

    # NEW: store the workflow ID that n8n returns when dynamically creating a workflow
    n8n_workflow_id = models.CharField(max_length=64, blank=True, null=True)

    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return f"{self.full_name()} ({self.phone})"
