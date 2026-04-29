"""
API de hábitos de consumo (Release 2). Mismos permisos que dashboard: Compras, Gerencia, Contable, Admin.
"""
import uuid
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
from .models import HechoConsumo, ResumenConsumoMensual, CorridaAnalitica, ResultadoTendenciaLineal
from .tasks import run_etl_analitico_d1


def puede_ver_analytics(user):
    return user.role in (Role.COMPRAS, Role.GERENCIA, Role.CONTABLE, Role.ADMINISTRADOR)


def puede_gestionar_corridas(user):
    return user.role in (Role.GERENCIA, Role.ADMINISTRADOR)


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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ejecutar_etl_d1(request):
    """
    Encola una corrida ETL D-1 vía Celery.
    No ejecuta procesamiento sincrónico.
    """
    if not puede_gestionar_corridas(request.user):
        return Response(
            {"detail": "No tiene permiso para ejecutar corridas analíticas."},
            status=status.HTTP_403_FORBIDDEN,
        )

    ayer = (timezone.now() - timedelta(days=1)).date()
    task_id = str(uuid.uuid4())
    CorridaAnalitica.objects.create(
        task_id=task_id,
        estado=CorridaAnalitica.Estado.QUEUED,
        queued_at=timezone.now(),
        metodo=CorridaAnalitica.Metodo.API,
        fecha_desde=ayer,
        fecha_hasta=ayer,
        parametros={"fecha_desde": str(ayer), "fecha_hasta": str(ayer), "scope": "D-1"},
        mensaje="Ejecución encolada desde API.",
        error_detalle="",
        ejecutado_por=request.user,
    )
    run_etl_analitico_d1.apply_async(task_id=task_id)
    return Response(
        {
            "message": "Corrida ETL D-1 encolada correctamente.",
            "task_id": task_id,
            "status": "QUEUED",
        },
        status=status.HTTP_202_ACCEPTED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def estado_corrida(request, task_id):
    """Consulta estado y métricas de una corrida por task_id."""
    if not puede_ver_analytics(request.user):
        return Response(
            {"detail": "No tiene permiso para consultar corridas analíticas."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        corrida = CorridaAnalitica.objects.get(task_id=task_id)
    except CorridaAnalitica.DoesNotExist:
        return Response(
            {"detail": "No existe una corrida analítica para ese task_id."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(
        {
            "task_id": corrida.task_id,
            "estado": corrida.estado,
            "queued_at": corrida.queued_at,
            "started_at": corrida.started_at,
            "finished_at": corrida.finished_at,
            "registros_procesados": corrida.registros_procesados,
            "puntos_usados": corrida.puntos_usados,
            "mensaje": corrida.mensaje,
            "error_detalle": corrida.error_detalle,
            "resultados_tendencia_count": corrida.resultados_tendencia.count(),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ultimas_corridas(request):
    """Lista últimas corridas (default 10, máximo 20)."""
    if not puede_ver_analytics(request.user):
        return Response(
            {"detail": "No tiene permiso para consultar corridas analíticas."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        limite = int(request.query_params.get("limit", 10))
    except (TypeError, ValueError):
        return Response({"detail": "Parámetro limit inválido."}, status=status.HTTP_400_BAD_REQUEST)

    limite = max(1, min(limite, 20))
    corridas = CorridaAnalitica.objects.all().order_by("-fecha_ejecucion")[:limite]
    data = [
        {
            "id": c.id,
            "task_id": c.task_id,
            "estado": c.estado,
            "fecha_ejecucion": c.fecha_ejecucion,
            "queued_at": c.queued_at,
            "started_at": c.started_at,
            "finished_at": c.finished_at,
            "registros_procesados": c.registros_procesados,
            "puntos_usados": c.puntos_usados,
            "mensaje": c.mensaje,
            "error_detalle": c.error_detalle,
            "resultados_tendencia_count": c.resultados_tendencia.count(),
        }
        for c in corridas
    ]
    return Response({"count": len(data), "results": data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tendencias_por_corrida(request, corrida_id):
    """Lista resultados de tendencia lineal asociados a una corrida."""
    if not puede_ver_analytics(request.user):
        return Response(
            {"detail": "No tiene permiso para ver analytics."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        corrida = CorridaAnalitica.objects.get(id=corrida_id)
    except CorridaAnalitica.DoesNotExist:
        return Response(
            {"detail": "No existe la corrida analítica solicitada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    resultados = (
        ResultadoTendenciaLineal.objects.filter(corrida=corrida)
        .select_related("producto")
        .order_by("producto__sku", "producto__nombre", "id")
    )
    data = [
        {
            "id": r.id,
            "producto_id": r.producto_id,
            "producto_nombre": r.producto.nombre,
            "producto_sku": r.producto.sku,
            "periodicidad": r.periodicidad,
            "puntos_usados": r.puntos_usados,
            "pendiente": float(r.pendiente),
            "intercepto": float(r.intercepto),
            "r2": float(r.r2) if r.r2 is not None else None,
            "mae": float(r.mae) if r.mae is not None else None,
            "rmse": float(r.rmse) if r.rmse is not None else None,
            "prediccion_siguiente": float(r.prediccion_siguiente),
            "fecha_inicio": r.fecha_inicio,
            "fecha_fin": r.fecha_fin,
        }
        for r in resultados
    ]
    return Response({"corrida_id": corrida.id, "task_id": corrida.task_id, "count": len(data), "results": data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def detalle_visual_tendencia(request, tendencia_id):
    """Devuelve serie histórica, línea de tendencia y predicción siguiente para una tendencia."""
    if not puede_ver_analytics(request.user):
        return Response(
            {"detail": "No tiene permiso para ver analytics."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        tendencia = ResultadoTendenciaLineal.objects.select_related("producto").get(id=tendencia_id)
    except ResultadoTendenciaLineal.DoesNotExist:
        return Response(
            {"detail": "No existe la tendencia solicitada."},
            status=status.HTTP_404_NOT_FOUND,
        )

    historico_qs = (
        HechoConsumo.objects.filter(
            producto_id=tendencia.producto_id,
            tipo_movimiento="OUT",
            fecha__gte=tendencia.fecha_inicio,
            fecha__lte=tendencia.fecha_fin,
        )
        .values("fecha")
        .annotate(consumo=Sum("cantidad_total"))
        .order_by("fecha")
    )
    historico_rows = list(historico_qs)
    historico = [{"fecha": row["fecha"], "consumo": float(row["consumo"])} for row in historico_rows]
    tendencia_estimacion = [
        {
            "fecha": row["fecha"],
            "valor": float(tendencia.intercepto) + (float(tendencia.pendiente) * idx),
        }
        for idx, row in enumerate(historico_rows)
    ]

    if tendencia.periodicidad == "DAILY":
        fecha_prediccion = tendencia.fecha_fin + timedelta(days=1)
    else:
        fecha_prediccion = tendencia.fecha_fin + timedelta(days=1)

    data = {
        "id": tendencia.id,
        "corrida_id": tendencia.corrida_id,
        "producto_id": tendencia.producto_id,
        "producto": tendencia.producto.nombre,
        "sku": tendencia.producto.sku,
        "periodicidad": tendencia.periodicidad,
        "historico": historico,
        "tendencia": tendencia_estimacion,
        "prediccion": {
            "fecha": fecha_prediccion,
            "valor": float(tendencia.prediccion_siguiente),
        },
    }
    if len(historico) < 2:
        data["detail"] = "No hay datos suficientes para visualizar la tendencia."
    return Response(data)
