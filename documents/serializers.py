from rest_framework import serializers
from .models import DocumentUpload

class DocumentUploadSerializer(serializers.ModelSerializer):
    file = serializers.FileField()
    
    class Meta:
        model = DocumentUpload
        fields = ['id', 'file', 'original_filename', 'file_type', 'file_size', 'upload_status']
        read_only_fields = ['id', 'upload_status']
    
    def create(self, validated_data):
        # Extraire les métadonnées du fichier
        file = validated_data['file']
        validated_data['original_filename'] = file.name
        validated_data['file_size'] = file.size
        validated_data['file_type'] = file.name.split('.')[-1].lower()
        
        return super().create(validated_data)