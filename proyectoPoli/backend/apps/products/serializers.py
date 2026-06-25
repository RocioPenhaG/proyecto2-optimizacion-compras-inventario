from django.db import transaction
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
    stock_inicial = serializers.IntegerField(required=False, min_value=0, write_only=True, default=0)
    solicitud_id = serializers.IntegerField(required=False, min_value=1, write_only=True, allow_null=True)

    class Meta:
        model = Producto
        fields = '__all__'

    def validate(self, attrs):
        solicitud_id = attrs.get("solicitud_id")
        stock_inicial = int(attrs.get("stock_inicial") or 0)
        if self.instance is None and solicitud_id is not None:
            from apps.purchases.models import SolicitudInsumo, TipoDestinoCompra

            try:
                solicitud = SolicitudInsumo.objects.get(pk=solicitud_id)
            except SolicitudInsumo.DoesNotExist:
                raise serializers.ValidationError(
                    {"solicitud_id": "La solicitud indicada no existe."}
                )
            if not solicitud.tipo_destino_compra:
                raise serializers.ValidationError(
                    {
                        "solicitud_id": "Compras debe definir el destino de compra antes de "
                        "crear el producto.",
                    }
                )
            if solicitud.tipo_destino_compra == TipoDestinoCompra.ENTREGA_INMEDIATA:
                attrs["stock_minimo"] = 0
            elif solicitud.tipo_destino_compra == TipoDestinoCompra.INVENTARIO:
                stock_minimo = int(attrs.get("stock_minimo") or 0)
                if stock_minimo < 1:
                    raise serializers.ValidationError(
                        {
                            "stock_minimo": "Indique el stock mínimo para activar el control "
                            "de inventario.",
                        }
                    )
            if stock_inicial < 1:
                raise serializers.ValidationError(
                    {"stock_inicial": "Indique las unidades compradas para el stock inicial."}
                )
        return attrs

    def create(self, validated_data):
        stock_inicial = int(validated_data.pop("stock_inicial", 0) or 0)
        solicitud_id = validated_data.pop("solicitud_id", None)
        if not str(validated_data.get("sku", "")).strip():
            validated_data.pop("sku", None)
        else:
            validated_data["sku"] = str(validated_data["sku"]).strip()

        request = self.context.get("request")
        with transaction.atomic():
            producto = super().create(validated_data)
            if solicitud_id is not None and stock_inicial > 0:
                from apps.inventory.models import MovStock

                MovStock.objects.create(
                    producto=producto,
                    tipo="IN",
                    cantidad=stock_inicial,
                    ref_tipo="SOLICITUD",
                    ref_id=solicitud_id,
                    observacion=f"Entrada inicial al crear producto para solicitud #{solicitud_id}",
                    usuario=request.user if request and request.user.is_authenticated else None,
                )
        return producto

    def update(self, instance, validated_data):
        if "sku" in validated_data:
            if not str(validated_data.get("sku", "")).strip():
                validated_data.pop("sku", None)
            else:
                validated_data["sku"] = str(validated_data["sku"]).strip()
        return super().update(instance, validated_data)

    def get_stock_actual(self, obj):
        try:
            return int(obj.stock.qty_on_hand)
        except Exception:
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