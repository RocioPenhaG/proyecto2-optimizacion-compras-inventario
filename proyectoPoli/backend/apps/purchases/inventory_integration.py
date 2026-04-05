"""
Registro de salidas de inventario al aprobar solicitudes (COMPRA_ACEPTADA).
"""
from django.core.exceptions import ValidationError

from apps.inventory.models import MovStock

from .rules import solicitud_cubierta_por_stock

REF_TIPO_SOLICITUD = "SOLICITUD"


def registrar_salidas_por_aprobacion(solicitud, usuario) -> list[MovStock]:
    """
    Si hay stock suficiente para todos los ítems y aún no se registró salida
    por esta solicitud, crea un MovStock OUT por cada línea y actualiza stock.

    Si no hay stock suficiente (p. ej. aprobación Gerencia sin existencias),
    no hace nada.

    Raises ValidationError si un movimiento dejara stock negativo (no debería
    ocurrir si solicitud_cubierta_por_stock es True).
    """
    if not solicitud_cubierta_por_stock(solicitud):
        return []

    if MovStock.objects.filter(ref_tipo=REF_TIPO_SOLICITUD, ref_id=solicitud.pk).exists():
        return []

    creados: list[MovStock] = []
    for d in solicitud.detalles.select_related("producto"):
        if d.producto_id is None:
            continue
        mov = MovStock(
            producto=d.producto,
            usuario=usuario,
            tipo="OUT",
            cantidad=d.cantidad,
            ref_tipo=REF_TIPO_SOLICITUD,
            ref_id=solicitud.pk,
            observacion=f"Salida automática por solicitud #{solicitud.pk} aprobada",
        )
        mov.save()
        creados.append(mov)
    return creados
