"""
Registro de salidas de inventario al aprobar solicitudes (COMPRA_ACEPTADA).
"""
from django.core.exceptions import ValidationError

from apps.inventory.models import MovStock

from .rules import solicitud_cubierta_por_stock, solicitud_tiene_items_fuera_catalogo

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


def registrar_movimientos_entrega_inmediata(solicitud, detalle, usuario) -> list[MovStock]:
    """
    Tras vincular un ítem en solicitud de entrega inmediata: registra entrada (compra)
    y salida (entrega al solicitante) por la cantidad pedida, si aún no existen.
    """
    from .models import TipoDestinoCompra

    if solicitud.tipo_destino_compra != TipoDestinoCompra.ENTREGA_INMEDIATA:
        return []
    if detalle.producto_id is None:
        return []

    creados: list[MovStock] = []
    cantidad = detalle.cantidad
    base = {
        "ref_tipo": REF_TIPO_SOLICITUD,
        "ref_id": solicitud.pk,
        "producto_id": detalle.producto_id,
    }
    solicitante = getattr(solicitud.solicitante, "username", "solicitante")

    if not MovStock.objects.filter(**base, tipo="IN").exists():
        mov_in = MovStock(
            producto_id=detalle.producto_id,
            usuario=usuario,
            tipo="IN",
            cantidad=cantidad,
            ref_tipo=REF_TIPO_SOLICITUD,
            ref_id=solicitud.pk,
            observacion=(
                f"Entrada por compra (entrega inmediata) — solicitud #{solicitud.pk}, "
                f"cantidad solicitada: {cantidad}"
            ),
        )
        mov_in.save()
        creados.append(mov_in)

    if not MovStock.objects.filter(**base, tipo="OUT").exists():
        mov_out = MovStock(
            producto_id=detalle.producto_id,
            usuario=usuario,
            tipo="OUT",
            cantidad=cantidad,
            ref_tipo=REF_TIPO_SOLICITUD,
            ref_id=solicitud.pk,
            observacion=(
                f"Entrega inmediata al solicitante ({solicitante}) — solicitud #{solicitud.pk}"
            ),
        )
        mov_out.save()
        creados.append(mov_out)

    return creados


def registrar_movimientos_inventario(solicitud, detalle, usuario) -> list[MovStock]:
    """
    Tras vincular un ítem en solicitud para inventario: registra entrada por la cantidad
    pedida si aún no existe (paridad con entrega inmediata al vincular producto existente).
    """
    from .models import TipoDestinoCompra

    if solicitud.tipo_destino_compra != TipoDestinoCompra.INVENTARIO:
        return []
    if detalle.producto_id is None:
        return []

    creados: list[MovStock] = []
    cantidad = detalle.cantidad
    base = {
        "ref_tipo": REF_TIPO_SOLICITUD,
        "ref_id": solicitud.pk,
        "producto_id": detalle.producto_id,
    }

    if not MovStock.objects.filter(**base, tipo="IN").exists():
        mov_in = MovStock(
            producto_id=detalle.producto_id,
            usuario=usuario,
            tipo="IN",
            cantidad=cantidad,
            ref_tipo=REF_TIPO_SOLICITUD,
            ref_id=solicitud.pk,
            observacion=(
                f"Entrada por compra (inventario) — solicitud #{solicitud.pk}, "
                f"cantidad solicitada: {cantidad}"
            ),
        )
        mov_in.save()
        creados.append(mov_in)

    return creados


OBS_ENTREGA_INVENTARIO_FINAL = "Entrega inventario al solicitante"


def registrar_salida_inventario_al_finalizar(solicitud, usuario) -> list[MovStock]:
    """
    Al finalizar solicitud fuera de catálogo con destino inventario: entrega al
    solicitante solo la cantidad inicial pedida; el resto permanece en stock.
    """
    from .models import TipoDestinoCompra

    if solicitud.tipo_destino_compra != TipoDestinoCompra.INVENTARIO:
        return []
    if not (solicitud.contiene_fuera_catalogo or solicitud_tiene_items_fuera_catalogo(solicitud)):
        return []

    creados: list[MovStock] = []
    solicitante = getattr(solicitud.solicitante, "username", "solicitante")

    for detalle in solicitud.detalles.select_related("producto"):
        if detalle.producto_id is None:
            continue
        cantidad_entrega = int(detalle.cantidad_inicial or detalle.cantidad)
        if cantidad_entrega <= 0:
            continue
        base = {
            "ref_tipo": REF_TIPO_SOLICITUD,
            "ref_id": solicitud.pk,
            "producto_id": detalle.producto_id,
        }
        if MovStock.objects.filter(
            **base,
            tipo="OUT",
            observacion__icontains=OBS_ENTREGA_INVENTARIO_FINAL,
        ).exists():
            continue
        mov_out = MovStock(
            producto_id=detalle.producto_id,
            usuario=usuario,
            tipo="OUT",
            cantidad=cantidad_entrega,
            ref_tipo=REF_TIPO_SOLICITUD,
            ref_id=solicitud.pk,
            observacion=(
                f"{OBS_ENTREGA_INVENTARIO_FINAL} ({solicitante}) — solicitud #{solicitud.pk}, "
                f"cantidad inicial: {cantidad_entrega}"
            ),
        )
        mov_out.save()
        creados.append(mov_out)

    return creados
