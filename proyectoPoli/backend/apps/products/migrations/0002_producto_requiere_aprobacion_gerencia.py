from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="producto",
            name="requiere_aprobacion_gerencia",
            field=models.BooleanField(
                default=False,
                help_text="Si es verdadero, la solicitud con este ítem debe ser aprobada/rechazada por Gerencia (insumo nuevo o estratégico).",
            ),
        ),
    ]
