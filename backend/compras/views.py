from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from api.permissions import IsComprasGroup, IsAdminGroup
from .models import SolicitudCompra
from .serializers import SolicitudCompraSerializer, SolicitudCompraItemSerializer


ALLOWED_TRANSITIONS = {
    "BORRADOR": ["ENVIADA"],
    "ENVIADA": ["APROBADA", "RECHAZADA"],
    "APROBADA": [],
    "RECHAZADA": [],
}


def is_admin_user(user):
    return user.is_staff or user.groups.filter(name__iexact="admin").exists()


@api_view(["GET", "POST"])
@permission_classes([IsComprasGroup])
def solicitudes(request):
    # ---------- GET: listar ----------
    if request.method == "GET":
        # 1) base queryset
        qs = SolicitudCompra.objects.all().order_by("-id")

        # 2) filtro opcional por estado (ej: ?estado=ENVIADA)
        estado = request.query_params.get("estado")
        if estado:
            qs = qs.filter(estado=estado)

        # 3) si NO es admin, solo ve las suyas
        if not is_admin_user(request.user):
            qs = qs.filter(solicitante=request.user)

        return Response(SolicitudCompraSerializer(qs, many=True).data)

    # ---------- POST: crear ----------
    ser = SolicitudCompraSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    obj = SolicitudCompra.objects.create(
        titulo=ser.validated_data["titulo"],
        descripcion=ser.validated_data.get("descripcion", ""),
        solicitante=request.user,
    )
    return Response(SolicitudCompraSerializer(obj).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsComprasGroup])
