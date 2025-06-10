from django.urls import path
from .views import ConversationLogAPIView, SessionStatsAPIView

urlpatterns = [
    path('api/conversations/log/', ConversationLogAPIView.as_view(), name='conversation-log'),
    path('api/sessions/stats/', SessionStatsAPIView.as_view(), name='session-stats'),
]