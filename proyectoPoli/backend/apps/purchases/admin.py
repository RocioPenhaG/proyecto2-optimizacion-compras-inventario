from django.contrib import admin
from .models import SolicitudInsumo, SolicitudDetalle


class SolicitudDetalleInline(admin.TabularInline):
    model = SolicitudDetalle
    extra = 0


@admin.register(SolicitudInsumo)
class SolicitudInsumoAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "estado", "solicitante", "creado_en", "motivo_rechazo")
    list_filter = ("estado", "fecha")
    search_fields = ("solicitante__username", "observacion")
    inlines = [SolicitudDetalleInline]


@admin.register(SolicitudDetalle)
class SolicitudDetalleAdmin(admin.ModelAdmin):
    list_display = ("solicitud", "producto", "descripcion_insumo_solicitado", "cantidad")