def enviar_solicitud(request, pk: int):
    try:
        obj = SolicitudCompra.objects.get(pk=pk)
    except SolicitudCompra.DoesNotExist:
        return Response({"detail": "No existe."}, status=status.HTTP_404_NOT_FOUND)

    # compras solo puede enviar las suyas; admin pasa
    if not is_admin_user(request.user) and obj.solicitante_id != request.user.id:
        return Response({"detail": "No permitido."}, status=status.HTTP_403_FORBIDDEN)

    if "ENVIADA" not in ALLOWED_TRANSITIONS.get(obj.estado, []):
        return Response(
            {"detail": f"No se puede enviar desde estado {obj.estado}."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not obj.items.exists():
        return Response({"detail": "No se puede enviar sin items."}, status=status.HTTP_400_BAD_REQUEST)

    obj.estado = SolicitudCompra.Estado.ENVIADA
    obj.save(update_fields=["estado"])
    return Response(SolicitudCompraSerializer(obj).data)


@api_view(["POST"])
@permission_classes([IsAdminGroup])
def aprobar_solicitud(request, pk: int):
    try:
        obj = SolicitudCompra.objects.get(pk=pk)
    except SolicitudCompra.DoesNotExist:
        return Response({"detail": "No existe."}, status=status.HTTP_404_NOT_FOUND)

    if "APROBADA" not in ALLOWED_TRANSITIONS.get(obj.estado, []):
        return Response(
            {"detail": f"No se puede aprobar desde estado {obj.estado}."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not obj.items.exists():
        return Response({"detail": "No se puede aprobar una solicitud sin items."}, status=status.HTTP_400_BAD_REQUEST)

    obj.estado = SolicitudCompra.Estado.APROBADA
    obj.aprobado_por = request.user
    obj.aprobado_at = timezone.now()
    obj.save(update_fields=["estado", "aprobado_por", "aprobado_at"])
    return Response(SolicitudCompraSerializer(obj).data)


@api_view(["POST"])
@permission_classes([IsAdminGroup])
def rechazar_solicitud(request, pk: int):
    try:
        obj = SolicitudCompra.objects.get(pk=pk)
    except SolicitudCompra.DoesNotExist:
        return Response({"detail": "No existe."}, status=status.HTTP_404_NOT_FOUND)

    if "RECHAZADA" not in ALLOWED_TRANSITIONS.get(obj.estado, []):
        return Response(
            {"detail": f"No se puede rechazar desde estado {obj.estado}."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    obj.estado = SolicitudCompra.Estado.RECHAZADA
    obj.rechazado_por = request.user
    obj.rechazado_at = timezone.now()
    obj.save(update_fields=["estado", "rechazado_por", "rechazado_at"])
    return Response(SolicitudCompraSerializer(obj).data)


@api_view(["GET", "POST"])
@permission_classes([IsComprasGroup])
def items(request, pk: int):
    """
    GET  -> lista items de una solicitud
    POST -> agrega item a una solicitud (solo BORRADOR)
    """
    try:
        sol = SolicitudCompra.objects.get(pk=pk)
    except SolicitudCompra.DoesNotExist:
        return Response({"detail": "No existe."}, status=status.HTTP_404_NOT_FOUND)

    # permisos: compras solo puede tocar sus solicitudes; admin pasa todo
    if not is_admin_user(request.user) and sol.solicitante_id != request.user.id:
        return Response({"detail": "No permitido."}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        return Response(SolicitudCompraItemSerializer(sol.items.all().order_by("id"), many=True).data)

    # POST
    if sol.estado != SolicitudCompra.Estado.BORRADOR:
        return Response({"detail": "Solo se pueden agregar items en BORRADOR."}, status=status.HTTP_400_BAD_REQUEST)

    ser = SolicitudCompraItemSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    item = sol.items.create(
        descripcion=ser.validated_data["descripcion"],
        cantidad=ser.validated_data["cantidad"],
        precio_estimado=ser.validated_data.get("precio_estimado", 0),
    )
    return Response(SolicitudCompraItemSerializer(item).data, status=status.HTTP_201_CREATED)


@api_view(["DELETE"])
@permission_classes([IsComprasGroup])
def borrar_item(request, pk: int, item_id: int):
    try:
        sol = SolicitudCompra.objects.get(pk=pk)
    except SolicitudCompra.DoesNotExist:
        return Response({"detail": "No existe."}, status=status.HTTP_404_NOT_FOUND)

    if not is_admin_user(request.user) and sol.solicitante_id != request.user.id:
        return Response({"detail": "No permitido."}, status=status.HTTP_403_FORBIDDEN)

    if sol.estado != SolicitudCompra.Estado.BORRADOR:
        return Response({"detail": "Solo se pueden borrar items en BORRADOR."}, status=status.HTTP_400_BAD_REQUEST)

    deleted, _ = sol.items.filter(id=item_id).delete()
    if not deleted:
        return Response({"detail": "Item no existe."}, status=status.HTTP_404_NOT_FOUND)

    return Response({"ok": True})


@api_view(["GET"])
@permission_classes([IsComprasGroup])
def flujo_estados(request):
    return Response(
        {
            "estados": ["BORRADOR", "ENVIADA", "APROBADA", "RECHAZADA"],
            "transiciones": ALLOWED_TRANSITIONS,
        }
    )

@api_view(["PATCH"])
@permission_classes([IsComprasGroup])
def editar_solicitud(request, pk: int):
    try:
        obj = SolicitudCompra.objects.get(pk=pk)
    except SolicitudCompra.DoesNotExist:
        return Response({"detail": "No existe."}, status=status.HTTP_404_NOT_FOUND)

    # permisos: compras solo la suya; admin pasa
    if not is_admin_user(request.user) and obj.solicitante_id != request.user.id:
        return Response({"detail": "No permitido."}, status=status.HTTP_403_FORBIDDEN)

    if obj.estado != SolicitudCompra.Estado.BORRADOR:
        return Response({"detail": "Solo se puede editar en BORRADOR."}, status=status.HTTP_400_BAD_REQUEST)

    ser = SolicitudCompraSerializer(obj, data=request.data, partial=True)
    ser.is_valid(raise_exception=True)
    ser.save()
    return Response(ser.data)
