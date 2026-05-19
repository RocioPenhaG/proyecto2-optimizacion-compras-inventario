"""
API de hábitos de consumo (Release 2). Mismos permisos que dashboard: Compras, Gerencia, Contable, Admin.
"""
import uuid
from datetime import datetime, time, timedelta

from django.db.models import Q, Sum, Count, Min, Max, Avg
from django.db.models.functions import ExtractYear, ExtractMonth, ExtractWeekDay
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.models import Role
from apps.products.models import Producto
from apps.purchases.models import SolicitudDetalle
from apps.inventory.models import StockProducto
from .models import (
    HechoConsumo,
    ResumenConsumoMensual,
    CorridaAnalitica,
    ProyeccionConsumoFuturo,
    ResultadoTendenciaLineal,
)
from .etl import (
    DEFAULT_PROYECCION_HORIZONTE_DIAS,
    generar_proyecciones_consumo,
    resolver_productos_candidatos_tendencia,
)
from .proyecciones import cantidad_entera
from .date_range import parse_fechas
from .tasks import run_etl_analitico_d1


def _productos_candidatos_tendencia_para_api(corrida):
    """Expone total de productos en ventana de tendencia; no infiere en corridas no finalizadas con éxito."""
    if corrida.productos_candidatos_tendencia is not None:
        return corrida.productos_candidatos_tendencia
    if corrida.estado not in (CorridaAnalitica.Estado.SUCCESS, CorridaAnalitica.Estado.OK):
        return None
    return resolver_productos_candidatos_tendencia(corrida)


def puede_ver_analytics(user):
    return user.role in (Role.COMPRAS, Role.GERENCIA, Role.CONTABLE, Role.ADMINISTRADOR)


def puede_gestionar_corridas(user):
    return user.role in (Role.GERENCIA, Role.ADMINISTRADOR)


def _stock_actual_producto(producto) -> int:
    try:
        return int(producto.stock.qty_on_hand)
    except Exception:
        return 0


def calcular_reposicion_sugerida_tendencia(
    stock_actual,
    stock_minimo,
    pendiente,
    prediccion_siguiente,
):
    """
    Cantidad orientativa de reposición para el listado de tendencias lineales.
    No usa proyecciones multi-día ni ProyeccionConsumoFuturo.
    """
    stock_actual_int = int(stock_actual or 0)
    stock_minimo_int = int(stock_minimo or 0)
    pendiente_int = cantidad_entera(pendiente) or 0
    prediccion_int = cantidad_entera(prediccion_siguiente) or 0

    if stock_actual_int >= stock_minimo_int:
        return 0, "Stock suficiente"

    if pendiente_int > 0:
        cantidad = max(0, stock_minimo_int + prediccion_int - stock_actual_int)
        return cantidad, "Stock bajo con tendencia creciente"

    cantidad = max(0, stock_minimo_int - stock_actual_int)
    return cantidad, "Stock bajo"


