from django.db.models import Q

from rest_framework import viewsets, mixins
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from apps.users.permissions import IsNotFuncionario

from .models import StockProducto, MovStock
from .serializers import StockProductoSerializer, MovStockSerializer


class MovStockPagination(PageNumberPagination):
    """Listado de movimientos en el frontend (20 por página)."""

    page_size = 20
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 100


class StockProductoViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    ViewSet de solo lectura para consultar stock.
    El stock no se crea ni se edita manualmente aquí, se actualiza mediante los Movimientos (MovStock).
    """
    queryset = StockProducto.objects.select_related("producto").all()
    serializer_class = StockProductoSerializer
    permission_classes = [IsAuthenticated, IsNotFuncionario]


class MovStockViewSet(viewsets.ModelViewSet):
    """
    ViewSet para registrar entradas, salidas y ajustes de stock.
    Al crear un movimiento, la lógica del modelo actualiza la tabla StockProducto automáticamente.

    Listado (GET): respuesta paginada (20 ítems por defecto); ``?page=2`` y opcional ``page_size``.
    Filtro de producto: ``?buscar=texto`` coincide con nombre o SKU (insensible a mayúsculas).
    """
    queryset = MovStock.objects.select_related("producto", "producto__stock", "usuario").all().order_by(
        "-fecha"
    )
    serializer_class = MovStockSerializer
    permission_classes = [IsAuthenticated, IsNotFuncionario]
    pagination_class = MovStockPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        buscar = self.request.query_params.get("buscar", "").strip()
        if buscar:
            queryset = queryset.filter(
                Q(producto__nombre__icontains=buscar) | Q(producto__sku__icontains=buscar)
            )
        orden_fecha = self.request.query_params.get("orden_fecha", "desc").strip().lower()
        if orden_fecha == "asc":
            return queryset.order_by("fecha")
        return queryset.order_by("-fecha")