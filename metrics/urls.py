from django.urls import path
from .views import MetricsDashboardAPIView

urlpatterns = [
    path('api/metrics/dashboard/', MetricsDashboardAPIView.as_view(), name='metrics-dashboard'),
]