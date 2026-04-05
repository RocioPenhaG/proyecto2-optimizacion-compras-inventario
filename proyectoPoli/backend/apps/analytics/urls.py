from django.urls import path
from . import views

urlpatterns = [
    path("consumo-mensual/", views.consumo_mensual),
    path("consumo-por-dia-semana/", views.consumo_por_dia_semana),
    path("indicadores/", views.indicadores),
    path("habitos-resumen/", views.habitos_resumen),
]
