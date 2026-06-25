from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0006_solicitudinsumo_tipo_destino_compra"),
    ]

    operations = [
        migrations.AlterField(
            model_name="solicitudinsumo",
            name="tipo_destino_compra",
            field=models.CharField(
                blank=True,
                choices=[
                    ("INVENTARIO", "Para inventario"),
                    ("ENTREGA_INMEDIATA", "Entrega inmediata"),
                ],
                default=None,
                help_text="Lo define Compras antes de enviar a Gerencia o gestionar la solicitud.",
                max_length=20,
                null=True,
            ),
        ),
    ]
