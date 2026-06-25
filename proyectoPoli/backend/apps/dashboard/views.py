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
from apps.purchases.rules import queryset_solicitudes_visible_para_rol
from apps.purchases.stock_alerts import excluir_de_alerta_stock_critico
from apps.products.models import Producto
from apps.analytics.date_range import parse_fechas
from apps.analytics.models import HechoConsumo


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

    try:
        fecha_desde_date, fecha_hasta_date = parse_fechas(request)
    except ValueError:
        return Response(
            {"detail": "Formato de fecha inválido. Use YYYY-MM-DD en desde y hasta."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    fecha_desde = timezone.make_aware(datetime.combine(fecha_desde_date, datetime.min.time()))
    fecha_hasta = timezone.make_aware(
        datetime.strptime(fecha_hasta_date.strftime("%Y-%m-%d") + " 23:59:59", "%Y-%m-%d %H:%M:%S")
    )
    desde = str(fecha_desde_date)
    hasta = str(fecha_hasta_date)

    qs_solicitudes = queryset_solicitudes_visible_para_rol(
        request.user,
        SolicitudInsumo.objects.filter(creado_en__range=(fecha_desde, fecha_hasta)),
    )

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

    # Productos con stock crítico + detalle de cobertura/riesgo/recomendación para renderizar sección visible.
    fecha_desde_date = fecha_desde.date()
    fecha_hasta_date = fecha_hasta.date()
    dias_periodo = max(1, (fecha_hasta_date - fecha_desde_date).days + 1)

    consumo_map = {
        row["producto_id"]: int(row["cantidad_total"] or 0)
        for row in HechoConsumo.objects.filter(
            tipo_movimiento="OUT",
            fecha__gte=fecha_desde_date,
            fecha__lte=fecha_hasta_date,
        )
        .values("producto_id")
        .annotate(cantidad_total=Sum("cantidad_total"))
    }

    def _riesgo_y_recomendacion(stock_actual: int, stock_minimo: int, cobertura_dias):
        if stock_actual <= 0 or cobertura_dias == 0:
            return "Alto", "Reponer urgente"
        if cobertura_dias is not None and cobertura_dias <= 7:
            return "Alto", "Reponer pronto"
        if stock_actual <= stock_minimo:
            return "Medio", "Monitorear"
        if cobertura_dias is not None and 8 <= cobertura_dias <= 15:
            return "Medio", "Monitorear"
        return "Bajo", "Sin acción inmediata"

    productos_activos = list(Producto.objects.filter(activo=True).select_related("stock"))

    detalle_criticos = []
    total_sin_stock = 0
    total_cobertura_baja = 0

    for p in productos_activos:
        try:
            stock_actual = int(p.stock.qty_on_hand) if p.stock else 0
        except Exception:
            stock_actual = 0
        stock_minimo = int(p.stock_minimo or 0)
        if excluir_de_alerta_stock_critico(p.id, stock_actual):
            continue
        cantidad_consumida = int(consumo_map.get(p.id, 0))
        if stock_minimo <= 0 and cantidad_consumida <= 0:
            continue
        consumo_promedio_diario = round(cantidad_consumida / dias_periodo, 2) if dias_periodo else 0.0
        if stock_actual <= 0:
            cobertura_dias, cobertura_texto = 0, "Sin stock"
        elif consumo_promedio_diario > 0:
            cobertura_dias = int(round(stock_actual / consumo_promedio_diario))
            cobertura_texto = f"{cobertura_dias} días"
        else:
            cobertura_dias, cobertura_texto = None, "Sin consumo en período"
        riesgo, recomendacion = _riesgo_y_recomendacion(stock_actual, stock_minimo, cobertura_dias)

        es_critico = (stock_actual <= stock_minimo) or (
            cobertura_dias is not None and cobertura_dias <= 7
        )
        if not es_critico:
            continue

        if stock_actual <= 0:
            total_sin_stock += 1
        if cobertura_dias is not None and cobertura_dias <= 7:
            total_cobertura_baja += 1

        detalle_criticos.append(
            {
                "producto_id": p.id,
                "nombre": p.nombre,
                "sku": p.sku,
                "stock_actual": stock_actual,
                "stock_minimo": stock_minimo,
                "cobertura_dias": cobertura_dias,
                "cobertura_texto": cobertura_texto,
                "riesgo": riesgo,
                "recomendacion": recomendacion,
            }
        )

    riesgo_rank = {"Alto": 0, "Medio": 1, "Bajo": 2}
    detalle_criticos.sort(
        key=lambda r: (
            riesgo_rank.get(r["riesgo"], 3),
            r["cobertura_dias"] if r["cobertura_dias"] is not None else 10**9,
            r["stock_actual"],
            r["nombre"],
        )
    )
    productos_stock_critico = len(detalle_criticos)

    return Response(
        {
            "solicitudes_por_estado": solicitudes_por_estado,
            "tiempo_promedio_aprobacion_dias": tiempo_promedio_aprobacion_dias,
            "top_insumos_solicitados": top_insumos,
            "productos_stock_critico": productos_stock_critico,
            "stock_critico": {
                "resumen": {
                    "total_productos_criticos": productos_stock_critico,
                    "total_sin_stock": total_sin_stock,
                    "total_cobertura_baja": total_cobertura_baja,
                },
                "resultados": detalle_criticos,
            },
            "filtro_desde": desde or fecha_desde.strftime("%Y-%m-%d"),
            "filtro_hasta": hasta or fecha_hasta.strftime("%Y-%m-%d"),
        }
    )
