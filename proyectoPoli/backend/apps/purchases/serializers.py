from rest_framework import serializers
from apps.products.models import Producto

from .models import SolicitudDetalle, SolicitudInsumo, EstadoSolicitud


class SolicitudDetalleSerializer(serializers.ModelSerializer):
    producto = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.all(), allow_null=True, required=False
    )
    producto_nombre = serializers.SerializerMethodField()
    producto_sku = serializers.SerializerMethodField()
    descripcion_insumo_solicitado = serializers.CharField(
        required=False, allow_blank=True, max_length=500, default=""
    )

    class Meta:
        model = SolicitudDetalle
        fields = (
            "id",
            "producto",
            "producto_nombre",
            "producto_sku",
            "descripcion_insumo_solicitado",
            "cantidad",
            "observacion",
        )

    def get_producto_nombre(self, obj):
        return obj.producto.nombre if obj.producto_id else ""

    def get_producto_sku(self, obj):
        return obj.producto.sku if obj.producto_id else ""

    def validate(self, attrs):
        producto = attrs.get("producto", None)
        if producto is None and self.instance:
            producto = self.instance.producto
        desc_raw = attrs.get("descripcion_insumo_solicitado")
        if desc_raw is None:
            desc_raw = self.instance.descripcion_insumo_solicitado if self.instance else ""
        desc = (desc_raw or "").strip()
        if producto is None and not desc:
            raise serializers.ValidationError(
                "Indique un producto del catálogo o una descripción del insumo (fuera de catálogo)."
            )
        if producto is not None:
            attrs["descripcion_insumo_solicitado"] = ""
        return attrs


class SolicitudInsumoSerializer(serializers.ModelSerializer):
    detalles = SolicitudDetalleSerializer(many=True)
    solicitante_nombre = serializers.CharField(source="solicitante.username", read_only=True)
    requiere_aprobacion_gerencia = serializers.SerializerMethodField()
    stock_cubre_solicitud = serializers.SerializerMethodField()

    class Meta:
        model = SolicitudInsumo
        fields = (
            "id",
            "fecha",
            "estado",
            "destino",
            "solicitante",
            "solicitante_nombre",
            "observacion",
            "creado_en",
            "aprobado_en",
            "motivo_rechazo",
            "detalles",
            "requiere_aprobacion_gerencia",
            "stock_cubre_solicitud",
        )
        read_only_fields = (
            "solicitante",
            "fecha",
            "creado_en",
            "aprobado_en",
            "requiere_aprobacion_gerencia",
            "stock_cubre_solicitud",
        )

    def get_requiere_aprobacion_gerencia(self, obj):
        from .rules import solicitud_requiere_gerencia

        return solicitud_requiere_gerencia(obj)

    def get_stock_cubre_solicitud(self, obj):
        from .rules import solicitud_cubierta_por_stock

        return solicitud_cubierta_por_stock(obj)

    def create(self, validated_data):
        detalles_data = validated_data.pop("detalles")
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Usuario no autenticado")
        validated_data["solicitante"] = request.user
        validated_data["estado"] = EstadoSolicitud.SOLICITADO
        solicitud = SolicitudInsumo.objects.create(**validated_data)
        for d in detalles_data:
            SolicitudDetalle.objects.create(solicitud=solicitud, **d)
        return solicitud


class SolicitudInsumoListSerializer(serializers.ModelSerializer):
    solicitante_nombre = serializers.CharField(source="solicitante.username", read_only=True)
    cantidad_items = serializers.SerializerMethodField()
    requiere_aprobacion_gerencia = serializers.SerializerMethodField()
    stock_cubre_solicitud = serializers.SerializerMethodField()
    pendiente_vincular_catalogo = serializers.SerializerMethodField()

    class Meta:
        model = SolicitudInsumo
        fields = (
            "id",
            "fecha",
            "estado",
            "destino",
            "solicitante_nombre",
            "observacion",
            "creado_en",
            "cantidad_items",
            "motivo_rechazo",
            "requiere_aprobacion_gerencia",
            "stock_cubre_solicitud",
            "pendiente_vincular_catalogo",
        )

    def get_cantidad_items(self, obj):
        return obj.detalles.count()

    def get_requiere_aprobacion_gerencia(self, obj):
        from .rules import solicitud_requiere_gerencia

        return solicitud_requiere_gerencia(obj)

    def get_stock_cubre_solicitud(self, obj):
        from .rules import solicitud_cubierta_por_stock

        return solicitud_cubierta_por_stock(obj)

    def get_pendiente_vincular_catalogo(self, obj):
        from .rules import solicitud_detalles_todos_vinculados

        return not solicitud_detalles_todos_vinculados(obj)


class SolicitudEstadoUpdateSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(choices=EstadoSolicitud.choices)
    motivo_rechazo = serializers.CharField(required=False, allow_blank=True)
