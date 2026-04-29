from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAuthenticated

from apps.users.permissions import IsNotFuncionario

from .models import StockProducto, MovStock
from .serializers import StockProductoSerializer, MovStockSerializer


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
    """
    queryset = MovStock.objects.select_related("producto", "usuario").all().order_by("-fecha")
    serializer_class = MovStockSerializer
    permission_classes = [IsAuthenticated, IsNotFuncionario]

    def get_queryset(self):
        queryset = super().get_queryset()
        orden_fecha = self.request.query_params.get("orden_fecha", "desc").strip().lower()
        if orden_fecha == "asc":
            return queryset.order_by("fecha")
        return queryset.order_by("-fecha")