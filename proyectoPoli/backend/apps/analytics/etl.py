"""
Proceso ETL: extrae de MovStock, carga en HechoConsumo (agregado por producto/fecha/tipo).

Ejecución manual: ``manage.py run_etl_analitico`` o llamada directa a ``ejecutar_etl_analitico``.
Ejecución automática D-1: tarea Celery ``run_etl_analitico_d1`` con ``metodo=SCHEDULED`` en
``CELERY_BEAT_SCHEDULE`` (settings); ejecución manual usa ``metodo=MANUAL`` (valor por defecto).
"""
from collections import defaultdict
from datetime import datetime, timedelta
from math import sqrt
from django.db import transaction
from django.utils import timezone

from django.db.models import Sum, Count
from django.db.models.functions import ExtractMonth, ExtractYear, TruncDate
from apps.inventory.models import MovStock
from .models import CorridaAnalitica, HechoConsumo, ResumenConsumoMensual, ResultadoTendenciaLineal


def _fmt_fecha_dmY(d):
    """Fecha calendario para textos legibles (DD-MM-YYYY)."""
    if d is None:
        return ""
    if hasattr(d, "strftime"):
        return d.strftime("%d-%m-%Y")
    return str(d)


def _fecha_mov_local(dt):
    """
    Día calendario local coherente con los filtros ``fecha__date`` del ORM cuando ``USE_TZ`` está activo.
    No usar ``dt.date()`` directamente sobre datetimes con zona: puede no coincidir con ``fecha__date``.
    """
    if dt is None:
        return None
    if timezone.is_aware(dt):
        return timezone.localtime(dt).date()
    return dt.date()


def _aggregate_movstock_por_dia_tipo(fecha_desde=None, fecha_hasta=None):
    """
    Suma cantidades de MovStock agrupadas por (producto_id, día calendario local, tipo).

    El día se obtiene con ``TruncDate`` en ``timezone.get_current_timezone()``, alineado a
    ``fecha__date__gte`` / ``fecha__date__lte`` usados en el filtro.
    """
    tz = timezone.get_current_timezone()
    qs = MovStock.objects.all()
    if fecha_desde is not None:
        qs = qs.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta is not None:
        qs = qs.filter(fecha__date__lte=fecha_hasta)

    rows = (
        qs.annotate(fecha_dia=TruncDate("fecha", tzinfo=tz))
        .values("producto_id", "fecha_dia", "tipo")
        .annotate(cantidad=Sum("cantidad"))
    )
    agg = defaultdict(int)
    for r in rows:
        fd = r["fecha_dia"]
        if isinstance(fd, datetime):
            fd = fd.date()
        key = (r["producto_id"], fd, r["tipo"])
        agg[key] += int(r["cantidad"] or 0)
    return agg


def calcular_fechas_ventana_tendencia(fecha_desde_etl, fecha_hasta_etl, tendencia_ventana_dias=30):
    """Misma ventana que usa `guardar_resultados_tendencia_lineal` vía `ejecutar_etl_analitico`."""
    fecha_fin_tendencia = fecha_hasta_etl or timezone.now().date()
    if tendencia_ventana_dias and tendencia_ventana_dias > 0:
        fecha_inicio_tendencia = fecha_fin_tendencia - timedelta(days=int(tendencia_ventana_dias) - 1)
    else:
        fecha_inicio_tendencia = fecha_desde_etl
    return fecha_inicio_tendencia, fecha_fin_tendencia


def contar_productos_distinct_out_en_rango(fecha_ini, fecha_fin):
    """Productos con al menos un hecho OUT en el rango (candidatos a serie de tendencia)."""
    q = HechoConsumo.objects.filter(tipo_movimiento="OUT")
    if fecha_ini is not None:
        q = q.filter(fecha__gte=fecha_ini)
    if fecha_fin is not None:
        q = q.filter(fecha__lte=fecha_fin)
    return q.values("producto_id").distinct().count()


