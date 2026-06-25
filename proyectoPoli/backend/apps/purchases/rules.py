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


def solicitud_tiene_items_fuera_catalogo(solicitud) -> bool:
    """True si queda al menos una línea sin vincular al catálogo."""
    return solicitud.detalles.filter(producto__isnull=True).exists()


def solicitud_compras_puede_rechazar(solicitud) -> bool:
    """Compras no rechaza solicitudes con ítems fuera de catálogo; corresponde Gerencia."""
    return not solicitud_tiene_items_fuera_catalogo(solicitud)


def solicitud_permite_transicion_sin_vinculo_completo(estado_actual, nuevo_estado, user_role) -> bool:
    """
    Transiciones permitidas aunque falte vincular ítems fuera de catálogo:
    - SOLICITADO → EN_REVISION (ingreso a bandeja de Compras)
    - EN_REVISION → COMPRA_ACEPTADA o COMPRA_RECHAZADA por Gerencia (solo fuera de catálogo)
    """
    from apps.users.models import Role

    from .models import EstadoSolicitud

    if estado_actual == EstadoSolicitud.SOLICITADO and nuevo_estado == EstadoSolicitud.EN_REVISION:
        return True
    if (
        estado_actual == EstadoSolicitud.EN_REVISION
        and user_role in (Role.GERENCIA, Role.ADMINISTRADOR)
        and nuevo_estado in (EstadoSolicitud.COMPRA_ACEPTADA, EstadoSolicitud.COMPRA_RECHAZADA)
    ):
        return True
    return False


def solicitud_compras_exige_vinculo_para_aprobar(user_role, nuevo_estado, solicitud=None) -> bool:
    """
    Compras debe vincular ítems del catálogo antes de aprobar (solo solicitudes de catálogo).
    Fuera de catálogo: Gerencia aprueba primero; la vinculación es posterior a COMPRA_ACEPTADA.
    """
    from apps.users.models import Role

    from .models import EstadoSolicitud

    if user_role != Role.COMPRAS:
        return False
    if nuevo_estado == EstadoSolicitud.FINALIZADO:
        return True
    if nuevo_estado == EstadoSolicitud.COMPRA_ACEPTADA:
        if solicitud is not None and solicitud.contiene_fuera_catalogo:
            return False
        return True
    return False


def solicitud_puede_vincular_detalle(solicitud) -> bool:
    """Ítems fuera de catálogo: vincular solo después de que Gerencia acepte la compra."""
    tiene_fuera = solicitud.contiene_fuera_catalogo or solicitud_tiene_items_fuera_catalogo(solicitud)
    if not tiene_fuera:
        return True
    from .models import EstadoSolicitud

    return solicitud.estado == EstadoSolicitud.COMPRA_ACEPTADA


def solicitud_puede_editar_cantidad_detalle_fuera_catalogo(solicitud, detalle) -> bool:
    """
    Compras o Gerencia pueden ajustar la cantidad a comprar en ítems fuera de catálogo
    destinados a inventario, mientras el ítem no esté vinculado al catálogo.
    La cantidad inicial del funcionario (cantidad_inicial) no se modifica.
    """
    from .models import EstadoSolicitud, TipoDestinoCompra

    if not solicitud.contiene_fuera_catalogo:
        return False
    if detalle.producto_id is not None:
        return False
    if solicitud.tipo_destino_compra == TipoDestinoCompra.ENTREGA_INMEDIATA:
        return False
    if solicitud.tipo_destino_compra not in (TipoDestinoCompra.INVENTARIO, None):
        return False
    return solicitud.estado in (
        EstadoSolicitud.SOLICITADO,
        EstadoSolicitud.EN_REVISION,
        EstadoSolicitud.COMPRA_ACEPTADA,
    )


def solicitud_puede_editar_tipo_destino_compra(solicitud) -> bool:
    """Compras define destino solo en solicitudes con ítems fuera de catálogo."""
    from .models import EstadoSolicitud

    if not solicitud.contiene_fuera_catalogo:
        return False
    if solicitud.estado == EstadoSolicitud.SOLICITADO:
        return True
    if solicitud.estado == EstadoSolicitud.EN_REVISION and not solicitud.tipo_destino_compra:
        return True
    if solicitud.estado == EstadoSolicitud.COMPRA_ACEPTADA and not solicitud.tipo_destino_compra:
        return True
    return False


MENSAJE_STOCK_INFERIOR_SOLICITADO = (
    "El producto seleccionado tiene un stock inferior al solicitado."
)


def solicitud_cubierta_por_stock(solicitud) -> bool:
    """True si hay cantidad suficiente en inventario para cada línea con producto."""
    return solicitud_primer_detalle_stock_insuficiente(solicitud) is None


def solicitud_primer_detalle_stock_insuficiente(solicitud):
    """Devuelve (detalle, stock_disponible) del primer ítem de catálogo sin stock suficiente."""
    for d in solicitud.detalles.select_related("producto"):
        if d.producto_id is None:
            continue
        disponible = _cantidad_disponible(d.producto_id)
        if disponible < d.cantidad:
            return d, disponible
    return None


def mensaje_stock_insuficiente_catalogo(solicitud) -> str:
    insuf = solicitud_primer_detalle_stock_insuficiente(solicitud)
    if not insuf:
        return MENSAJE_STOCK_INFERIOR_SOLICITADO
    detalle, disponible = insuf
    nombre = detalle.producto.nombre if detalle.producto_id else "Producto"
    return (
        f"{MENSAJE_STOCK_INFERIOR_SOLICITADO} "
        f"({nombre}: disponible {disponible}, solicitado {detalle.cantidad})."
    )


def solicitud_requiere_gerencia(solicitud) -> bool:
    """
    Solicitudes de catálogo las aprueba Compras (sin circuito Gerencia por stock).
    Fuera de catálogo: Gerencia decide en EN_REVISION (no usa este flag).
    """
    return False


def gerencia_puede_cambiar_estado_solicitud(solicitud) -> bool:
    """Gerencia solo aprueba o rechaza solicitudes con ítems fuera de catálogo."""
    return bool(solicitud.contiene_fuera_catalogo)


def gerencia_puede_ver_solicitud(solicitud) -> bool:
    """
    Fuera de catálogo: Gerencia solo ve la solicitud después de que Compras
    la envía a revisión (solicitud de aprobación). Catálogo: siempre visible.
    """
    from .models import EstadoSolicitud

    if not solicitud.contiene_fuera_catalogo:
        return True
    return solicitud.estado != EstadoSolicitud.SOLICITADO


def queryset_solicitudes_visible_para_rol(user, qs):
    """Filtra solicitudes según permisos de listado/detalle por rol."""
    from django.db.models import Q

    from apps.users.models import Role

    from .models import EstadoSolicitud

    if user.role == Role.GERENCIA:
        return qs.filter(
            Q(contiene_fuera_catalogo=False)
            | ~Q(estado=EstadoSolicitud.SOLICITADO)
        )
    if user.role in (Role.COMPRAS, Role.CONTABLE, Role.ADMINISTRADOR):
        return qs
    return qs.filter(solicitante=user)


def solicitud_alerta_proyeccion_consumo(solicitud) -> bool:
    """Reservado por compatibilidad de API; ya no se usa proyección de consumo en solicitudes."""
    return False


def solicitud_alertas_proyeccion_detalle(solicitud):
    """Reservado por compatibilidad de API; reposición según stock operativo, no proyección."""
    return []
