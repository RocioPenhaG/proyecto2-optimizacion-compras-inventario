"""
Tareas Celery para el módulo analítico (Release 2).

``run_etl_analitico_d1`` procesa solo el día anterior (D-1) respecto a ``timezone.now()`` y debe
invocarse desde Celery Beat (``metodo=SCHEDULED`` en ``CELERY_BEAT_SCHEDULE``) o de forma manual
(``metodo=MANUAL`` por defecto: shell, ``.apply()``, API con corrida previa, etc.).
"""
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .etl import ejecutar_etl_analitico
from .models import CorridaAnalitica

_METODOS_CREACION_D1 = frozenset(
    (CorridaAnalitica.Metodo.MANUAL, CorridaAnalitica.Metodo.SCHEDULED)
)


def _metodo_valido_para_nueva_corrida(metodo) -> str:
    """Solo MANUAL o SCHEDULED al crear fila desde la task; cualquier otro valor cae en MANUAL."""
    if metodo in _METODOS_CREACION_D1:
        return metodo
    return CorridaAnalitica.Metodo.MANUAL


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
def run_etl_analitico_d1(self, metodo=CorridaAnalitica.Metodo.MANUAL):
    """
    Ejecuta el ETL analítico para el día anterior (D-1) en la zona horaria activa de Django.

    ``metodo`` indica el origen cuando la task crea ``CorridaAnalitica`` (por defecto ``MANUAL``).
    Celery Beat debe invocar con ``metodo=SCHEDULED``. Si ya existe corrida (p. ej. API), se
    respeta su ``metodo`` y demás datos previos.
    """
    ayer = (timezone.now() - timedelta(days=1)).date()
    task_id = getattr(self.request, "id", None)
    metodo_nueva_corrida = _metodo_valido_para_nueva_corrida(metodo)

    corrida = CorridaAnalitica.objects.filter(task_id=task_id).first() if task_id else None
    if corrida is None:
        msg = (
            "Ejecución encolada (programación Celery Beat)."
            if metodo_nueva_corrida == CorridaAnalitica.Metodo.SCHEDULED
            else "Ejecución encolada (ejecución manual)."
        )
        defaults = {
            "estado": CorridaAnalitica.Estado.QUEUED,
            "queued_at": timezone.now(),
            "metodo": metodo_nueva_corrida,
            "fecha_desde": ayer,
            "fecha_hasta": ayer,
            "parametros": {"fecha_desde": str(ayer), "fecha_hasta": str(ayer), "scope": "D-1"},
            "mensaje": msg,
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


@shared_task(name="apps.analytics.tasks.limpiar_datos_analiticos_programado")
def limpiar_datos_analiticos_programado(dias_retencion=180):
    """
    Tarea opcional de retención: depura corridas y tendencias antiguas.

    No está en CELERY_BEAT_SCHEDULE por defecto. Para programarla, agregar una entrada
    en settings que invoque esta task (p. ej. semanal).
    """
    from apps.analytics.services.retencion import limpiar_datos_analiticos

    resultado = limpiar_datos_analiticos(dias_retencion=dias_retencion, dry_run=False)
    return resultado.as_dict()
