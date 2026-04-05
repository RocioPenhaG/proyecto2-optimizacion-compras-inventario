from django.urls import path
from .views import dashboard_metrics

urlpatterns = [
    path("", dashboard_metrics),
]