def resolver_productos_candidatos_tendencia(corrida):
    """
    Total de productos evaluables en la ventana de tendencia.
    Usa el valor persistido por el ETL; si es null, intenta inferirlo (corridas previas a Release).
    """
    if corrida.productos_candidatos_tendencia is not None:
        return corrida.productos_candidatos_tendencia
    params = corrida.parametros if isinstance(corrida.parametros, dict) else {}
    pfi = params.get("fecha_inicio_ventana_tendencia")
    pff = params.get("fecha_fin_ventana_tendencia")
    if pfi and pff:
        from datetime import datetime as dt

        try:
            fi = dt.strptime(str(pfi)[:10], "%Y-%m-%d").date()
            ff = dt.strptime(str(pff)[:10], "%Y-%m-%d").date()
            return contar_productos_distinct_out_en_rango(fi, ff)
        except ValueError:
            pass
    ventana = 30
    if params.get("tendencia_ventana_dias") is not None:
        try:
            ventana = int(params["tendencia_ventana_dias"])
        except (TypeError, ValueError):
            ventana = 30
    fi, ff = calcular_fechas_ventana_tendencia(corrida.fecha_desde, corrida.fecha_hasta, ventana)
    return contar_productos_distinct_out_en_rango(fi, ff)


def _calcular_regresion_lineal(y_values):
    """
    Regresión lineal simple (OLS) con x = 0..n-1.
    Retorna pendiente, intercepto, r2, mae, rmse y predicción para x=n.
    """
    n = len(y_values)
    x_values = list(range(n))
    sum_x = sum(x_values)
    sum_y = sum(y_values)
    sum_x2 = sum(x * x for x in x_values)
    sum_xy = sum(x * y for x, y in zip(x_values, y_values))
    denominator = (n * sum_x2) - (sum_x * sum_x)
    if denominator == 0:
        return None

    pendiente = ((n * sum_xy) - (sum_x * sum_y)) / denominator
    intercepto = (sum_y - (pendiente * sum_x)) / n
    predicciones = [intercepto + (pendiente * x) for x in x_values]
    residuos = [real - pred for real, pred in zip(y_values, predicciones)]
    ss_res = sum(r * r for r in residuos)
    mean_y = sum_y / n
    ss_tot = sum((y - mean_y) ** 2 for y in y_values)
    r2 = None if ss_tot == 0 else (1 - (ss_res / ss_tot))
    mae = sum(abs(r) for r in residuos) / n
    rmse = sqrt(ss_res / n)
    prediccion_siguiente = intercepto + (pendiente * n)
    return {
        "pendiente": pendiente,
        "intercepto": intercepto,
        "r2": r2,
        "mae": mae,
        "rmse": rmse,
        "prediccion_siguiente": prediccion_siguiente,
    }


def guardar_resultados_tendencia_lineal(corrida, fecha_desde=None, fecha_hasta=None, minimo_puntos=3):
    """
    Construye serie temporal diaria por producto (consumo OUT), calcula tendencia
    lineal por producto y persiste resultados vinculados a la corrida.
    """
    base = HechoConsumo.objects.filter(tipo_movimiento="OUT")
    if fecha_desde:
        base = base.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        base = base.filter(fecha__lte=fecha_hasta)

    rows = list(
        base.values("producto_id", "fecha")
        .annotate(consumo=Sum("cantidad_total"))
        .order_by("producto_id", "fecha")
    )
    series_por_producto = defaultdict(list)
    for row in rows:
        series_por_producto[row["producto_id"]].append((row["fecha"], float(row["consumo"])))

    ResultadoTendenciaLineal.objects.filter(corrida=corrida).delete()
    bulk = []
    puntos_totales = 0

    for producto_id, serie in series_por_producto.items():
        if len(serie) < minimo_puntos:
            continue
        y_values = [punto[1] for punto in serie]
        regresion = _calcular_regresion_lineal(y_values)
        if regresion is None:
            continue
        puntos_totales += len(serie)
        bulk.append(
            ResultadoTendenciaLineal(
                corrida=corrida,
                producto_id=producto_id,
                variable_objetivo="consumo_out",
                periodicidad="DAILY",
                fecha_inicio=serie[0][0],
                fecha_fin=serie[-1][0],
                puntos_usados=len(serie),
                pendiente=regresion["pendiente"],
                intercepto=regresion["intercepto"],
                r2=regresion["r2"],
                mae=regresion["mae"],
                rmse=regresion["rmse"],
                prediccion_siguiente=regresion["prediccion_siguiente"],
                metadata={"serie": "consumo_out_diario", "minimo_puntos": minimo_puntos},
            )
        )

    if bulk:
        ResultadoTendenciaLineal.objects.bulk_create(bulk)

    productos_candidatos = len(series_por_producto)
    return {
        "resultados_guardados": len(bulk),
        "puntos_totales": puntos_totales,
        "productos_candidatos": productos_candidatos,
    }