def _respuesta_fecha_invalida():
    return Response(
        {"detail": "Formato de fecha inválido. Use YYYY-MM-DD en desde y hasta."},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _qs_hecho_out(fecha_desde, fecha_hasta):
    return HechoConsumo.objects.filter(
        tipo_movimiento="OUT",
        fecha__gte=fecha_desde,
        fecha__lte=fecha_hasta,
    )


def _qs_resumen_mensual(fecha_desde, fecha_hasta):
    return ResumenConsumoMensual.objects.filter(
        Q(anio__gt=fecha_desde.year) | Q(anio=fecha_desde.year, mes__gte=fecha_desde.month),
        Q(anio__lt=fecha_hasta.year) | Q(anio=fecha_hasta.year, mes__lte=fecha_hasta.month),
    )


def _consumo_mensual_desde_hecho(fecha_desde, fecha_hasta, producto_id=None):
    """
    Consumo OUT agrupado por producto y mes calendario, respetando el rango [desde, hasta]
    (solo días dentro del filtro, no el mes completo del resumen materializado).
    """
    qs = _qs_hecho_out(fecha_desde, fecha_hasta).select_related("producto")
    if producto_id:
        qs = qs.filter(producto_id=producto_id)
    rows = list(
        qs.annotate(anio=ExtractYear("fecha"), mes=ExtractMonth("fecha"))
        .values("producto_id", "producto__sku", "producto__nombre", "anio", "mes")
        .annotate(
            cantidad_total=Sum("cantidad_total"),
            dias_con_movimiento=Count("fecha", distinct=True),
        )
        .order_by("anio", "mes", "producto_id")
    )
    out = []
    for r in rows:
        cant = int(r["cantidad_total"] or 0)
        dias = int(r["dias_con_movimiento"] or 0)
        out.append(
            {
                "producto_id": r["producto_id"],
                "producto_sku": r["producto__sku"],
                "producto_nombre": r["producto__nombre"],
                "anio": r["anio"],
                "mes": r["mes"],
                "cantidad_total": cant,
                "promedio_diario": round(cant / dias, 2) if dias else 0.0,
                "dias_con_movimiento": dias,
            }
        )
    return out


def _meta_filtro_fechas(fecha_desde, fecha_hasta):
    return {
        "filtro_desde": str(fecha_desde),
        "filtro_hasta": str(fecha_hasta),
        "filtro_historico": False,
    }


def _dias_periodo_analitico(fecha_desde, fecha_hasta):
    if fecha_desde and fecha_hasta:
        return max(1, (fecha_hasta - fecha_desde).days + 1)
    agg = HechoConsumo.objects.filter(tipo_movimiento="OUT").aggregate(
        mn=Min("fecha"),
        mx=Max("fecha"),
    )
    if agg["mn"] and agg["mx"]:
        return max(1, (agg["mx"] - agg["mn"]).days + 1)
    return 1


def _proyeccion_horizonte_corrida(corrida):
    params = corrida.parametros if isinstance(corrida.parametros, dict) else {}
    raw = params.get("proyeccion_horizonte_dias")
    if raw is not None:
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            pass
    return DEFAULT_PROYECCION_HORIZONTE_DIAS


def _mapa_acumulados_proyeccion(tendencia_ids, horizontes=(7, 14, 30)):
    """Acumulado de consumo proyectado por tendencia en horizontes clave."""
    if not tendencia_ids:
        return {}
    filas = ProyeccionConsumoFuturo.objects.filter(
        tendencia_id__in=tendencia_ids,
        horizonte_dias__in=horizontes,
    ).values("tendencia_id", "horizonte_dias", "consumo_acumulado")
    out = {}
    for fila in filas:
        tid = fila["tendencia_id"]
        out.setdefault(tid, {})[fila["horizonte_dias"]] = cantidad_entera(fila["consumo_acumulado"])
    return out


def _serializar_proyeccion_fila(p):
    return serializar_fila_proyeccion_diaria(
        {
            "fecha": p.fecha,
            "horizonte_dias": p.horizonte_dias,
            "valor_diario": p.valor_diario,
            "consumo_acumulado": p.consumo_acumulado,
        }
    )


def _proyecciones_para_tendencia(tendencia):
    qs = ProyeccionConsumoFuturo.objects.filter(tendencia=tendencia).order_by("horizonte_dias")
    if qs.exists():
        return [_serializar_proyeccion_fila(p) for p in qs]
    horizonte = _proyeccion_horizonte_corrida(tendencia.corrida)
    filas = generar_proyecciones_consumo(
        tendencia.intercepto,
        tendencia.pendiente,
        tendencia.puntos_usados,
        tendencia.fecha_fin,
        horizonte_dias=horizonte,
    )
    return [serializar_fila_proyeccion_diaria(p) for p in filas]


def _resumen_proyecciones(proyecciones, fecha_fin):
    return serializar_resumen_proyecciones_api(
        resumen_proyecciones_completo(proyecciones, fecha_fin)
    )


def _serialize_corrida_resumida(c):
    """Payload común para listados y última corrida (sin duplicar lógica)."""
    return {
        "id": c.id,
        "task_id": c.task_id,
        "estado": c.estado,
        "metodo": c.metodo,
        "fecha_ejecucion": c.fecha_ejecucion,
        "queued_at": c.queued_at,
        "started_at": c.started_at,
        "finished_at": c.finished_at,
        "fecha_desde": c.fecha_desde,
        "fecha_hasta": c.fecha_hasta,
        "registros_procesados": c.registros_procesados,
        "puntos_usados": c.puntos_usados,
        "mensaje": c.mensaje,
        "error_detalle": c.error_detalle,
        "resultados_tendencia_count": c.resultados_tendencia.count(),
        "proyecciones_count": c.proyecciones_consumo.count(),
        "proyeccion_horizonte_dias": _proyeccion_horizonte_corrida(c),
        "productos_candidatos_tendencia": _productos_candidatos_tendencia_para_api(c),
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def resumen_consumo(request):
    """
    Indicadores agregados de consumo (salidas OUT) en el período, desde HechoConsumo.
    No usa MovStock.
    """
    if not puede_ver_analytics(request.user):
        return Response(
            {"detail": "No tiene permiso para ver analytics."},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        fecha_desde, fecha_hasta = parse_fechas(request)
    except ValueError:
        return _respuesta_fecha_invalida()

    agg = _qs_hecho_out(fecha_desde, fecha_hasta).aggregate(
        total_salidas=Sum("cantidad_total"),
        productos_distintos=Count("producto_id", distinct=True),
        dias_con_consumo=Count("fecha", distinct=True),
        filas_hecho=Count("id"),
    )
    total = int(agg["total_salidas"] or 0)
    dias = int(agg["dias_con_consumo"] or 0)
    promedio = round(total / dias, 2) if dias else 0.0

    meses_cubiertos = (
        _qs_hecho_out(fecha_desde, fecha_hasta)
        .annotate(anio=ExtractYear("fecha"), mes=ExtractMonth("fecha"))
        .values("anio", "mes")
        .distinct()
        .count()
    )

    return Response({
        "total_salidas": total,
        "productos_distintos": int(agg["productos_distintos"] or 0),
        "dias_con_consumo": dias,
        "promedio_diario_periodo": float(promedio),
        "filas_hecho_consumo": int(agg["filas_hecho"] or 0),
        "meses_con_resumen_mensual": meses_cubiertos,
        **_meta_filtro_fechas(fecha_desde, fecha_hasta),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def top_productos_consumidos(request):
    """
    Ranking de productos por cantidad consumida (OUT) en el período, desde HechoConsumo.
    Query: desde, hasta, limit (default 10, máx. 50).
    """
    if not puede_ver_analytics(request.user):
        return Response(
            {"detail": "No tiene permiso para ver analytics."},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        fecha_desde, fecha_hasta = parse_fechas(request)
    except ValueError:
        return _respuesta_fecha_invalida()
    try:
        limit = int(request.query_params.get("limit", 10))
    except (TypeError, ValueError):
        return Response({"detail": "Parámetro limit inválido."}, status=status.HTTP_400_BAD_REQUEST)
    limit = max(1, min(limit, 50))

    rows = (
        _qs_hecho_out(fecha_desde, fecha_hasta)
        .values("producto_id", "producto__sku", "producto__nombre")
        .annotate(cantidad_total=Sum("cantidad_total"))
        .order_by("-cantidad_total")[:limit]
    )
    data = [
        {
            "producto_id": r["producto_id"],
            "producto_sku": r["producto__sku"],
            "producto_nombre": r["producto__nombre"],
            "cantidad_total": r["cantidad_total"],
        }
        for r in rows
    ]
    return Response({
        "top_productos": data,
        "limit": limit,
        **_meta_filtro_fechas(fecha_desde, fecha_hasta),
    })


def _clasificar_demanda_vs_consumo(cantidad_solicitada: int, cantidad_consumida: int):
    """
    diferencia = solicitado - consumido.
    Coherente si |diff| <= 1 o |diff| <= 10% del máximo entre solicitado y consumido.
    """
    diff = int(cantidad_solicitada) - int(cantidad_consumida)
    mx = max(int(cantidad_solicitada), int(cantidad_consumida))
    if mx == 0:
        return diff, "coherente", "Demanda coherente"
    umbral_rel = 0.10 * mx
    coherente = abs(diff) <= 1 or abs(diff) <= umbral_rel
    if coherente:
        return diff, "coherente", "Demanda coherente"
    if diff > 0:
        return diff, "solicitado_mayor", "Se solicita más de lo que se consume"
    return diff, "consumo_mayor", "Se consume más de lo solicitado"


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def demanda_vs_consumo(request):
    """
    Compara cantidades solicitadas (detalle de solicitudes en el rango) vs consumidas
    (HechoConsumo OUT, misma fuente que el ranking de productos más consumidos).
    """
    if not puede_ver_analytics(request.user):
        return Response(
            {"detail": "No tiene permiso para ver analytics."},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        fecha_desde, fecha_hasta = parse_fechas(request)
    except ValueError:
        return _respuesta_fecha_invalida()
    try:
        limit = int(request.query_params.get("limit", 50))
    except (TypeError, ValueError):
        return Response({"detail": "Parámetro limit inválido."}, status=status.HTTP_400_BAD_REQUEST)
    limit = max(1, min(limit, 100))

    sol_qs = SolicitudDetalle.objects.filter(producto_id__isnull=False)
    dt_desde = timezone.make_aware(datetime.combine(fecha_desde, time.min))
    dt_hasta = timezone.make_aware(
        datetime.strptime(fecha_hasta.strftime("%Y-%m-%d") + " 23:59:59", "%Y-%m-%d %H:%M:%S")
    )
    sol_qs = sol_qs.filter(solicitud__creado_en__range=(dt_desde, dt_hasta))

    por_solicitud = {
        r["producto_id"]: int(r["cantidad_total"] or 0)
        for r in sol_qs.values("producto_id").annotate(cantidad_total=Sum("cantidad"))
    }

    consumo_rows = list(
        _qs_hecho_out(fecha_desde, fecha_hasta)
        .values("producto_id")
        .annotate(
            cantidad_total=Sum("cantidad_total"),
            dias_con_consumo=Count("fecha", distinct=True),
        )
    )
    por_consumo = {r["producto_id"]: int(r["cantidad_total"] or 0) for r in consumo_rows}
    por_dias_consumo = {r["producto_id"]: int(r["dias_con_consumo"] or 0) for r in consumo_rows}

    stock_map = {
        s["producto_id"]: int(s["qty_on_hand"] or 0)
        for s in StockProducto.objects.values("producto_id", "qty_on_hand")
    }
    stock_relevante_ids = {
        s["producto_id"] for s in StockProducto.objects.filter(qty_on_hand__gt=0).values("producto_id")
    }

    pendiente_por_producto = {}
    for t in (
        ResultadoTendenciaLineal.objects.select_related("corrida")
        .filter(producto_id__isnull=False)
        .order_by("producto_id", "-corrida__fecha_ejecucion", "-id")
        .values("producto_id", "pendiente")
    ):
        pid = t["producto_id"]
        if pid not in pendiente_por_producto:
            pendiente_por_producto[pid] = float(t["pendiente"])

    all_ids = set(por_solicitud.keys()) | set(por_consumo.keys()) | set(stock_relevante_ids)
    all_ids.discard(None)
    productos_map = {p.id: p for p in Producto.objects.filter(id__in=all_ids)}
    dias_periodo = _dias_periodo_analitico(fecha_desde, fecha_hasta)

    def _habito_detectado(pid: int, consumo: int, dias_con_consumo: int):
        pendiente = pendiente_por_producto.get(pid)
        if pendiente is not None:
            if pendiente > 0.2:
                return "Consumo creciente"
            if pendiente < -0.2:
                return "Consumo decreciente"
            return "Consumo estable"
        if consumo <= 0:
            return "Sin consumo reciente"
        frecuencia = dias_con_consumo / dias_periodo
        if frecuencia >= 0.30:
            return "Consumo frecuente"
        return "Consumo esporádico"

    def _cobertura(stock_actual: int, consumo_promedio_diario: float):
        if stock_actual <= 0:
            return None, "Sin stock"
        if consumo_promedio_diario > 0:
            dias = int(round(stock_actual / consumo_promedio_diario))
            return dias, f"{dias} días"
        if consumo_promedio_diario == 0:
            return None, "Sin consumo reciente"
        return None, "No disponible"

    def _demanda_vs_consumo_texto(solicitado: int, consumido: int):
        diff, estado, lectura = _clasificar_demanda_vs_consumo(solicitado, consumido)
        if estado == "consumo_mayor":
            return diff, estado, lectura, "Se consume más de lo solicitado"
        if estado == "solicitado_mayor":
            return diff, estado, lectura, "Se solicita más de lo que se consume"
        return diff, estado, lectura, "Demanda coherente"

    def _riesgo_y_recomendacion(stock_actual, stock_minimo, cobertura_dias, habito, estado):
        consumo_fuerte = habito in ("Consumo frecuente", "Consumo creciente")
        if ((cobertura_dias is not None and cobertura_dias <= 7) or stock_actual <= stock_minimo) and consumo_fuerte:
            riesgo = "Alto"
        elif (cobertura_dias is not None and 8 <= cobertura_dias <= 15) or estado == "consumo_mayor":
            riesgo = "Medio"
        else:
            riesgo = "Bajo"

        if stock_actual <= 0 or cobertura_dias == 0:
            recomendacion = "Reponer urgente"
        elif habito == "Sin consumo reciente":
            recomendacion = "Revisar stock inmovilizado"
        elif estado == "consumo_mayor" and cobertura_dias is not None and cobertura_dias <= 7:
            recomendacion = "Revisar reposición"
        elif estado == "solicitado_mayor":
            recomendacion = "Validar necesidad"
        elif riesgo == "Alto":
            recomendacion = "Reponer pronto"
        elif riesgo == "Medio":
            recomendacion = "Monitorear"
        elif habito in ("Bajo movimiento", "Sin consumo reciente") and stock_actual > max(stock_minimo * 2, 0):
            recomendacion = "No priorizar compra"
        else:
            recomendacion = "Sin acción inmediata"
        return riesgo, recomendacion

    rows_full = []
    total_solicitado = 0
    total_consumido = 0
    n_solicitud_mayor = 0
    n_consumo_mayor = 0
    n_coherentes = 0
    n_riesgo_alto = 0
    n_baja_cobertura = 0

    for pid in all_ids:
        sol = por_solicitud.get(pid, 0)
        cons = por_consumo.get(pid, 0)
        dias_con_consumo = por_dias_consumo.get(pid, 0)
        total_solicitado += sol
        total_consumido += cons
        diff, estado, lectura, demanda_texto = _demanda_vs_consumo_texto(sol, cons)
        if estado == "solicitado_mayor":
            n_solicitud_mayor += 1
        elif estado == "consumo_mayor":
            n_consumo_mayor += 1
        else:
            n_coherentes += 1

        prod = productos_map.get(pid)
        stock_actual = int(stock_map.get(pid, 0))
        stock_minimo = int(prod.stock_minimo if prod else 0)
        consumo_promedio_diario = round((cons / dias_periodo), 2) if dias_periodo else 0.0
        cobertura_dias, cobertura_texto = _cobertura(stock_actual, consumo_promedio_diario)
        habito = _habito_detectado(pid, cons, dias_con_consumo)
        if habito == "Sin consumo reciente" and sol > 0:
            habito = "Bajo movimiento"
        riesgo, recomendacion = _riesgo_y_recomendacion(stock_actual, stock_minimo, cobertura_dias, habito, estado)
        if riesgo == "Alto":
            n_riesgo_alto += 1
        if cobertura_dias is not None and cobertura_dias <= 7:
            n_baja_cobertura += 1

        row = {
            "producto_id": pid,
            "sku": prod.sku if prod else "—",
            "nombre": prod.nombre if prod else "—",
            "cantidad_solicitada": sol,
            "cantidad_consumida": cons,
            "diferencia": diff,
            "estado": estado,
            "lectura": lectura,
            "demanda_vs_consumo": demanda_texto,
            "habito_detectado": habito,
            "stock_actual": stock_actual,
            "consumo_promedio_diario": consumo_promedio_diario,
            "cobertura_dias": cobertura_dias,
            "cobertura_texto": cobertura_texto,
            "riesgo": riesgo,
            "recomendacion": recomendacion,
        }
        rows_full.append(row)

    riesgo_rank = {"Alto": 0, "Medio": 1, "Bajo": 2}
    rows_full.sort(
        key=lambda r: (
            riesgo_rank.get(r["riesgo"], 3),
            r["cobertura_dias"] if r["cobertura_dias"] is not None else 10**9,
            -r["cantidad_consumida"],
            r["nombre"] or "",
        )
    )
    resultados = rows_full[:limit]

    return Response(
        {
            "desde": str(fecha_desde),
            "hasta": str(fecha_hasta),
            "limit": limit,
            "filtro_historico": False,
            "resumen": {
                "total_solicitado": total_solicitado,
                "total_consumido": total_consumido,
                "mayor_solicitud_que_consumo": n_solicitud_mayor,
                "mayor_consumo_que_solicitud": n_consumo_mayor,
                "coherentes": n_coherentes,
                "riesgo_alto": n_riesgo_alto,
                "consumo_mayor_solicitud": n_consumo_mayor,
                "demanda_coherente": n_coherentes,
                "baja_cobertura": n_baja_cobertura,
                "mayor_solicitud_consumo": n_solicitud_mayor,
            },
            "resultados": resultados,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ultima_corrida(request):
    """Última corrida analítica registrada (por fecha_ejecucion), para panel de estado ETL."""
    if not puede_ver_analytics(request.user):
        return Response(
            {"detail": "No tiene permiso para consultar corridas analíticas."},
            status=status.HTTP_403_FORBIDDEN,
        )

    c = CorridaAnalitica.objects.order_by("-fecha_ejecucion").first()
    if c is None:
        return Response({"corrida": None})
    return Response({"corrida": _serialize_corrida_resumida(c)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def consumo_mensual(request):
    """Consumo (salidas OUT) mensual por producto. Query: desde, hasta, producto_id (opcional)."""
    if not puede_ver_analytics(request.user):
        return Response(
            {"detail": "No tiene permiso para ver analytics."},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        fecha_desde, fecha_hasta = parse_fechas(request)
    except ValueError:
        return _respuesta_fecha_invalida()
    producto_id = request.query_params.get("producto_id")
    out = _consumo_mensual_desde_hecho(fecha_desde, fecha_hasta, producto_id)
    return Response({
        "consumo_mensual": out,
        **_meta_filtro_fechas(fecha_desde, fecha_hasta),
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
    try:
        fecha_desde, fecha_hasta = parse_fechas(request)
    except ValueError:
        return _respuesta_fecha_invalida()
    producto_id = request.query_params.get("producto_id")
    qs = (
        _qs_hecho_out(fecha_desde, fecha_hasta)
        .annotate(dia_semana=ExtractWeekDay("fecha"))
        .values("producto_id", "producto__sku", "producto__nombre", "dia_semana")
        .annotate(cantidad_total=Sum("cantidad_total"), dias=Count("fecha", distinct=True))
    )
    if producto_id:
        qs = qs.filter(producto_id=producto_id)
    rows = list(qs.order_by("producto_id", "dia_semana"))
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
        **_meta_filtro_fechas(fecha_desde, fecha_hasta),
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
    try:
        fecha_desde, fecha_hasta = parse_fechas(request)
    except ValueError:
        return _respuesta_fecha_invalida()
    producto_id = request.query_params.get("producto_id")
    qs = _qs_resumen_mensual(fecha_desde, fecha_hasta).select_related("producto")
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
        **_meta_filtro_fechas(fecha_desde, fecha_hasta),
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
    try:
        fecha_desde, fecha_hasta = parse_fechas(request)
    except ValueError:
        return _respuesta_fecha_invalida()
    producto_id = request.query_params.get("producto_id")

    consumo_mensual_list = _consumo_mensual_desde_hecho(fecha_desde, fecha_hasta, producto_id)

    qs_d = (
        _qs_hecho_out(fecha_desde, fecha_hasta)
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
        **_meta_filtro_fechas(fecha_desde, fecha_hasta),
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
        metodo=CorridaAnalitica.Metodo.MANUAL,
        fecha_desde=ayer,
        fecha_hasta=ayer,
        parametros={"fecha_desde": str(ayer), "fecha_hasta": str(ayer), "scope": "D-1"},
        mensaje="Ejecución encolada desde API.",
        error_detalle="",
        ejecutado_por=request.user,
    )
    run_etl_analitico_d1.apply_async(
        task_id=task_id,
        kwargs={"metodo": CorridaAnalitica.Metodo.MANUAL},
    )
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
    """Consulta estado y métricas de una corrida por task_id (mismo alcance que visualización analítica)."""
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
            "productos_candidatos_tendencia": _productos_candidatos_tendencia_para_api(corrida),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ultimas_corridas(request):
    """Lista últimas corridas (default 10, máximo 20). Lectura para roles con acceso a analytics."""
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
    data = [_serialize_corrida_resumida(c) for c in corridas]
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

    resultados = list(
        ResultadoTendenciaLineal.objects.filter(corrida=corrida)
        .select_related("producto", "producto__stock")
        .order_by("-prediccion_siguiente", "producto__nombre", "id")
    )
    data = []
    for r in resultados:
        stock_actual = _stock_actual_producto(r.producto)
        stock_minimo = int(r.producto.stock_minimo or 0)
        pendiente_int = cantidad_entera(r.pendiente)
        prediccion_int = cantidad_entera(r.prediccion_siguiente)
        cantidad_sugerida, criterio = calcular_reposicion_sugerida_tendencia(
            stock_actual,
            stock_minimo,
            pendiente_int,
            prediccion_int,
        )
        data.append(
            {
                "id": r.id,
                "producto_id": r.producto_id,
                "producto_nombre": r.producto.nombre,
                "producto_sku": r.producto.sku,
                "periodicidad": r.periodicidad,
                "puntos_usados": int(r.puntos_usados),
                "pendiente": pendiente_int,
                "prediccion_siguiente": prediccion_int,
                "stock_actual": stock_actual,
                "stock_minimo": stock_minimo,
                "cantidad_sugerida_reposicion": cantidad_sugerida,
                "criterio_reposicion": criterio,
                "fecha_inicio": r.fecha_inicio,
                "fecha_fin": r.fecha_fin,
            }
        )
    return Response(
        {
            "corrida_id": corrida.id,
            "task_id": corrida.task_id,
            "count": len(data),
            "results": data,
        }
    )


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

    fecha_prediccion = tendencia.fecha_fin + timedelta(days=1)
    valor_prediccion = float(tendencia.prediccion_siguiente)

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
            "valor": cantidad_entera(valor_prediccion),
        },
    }
    if len(historico) < 2:
        data["detail"] = "No hay datos suficientes para visualizar la tendencia."
    return Response(data)
