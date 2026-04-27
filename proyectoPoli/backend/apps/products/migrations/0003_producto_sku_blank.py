# Generated manually for auto-SKU: allow empty SKU in forms until save() assigns SPK-XXXX.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0002_producto_requiere_aprobacion_gerencia"),
    ]

    operations = [
        migrations.AlterField(
            model_name="producto",
            name="sku",
            field=models.CharField(blank=True, max_length=50, unique=True),
        ),
    ]
