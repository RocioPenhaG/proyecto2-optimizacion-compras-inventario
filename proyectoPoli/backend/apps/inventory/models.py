from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from apps.products.models import Producto

class StockProducto(models.Model):
    producto = models.OneToOneField(Producto, on_delete=models.CASCADE, related_name="stock")
    qty_on_hand = models.IntegerField(default=0)
    ultimo_movimiento = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )

    class Meta:
        verbose_name = "Stock de Producto"
        verbose_name_plural = "Stock de Productos"

    def __str__(self):
        return f"{self.producto.nombre} - Stock: {self.qty_on_hand}"


class MovStock(models.Model):
    TIPO_CHOICES = (
        ('IN', 'Entrada'),
        ('OUT', 'Salida'),
        ('ADJ', 'Ajuste'),
    )

    fecha = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=3, choices=TIPO_CHOICES)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="movimientos")
    cantidad = models.IntegerField()
    ref_tipo = models.CharField(max_length=50, blank=True, null=True) # ej. "COMPRA", "SOLICITUD"
    ref_id = models.IntegerField(blank=True, null=True)
    observacion = models.TextField(blank=True, null=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )

    class Meta:
        verbose_name = "Movimiento de Stock"
        verbose_name_plural = "Movimientos de Stock"

    def __str__(self):
        return f"{self.fecha.strftime('%Y-%m-%d %H:%M')} | {self.tipo} | {self.producto.sku} | Cant: {self.cantidad}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            stock, _ = StockProducto.objects.get_or_create(producto=self.producto)
            new_qty = stock.qty_on_hand
            
            if self.tipo == 'IN':
                new_qty += self.cantidad
            elif self.tipo == 'OUT':
                new_qty -= self.cantidad
            elif self.tipo == 'ADJ':
                new_qty += self.cantidad
                
            if new_qty < 0:
                raise ValidationError("El movimiento dejaría el stock en negativo.")
                
            stock.qty_on_hand = new_qty
            stock.actualizado_por = self.usuario
            stock.save()
            
        super().save(*args, **kwargs)

    def revertir_efecto_en_stock(self):
        """Deshace el impacto de este movimiento en StockProducto (para eliminación por administrador)."""
        stock, _ = StockProducto.objects.get_or_create(producto=self.producto)
        if self.tipo == "IN":
            new_qty = stock.qty_on_hand - self.cantidad
        elif self.tipo == "OUT":
            new_qty = stock.qty_on_hand + self.cantidad
        else:
            new_qty = stock.qty_on_hand - self.cantidad
        if new_qty < 0:
            raise ValidationError(
                "No se puede eliminar el movimiento: el stock quedaría negativo."
            )
        stock.qty_on_hand = new_qty
        stock.save()