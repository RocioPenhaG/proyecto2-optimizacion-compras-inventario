from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProveedorViewSet, ProductoViewSet, estadisticas_productos

router = DefaultRouter()
router.register(r"proveedores", ProveedorViewSet)
router.register(r"productos", ProductoViewSet)

urlpatterns = [
    path("estadisticas/", estadisticas_productos),
    path("", include(router.urls)),
]