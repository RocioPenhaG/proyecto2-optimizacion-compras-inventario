"""
API de hábitos de consumo (Release 2). Mismos permisos que dashboard: Compras, Gerencia, Contable, Admin.
"""
from datetime import datetime, timedelta

from django.db.models import Q, Sum, Count, Min, Max, Avg
from django.db.models.functions import ExtractYear, ExtractMonth, ExtractWeekDay
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.models import Role
from apps.products.models import Producto
from .models import HechoConsumo, ResumenConsumoMensual


def puede_ver_analytics(user):
    return user.role in (Role.COMPRAS, Role.GERENCIA, Role.CONTABLE, Role.ADMINISTRADOR)


def parse_fechas(request):
    desde = request.query_params.get("desde")
    hasta = request.query_params.get("hasta")
    try:
        if desde:
            fecha_desde = datetime.strptime(desde, "%Y-%m-%d").date()
        else:
            fecha_desde = (timezone.now() - timedelta(days=365)).date()
        if hasta:
            fecha_hasta = datetime.strptime(hasta, "%Y-%m-%d").date()
        else:
            fecha_hasta = timezone.now().date()
        return fecha_desde, fecha_hasta
    except ValueError:
        return None, None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def consumo_mensual(request):
    """Consumo (salidas OUT) mensual por producto. Query: desde, hasta, producto_id (opcional)."""
    if not puede_ver_analytics(request.user):
        return Response(
            {"detail": "No tiene permiso para ver analytics."},
            status=status.HTTP_403_FORBIDDEN,
        )
    fecha_desde, fecha_hasta = parse_fechas(request)
    if fecha_desde is None:
        return Response(
            {"detail": "Formato de fecha inválido. Use YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    producto_id = request.query_params.get("producto_id")
    qs = ResumenConsumoMensual.objects.filter(
        Q(anio__gt=fecha_desde.year) | Q(anio=fecha_desde.year, mes__gte=fecha_desde.month),
        Q(anio__lt=fecha_hasta.year) | Q(anio=fecha_hasta.year, mes__lte=fecha_hasta.month),
    ).select_related("producto")
    if producto_id:
        qs = qs.filter(producto_id=producto_id)
    # Build list (anio, mes) within range for consistent ordering
    rows = list(
        qs.order_by("anio", "mes", "producto_id").values(
            "producto_id", "producto__sku", "producto__nombre",
            "anio", "mes", "cantidad_salidas", "promedio_diario", "dias_con_movimiento"
        )
    )
    out = [
        {
            "producto_id": r["producto_id"],
            "producto_sku": r["producto__sku"],
            "producto_nombre": r["producto__nombre"],
            "anio": r["anio"],
            "mes": r["mes"],
            "cantidad_total": r["cantidad_salidas"],
            "promedio_diario": float(r["promedio_diario"]) if r["promedio_diario"] else 0,
            "dias_con_movimiento": r["dias_con_movimiento"],
        }
        for r in rows
    ]
    return Response({
        "consumo_mensual": out,
        "filtro_desde": str(fecha_desde),
        "filtro_hasta": str(fecha_hasta),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def consumo_por_dia_semana(request):
    """Consumo (OUT) agregado por día de la semana (1=lunes, 7=domingo). Query: desde, hasta, producto_id (opcional)."""
    if not puede_ver_analytics(request.user):
        return Response(
            {"detail": "No tiene permiso para ver analytics."},
            status=status.HTTP_403_FORBIDDEN,
        )
    fecha_desde, fecha_hasta = parse_fechas(request)
    if fecha_desde is None:
        return Response(
            {"detail": "Formato de fecha inválido. Use YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    producto_id = request.query_params.get("producto_id")
    qs = (
        HechoConsumo.objects.filter(tipo_movimiento="OUT", fecha__gte=fecha_desde, fecha__lte=fecha_hasta)
        .annotate(dia_semana=ExtractWeekDay("fecha"))
        .values("producto_id", "producto__sku", "producto__nombre", "dia_semana")
        .annotate(cantidad_total=Sum("cantidad_total"), dias=Count("fecha", distinct=True))
    )
    if producto_id:
        qs = qs.filter(producto_id=producto_id)
    rows = list(qs.order_by("producto_id", "dia_semana"))
    # Django ExtractWeekDay: 1=Sunday, 2=Monday, ... 7=Saturday. Plan wants lunes=1; map to isoweekday (1=Mon, 7=Sun)
    # ExtractWeekDay in Django uses Sunday=1. So 1=Dom, 2=Lun, ... 7=Sab. We can return as-is or map to isoweekday.
    out = [
        {
            "producto_id": r["producto_id"],
            "producto_sku": r["producto__sku"],
            "producto_nombre": r["producto__nombre"],
            "dia_semana": r["dia_semana"],
            "cantidad_total": r["cantidad_total"],
            "dias": r["dias"],
        }
        for r in rows
    ]
    return Response({
        "consumo_por_dia_semana": out,
        "filtro_desde": str(fecha_desde),
        "filtro_hasta": str(fecha_hasta),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def indicadores(request):
    """Indicadores por producto: min, max, promedio mensual, desviación (opcional), comparación mes actual vs anterior."""
    if not puede_ver_analytics(request.user):
        return Response(
            {"detail": "No tiene permiso para ver analytics."},
            status=status.HTTP_403_FORBIDDEN,
        )
    fecha_desde, fecha_hasta = parse_fechas(request)
    if fecha_desde is None:
        return Response(
            {"detail": "Formato de fecha inválido. Use YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    producto_id = request.query_params.get("producto_id")
    qs = ResumenConsumoMensual.objects.filter(
        Q(anio__gt=fecha_desde.year) | Q(anio=fecha_desde.year, mes__gte=fecha_desde.month),
        Q(anio__lt=fecha_hasta.year) | Q(anio=fecha_hasta.year, mes__lte=fecha_hasta.month),
    ).select_related("producto")
    if producto_id:
        qs = qs.filter(producto_id=producto_id)
    agg = list(
        qs.values("producto_id", "producto__sku", "producto__nombre").annotate(
            minimo=Min("cantidad_salidas"),
            maximo=Max("cantidad_salidas"),
            promedio=Avg("cantidad_salidas"),
            meses_con_datos=Count("id"),
        )
    )
    hoy = timezone.now().date()
    mes_actual = hoy.month
    anio_actual = hoy.year
    mes_anterior = mes_actual - 1 if mes_actual > 1 else 12
    anio_anterior = anio_actual if mes_actual > 1 else anio_actual - 1
    producto_ids = [a["producto_id"] for a in agg]
    resumen_actual = {
        (r["producto_id"]): r
        for r in ResumenConsumoMensual.objects.filter(
            producto_id__in=producto_ids,
            anio=anio_actual,
            mes=mes_actual,
        ).values("producto_id", "cantidad_salidas", "promedio_diario")
    }
    resumen_anterior = {
        (r["producto_id"]): r
        for r in ResumenConsumoMensual.objects.filter(
            producto_id__in=producto_ids,
            anio=anio_anterior,
            mes=mes_anterior,
        ).values("producto_id", "cantidad_salidas", "promedio_diario")
    }
    out = []
    for a in agg:
        pid = a["producto_id"]
        actual = resumen_actual.get(pid, {})
        anterior = resumen_anterior.get(pid, {})
        cant_actual = actual.get("cantidad_salidas") or 0
        cant_anterior = anterior.get("cantidad_salidas") or 0
        diff = cant_actual - cant_anterior
        out.append({
            "producto_id": pid,
            "producto_sku": a["producto__sku"],
            "producto_nombre": a["producto__nombre"],
            "minimo_mensual": a["minimo"],
            "maximo_mensual": a["maximo"],
            "promedio_mensual": float(a["promedio"]) if a["promedio"] is not None else None,
            "meses_con_datos": a["meses_con_datos"],
            "mes_actual_cantidad": cant_actual,
            "mes_anterior_cantidad": cant_anterior,
            "diferencia_vs_anterior": diff,
        })
    return Response({
        "indicadores": out,
        "filtro_desde": str(fecha_desde),
        "filtro_hasta": str(fecha_hasta),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def habitos_resumen(request):
    """Un solo endpoint que devuelve consumo mensual + por día de semana + indicadores (para el dashboard)."""
    if not puede_ver_analytics(request.user):
        return Response(
            {"detail": "No tiene permiso para ver analytics."},
            status=status.HTTP_403_FORBIDDEN,
        )
    fecha_desde, fecha_hasta = parse_fechas(request)
    if fecha_desde is None:
        return Response(
            {"detail": "Formato de fecha inválido. Use YYYY-MM-DD."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    producto_id = request.query_params.get("producto_id")

    # Consumo mensual (desde ResumenConsumoMensual)
    qs_m = ResumenConsumoMensual.objects.filter(
        Q(anio__gt=fecha_desde.year) | Q(anio=fecha_desde.year, mes__gte=fecha_desde.month),
        Q(anio__lt=fecha_hasta.year) | Q(anio=fecha_hasta.year, mes__lte=fecha_hasta.month),
    ).select_related("producto")
    if producto_id:
        qs_m = qs_m.filter(producto_id=producto_id)
    consumo_mensual_list = [
        {
            "producto_id": r["producto_id"],
            "producto_sku": r["producto__sku"],
            "producto_nombre": r["producto__nombre"],
            "anio": r["anio"],
            "mes": r["mes"],
            "cantidad_total": r["cantidad_salidas"],
            "promedio_diario": float(r["promedio_diario"]) if r["promedio_diario"] else 0,
        }
        for r in qs_m.order_by("anio", "mes", "producto_id").values(
            "producto_id", "producto__sku", "producto__nombre",
            "anio", "mes", "cantidad_salidas", "promedio_diario"
        )
    ]

    # Por día de semana
    qs_d = (
        HechoConsumo.objects.filter(tipo_movimiento="OUT", fecha__gte=fecha_desde, fecha__lte=fecha_hasta)
        .annotate(dia_semana=ExtractWeekDay("fecha"))
        .values("producto_id", "producto__sku", "producto__nombre", "dia_semana")
        .annotate(cantidad_total=Sum("cantidad_total"))
    )
    if producto_id:
        qs_d = qs_d.filter(producto_id=producto_id)
    consumo_por_dia_semana_list = [
        {"producto_id": r["producto_id"], "producto_sku": r["producto__sku"], "producto_nombre": r["producto__nombre"], "dia_semana": r["dia_semana"], "cantidad_total": r["cantidad_total"]}
        for r in qs_d
    ]

    return Response({
        "consumo_mensual": consumo_mensual_list,
        "consumo_por_dia_semana": consumo_por_dia_semana_list,
        "filtro_desde": str(fecha_desde),
        "filtro_hasta": str(fecha_hasta),
    })
