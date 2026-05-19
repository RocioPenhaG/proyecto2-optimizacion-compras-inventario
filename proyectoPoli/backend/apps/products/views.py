from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.models import Role
from apps.users.permissions import IsNotFuncionario, ProductoProveedorWriteOrReadOnly

from .models import Proveedor, Producto
from .serializers import ProveedorSerializer, ProductoCatalogoSerializer, ProductoSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsNotFuncionario])
def estadisticas_productos(request):
    """Cuenta de productos con stock por debajo del mínimo (para panel/alertas)."""
    productos = Producto.objects.filter(stock_minimo__gt=0).select_related("stock")
    count = 0
    for p in productos:
        try:
            qty = int(p.stock.qty_on_hand)
        except Exception:
            qty = 0
        if qty <= p.stock_minimo:
            count += 1
    return Response({"productos_stock_critico": count})

class ProveedorViewSet(viewsets.ModelViewSet):
    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer
    permission_classes = [IsAuthenticated, ProductoProveedorWriteOrReadOnly]


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.select_related("proveedor", "stock").all()
    permission_classes = [IsAuthenticated, ProductoProveedorWriteOrReadOnly]

    def get_serializer_class(self):
        if (
            getattr(self.request.user, "role", None) == Role.FUNCIONARIO
            and self.action in ("list", "retrieve")
        ):
            return ProductoCatalogoSerializer
        return ProductoSerializer