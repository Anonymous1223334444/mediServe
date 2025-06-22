from django.urls import path
from .views import (
    PatientCreateAPIView,
    PatientConfirmAPIView,
    ActivateRedirectView,
    PatientCheckActiveAPIView,
    PatientListAPIView,
    PatientIndexingStatusView, 
    DocumentIndexingStatusView,
    DocumentRetryView
)

urlpatterns = [
    path('api/patients/', PatientCreateAPIView.as_view(), name='patient-create'),
    path('api/patients/list/', PatientListAPIView.as_view(), name='patient-list'),
    path('api/patients/confirm/', PatientConfirmAPIView.as_view(), name='patient-confirm'),
    path('api/patients/check-active/', PatientCheckActiveAPIView.as_view(), name='patient-check-active'),
    path('api/patients/activate/<uuid:token>/', ActivateRedirectView.as_view(), name='patient-activate'),
    path('api/patients/<int:patient_id>/indexing-status/', 
         PatientIndexingStatusView.as_view(), 
         name='patient-indexing-status'),
    path('api/documents/<int:document_id>/status/', 
         DocumentIndexingStatusView.as_view(), 
         name='document-status'),
    path('api/documents/<int:document_id>/retry/', 
     DocumentRetryView.as_view(), 
     name='document-retry'),
]