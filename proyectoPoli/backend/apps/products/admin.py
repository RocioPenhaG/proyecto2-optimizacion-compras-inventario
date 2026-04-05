from django.contrib import admin
from .models import Proveedor, Producto

admin.site.register(Proveedor)

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "nombre",
        "unidad",
        "categoria",
        "costo_promedio",
        "requiere_aprobacion_gerencia",
        "activo",
    )
    list_filter = ("requiere_aprobacion_gerencia", "activo")
    search_fields = ("sku", "nombre")