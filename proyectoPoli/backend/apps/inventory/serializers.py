from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from .models import StockProducto, MovStock


class StockProductoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_sku = serializers.CharField(source='producto.sku', read_only=True)

    class Meta:
        model = StockProducto
        fields = '__all__'

class MovStockSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    usuario_nombre = serializers.CharField(source="usuario.username", read_only=True)
    stock_actual = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = MovStock
        fields = (
            "id",
            "fecha",
            "tipo",
            "producto",
            "cantidad",
            "ref_tipo",
            "ref_id",
            "observacion",
            "usuario",
            "producto_nombre",
            "usuario_nombre",
            "stock_actual",
        )
        read_only_fields = ["usuario"]

    def get_stock_actual(self, obj):
        """Stock vigente del producto (tabla StockProducto), no el saldo histórico al momento del movimiento."""
        try:
            return obj.producto.stock.qty_on_hand
        except ObjectDoesNotExist:
            return 0

    def create(self, validated_data):
        # Asignar usuario autenticado automáticamente al movimiento
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['usuario'] = request.user
        return super().create(validated_data)