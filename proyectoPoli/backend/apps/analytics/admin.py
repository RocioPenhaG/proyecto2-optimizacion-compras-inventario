from django.contrib import admin
from .models import (
    CorridaAnalitica,
    HechoConsumo,
    ProyeccionConsumoFuturo,
    ResumenConsumoMensual,
    ResultadoTendenciaLineal,
)


class ResultadoTendenciaLinealInline(admin.TabularInline):
    model = ResultadoTendenciaLineal
    extra = 0
    fields = (
        "producto",
        "periodicidad",
        "puntos_usados",
        "pendiente",
        "intercepto",
        "r2",
        "prediccion_siguiente",
        "fecha_inicio",
        "fecha_fin",
    )
    readonly_fields = fields
    can_delete = False


@admin.register(CorridaAnalitica)
class CorridaAnaliticaAdmin(admin.ModelAdmin):
    list_display = (
        "fecha_ejecucion",
        "estado",
        "task_id",
        "registros_procesados",
        "puntos_usados",
        "started_at",
        "finished_at",
        "fecha_desde",
        "fecha_hasta",
    )
    list_filter = ("estado",)
    readonly_fields = (
        "fecha_ejecucion",
        "estado",
        "task_id",
        "queued_at",
        "started_at",
        "finished_at",
        "mensaje",
        "error_detalle",
        "registros_procesados",
        "puntos_usados",
        "metodo",
        "parametros",
        "fecha_desde",
        "fecha_hasta",
    )
    inlines = (ResultadoTendenciaLinealInline,)

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


@admin.register(ProyeccionConsumoFuturo)
class ProyeccionConsumoFuturoAdmin(admin.ModelAdmin):
    list_display = (
        "corrida",
        "producto",
        "fecha",
        "horizonte_dias",
        "valor_diario",
        "consumo_acumulado",
    )
    list_filter = ("corrida", "horizonte_dias")
    search_fields = ("producto__nombre", "producto__sku")

    def has_add_permission(self, request):
        return False


@admin.register(ResultadoTendenciaLineal)
class ResultadoTendenciaLinealAdmin(admin.ModelAdmin):
    list_display = (
        "corrida",
        "producto",
        "periodicidad",
        "puntos_usados",
        "pendiente",
        "intercepto",
        "r2",
        "prediccion_siguiente",
        "fecha_inicio",
        "fecha_fin",
    )
    list_filter = ("producto", "periodicidad", "fecha_inicio", "fecha_fin")
    search_fields = ("producto__nombre", "producto__sku")