def ejecutar_etl_analitico(fecha_desde=None, fecha_hasta=None, corrida=None, tendencia_ventana_dias=30):
    """
    Extrae movimientos de stock (opcionalmente en rango de fechas), agrega por
    producto + fecha (día) + tipo, y carga en HechoConsumo.
    Crea registro en CorridaAnalitica.
    """
    if corrida is None:
        corrida = CorridaAnalitica(
            estado=CorridaAnalitica.Estado.RUNNING,
            mensaje="",
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            started_at=timezone.now(),
        )
        corrida.save()
    else:
        corrida.estado = CorridaAnalitica.Estado.RUNNING
        corrida.started_at = corrida.started_at or timezone.now()
        corrida.finished_at = None
        corrida.fecha_desde = fecha_desde
        corrida.fecha_hasta = fecha_hasta
        corrida.error_detalle = ""
        corrida.save(
            update_fields=[
                "estado",
                "started_at",
                "finished_at",
                "fecha_desde",
                "fecha_hasta",
                "error_detalle",
            ]
        )
    try:
        agg = _aggregate_movstock_por_dia_tipo(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)

        with transaction.atomic():
            # Borrar solo hechos del rango afectado (rangos abiertos: solo desde / solo hasta).
            # Sin ninguna fecha: reprocesar todo el universo (reemplazo completo).
            hc_delete = HechoConsumo.objects.all()
            if fecha_desde is not None and fecha_hasta is not None:
                hc_delete = hc_delete.filter(fecha__gte=fecha_desde, fecha__lte=fecha_hasta)
            elif fecha_desde is not None:
                hc_delete = hc_delete.filter(fecha__gte=fecha_desde)
            elif fecha_hasta is not None:
                hc_delete = hc_delete.filter(fecha__lte=fecha_hasta)

            resumen_pairs = None
            if fecha_desde is not None or fecha_hasta is not None:
                out_before = (
                    hc_delete.filter(tipo_movimiento="OUT")
                    .annotate(anio=ExtractYear("fecha"), mes=ExtractMonth("fecha"))
                    .values_list("producto_id", "anio", "mes")
                    .distinct()
                )
                resumen_pairs = set(out_before)

            hc_delete.delete()

            bulk = []
            for (producto_id, fecha, tipo), cantidad in agg.items():
                bulk.append(
                    HechoConsumo(
                        producto_id=producto_id,
                        fecha=fecha,
                        tipo_movimiento=tipo,
                        cantidad_total=cantidad,
                    )
                )
            if bulk:
                HechoConsumo.objects.bulk_create(bulk)

            if fecha_desde is not None or fecha_hasta is not None:
                for row in bulk:
                    if row.tipo_movimiento == "OUT":
                        resumen_pairs.add((row.producto_id, row.fecha.year, row.fecha.month))
                actualizar_resumen_consumo_mensual(
                    fecha_desde=fecha_desde,
                    fecha_hasta=fecha_hasta,
                    _pares_producto_mes=resumen_pairs,
                )
            else:
                actualizar_resumen_consumo_mensual()
            fecha_inicio_tendencia, fecha_fin_tendencia = calcular_fechas_ventana_tendencia(
                fecha_desde, fecha_hasta, tendencia_ventana_dias
            )

            tendencia = guardar_resultados_tendencia_lineal(
                corrida=corrida,
                fecha_desde=fecha_inicio_tendencia,
                fecha_hasta=fecha_fin_tendencia,
            )

            corrida.estado = CorridaAnalitica.Estado.SUCCESS
            corrida.registros_procesados = len(bulk)
            corrida.puntos_usados = len(agg)
            corrida.productos_candidatos_tendencia = tendencia["productos_candidatos"]
            prev_params = corrida.parametros if isinstance(corrida.parametros, dict) else {}
            corrida.parametros = {
                **prev_params,
                "tendencia_ventana_dias": tendencia_ventana_dias,
                "fecha_inicio_ventana_tendencia": str(fecha_inicio_tendencia),
                "fecha_fin_ventana_tendencia": str(fecha_fin_tendencia),
            }
            fi_txt = _fmt_fecha_dmY(fecha_inicio_tendencia)
            ff_txt = _fmt_fecha_dmY(fecha_fin_tendencia)
            corrida.mensaje = (
                f"Procesados {len(bulk)} registros. "
                f"Tendencias Guardadas: {tendencia['resultados_guardados']}. "
                f"Evaluación del {fi_txt} al {ff_txt}."
            )
            corrida.error_detalle = ""
            corrida.finished_at = timezone.now()
            corrida.save()
    except Exception as e:
        corrida.estado = CorridaAnalitica.Estado.ERROR
        corrida.mensaje = str(e)
        corrida.error_detalle = str(e)
        corrida.finished_at = timezone.now()
        corrida.save()
        raise
    return corrida


