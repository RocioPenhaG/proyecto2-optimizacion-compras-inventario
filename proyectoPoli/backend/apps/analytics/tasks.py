"""
Tareas Celery para el módulo analítico (Release 2).
Ejecución programada del ETL incremental D-1.
"""
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .etl import ejecutar_etl_analitico


@shared_task(name="apps.analytics.tasks.run_etl_analitico_d1")
def run_etl_analitico_d1():
    """
    Ejecuta el ETL analítico para el día anterior (D-1).
    Pensado para ser invocado por Celery Beat (ej. diario a las 02:00).
    """
    ayer = (timezone.now() - timedelta(days=1)).date()
    corrida = ejecutar_etl_analitico(fecha_desde=ayer, fecha_hasta=ayer)
    return {"estado": corrida.estado, "registros": corrida.registros_procesados, "fecha": str(ayer)}
