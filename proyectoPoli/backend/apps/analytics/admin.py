from django.contrib import admin
from django.utils import timezone
from .models import CorridaAnalitica, HechoConsumo, ResumenConsumoMensual
from .etl import ejecutar_etl_analitico


@admin.register(CorridaAnalitica)
class CorridaAnaliticaAdmin(admin.ModelAdmin):
    list_display = ("fecha_ejecucion", "estado", "registros_procesados", "fecha_desde", "fecha_hasta")
    list_filter = ("estado",)
    readonly_fields = ("fecha_ejecucion", "estado", "mensaje", "registros_procesados", "fecha_desde", "fecha_hasta")

    def has_add_permission(self, request):
        return False


@admin.register(HechoConsumo)
class HechoConsumoAdmin(admin.ModelAdmin):
    list_display = ("producto", "fecha", "tipo_movimiento", "cantidad_total")
    list_filter = ("tipo_movimiento", "fecha")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ResumenConsumoMensual)
class ResumenConsumoMensualAdmin(admin.ModelAdmin):
    list_display = ("producto", "anio", "mes", "cantidad_salidas", "promedio_diario", "dias_con_movimiento")
    list_filter = ("anio", "mes")

    def has_add_permission(self, request):
        return False
