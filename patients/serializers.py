# patients/serializers.py

from rest_framework import serializers
from .models import Patient

class PatientCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "date_of_birth",
            "gender",
            "address",
            "emergency_contact",
            "emergency_phone",
            "medical_history",
            "allergies",
            "current_medications",
        ]
        extra_kwargs = {
            "first_name": {"required": True},
            "last_name": {"required": True},
            "phone": {"required": True},
        }

    def create(self, validated_data):
        # The activation_token and is_active will use defaults from the model.
        return Patient.objects.create(**validated_data)
