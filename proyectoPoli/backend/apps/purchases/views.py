from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.products.models import Producto
from apps.users.models import Role

from .models import EstadoSolicitud, SolicitudDetalle, SolicitudInsumo
from .inventory_integration import registrar_salidas_por_aprobacion
from .rules import (
    solicitud_cubierta_por_stock,
    solicitud_detalles_todos_vinculados,
    solicitud_requiere_gerencia,
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


def puede_ver_todas(user):
    """Compras, Gerencia, Contable (consulta) y Administrador ven todas las solicitudes."""
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


class SolicitudInsumoViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = SolicitudInsumoSerializer

    def get_queryset(self):
        qs = SolicitudInsumo.objects.select_related("solicitante").prefetch_related("detalles__producto")
        if puede_ver_todas(self.request.user):
            return qs
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
        if not puede_cambiar_estado(request.user):
            return Response(
                {"detail": "No tiene permiso para cambiar el estado."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = SolicitudEstadoUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        nuevo_estado = serializer.validated_data["estado"]

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

        if nuevo_estado == EstadoSolicitud.COMPRA_ACEPTADA:
            if not solicitud_detalles_todos_vinculados(instance):
                return Response(
                    {
                        "detail": "Todos los ítems deben estar vinculados al catálogo antes de aprobar. "
                        "Cree el producto si no existe y use POST .../vincular-detalle/ con detalle_id y producto_id.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if instance.estado == EstadoSolicitud.EN_REVISION and nuevo_estado in (
            EstadoSolicitud.COMPRA_ACEPTADA,
            EstadoSolicitud.COMPRA_RECHAZADA,
        ):
            req_g = solicitud_requiere_gerencia(instance)
            stock_ok = solicitud_cubierta_por_stock(instance)
            if request.user.role == Role.COMPRAS:
                if nuevo_estado == EstadoSolicitud.COMPRA_ACEPTADA:
                    if req_g:
                        return Response(
                            {
                                "detail": "Debe aprobarla Gerencia: falta de stock para surtir desde inventario.",
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    if not stock_ok:
                        return Response(
                            {
                                "detail": "No hay stock suficiente; corresponde aprobación por Gerencia.",
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
            elif request.user.role == Role.GERENCIA:
                if not req_g:
                    return Response(
                        {
                            "detail": "Las solicitudes con stock suficiente en depósito las aprueba o rechaza Compras.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            elif request.user.role == Role.ADMINISTRADOR:
                # Administrador: sin restricción extra (auditoría manual).
                pass

        try:
            with transaction.atomic():
                instance.estado = nuevo_estado
                if nuevo_estado in (
                    EstadoSolicitud.COMPRA_ACEPTADA,
                    EstadoSolicitud.COMPRA_RECHAZADA,
                    EstadoSolicitud.FINALIZADO,
                ):
                    instance.aprobado_en = timezone.now()
                if nuevo_estado == EstadoSolicitud.COMPRA_RECHAZADA:
                    instance.motivo_rechazo = serializer.validated_data.get("motivo_rechazo", "") or ""
                else:
                    instance.motivo_rechazo = ""  # limpiar si se cambia de estado
                instance.save()
                if nuevo_estado == EstadoSolicitud.COMPRA_ACEPTADA:
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
        """Asocia un ítem fuera de catálogo a un Producto existente (Compras, Gerencia o Admin)."""
        if request.user.role not in (Role.COMPRAS, Role.GERENCIA, Role.ADMINISTRADOR):
            return Response(
                {"detail": "No tiene permiso para vincular ítems al catálogo."},
                status=status.HTTP_403_FORBIDDEN,
            )
        solicitud = self.get_object()
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
        detalle.producto = producto
        detalle.descripcion_insumo_solicitado = ""
        detalle.save()
        # Refrescar para no devolver detalles en caché del prefetch del get_object.
        solicitud_refresh = (
            SolicitudInsumo.objects.select_related("solicitante")
            .prefetch_related("detalles__producto")
            .get(pk=solicitud.pk)
        )
        return Response(SolicitudInsumoSerializer(solicitud_refresh).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.estado != EstadoSolicitud.SOLICITADO:
            return Response(
                {"detail": "Solo se puede eliminar una solicitud en estado Solicitado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if instance.solicitante_id != request.user.id and request.user.role not in (Role.COMPRAS, Role.GERENCIA, Role.ADMINISTRADOR):
            return Response({"detail": "No tiene permiso para eliminar esta solicitud."}, status=status.HTTP_403_FORBIDDEN)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
