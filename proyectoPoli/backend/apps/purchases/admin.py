from django.contrib import admin
from .models import SolicitudInsumo, SolicitudDetalle


class SolicitudDetalleInline(admin.TabularInline):
    model = SolicitudDetalle
    extra = 0
    readonly_fields = ("cantidad_inicial",)


@admin.register(SolicitudInsumo)
class SolicitudInsumoAdmin(admin.ModelAdmin):
    list_display = (
        "numero",
        "id",
        "fecha",
        "estado",
        "tipo_destino_compra",
        "solicitante",
        "creado_en",
        "motivo_rechazo",
    )
    list_filter = ("estado", "tipo_destino_compra", "fecha")
    search_fields = ("solicitante__username", "observacion")
    inlines = [SolicitudDetalleInline]


@admin.register(SolicitudDetalle)
class SolicitudDetalleAdmin(admin.ModelAdmin):
    list_display = ("solicitud", "producto", "descripcion_insumo_solicitado", "cantidad_inicial", "cantidad")
