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
            return int(obj.producto.stock.qty_on_hand)
        except (ObjectDoesNotExist, AttributeError, TypeError, ValueError):
            return 0

    def _stock_disponible(self, producto) -> int:
        try:
            return int(producto.stock.qty_on_hand)
        except Exception:
            return 0

    def validate(self, attrs):
        tipo = attrs.get("tipo")
        if self.instance is not None:
            tipo = tipo or self.instance.tipo
        cantidad = attrs.get("cantidad")
        if self.instance is not None and cantidad is None:
            cantidad = self.instance.cantidad
        producto = attrs.get("producto")
        if self.instance is not None and producto is None:
            producto = self.instance.producto

        if cantidad is not None and cantidad <= 0:
            raise serializers.ValidationError({"cantidad": "La cantidad debe ser mayor a 0."})

        if tipo == "OUT" and producto is not None and cantidad is not None:
            disponible = self._stock_disponible(producto)
            if disponible <= 0:
                raise serializers.ValidationError(
                    {
                        "cantidad": "No hay stock disponible para este producto (stock actual: 0). "
                        "Registre una entrada antes de hacer una salida.",
                    }
                )
            if cantidad > disponible:
                raise serializers.ValidationError(
                    {
                        "cantidad": f"Stock insuficiente. Disponible: {disponible}.",
                    }
                )
        return attrs

    def create(self, validated_data):
        # Asignar usuario autenticado automáticamente al movimiento
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['usuario'] = request.user
        return super().create(validated_data)