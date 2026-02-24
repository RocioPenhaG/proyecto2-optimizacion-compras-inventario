from django.contrib import admin
from .models import SolicitudCompra

@admin.register(SolicitudCompra)
class SolicitudCompraAdmin(admin.ModelAdmin):
    list_display = ("id", "titulo", "estado", "solicitante", "created_at")
    list_filter = ("estado", "created_at")
    search_fields = ("titulo", "descripcion", "solicitante__username")
