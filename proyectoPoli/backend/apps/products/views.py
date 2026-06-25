from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.purchases.models import SolicitudDetalle
from apps.users.models import Role
from apps.users.permissions import IsNotFuncionario, ProductoProveedorWriteOrReadOnly

from apps.purchases.stock_alerts import excluir_de_alerta_stock_critico

from .models import Proveedor, Producto, numero_sku_spk, renumerar_skus_spk_tras_eliminacion
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
        if qty <= p.stock_minimo and not excluir_de_alerta_stock_critico(p.id, qty):
            count += 1
    return Response({"productos_stock_critico": count})

class ProveedorViewSet(viewsets.ModelViewSet):
    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer
    permission_classes = [IsAuthenticated, ProductoProveedorWriteOrReadOnly]


ORDEN_PRODUCTOS_VALIDOS = frozenset({"creacion_asc", "creacion_desc"})


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.select_related("proveedor", "stock").all()
    permission_classes = [IsAuthenticated, ProductoProveedorWriteOrReadOnly]

    def get_queryset(self):
        qs = Producto.objects.select_related("proveedor", "stock").all()
        if self.action not in ("list", "retrieve"):
            return qs

        buscar = (self.request.query_params.get("buscar") or "").strip()
        if buscar:
            qs = qs.filter(
                Q(sku__icontains=buscar)
                | Q(nombre__icontains=buscar)
                | Q(categoria__icontains=buscar)
            )

        orden = (self.request.query_params.get("orden") or "creacion_asc").strip()
        if orden not in ORDEN_PRODUCTOS_VALIDOS:
            orden = "creacion_asc"

        if orden == "creacion_desc":
            return qs.order_by("-id")
        return qs.order_by("id")

    def get_serializer_class(self):
        if (
            getattr(self.request.user, "role", None) == Role.FUNCIONARIO
            and self.action in ("list", "retrieve")
        ):
            return ProductoCatalogoSerializer
        return ProductoSerializer

    def destroy(self, request, *args, **kwargs):
        if request.user.role != Role.ADMINISTRADOR:
            return Response(
                {"detail": "Solo el administrador puede eliminar productos."},
                status=status.HTTP_403_FORBIDDEN,
            )
        instance = self.get_object()
        numero_spk = numero_sku_spk(instance.sku)
        with transaction.atomic():
            SolicitudDetalle.objects.filter(producto=instance).update(producto=None)
            instance.delete()
            if numero_spk is not None:
                renumerar_skus_spk_tras_eliminacion(numero_spk)
        return Response(status=status.HTTP_204_NO_CONTENT)