from rest_framework import serializers
from .models import PatientMetric

class PatientMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientMetric
        fields = '__all__'
