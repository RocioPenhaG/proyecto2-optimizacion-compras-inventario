from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StockProductoViewSet, MovStockViewSet

router = DefaultRouter()
router.register(r'stock', StockProductoViewSet, basename='stockproducto')
router.register(r'movimientos', MovStockViewSet)

urlpatterns = [
    path('', include(router.urls)),
]