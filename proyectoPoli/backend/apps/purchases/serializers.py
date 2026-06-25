from rest_framework import serializers
from apps.products.models import Producto

from .models import (
    EstadoSolicitud,
    SolicitudDetalle,
    SolicitudInsumo,
    TipoDestinoCompra,
)


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
            "cantidad_inicial",
            "observacion",
        )
        read_only_fields = ("cantidad_inicial",)

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
    pendiente_vincular_catalogo = serializers.SerializerMethodField()
    compras_puede_rechazar = serializers.SerializerMethodField()
    alerta_proyeccion_consumo = serializers.SerializerMethodField()
    alertas_proyeccion = serializers.SerializerMethodField()
    tipo_destino_compra_label = serializers.SerializerMethodField()

    class Meta:
        model = SolicitudInsumo
        fields = (
            "id",
            "numero",
            "fecha",
            "estado",
            "destino",
            "tipo_destino_compra",
            "tipo_destino_compra_label",
            "solicitante",
            "solicitante_nombre",
            "observacion",
            "creado_en",
            "aprobado_en",
            "motivo_rechazo",
            "contiene_fuera_catalogo",
            "detalles",
            "requiere_aprobacion_gerencia",
            "stock_cubre_solicitud",
            "pendiente_vincular_catalogo",
            "compras_puede_rechazar",
            "alerta_proyeccion_consumo",
            "alertas_proyeccion",
        )
        read_only_fields = (
            "solicitante",
            "fecha",
            "creado_en",
            "aprobado_en",
            "contiene_fuera_catalogo",
            "numero",
            "requiere_aprobacion_gerencia",
            "stock_cubre_solicitud",
            "pendiente_vincular_catalogo",
            "compras_puede_rechazar",
            "alerta_proyeccion_consumo",
            "alertas_proyeccion",
        )

    def get_requiere_aprobacion_gerencia(self, obj):
        from .rules import solicitud_requiere_gerencia

        return solicitud_requiere_gerencia(obj)

    def get_stock_cubre_solicitud(self, obj):
        from .rules import solicitud_cubierta_por_stock

        return solicitud_cubierta_por_stock(obj)

    def get_pendiente_vincular_catalogo(self, obj):
        from .rules import solicitud_detalles_todos_vinculados

        return not solicitud_detalles_todos_vinculados(obj)

    def get_compras_puede_rechazar(self, obj):
        from .rules import solicitud_compras_puede_rechazar

        return solicitud_compras_puede_rechazar(obj)

    def get_alerta_proyeccion_consumo(self, obj):
        from .rules import solicitud_alerta_proyeccion_consumo

        return solicitud_alerta_proyeccion_consumo(obj)

    def get_alertas_proyeccion(self, obj):
        from .rules import solicitud_alertas_proyeccion_detalle

        return solicitud_alertas_proyeccion_detalle(obj)

    def get_tipo_destino_compra_label(self, obj):
        if not obj.tipo_destino_compra:
            return ""
        return obj.get_tipo_destino_compra_display()

    def create(self, validated_data):
        detalles_data = validated_data.pop("detalles")
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Usuario no autenticado")
        validated_data["solicitante"] = request.user
        validated_data["estado"] = EstadoSolicitud.SOLICITADO
        validated_data["contiene_fuera_catalogo"] = any(
            d.get("producto") is None for d in detalles_data
        )
        from apps.users.models import Role

        if request.user.role not in (Role.COMPRAS, Role.ADMINISTRADOR):
            validated_data.pop("tipo_destino_compra", None)
        elif not validated_data["contiene_fuera_catalogo"]:
            validated_data.pop("tipo_destino_compra", None)
        solicitud = SolicitudInsumo.objects.create(**validated_data)
        for d in detalles_data:
            cantidad = d.get("cantidad", 1)
            d.setdefault("cantidad_inicial", cantidad)
            SolicitudDetalle.objects.create(solicitud=solicitud, **d)
        return solicitud


class SolicitudInsumoListSerializer(serializers.ModelSerializer):
    solicitante_nombre = serializers.CharField(source="solicitante.username", read_only=True)
    cantidad_items = serializers.SerializerMethodField()
    requiere_aprobacion_gerencia = serializers.SerializerMethodField()
    stock_cubre_solicitud = serializers.SerializerMethodField()
    pendiente_vincular_catalogo = serializers.SerializerMethodField()
    en_catalogo = serializers.SerializerMethodField()
    productos_resumen = serializers.SerializerMethodField()
    compras_puede_rechazar = serializers.SerializerMethodField()
    alerta_proyeccion_consumo = serializers.SerializerMethodField()
    tipo_destino_compra_label = serializers.SerializerMethodField()

    class Meta:
        model = SolicitudInsumo
        fields = (
            "id",
            "numero",
            "fecha",
            "estado",
            "destino",
            "tipo_destino_compra",
            "tipo_destino_compra_label",
            "solicitante_nombre",
            "observacion",
            "creado_en",
            "cantidad_items",
            "motivo_rechazo",
            "contiene_fuera_catalogo",
            "requiere_aprobacion_gerencia",
            "stock_cubre_solicitud",
            "pendiente_vincular_catalogo",
            "en_catalogo",
            "productos_resumen",
            "compras_puede_rechazar",
            "alerta_proyeccion_consumo",
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

    def get_en_catalogo(self, obj):
        from .rules import solicitud_detalles_todos_vinculados

        return solicitud_detalles_todos_vinculados(obj)

    def get_productos_resumen(self, obj):
        nombres: list[str] = []
        for d in obj.detalles.all():
            if d.producto_id:
                nombres.append(d.producto.nombre)
            elif (d.descripcion_insumo_solicitado or "").strip():
                nombres.append(d.descripcion_insumo_solicitado.strip())
        return ", ".join(nombres)

    def get_compras_puede_rechazar(self, obj):
        from .rules import solicitud_compras_puede_rechazar

        return solicitud_compras_puede_rechazar(obj)

    def get_alerta_proyeccion_consumo(self, obj):
        from .rules import solicitud_alerta_proyeccion_consumo

        return solicitud_alerta_proyeccion_consumo(obj)

    def get_tipo_destino_compra_label(self, obj):
        if not obj.tipo_destino_compra:
            return ""
        return obj.get_tipo_destino_compra_display()


class SolicitudEstadoUpdateSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(choices=EstadoSolicitud.choices, required=False)
    tipo_destino_compra = serializers.ChoiceField(
        choices=TipoDestinoCompra.choices,
        required=False,
    )
    motivo_rechazo = serializers.CharField(required=False, allow_blank=True)
    comentario_decision = serializers.CharField(required=False, allow_blank=True)
    accion = serializers.ChoiceField(
        choices=[
            ("TOMAR_SOLICITUD", "Tomar solicitud"),
            ("SOLICITAR_GERENCIA", "Solicitar aprobación Gerencia"),
        ],
        required=False,
        allow_blank=True,
    )

    def validate(self, attrs):
        if not attrs.get("estado") and not attrs.get("tipo_destino_compra"):
            raise serializers.ValidationError(
                "Indique el estado y/o el destino de compra a actualizar."
            )
        return attrs
