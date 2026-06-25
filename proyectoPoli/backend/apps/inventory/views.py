from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from rest_framework import status, viewsets, mixins
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.models import Role
from apps.users.permissions import InventoryAccess

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
    permission_classes = [IsAuthenticated, InventoryAccess]


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
    permission_classes = [IsAuthenticated, InventoryAccess]
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

    def destroy(self, request, *args, **kwargs):
        if request.user.role != Role.ADMINISTRADOR:
            return Response(
                {"detail": "Solo el administrador puede eliminar movimientos de inventario."},
                status=status.HTTP_403_FORBIDDEN,
            )
        instance = self.get_object()
        try:
            with transaction.atomic():
                instance.revertir_efecto_en_stock()
                instance.delete()
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)