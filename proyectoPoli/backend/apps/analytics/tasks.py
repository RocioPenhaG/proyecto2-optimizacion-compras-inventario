"""
Tareas Celery para el módulo analítico (Release 2).

``run_etl_analitico_d1`` procesa solo el día anterior (D-1) respecto a ``timezone.now()`` y debe
invocarse desde Celery Beat (programación diaria) o desde la API (corrida ya en QUEUED con task_id).
"""
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .etl import ejecutar_etl_analitico
from .models import CorridaAnalitica


@shared_task(name="apps.analytics.tasks.ping_analytics")
def ping_analytics():
    """
    Tarea simple de health-check para validar que Celery + Redis
    procesan tareas en background correctamente.
    """
    return {
        "ok": True,
        "service": "analytics",
        "executed_at": timezone.now().isoformat(),
    }


@shared_task(bind=True, name="apps.analytics.tasks.run_etl_analitico_d1")
def run_etl_analitico_d1(self):
    """
    Ejecuta el ETL analítico para el día anterior (D-1) en la zona horaria activa de Django.

    Invocado desde la API (CorridaAnalitica ya creada en QUEUED con task_id) o desde
    Celery Beat (crea la fila con metodo=SCHEDULED si no existía corrida para este task_id).
    """
    ayer = (timezone.now() - timedelta(days=1)).date()
    task_id = getattr(self.request, "id", None)

    corrida = CorridaAnalitica.objects.filter(task_id=task_id).first() if task_id else None
    if corrida is None:
        defaults = {
            "estado": CorridaAnalitica.Estado.QUEUED,
            "queued_at": timezone.now(),
            "metodo": CorridaAnalitica.Metodo.SCHEDULED,
            "fecha_desde": ayer,
            "fecha_hasta": ayer,
            "parametros": {"fecha_desde": str(ayer), "fecha_hasta": str(ayer), "scope": "D-1"},
            "mensaje": "Ejecución encolada (Celery Beat o worker).",
        }
        if task_id:
            corrida = CorridaAnalitica.objects.create(task_id=task_id, **defaults)
        else:
            corrida = CorridaAnalitica.objects.create(**defaults)

    corrida = ejecutar_etl_analitico(fecha_desde=ayer, fecha_hasta=ayer, corrida=corrida)
    return {
        "estado": corrida.estado,
        "registros_procesados": corrida.registros_procesados,
        "fecha_procesada": str(ayer),
    }
