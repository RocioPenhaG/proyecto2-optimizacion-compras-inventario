from django.db import migrations, models


def marcar_fuera_catalogo_existentes(apps, schema_editor):
    SolicitudInsumo = apps.get_model("purchases", "SolicitudInsumo")
    SolicitudDetalle = apps.get_model("purchases", "SolicitudDetalle")
    ids = (
        SolicitudDetalle.objects.filter(producto_id__isnull=True)
        .values_list("solicitud_id", flat=True)
        .distinct()
    )
    SolicitudInsumo.objects.filter(pk__in=ids).update(contiene_fuera_catalogo=True)


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0004_alter_solicituddetalle_descripcion_insumo_solicitado"),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitudinsumo",
            name="contiene_fuera_catalogo",
            field=models.BooleanField(
                default=False,
                help_text="True si al crear la solicitud hubo al menos un ítem fuera de catálogo.",
            ),
        ),
        migrations.RunPython(marcar_fuera_catalogo_existentes, migrations.RunPython.noop),
    ]
