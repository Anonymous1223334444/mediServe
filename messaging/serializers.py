from rest_framework import serializers
from .models import BroadcastMessage, MessageDelivery

class BroadcastMessageSerializer(serializers.ModelSerializer):
    deliveries_count = serializers.SerializerMethodField()
    sent_count = serializers.SerializerMethodField()
    
    class Meta:
        model = BroadcastMessage
        fields = [
            'id', 'title', 'content', 'category', 'status', 
            'scheduled_at', 'sent_at', 'created_at', 'updated_at',
            'target_all_patients', 'target_gender', 'target_age_min', 'target_age_max',
            'deliveries_count', 'sent_count'
        ]
    
    def get_deliveries_count(self, obj):
        return obj.deliveries.count()
    
    def get_sent_count(self, obj):
        return obj.deliveries.filter(status='sent').count()
