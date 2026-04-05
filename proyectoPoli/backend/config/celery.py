"""
Configuración de Celery para el backend Segupak.
Usa Redis como broker (CELERY_BROKER_URL). Tareas en apps.analytics.tasks.
"""
from celery import Celery
from django.conf import settings

app = Celery("config")
app.config_from_object(settings, namespace="CELERY")
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
