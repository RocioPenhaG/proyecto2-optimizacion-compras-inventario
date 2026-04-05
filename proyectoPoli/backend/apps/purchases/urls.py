from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SolicitudInsumoViewSet

router = DefaultRouter()
router.register(r"solicitudes", SolicitudInsumoViewSet, basename="solicitudinsumo")

urlpatterns = [
    path("", include(router.urls)),
]
