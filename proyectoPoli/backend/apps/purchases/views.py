from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.products.models import Producto
from apps.users.models import Role

from .models import (
    AccionTransicionSolicitud,
    EstadoSolicitud,
    SolicitudDetalle,
    SolicitudInsumo,
    TipoDestinoCompra,
    renumerar_numeros_solicitud_tras_eliminacion,
)
from .inventory_integration import (
    registrar_movimientos_entrega_inmediata,
    registrar_movimientos_inventario,
    registrar_salida_inventario_al_finalizar,
    registrar_salidas_por_aprobacion,
)
from .rules import (
    gerencia_puede_cambiar_estado_solicitud,
    queryset_solicitudes_visible_para_rol,
    solicitud_compras_exige_vinculo_para_aprobar,
    solicitud_puede_editar_tipo_destino_compra,
    solicitud_puede_editar_cantidad_detalle_fuera_catalogo,
    solicitud_puede_vincular_detalle,
    solicitud_compras_puede_rechazar,
    solicitud_cubierta_por_stock,
    solicitud_detalles_todos_vinculados,
    mensaje_stock_insuficiente_catalogo,
    solicitud_primer_detalle_stock_insuficiente,
)
from .serializers import (
    SolicitudDetalleSerializer,
    SolicitudEstadoUpdateSerializer,
    SolicitudInsumoListSerializer,
    SolicitudInsumoSerializer,
)

# Transiciones permitidas por rol: (estado_actual -> [estados permitidos])
TRANSICIONES_COMPRAS = {
    EstadoSolicitud.SOLICITADO: [EstadoSolicitud.EN_REVISION],
    EstadoSolicitud.EN_REVISION: [
        EstadoSolicitud.COMPRA_ACEPTADA,
        EstadoSolicitud.COMPRA_RECHAZADA,
    ],
    EstadoSolicitud.COMPRA_ACEPTADA: [EstadoSolicitud.FINALIZADO],
}
TRANSICIONES_GERENCIA = {
    EstadoSolicitud.EN_REVISION: [EstadoSolicitud.COMPRA_ACEPTADA, EstadoSolicitud.COMPRA_RECHAZADA],
}


class SolicitudInsumoPagination(PageNumberPagination):
    page_size = 10
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 50


def puede_ver_todas(user):
    """Compras, Gerencia, Contable (consulta) y Administrador ven el listado de solicitudes."""
    return user.role in (
        Role.COMPRAS,
        Role.GERENCIA,
        Role.CONTABLE,
        Role.ADMINISTRADOR,
    )


def puede_cambiar_estado(user):
    return user.role in (Role.COMPRAS, Role.GERENCIA, Role.ADMINISTRADOR)


def puede_crear_solicitud(user):
    """Funcionario, Compras, Contable y Administrador pueden crear solicitudes."""
    return user.role in (Role.FUNCIONARIO, Role.COMPRAS, Role.CONTABLE, Role.ADMINISTRADOR)


def puede_definir_destino_compra(user):
    return user.role in (Role.COMPRAS, Role.ADMINISTRADOR)


class SolicitudInsumoViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = SolicitudInsumoSerializer
    pagination_class = SolicitudInsumoPagination

    def get_queryset(self):
        qs = SolicitudInsumo.objects.select_related("solicitante").prefetch_related("detalles__producto")
        if puede_ver_todas(self.request.user):
            return queryset_solicitudes_visible_para_rol(self.request.user, qs)
        return qs.filter(solicitante=self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return SolicitudInsumoListSerializer
        if self.action in ("update", "partial_update"):
            return SolicitudEstadoUpdateSerializer
        return SolicitudInsumoSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        estado = request.query_params.get("estado")
        if estado:
            qs = qs.filter(estado=estado)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = SolicitudInsumoListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = SolicitudInsumoListSerializer(qs, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        if not puede_crear_solicitud(request.user):
            return Response(
                {"detail": "No tiene permiso para crear solicitudes de compra."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = SolicitudInsumoSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        detalles = serializer.validated_data.get("detalles", [])
        if not detalles:
            return Response(
                {"detalles": ["Debe incluir al menos un ítem."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for d in detalles:
            if d.get("cantidad", 0) < 1:
                return Response(
                    {"detalles": ["Cantidad debe ser mayor a 0."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        solicitud = serializer.save()
        return Response(
            SolicitudInsumoSerializer(solicitud).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = SolicitudInsumoSerializer(instance)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        return Response({"detail": "Use PATCH para cambiar solo el estado."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = SolicitudEstadoUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        tipo_destino = serializer.validated_data.get("tipo_destino_compra")
        if tipo_destino is not None and tipo_destino != instance.tipo_destino_compra:
            if not instance.contiene_fuera_catalogo:
                return Response(
                    {
                        "detail": "El destino de compra solo aplica a solicitudes "
                        "con ítems fuera de catálogo.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not puede_definir_destino_compra(request.user):
                return Response(
                    {"detail": "No tiene permiso para definir el destino de compra."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if not solicitud_puede_editar_tipo_destino_compra(instance):
                return Response(
                    {
                        "detail": "El destino de compra ya no puede modificarse en este estado.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            instance.tipo_destino_compra = tipo_destino
            instance.save(update_fields=["tipo_destino_compra"])

        nuevo_estado = serializer.validated_data.get("estado")
        if nuevo_estado is None:
            instance.refresh_from_db()
            return Response(SolicitudInsumoSerializer(instance).data)

        if not puede_cambiar_estado(request.user):
            return Response(
                {"detail": "No tiene permiso para cambiar el estado."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if (
            request.user.role == Role.GERENCIA
            and not gerencia_puede_cambiar_estado_solicitud(instance)
        ):
            return Response(
                {
                    "detail": "Gerencia solo consulta solicitudes de catálogo; "
                    "la aprobación o rechazo corresponde a Compras.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        transiciones = {}
        if request.user.role == Role.COMPRAS:
            transiciones = TRANSICIONES_COMPRAS
        elif request.user.role == Role.GERENCIA:
            transiciones = TRANSICIONES_GERENCIA
        elif request.user.role == Role.ADMINISTRADOR:
            transiciones = {**TRANSICIONES_COMPRAS, **TRANSICIONES_GERENCIA}

        permitidos = transiciones.get(instance.estado, [])
        if nuevo_estado not in permitidos:
            return Response(
                {"detail": f"No se puede pasar de {instance.get_estado_display()} a {dict(EstadoSolicitud.choices).get(nuevo_estado, nuevo_estado)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            instance.estado == EstadoSolicitud.SOLICITADO
            and nuevo_estado == EstadoSolicitud.EN_REVISION
            and request.user.role in (Role.COMPRAS, Role.ADMINISTRADOR)
        ):
            if instance.contiene_fuera_catalogo:
                destino = tipo_destino or instance.tipo_destino_compra
                if not destino:
                    return Response(
                        {
                            "detail": "Defina el destino de compra (para inventario o entrega inmediata) "
                            "antes de continuar.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if tipo_destino:
                    instance.tipo_destino_compra = tipo_destino
                    instance.save(update_fields=["tipo_destino_compra"])
            accion = serializer.validated_data.get("accion")
            if instance.contiene_fuera_catalogo:
                if accion != AccionTransicionSolicitud.SOLICITAR_GERENCIA:
                    return Response(
                        {
                            "detail": "Esta solicitud incluye ítems fuera de catálogo. "
                            "Use «Solicitar aprobación de Gerencia».",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            elif accion != AccionTransicionSolicitud.TOMAR_SOLICITUD:
                return Response(
                    {
                        "detail": "Debe tomar la solicitud antes de continuar con la gestión.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if (
            not solicitud_detalles_todos_vinculados(instance)
            and solicitud_compras_exige_vinculo_para_aprobar(
                request.user.role, nuevo_estado, instance
            )
        ):
            return Response(
                {
                    "detail": "Hay ítems fuera de catálogo sin vincular. Vincule cada línea "
                    "antes de aprobar la solicitud.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            not solicitud_detalles_todos_vinculados(instance)
            and nuevo_estado == EstadoSolicitud.FINALIZADO
            and instance.contiene_fuera_catalogo
        ):
            return Response(
                {
                    "detail": "Hay ítems fuera de catálogo sin vincular. Vincule cada línea "
                    "antes de finalizar la solicitud.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            nuevo_estado == EstadoSolicitud.COMPRA_RECHAZADA
            and request.user.role == Role.COMPRAS
            and not solicitud_compras_puede_rechazar(instance)
        ):
            return Response(
                {
                    "detail": "Las solicitudes con ítems fuera de catálogo solo pueden rechazarlas Gerencia.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            instance.estado == EstadoSolicitud.EN_REVISION
            and nuevo_estado
            in (EstadoSolicitud.COMPRA_ACEPTADA, EstadoSolicitud.COMPRA_RECHAZADA)
            and instance.contiene_fuera_catalogo
            and request.user.role == Role.COMPRAS
        ):
            return Response(
                {
                    "detail": "Las solicitudes con ítems fuera de catálogo solo pueden "
                    "aprobarlas o rechazarlas Gerencia.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if (
            not instance.contiene_fuera_catalogo
            and not solicitud_cubierta_por_stock(instance)
            and nuevo_estado
            in (EstadoSolicitud.COMPRA_ACEPTADA, EstadoSolicitud.FINALIZADO)
        ):
            return Response(
                {"detail": mensaje_stock_insuficiente_catalogo(instance)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                comentario_decision = (serializer.validated_data.get("comentario_decision") or "").strip()
                instance.estado = nuevo_estado
                if nuevo_estado in (
                    EstadoSolicitud.COMPRA_ACEPTADA,
                    EstadoSolicitud.COMPRA_RECHAZADA,
                    EstadoSolicitud.FINALIZADO,
                ):
                    instance.aprobado_en = timezone.now()
                if nuevo_estado == EstadoSolicitud.COMPRA_RECHAZADA:
                    instance.motivo_rechazo = (
                        comentario_decision
                        or serializer.validated_data.get("motivo_rechazo", "")
                        or ""
                    )
                else:
                    instance.motivo_rechazo = ""
                    if (
                        nuevo_estado == EstadoSolicitud.COMPRA_ACEPTADA
                        and comentario_decision
                        and request.user.role == Role.GERENCIA
                    ):
                        base = (instance.observacion or "").strip()
                        nota = f"Comentario Gerencia (aprobación): {comentario_decision}"
                        instance.observacion = f"{base}\n{nota}".strip() if base else nota
                instance.save()
                if nuevo_estado == EstadoSolicitud.FINALIZADO:
                    registrar_salida_inventario_al_finalizar(instance, request.user)
                if nuevo_estado in (EstadoSolicitud.COMPRA_ACEPTADA, EstadoSolicitud.FINALIZADO):
                    if not instance.contiene_fuera_catalogo and solicitud_cubierta_por_stock(
                        instance
                    ):
                        registrar_salidas_por_aprobacion(instance, request.user)
        except ValidationError as exc:
            if getattr(exc, "message_dict", None):
                detail = next(
                    (v[0] for v in exc.message_dict.values() if v),
                    str(exc),
                )
            elif getattr(exc, "messages", None):
                detail = " ".join(str(m) for m in exc.messages)
            else:
                detail = str(exc)
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        from .notifications import send_solicitud_estado_email
        send_solicitud_estado_email(instance, nuevo_estado)

        return Response(SolicitudInsumoSerializer(instance).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="vincular-detalle",
    )
    def vincular_detalle(self, request, pk=None):
        """Asocia un ítem fuera de catálogo a un Producto existente (Compras o Admin)."""
        if request.user.role not in (Role.COMPRAS, Role.ADMINISTRADOR):
            return Response(
                {"detail": "No tiene permiso para vincular ítems al catálogo."},
                status=status.HTTP_403_FORBIDDEN,
            )
        solicitud = self.get_object()
        if not solicitud_puede_vincular_detalle(solicitud):
            return Response(
                {
                    "detail": "La vinculación al catálogo está disponible después de que "
                    "Gerencia acepte la compra.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not solicitud.tipo_destino_compra:
            return Response(
                {
                    "detail": "La solicitud no tiene destino de compra definido.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        detalle_id = request.data.get("detalle_id")
        producto_id = request.data.get("producto_id")
        if detalle_id is None or producto_id is None:
            return Response(
                {"detail": "Envíe detalle_id y producto_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        detalle = get_object_or_404(SolicitudDetalle, pk=detalle_id, solicitud=solicitud)
        if detalle.producto_id is not None:
            return Response(
                {"detail": "Este ítem ya está vinculado a un producto del catálogo."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        producto = get_object_or_404(Producto, pk=producto_id)
        try:
            with transaction.atomic():
                detalle.producto = producto
                detalle.descripcion_insumo_solicitado = ""
                detalle.save()
                registrar_movimientos_entrega_inmediata(solicitud, detalle, request.user)
                registrar_movimientos_inventario(solicitud, detalle, request.user)
        except ValidationError as exc:
            detail = str(exc)
            if getattr(exc, "messages", None):
                detail = " ".join(str(m) for m in exc.messages)
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        # Refrescar para no devolver detalles en caché del prefetch del get_object.
        solicitud_refresh = (
            SolicitudInsumo.objects.select_related("solicitante")
            .prefetch_related("detalles__producto")
            .get(pk=solicitud.pk)
        )
        return Response(SolicitudInsumoSerializer(solicitud_refresh).data)

    @action(
        detail=True,
        methods=["post"],
        url_path="actualizar-cantidad-detalle",
    )
    def actualizar_cantidad_detalle(self, request, pk=None):
        """Compras o Gerencia ajustan la cantidad a comprar (fuera de catálogo, inventario)."""
        if request.user.role not in (Role.COMPRAS, Role.GERENCIA, Role.ADMINISTRADOR):
            return Response(
                {"detail": "No tiene permiso para modificar la cantidad a comprar."},
                status=status.HTTP_403_FORBIDDEN,
            )
        solicitud = self.get_object()
        detalle_id = request.data.get("detalle_id")
        cantidad_raw = request.data.get("cantidad")
        if detalle_id is None or cantidad_raw is None:
            return Response(
                {"detail": "Envíe detalle_id y cantidad."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            cantidad = int(cantidad_raw)
        except (TypeError, ValueError):
            return Response(
                {"detail": "Cantidad debe ser un número entero."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if cantidad < 1:
            return Response(
                {"detail": "Cantidad debe ser mayor a 0."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        detalle = get_object_or_404(SolicitudDetalle, pk=detalle_id, solicitud=solicitud)
        if not solicitud_puede_editar_cantidad_detalle_fuera_catalogo(solicitud, detalle):
            return Response(
                {
                    "detail": "La cantidad a comprar solo puede modificarse en ítems fuera de "
                    "catálogo con destino de inventario, antes de vincular el producto.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if cantidad < detalle.cantidad_inicial:
            return Response(
                {
                    "detail": (
                        f"La cantidad a comprar no puede ser menor que la cantidad inicial "
                        f"solicitada ({detalle.cantidad_inicial})."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        detalle.cantidad = cantidad
        detalle.save(update_fields=["cantidad"])
        solicitud_refresh = (
            SolicitudInsumo.objects.select_related("solicitante")
            .prefetch_related("detalles__producto")
            .get(pk=solicitud.pk)
        )
        return Response(SolicitudInsumoSerializer(solicitud_refresh).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        numero = instance.numero
        if request.user.role == Role.ADMINISTRADOR:
            with transaction.atomic():
                self.perform_destroy(instance)
                if numero is not None:
                    renumerar_numeros_solicitud_tras_eliminacion(numero)
            return Response(status=status.HTTP_204_NO_CONTENT)
        if instance.estado != EstadoSolicitud.SOLICITADO:
            return Response(
                {"detail": "Solo se puede eliminar una solicitud en estado Solicitado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if instance.solicitante_id != request.user.id and request.user.role not in (
            Role.COMPRAS,
            Role.GERENCIA,
        ):
            return Response(
                {"detail": "No tiene permiso para eliminar esta solicitud."},
                status=status.HTTP_403_FORBIDDEN,
            )
        with transaction.atomic():
            self.perform_destroy(instance)
            if numero is not None:
                renumerar_numeros_solicitud_tras_eliminacion(numero)
        return Response(status=status.HTTP_204_NO_CONTENT)
