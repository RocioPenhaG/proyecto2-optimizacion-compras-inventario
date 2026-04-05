"""
Proceso ETL: extrae de MovStock, carga en HechoConsumo (agregado por producto/fecha/tipo).
Ejecución manual en R1 (sin Celery).
"""
from collections import defaultdict
from datetime import datetime
from django.db import transaction
from django.utils import timezone

from django.db.models import Sum, Count
from apps.products.models import Producto
from apps.inventory.models import MovStock
from .models import CorridaAnalitica, HechoConsumo, ResumenConsumoMensual


def ejecutar_etl_analitico(fecha_desde=None, fecha_hasta=None):
    """
    Extrae movimientos de stock (opcionalmente en rango de fechas), agrega por
    producto + fecha (día) + tipo, y carga en HechoConsumo.
    Crea registro en CorridaAnalitica.
    """
    corrida = CorridaAnalitica(estado=CorridaAnalitica.Estado.ERROR, mensaje="")
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

            corrida.estado = CorridaAnalitica.Estado.OK
            corrida.registros_procesados = len(bulk)
            corrida.mensaje = f"Procesados {len(agg)} agrupaciones, {len(bulk)} filas en HechoConsumo."
            corrida.fecha_desde = fecha_desde
            corrida.fecha_hasta = fecha_hasta
            corrida.save()
            actualizar_resumen_consumo_mensual(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    except Exception as e:
        corrida.mensaje = str(e)
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
