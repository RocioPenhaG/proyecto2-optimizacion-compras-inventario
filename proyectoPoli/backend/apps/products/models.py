import re

from django.db import IntegrityError, models

# Solo SKUs exactamente SPK-#### (4 dígitos) participan del contador secuencial.
_SKU_SPK_NUMERIC = re.compile(r"^SPK-(\d{4})$")


def siguiente_sku_spk() -> str:
    """
    Genera el siguiente SKU libre en formato SPK-0001, SPK-0002, ...
    Ignora productos cuyo SKU no coincida con el patrón.
    Si no hay ninguno SPK-####, devuelve SPK-0001.
    """
    max_n = 0
    for sku in Producto.objects.values_list("sku", flat=True):
        if not sku:
            continue
        m = _SKU_SPK_NUMERIC.match(str(sku).strip())
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    return f"SPK-{max_n + 1:04d}"


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
    sku = models.CharField(max_length=50, unique=True, blank=True)
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
        related_name="productos",
    )

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

    def __str__(self):
        return f"[{self.sku}] {self.nombre}"

    def _sku_es_vacio(self) -> bool:
        return self.sku is None or str(self.sku).strip() == ""

    def _asignar_sku_autogenerado_si_vacio(self) -> bool:
        """
        Si el SKU está vacío, asigna el siguiente SPK-####.
        Devuelve True si se autogeneró (para reintentos ante colisiones concurrentes).
        """
        if not self._sku_es_vacio():
            self.sku = str(self.sku).strip()
            return False
        self.sku = siguiente_sku_spk()
        return True

    def clean(self):
        # Normalizar espacios; el SKU autogenerado se asigna en save().
        if not self._sku_es_vacio():
            self.sku = str(self.sku).strip()
        super().clean()

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "sku" not in update_fields:
            return super().save(*args, **kwargs)

        was_blank_at_entry = self._sku_es_vacio()
        self._asignar_sku_autogenerado_si_vacio()
        intentos = 10 if was_blank_at_entry else 1

        for intento in range(intentos):
            try:
                return super().save(*args, **kwargs)
            except IntegrityError:
                if not was_blank_at_entry or intento == intentos - 1:
                    raise
                self.sku = ""
                self._asignar_sku_autogenerado_si_vacio()
