import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0001_initial"),
        ("analytics", "0005_corridaanalitica_productos_candidatos_tendencia"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProyeccionConsumoFuturo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha", models.DateField()),
                (
                    "horizonte_dias",
                    models.PositiveIntegerField(
                        help_text="Días hacia adelante desde fecha_fin de la tendencia (1 = primer día proyectado).",
                    ),
                ),
                ("valor_diario", models.DecimalField(decimal_places=6, max_digits=18)),
                ("consumo_acumulado", models.DecimalField(decimal_places=6, max_digits=18)),
                (
                    "corrida",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proyecciones_consumo",
                        to="analytics.corridaanalitica",
                    ),
                ),
                (
                    "producto",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proyecciones_consumo",
                        to="products.producto",
                    ),
                ),
                (
                    "tendencia",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proyecciones",
                        to="analytics.resultadotendencialineal",
                    ),
                ),
            ],
            options={
                "verbose_name": "Proyección de consumo futuro",
                "verbose_name_plural": "Proyecciones de consumo futuro",
                "ordering": ["tendencia_id", "horizonte_dias"],
                "unique_together": {("tendencia", "horizonte_dias")},
            },
        ),
    ]
