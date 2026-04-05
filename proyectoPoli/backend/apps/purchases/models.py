from django.conf import settings
from django.db import models

from apps.products.models import Producto


class EstadoSolicitud(models.TextChoices):
    SOLICITADO = "SOLICITADO", "Solicitado"
    EN_REVISION = "EN_REVISION", "En revisión"
    COMPRA_ACEPTADA = "COMPRA_ACEPTADA", "Compra aceptada"
    COMPRA_RECHAZADA = "COMPRA_RECHAZADA", "Compra rechazada"
    FINALIZADO = "FINALIZADO", "Finalizado"


class SolicitudInsumo(models.Model):
    fecha = models.DateField(auto_now_add=True)
    estado = models.CharField(
        max_length=20,
        choices=EstadoSolicitud.choices,
        default=EstadoSolicitud.SOLICITADO,
    )
    destino = models.CharField(max_length=200, blank=True, default="")
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="solicitudes_creadas",
    )
    observacion = models.TextField(blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)
    aprobado_en = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Solicitud de Insumo"
        verbose_name_plural = "Solicitudes de Insumo"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Solicitud #{self.pk} ({self.get_estado_display()}) - {self.solicitante.username}"


class SolicitudDetalle(models.Model):
    solicitud = models.ForeignKey(
        SolicitudInsumo,
        on_delete=models.CASCADE,
        related_name="detalles",
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="solicitud_detalles",
        null=True,
        blank=True,
    )
    descripcion_insumo_solicitado = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Insumo pedido fuera de catálogo hasta que Compras cree el producto y vincule.",
    )
    cantidad = models.PositiveIntegerField()
    observacion = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Detalle de Solicitud"
        verbose_name_plural = "Detalles de Solicitud"

    def __str__(self):
        if self.producto_id:
            return f"{self.solicitud_id} - {self.producto.sku} x {self.cantidad}"
        return f"{self.solicitud_id} - [fuera catálogo] {self.descripcion_insumo_solicitado[:40]} x {self.cantidad}"
