from django.db import models

class Proveedor(models.Model):
    nombre = models.CharField(max_length=100)
    ruc = models.CharField(max_length=20, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=150)
    unidad = models.CharField(max_length=20, default="UNIDAD")
    categoria = models.CharField(max_length=100, blank=True, null=True)
    stock_minimo = models.PositiveIntegerField(default=0)
    stock_maximo = models.PositiveIntegerField(default=0)
    punto_reposicion = models.PositiveIntegerField(default=0)
    costo_promedio = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    requiere_aprobacion_gerencia = models.BooleanField(
        default=False,
        help_text="Si es verdadero, la solicitud con este ítem debe ser aprobada/rechazada por Gerencia (insumo nuevo o estratégico).",
    )
    activo = models.BooleanField(default=True)
    proveedor = models.ForeignKey(
        Proveedor, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="productos"
    )

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

    def __str__(self):
        return f"[{self.sku}] {self.nombre}"