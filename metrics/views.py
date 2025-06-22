from rest_framework import views
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Avg, Count
from datetime import datetime, timedelta
from django.utils import timezone
from .models import SystemMetric, PerformanceAlert

class MetricsDashboardAPIView(views.APIView):
    """
    GET /api/metrics/dashboard/
    Tableau de bord des métriques système
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        # Période d'analyse (dernières 24h par défaut)
        hours = int(request.GET.get('hours', 24))
        since = timezone.now() - timedelta(hours=hours)
        
        # Temps de réponse moyen
        avg_response_time = SystemMetric.objects.filter(
            metric_type='response_time',
            timestamp__gte=since
        ).aggregate(avg_time=Avg('value'))['avg_time'] or 0
        
        # Taux de succès indexation
        indexing_metrics = SystemMetric.objects.filter(
            metric_type='document_indexing',
            timestamp__gte=since
        )
        indexing_success_rate = 0
        if indexing_metrics.exists():
            total_indexing = indexing_metrics.count()
            successful_indexing = indexing_metrics.filter(value=1.0).count()
            indexing_success_rate = (successful_indexing / total_indexing) * 100
        
        # Taux de livraison messages
        delivery_metrics = SystemMetric.objects.filter(
            metric_type='message_delivery',
            timestamp__gte=since
        )
        delivery_success_rate = 0
        if delivery_metrics.exists():
            total_delivery = delivery_metrics.count()
            successful_delivery = delivery_metrics.filter(value=1.0).count()
            delivery_success_rate = (successful_delivery / total_delivery) * 100
        
        # Alertes actives
        active_alerts = PerformanceAlert.objects.filter(resolved=False).count()
        
        # Évolution des métriques (par heure)
        hourly_metrics = []
        for i in range(hours):
            hour_start = timezone.now() - timedelta(hours=i+1)
            hour_end = timezone.now() - timedelta(hours=i)
            
            hour_data = {
                'hour': hour_start.strftime('%H:00'),
                'response_time': SystemMetric.objects.filter(
                    metric_type='response_time',
                    timestamp__gte=hour_start,
                    timestamp__lt=hour_end
                ).aggregate(avg=Avg('value'))['avg'] or 0,
                'conversations': SystemMetric.objects.filter(
                    metric_type='response_time',
                    timestamp__gte=hour_start,
                    timestamp__lt=hour_end
                ).count()
            }
            hourly_metrics.append(hour_data)
        
        return Response({
            "period_hours": hours,
            "avg_response_time_ms": round(avg_response_time, 2),
            "indexing_success_rate": round(indexing_success_rate, 2),
            "delivery_success_rate": round(delivery_success_rate, 2),
            "active_alerts": active_alerts,
            "hourly_trends": list(reversed(hourly_metrics))
        })
