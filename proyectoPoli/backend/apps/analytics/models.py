"""
Base analítica Release 1: tablas de hechos para consumo y registro de corridas ETL.
Origen: tablas operativas (inventory.MovStock). Destino: HechoConsumo.
"""
from django.db import models
from django.utils import timezone

from apps.products.models import Producto


class CorridaAnalitica(models.Model):
    """Registro de cada ejecución del proceso ETL analítico."""
    class Estado(models.TextChoices):
        OK = "OK", "OK"
        ERROR = "ERROR", "Error"

    fecha_ejecucion = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=10, choices=Estado.choices)
    mensaje = models.TextField(blank=True, default="")
    registros_procesados = models.PositiveIntegerField(default=0)
    fecha_desde = models.DateField(null=True, blank=True)
    fecha_hasta = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Corrida analítica"
        verbose_name_plural = "Corridas analíticas"
        ordering = ["-fecha_ejecucion"]

    def __str__(self):
        return f"Corrida {self.fecha_ejecucion.strftime('%Y-%m-%d %H:%M')} — {self.estado} ({self.registros_procesados} registros)"


class HechoConsumo(models.Model):
    """
    Tabla analítica: consumo/movimientos agregados por producto, fecha y tipo.
    Origen: inventory.MovStock (ETL).
    """
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="hechos_consumo")
    fecha = models.DateField()
    tipo_movimiento = models.CharField(max_length=3)  # IN, OUT, ADJ
    cantidad_total = models.IntegerField()

    class Meta:
        verbose_name = "Hecho de consumo"
        verbose_name_plural = "Hechos de consumo"
        ordering = ["-fecha", "producto", "tipo_movimiento"]
        unique_together = [["producto", "fecha", "tipo_movimiento"]]

    def __str__(self):
        return f"{self.producto.sku} | {self.fecha} | {self.tipo_movimiento} | {self.cantidad_total}"


class ResumenConsumoMensual(models.Model):
    """
    Agregado mensual de consumo (salidas OUT) por producto. Release 2.
    Fuente: HechoConsumo con tipo_movimiento='OUT'.
    """
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="resumenes_consumo")
    anio = models.PositiveSmallIntegerField()
    mes = models.PositiveSmallIntegerField()
    cantidad_salidas = models.IntegerField(default=0)
    promedio_diario = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    dias_con_movimiento = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Resumen consumo mensual"
        verbose_name_plural = "Resúmenes consumo mensual"
        ordering = ["-anio", "-mes", "producto"]
        unique_together = [["producto", "anio", "mes"]]

    def __str__(self):
        return f"{self.producto.sku} | {self.anio}-{self.mes:02d} | {self.cantidad_salidas}"
