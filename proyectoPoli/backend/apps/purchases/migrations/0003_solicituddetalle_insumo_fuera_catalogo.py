import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0002_producto_requiere_aprobacion_gerencia"),
        ("purchases", "0002_add_motivo_rechazo"),
    ]

    operations = [
        migrations.AddField(
            model_name="solicituddetalle",
            name="descripcion_insumo_solicitado",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Si aún no hay producto en catálogo, descripción libre del insumo (funcionario).",
                max_length=500,
            ),
        ),
        migrations.AlterField(
            model_name="solicituddetalle",
            name="producto",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="solicitud_detalles",
                to="products.producto",
            ),
        ),
    ]
