from django.conf import settings
from django.db import IntegrityError, models

from apps.products.models import Producto


class EstadoSolicitud(models.TextChoices):
    SOLICITADO = "SOLICITADO", "Solicitado"
    EN_REVISION = "EN_REVISION", "En revisión"
    COMPRA_ACEPTADA = "COMPRA_ACEPTADA", "Compra aceptada"
    COMPRA_RECHAZADA = "COMPRA_RECHAZADA", "Compra rechazada"
    FINALIZADO = "FINALIZADO", "Finalizado"


class AccionTransicionSolicitud(models.TextChoices):
    TOMAR_SOLICITUD = "TOMAR_SOLICITUD", "Tomar solicitud"
    SOLICITAR_GERENCIA = "SOLICITAR_GERENCIA", "Solicitar aprobación Gerencia"


class TipoDestinoCompra(models.TextChoices):
    INVENTARIO = "INVENTARIO", "Para inventario"
    ENTREGA_INMEDIATA = "ENTREGA_INMEDIATA", "Entrega inmediata"


def siguiente_numero_solicitud() -> int:
    """Siguiente número correlativo visible (1, 2, 3…)."""
    ultimo = (
        SolicitudInsumo.objects.order_by("-numero").values_list("numero", flat=True).first()
    )
    return (ultimo or 0) + 1


def renumerar_numeros_solicitud_tras_eliminacion(numero_eliminado: int) -> None:
    """
    Tras borrar la solicitud N, las solicitudes con número mayor se decrementan en 1
    para mantener la secuencia visible sin saltos.
    """
    candidatos = list(
        SolicitudInsumo.objects.filter(numero__gt=numero_eliminado)
        .order_by("numero")
        .values_list("pk", "numero")
    )
    for pk, numero in candidatos:
        SolicitudInsumo.objects.filter(pk=pk).update(numero=numero - 1)


class SolicitudInsumo(models.Model):
    numero = models.PositiveIntegerField(
        unique=True,
        null=True,
        blank=True,
        help_text="Número correlativo visible en listados (#1, #2…).",
    )
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
    contiene_fuera_catalogo = models.BooleanField(
        default=False,
        help_text="True si al crear la solicitud hubo al menos un ítem fuera de catálogo.",
    )
    tipo_destino_compra = models.CharField(
        max_length=20,
        choices=TipoDestinoCompra.choices,
        null=True,
        blank=True,
        default=None,
        help_text="Lo define Compras antes de enviar a Gerencia o gestionar la solicitud.",
    )

    class Meta:
        verbose_name = "Solicitud de Insumo"
        verbose_name_plural = "Solicitudes de Insumo"
        ordering = ["-creado_en"]

    def __str__(self):
        etiqueta = self.numero if self.numero is not None else self.pk
        return f"Solicitud #{etiqueta} ({self.get_estado_display()}) - {self.solicitante.username}"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "numero" not in update_fields:
            return super().save(*args, **kwargs)

        asignar_numero = self.pk is None and self.numero is None
        if asignar_numero:
            self.numero = siguiente_numero_solicitud()

        intentos = 5 if asignar_numero else 1
        for intento in range(intentos):
            try:
                return super().save(*args, **kwargs)
            except IntegrityError:
                if not asignar_numero or intento == intentos - 1:
                    raise
                self.numero = siguiente_numero_solicitud()


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
    cantidad_inicial = models.PositiveIntegerField(
        help_text="Cantidad pedida por el funcionario al crear la solicitud (no se modifica).",
    )
    observacion = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Detalle de Solicitud"
        verbose_name_plural = "Detalles de Solicitud"

    def __str__(self):
        if self.producto_id:
            return f"{self.solicitud_id} - {self.producto.sku} x {self.cantidad}"
        return f"{self.solicitud_id} - [fuera catálogo] {self.descripcion_insumo_solicitado[:40]} x {self.cantidad}"

    def save(self, *args, **kwargs):
        if self.pk is None:
            self.cantidad_inicial = self.cantidad
        super().save(*args, **kwargs)
