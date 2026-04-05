from django.contrib import admin
from .models import StockProducto, MovStock

@admin.register(StockProducto)
class StockProductoAdmin(admin.ModelAdmin):
    list_display = ('producto', 'qty_on_hand', 'ultimo_movimiento', 'actualizado_por')
    search_fields = ('producto__nombre', 'producto__sku')

@admin.register(MovStock)
class MovStockAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tipo', 'producto', 'cantidad', 'usuario')
    list_filter = ('tipo', 'fecha')