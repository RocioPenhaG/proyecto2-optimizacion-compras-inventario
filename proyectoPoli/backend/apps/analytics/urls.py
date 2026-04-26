from django.urls import path
from . import views

urlpatterns = [
    path("consumo-mensual/", views.consumo_mensual),
    path("consumo-por-dia-semana/", views.consumo_por_dia_semana),
    path("indicadores/", views.indicadores),
    path("habitos-resumen/", views.habitos_resumen),
    path("etl/run-d1/", views.ejecutar_etl_d1),
    path("etl/status/<str:task_id>/", views.estado_corrida),
    path("etl/corridas/", views.ultimas_corridas),
    path("etl/corridas/<int:corrida_id>/tendencias/", views.tendencias_por_corrida),
]
