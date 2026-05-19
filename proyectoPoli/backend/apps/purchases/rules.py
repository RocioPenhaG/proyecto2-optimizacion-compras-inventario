"""
Reglas de negocio para transiciones de solicitudes (Compras vs Gerencia).
"""


from apps.inventory.models import StockProducto


def _cantidad_disponible(producto_id: int) -> int:
    try:
        return StockProducto.objects.get(producto_id=producto_id).qty_on_hand
    except StockProducto.DoesNotExist:
        return 0


def solicitud_detalles_todos_vinculados(solicitud) -> bool:
    """True si cada línea tiene ya un producto del catálogo (no insumo solo texto)."""
    return not solicitud.detalles.filter(producto__isnull=True).exists()


def solicitud_cubierta_por_stock(solicitud) -> bool:
    """True si hay cantidad suficiente en inventario para cada línea con producto."""
    for d in solicitud.detalles.all():
        if d.producto_id is None:
            return False
        if _cantidad_disponible(d.producto_id) < d.cantidad:
            return False
    return True


def solicitud_requiere_gerencia(solicitud) -> bool:
    """
    True solo si todas las líneas están vinculadas al catálogo y falta stock
    suficiente en depósito para surtir la solicitud (Compras no puede aprobar;
    corresponde Gerencia).
    """
    if not solicitud_detalles_todos_vinculados(solicitud):
        return False
    return not solicitud_cubierta_por_stock(solicitud)


def solicitud_alerta_proyeccion_consumo(solicitud) -> bool:
    """Reservado por compatibilidad de API; ya no se usa proyección de consumo en solicitudes."""
    return False


def solicitud_alertas_proyeccion_detalle(solicitud):
    """Reservado por compatibilidad de API; reposición según stock operativo, no proyección."""
    return []
