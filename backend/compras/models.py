from django.conf import settings
from django.db import models


class SolicitudCompra(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        ENVIADA = "ENVIADA", "Enviada"
        APROBADA = "APROBADA", "Aprobada"
        RECHAZADA = "RECHAZADA", "Rechazada"

    titulo = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    departamento = models.CharField(max_length=120, blank=True, default="")
    tipo_producto = models.CharField(max_length=120, blank=True, default="")
    marca_recomendada = models.CharField(max_length=120, blank=True, default="")
    proveedor_recomendado = models.CharField(max_length=120, blank=True, default="")
    tamano = models.CharField(max_length=120, blank=True, default="")
    medidas = models.CharField(max_length=120, blank=True, default="")
    cantidad_texto = models.CharField(max_length=120, blank=True, default="")  # opcional, si quieren “Cantidad: ___” general
    destino_producto = models.CharField(max_length=200, blank=True, default="")
    firma_encargado = models.CharField(max_length=120, blank=True, default="")  # opcional (por ahora texto)


    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.BORRADOR,
    )

    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="solicitudes_compra",
    )

    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="solicitudes_aprobadas",
    )
    aprobado_at = models.DateTimeField(null=True, blank=True)

    rechazado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="solicitudes_rechazadas",
    )
    rechazado_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.estado}] {self.titulo}"

class SolicitudCompraItem(models.Model):
    solicitud = models.ForeignKey(
        SolicitudCompra,
        on_delete=models.CASCADE,
        related_name="items",
    )

    descripcion = models.CharField(max_length=200)
    cantidad = models.DecimalField(max_digits=12, decimal_places=2)
    precio_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.descripcion} x {self.cantidad}"


