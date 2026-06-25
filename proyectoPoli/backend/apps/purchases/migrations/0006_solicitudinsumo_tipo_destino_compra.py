from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0005_solicitudinsumo_contiene_fuera_catalogo"),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitudinsumo",
            name="tipo_destino_compra",
            field=models.CharField(
                choices=[
                    ("INVENTARIO", "Para inventario"),
                    ("ENTREGA_INMEDIATA", "Entrega inmediata"),
                ],
                default="INVENTARIO",
                help_text="Para inventario (stock permanente) o entrega inmediata al solicitante.",
                max_length=20,
            ),
        ),
    ]
