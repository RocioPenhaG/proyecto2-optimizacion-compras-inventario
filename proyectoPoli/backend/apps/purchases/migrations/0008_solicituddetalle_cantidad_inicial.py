from django.db import migrations, models


def copiar_cantidad_a_inicial(apps, schema_editor):
    SolicitudDetalle = apps.get_model("purchases", "SolicitudDetalle")
    for detalle in SolicitudDetalle.objects.all().only("id", "cantidad", "cantidad_inicial"):
        if detalle.cantidad_inicial != detalle.cantidad:
            detalle.cantidad_inicial = detalle.cantidad
            detalle.save(update_fields=["cantidad_inicial"])


class Migration(migrations.Migration):
    dependencies = [
        ("purchases", "0007_alter_solicitudinsumo_tipo_destino_compra"),
    ]

    operations = [
        migrations.AddField(
            model_name="solicituddetalle",
            name="cantidad_inicial",
            field=models.PositiveIntegerField(default=1),
            preserve_default=False,
        ),
        migrations.RunPython(copiar_cantidad_a_inicial, migrations.RunPython.noop),
    ]
