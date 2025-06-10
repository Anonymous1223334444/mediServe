from django.urls import path
from .views import (
    PatientCreateAPIView,
    PatientConfirmAPIView,
    ActivateRedirectView,
    PatientCheckActiveAPIView,
    PatientListAPIView
)

urlpatterns = [
    path('api/patients/', PatientCreateAPIView.as_view(), name='patient-create'),
    path('api/patients/list/', PatientListAPIView.as_view(), name='patient-list'),
    path('api/patients/confirm/', PatientConfirmAPIView.as_view(), name='patient-confirm'),
    path('api/patients/check-active/', PatientCheckActiveAPIView.as_view(), name='patient-check-active'),
    path('activate/', ActivateRedirectView.as_view(), name='patient-activate'),
]