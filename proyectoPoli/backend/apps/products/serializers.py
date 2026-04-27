from rest_framework import serializers
from .models import Proveedor, Producto

class ProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = '__all__'

class ProductoSerializer(serializers.ModelSerializer):
    sku = serializers.CharField(max_length=50, required=False, allow_blank=True)
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    stock_actual = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = '__all__'

    def create(self, validated_data):
        if not str(validated_data.get("sku", "")).strip():
            validated_data.pop("sku", None)
        else:
            validated_data["sku"] = str(validated_data["sku"]).strip()
        return super().create(validated_data)

    def get_stock_actual(self, obj):
        if hasattr(obj, 'stock'):
            return obj.stock.qty_on_hand
        return 0


class ProductoCatalogoSerializer(serializers.ModelSerializer):
    """Catálogo para solicitudes: sin cantidades ni umbrales de inventario."""

    proveedor_nombre = serializers.CharField(source="proveedor.nombre", read_only=True)

    class Meta:
        model = Producto
        fields = [
            "id",
            "sku",
            "nombre",
            "unidad",
            "categoria",
            "activo",
            "proveedor",
            "proveedor_nombre",
        ]