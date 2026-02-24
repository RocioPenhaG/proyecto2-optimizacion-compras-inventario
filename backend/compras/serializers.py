from rest_framework import serializers
from .models import SolicitudCompra, SolicitudCompraItem


class SolicitudCompraItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SolicitudCompraItem
        fields = [
            "id",
            "solicitud",
            "descripcion",
            "cantidad",
            "precio_estimado",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "solicitud", "created_at", "updated_at"]


class SolicitudCompraSerializer(serializers.ModelSerializer):
    solicitante_username = serializers.CharField(source="solicitante.username", read_only=True)
    aprobado_por_username = serializers.CharField(source="aprobado_por.username", read_only=True)
    rechazado_por_username = serializers.CharField(source="rechazado_por.username", read_only=True)

    items = SolicitudCompraItemSerializer(many=True, read_only=True)

    total_estimado = serializers.SerializerMethodField()

    def get_total_estimado(self, obj):
        # suma cantidad * precio_estimado
        total = 0
        for it in obj.items.all():
            total += float(it.cantidad) * float(it.precio_estimado)
        return total

    class Meta:
        model = SolicitudCompra
        fields = [
            "id",
            "titulo",
            "descripcion",
            "estado",
            "solicitante",
            "solicitante_username",
            "created_at",
            "updated_at",
            "aprobado_por",
            "aprobado_por_username",
            "aprobado_at",
            "rechazado_por",
            "rechazado_por_username",
            "rechazado_at",
            "items",
            "total_estimado",
            "departamento",
            "tipo_producto",
            "marca_recomendada",
            "proveedor_recomendado",
            "tamano",
            "medidas",
            "cantidad_texto",
            "destino_producto",
            "firma_encargado",
        ]
        read_only_fields = [
            "id",
            "estado",
            "solicitante",
            "created_at",
            "updated_at",
            "solicitante_username",
            "aprobado_por",
            "aprobado_por_username",
            "aprobado_at",
            "rechazado_por",
            "rechazado_por_username",
            "rechazado_at",
            "items",
            "total_estimado",
        ]
