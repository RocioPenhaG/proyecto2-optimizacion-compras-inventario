"""
Vista de dashboard para Release 1: métricas de solicitudes e insumos.
Acceso: Compras, Gerencia, Contable (solo lectura), Administrador.
"""
from datetime import datetime, timedelta
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.models import Role
from apps.purchases.models import SolicitudInsumo, EstadoSolicitud
from apps.purchases.models import SolicitudDetalle
from apps.products.models import Producto


def puede_ver_dashboard(user):
    return user.role in (Role.COMPRAS, Role.GERENCIA, Role.CONTABLE, Role.ADMINISTRADOR)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_metrics(request):
    if not puede_ver_dashboard(request.user):
        return Response(
            {"detail": "No tiene permiso para ver el dashboard."},
            status=status.HTTP_403_FORBIDDEN,
        )

    desde = request.query_params.get("desde")
    hasta = request.query_params.get("hasta")
    try:
        if desde:
            fecha_desde = timezone.make_aware(datetime.strptime(desde, "%Y-%m-%d"))
        else:
            fecha_desde = timezone.now() - timedelta(days=90)
        if hasta:
            fecha_hasta = timezone.make_aware(
                datetime.strptime(hasta + " 23:59:59", "%Y-%m-%d %H:%M:%S")
            )
        else:
            fecha_hasta = timezone.now()
    except ValueError:
        return Response(
            {"detail": "Formato de fecha inválido. Use YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    qs_solicitudes = SolicitudInsumo.objects.filter(creado_en__range=(fecha_desde, fecha_hasta))

    # Solicitudes por estado
    por_estado = dict(
        qs_solicitudes.values("estado").annotate(cantidad=Count("id")).values_list("estado", "cantidad")
    )
    solicitudes_por_estado = {
        estado: por_estado.get(estado, 0)
        for estado in [e[0] for e in EstadoSolicitud.choices]
    }

    # Tiempo promedio de aprobación (días): desde creado_en hasta aprobado_en para aprobadas/rechazadas/finalizadas
    finalizadas = qs_solicitudes.filter(
        estado__in=(
            EstadoSolicitud.COMPRA_ACEPTADA,
            EstadoSolicitud.COMPRA_RECHAZADA,
            EstadoSolicitud.FINALIZADO,
        ),
        aprobado_en__isnull=False,
    )
    tiempos = []
    for s in finalizadas:
        delta = s.aprobado_en - s.creado_en
        tiempos.append(delta.total_seconds() / 86400.0)
    tiempo_promedio_aprobacion_dias = round(sum(tiempos) / len(tiempos), 1) if tiempos else 0.0

    # Top insumos solicitados (por cantidad total en detalles en el rango)
    detalles = SolicitudDetalle.objects.filter(
        solicitud__creado_en__range=(fecha_desde, fecha_hasta)
    ).values("producto_id").annotate(cantidad_total=Sum("cantidad")).order_by("-cantidad_total")[:10]

    productos_ids = [d["producto_id"] for d in detalles]
    productos_map = {p.id: p for p in Producto.objects.filter(id__in=productos_ids)}
    top_insumos = [
        {
            "producto_id": d["producto_id"],
            "producto_nombre": productos_map.get(d["producto_id"]).nombre
            if productos_map.get(d["producto_id"])
            else "—",
            "producto_sku": productos_map.get(d["producto_id"]).sku
            if productos_map.get(d["producto_id"])
            else "—",
            "cantidad_total": d["cantidad_total"],
        }
        for d in detalles
    ]

    # Productos con stock crítico (stock actual < stock mínimo)
    productos_criticos = Producto.objects.filter(stock_minimo__gt=0).select_related("stock")
    def _es_critico(p):
        try:
            qty = p.stock.qty_on_hand if p.stock else 0
        except Exception:
            qty = 0
        return qty < p.stock_minimo
    productos_stock_critico = sum(1 for p in productos_criticos if _es_critico(p))

    return Response(
        {
            "solicitudes_por_estado": solicitudes_por_estado,
            "tiempo_promedio_aprobacion_dias": tiempo_promedio_aprobacion_dias,
            "top_insumos_solicitados": top_insumos,
            "productos_stock_critico": productos_stock_critico,
            "filtro_desde": desde or fecha_desde.strftime("%Y-%m-%d"),
            "filtro_hasta": hasta or fecha_hasta.strftime("%Y-%m-%d"),
        }
    )
