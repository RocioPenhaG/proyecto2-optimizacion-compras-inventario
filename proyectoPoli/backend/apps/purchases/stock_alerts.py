"""
Reglas para excluir productos de alertas de stock crítico cuando fueron adquiridos
solo para entrega inmediata (solicitud puntual, sin inventario permanente).
"""
from .models import EstadoSolicitud, SolicitudDetalle, TipoDestinoCompra

_ESTADOS_NO_RECHAZADA = (
    EstadoSolicitud.SOLICITADO,
    EstadoSolicitud.EN_REVISION,
    EstadoSolicitud.COMPRA_ACEPTADA,
    EstadoSolicitud.FINALIZADO,
)


def producto_parte_inventario_permanente(producto_id: int) -> bool:
    """True si el producto figura en al menos una solicitud marcada como para inventario."""
    return SolicitudDetalle.objects.filter(
        producto_id=producto_id,
        solicitud__estado__in=_ESTADOS_NO_RECHAZADA,
        solicitud__tipo_destino_compra=TipoDestinoCompra.INVENTARIO,
    ).exists()


def producto_solo_entrega_inmediata(producto_id: int) -> bool:
    """
    True si todas las solicitudes no rechazadas del producto son entrega inmediata.
    Solicitudes antiguas sin el campo quedan como INVENTARIO por defecto en BD.
    """
    detalles = (
        SolicitudDetalle.objects.filter(producto_id=producto_id)
        .exclude(solicitud__estado=EstadoSolicitud.COMPRA_RECHAZADA)
        .select_related("solicitud")
    )
    if not detalles.exists():
        return False
    return all(
        d.solicitud.tipo_destino_compra == TipoDestinoCompra.ENTREGA_INMEDIATA for d in detalles
    )


def excluir_de_alerta_stock_critico(producto_id: int, stock_actual: int) -> bool:
    """
    No alertar por stock 0 cuando el insumo se compró únicamente para entrega inmediata.
    Productos con solicitudes de inventario mantienen el comportamiento habitual.
    """
    if stock_actual > 0:
        return False
    if producto_parte_inventario_permanente(producto_id):
        return False
    return producto_solo_entrega_inmediata(producto_id)