def actualizar_resumen_consumo_mensual(fecha_desde=None, fecha_hasta=None, _pares_producto_mes=None):
    """
    Actualiza ResumenConsumoMensual a partir de HechoConsumo (solo tipo OUT).

    Reconstrucción completa (sin fechas ni pares): recalcula todos los resúmenes desde HechoConsumo.

    Actualización parcial: recalcula cada par (producto, año, mes) afectado usando **todo** el consumo
    OUT de ese mes calendario (no solo el subrango de fechas), para que corridas D-1 no pisen el mes.
    ``_pares_producto_mes`` lo arma el ETL (OUT tocados antes del borrado + filas OUT nuevas).
    Si no se pasa, se infieren pares con OUT cuyo ``fecha`` cae en el filtro fecha_desde/fecha_hasta.
    """
    if fecha_desde is None and fecha_hasta is None and _pares_producto_mes is None:
        base = HechoConsumo.objects.filter(tipo_movimiento="OUT")
        qs = (
            base.annotate(anio=ExtractYear("fecha"), mes=ExtractMonth("fecha"))
            .values("producto_id", "anio", "mes")
            .annotate(
                cantidad_salidas=Sum("cantidad_total"),
                dias_con_movimiento=Count("fecha", distinct=True),
            )
        )
        rows = list(qs)
        to_create = []
        keys_to_delete = set()
        for r in rows:
            dias = r["dias_con_movimiento"] or 1
            to_create.append(
                ResumenConsumoMensual(
                    producto_id=r["producto_id"],
                    anio=r["anio"],
                    mes=r["mes"],
                    cantidad_salidas=r["cantidad_salidas"],
                    promedio_diario=round(r["cantidad_salidas"] / dias, 2),
                    dias_con_movimiento=r["dias_con_movimiento"],
                )
            )
            keys_to_delete.add((r["producto_id"], r["anio"], r["mes"]))
        if not to_create:
            return
        for producto_id, anio, mes in keys_to_delete:
            ResumenConsumoMensual.objects.filter(producto_id=producto_id, anio=anio, mes=mes).delete()
        ResumenConsumoMensual.objects.bulk_create(to_create)
        return

    if _pares_producto_mes is not None:
        pairs = set(_pares_producto_mes)
    else:
        base = HechoConsumo.objects.filter(tipo_movimiento="OUT")
        if fecha_desde:
            base = base.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            base = base.filter(fecha__lte=fecha_hasta)
        pairs = set(
            base.annotate(anio=ExtractYear("fecha"), mes=ExtractMonth("fecha")).values_list(
                "producto_id", "anio", "mes"
            ).distinct()
        )

    if not pairs:
        return

    to_create = []
    keys_to_delete = []
    for producto_id, anio, mes in pairs:
        agg = HechoConsumo.objects.filter(
            tipo_movimiento="OUT",
            producto_id=producto_id,
            fecha__year=anio,
            fecha__month=mes,
        ).aggregate(
            cantidad_salidas=Sum("cantidad_total"),
            dias_con_movimiento=Count("fecha", distinct=True),
        )
        cant = agg["cantidad_salidas"] or 0
        dias = agg["dias_con_movimiento"] or 0
        if cant == 0 and dias == 0:
            ResumenConsumoMensual.objects.filter(producto_id=producto_id, anio=anio, mes=mes).delete()
            continue
        dias_eff = dias or 1
        keys_to_delete.append((producto_id, anio, mes))
        to_create.append(
            ResumenConsumoMensual(
                producto_id=producto_id,
                anio=anio,
                mes=mes,
                cantidad_salidas=cant,
                promedio_diario=round(cant / dias_eff, 2),
                dias_con_movimiento=dias,
            )
        )

    for producto_id, anio, mes in keys_to_delete:
        ResumenConsumoMensual.objects.filter(producto_id=producto_id, anio=anio, mes=mes).delete()
    if to_create:
        ResumenConsumoMensual.objects.bulk_create(to_create)
