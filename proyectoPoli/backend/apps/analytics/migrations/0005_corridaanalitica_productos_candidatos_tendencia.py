from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0004_resultadotendencialineal"),
    ]

    operations = [
        migrations.AddField(
            model_name="corridaanalitica",
            name="productos_candidatos_tendencia",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Productos distintos con consumo OUT en la ventana usada para evaluar tendencias (incluye los que no alcanzaron puntos mínimos).",
                null=True,
            ),
        ),
    ]
