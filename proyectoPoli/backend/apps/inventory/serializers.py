from rest_framework import serializers
from .models import StockProducto, MovStock

class StockProductoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_sku = serializers.CharField(source='producto.sku', read_only=True)

    class Meta:
        model = StockProducto
        fields = '__all__'

class MovStockSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    usuario_nombre = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model = MovStock
        fields = '__all__'
        read_only_fields = ['usuario']

    def create(self, validated_data):
        # Asignar usuario autenticado automáticamente al movimiento
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['usuario'] = request.user
        return super().create(validated_data)