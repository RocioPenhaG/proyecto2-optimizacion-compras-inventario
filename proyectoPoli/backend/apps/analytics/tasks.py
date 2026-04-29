"""
Tareas Celery para el módulo analítico (Release 2).
Ejecución programada del ETL incremental D-1.
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
    Ejecuta el ETL analítico para el día anterior (D-1).
    Invocado desde la API (CorridaAnalitica ya creada en QUEUED con task_id) o desde
    Celery Beat (crea la fila QUEUED aquí si no existía).
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
            "mensaje": "Ejecución encolada desde Celery.",
        }
        if task_id:
            corrida = CorridaAnalitica.objects.create(task_id=task_id, **defaults)
        else:
            corrida = CorridaAnalitica.objects.create(**defaults)

    corrida = ejecutar_etl_analitico(fecha_desde=ayer, fecha_hasta=ayer, corrida=corrida)
    return {"estado": corrida.estado, "registros": corrida.registros_procesados, "fecha": str(ayer)}
