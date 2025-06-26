# patients/serializers.py

from rest_framework import serializers
from .models import Patient
import phonenumbers
import logging
logger = logging.getLogger(__name__)


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
        "email": {"required": False, "allow_blank": True, "allow_null": True},
        "date_of_birth": {"required": False, "allow_null": True},
        "gender": {"required": False, "allow_blank": True, "allow_null": True},
        "address": {"required": False, "allow_blank": True, "allow_null": True},
        "emergency_contact": {"required": False, "allow_blank": True, "allow_null": True},
        "emergency_phone": {"required": False, "allow_blank": True, "allow_null": True},
        "medical_history": {"required": False, "allow_blank": True, "allow_null": True},
        "allergies": {"required": False, "allow_blank": True, "allow_null": True},
        "current_medications": {"required": False, "allow_blank": True, "allow_null": True},
        }
        def validate_phone(self, value):
            try:
                logger.info(f"Validation du numéro de téléphone: {value}")
                
                # Si la valeur est None ou vide, lever une exception
                if not value:
                    raise serializers.ValidationError("Le numéro de téléphone est requis")
                
                # Nettoyer le numéro en enlevant les espaces et autres caractères non numériques
                cleaned_number = ''.join(c for c in value if c.isdigit() or c == '+')
                logger.info(f"Numéro nettoyé: {cleaned_number}")
                
                # Ajouter le + si nécessaire
                if not cleaned_number.startswith('+'):
                    cleaned_number = '+' + cleaned_number
                    logger.info(f"Ajout du +: {cleaned_number}")
                
                try:
                    # Essayer de parser le numéro de téléphone
                    phone_number = phonenumbers.parse(cleaned_number)
                    logger.info(f"Numéro parsé: {phone_number}")
                    
                    # Vérifier si le numéro est valide
                    is_valid = phonenumbers.is_valid_number(phone_number)
                    logger.info(f"Est valide: {is_valid}")
                    
                    if not is_valid:
                        raise serializers.ValidationError("Numéro de téléphone invalide")
                    
                    # Formater le numéro au format E.164
                    formatted_number = phonenumbers.format_number(phone_number, phonenumbers.PhoneNumberFormat.E164)
                    logger.info(f"Numéro formaté final: {formatted_number}")
                    formatted_number = formatted_number.replace(' ', '')
                    return formatted_number
                    
                except phonenumbers.NumberParseException as e:
                    logger.error(f"Erreur de parsing du numéro: {e}")
                    raise serializers.ValidationError(f"Format de numéro de téléphone invalide: {e}")
                    
            except Exception as e:
                logger.error(f"Erreur inattendue lors de la validation du numéro: {e}")
                raise serializers.ValidationError(f"Erreur lors de la validation du numéro: {str(e)}")