"""
Proceso ETL: extrae de MovStock, carga en HechoConsumo (agregado por producto/fecha/tipo).
Ejecución manual en R1 (sin Celery).
"""
from collections import defaultdict
from datetime import timedelta
from math import sqrt
from django.db import transaction
from django.utils import timezone

from django.db.models import Sum, Count
from apps.inventory.models import MovStock
from .models import CorridaAnalitica, HechoConsumo, ResumenConsumoMensual, ResultadoTendenciaLineal


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

    return {"resultados_guardados": len(bulk), "puntos_totales": puntos_totales}


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
        qs = MovStock.objects.select_related("producto").all().order_by("fecha")
        if fecha_desde:
            qs = qs.filter(fecha__date__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha__date__lte=fecha_hasta)

        # Agregar en memoria: (producto_id, fecha_date, tipo) -> suma cantidad
        agg = defaultdict(int)
        for m in qs:
            key = (m.producto_id, m.fecha.date(), m.tipo)
            agg[key] += m.cantidad

        with transaction.atomic():
            # Reemplazar hechos en el rango procesado (o todos si no hay filtro)
            if fecha_desde and fecha_hasta:
                HechoConsumo.objects.filter(
                    fecha__gte=fecha_desde,
                    fecha__lte=fecha_hasta,
                ).delete()
            else:
                HechoConsumo.objects.all().delete()

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

            actualizar_resumen_consumo_mensual(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
            fecha_fin_tendencia = fecha_hasta or timezone.now().date()
            if tendencia_ventana_dias and tendencia_ventana_dias > 0:
                fecha_inicio_tendencia = fecha_fin_tendencia - timedelta(days=tendencia_ventana_dias - 1)
            else:
                # Fallback: mantener comportamiento anterior si se desactiva la ventana.
                fecha_inicio_tendencia = fecha_desde

            tendencia = guardar_resultados_tendencia_lineal(
                corrida=corrida,
                fecha_desde=fecha_inicio_tendencia,
                fecha_hasta=fecha_fin_tendencia,
            )

            corrida.estado = CorridaAnalitica.Estado.SUCCESS
            corrida.registros_procesados = len(bulk)
            corrida.puntos_usados = len(agg)
            corrida.mensaje = (
                f"Procesados {len(agg)} agrupaciones, {len(bulk)} filas en HechoConsumo. "
                f"Tendencias guardadas: {tendencia['resultados_guardados']} "
                f"(ventana {fecha_inicio_tendencia} a {fecha_fin_tendencia})."
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


def actualizar_resumen_consumo_mensual(fecha_desde=None, fecha_hasta=None):
    """
    Actualiza ResumenConsumoMensual a partir de HechoConsumo (solo tipo OUT).
    Si se pasan fechas, solo actualiza los meses que tocan ese rango.
    """
    from django.db.models.functions import ExtractMonth, ExtractYear

    base = HechoConsumo.objects.filter(tipo_movimiento="OUT")
    if fecha_desde:
        base = base.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        base = base.filter(fecha__lte=fecha_hasta)
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
