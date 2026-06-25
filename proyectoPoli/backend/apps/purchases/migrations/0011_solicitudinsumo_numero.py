from django.db import migrations, models


def asignar_numeros_iniciales(apps, schema_editor):
    SolicitudInsumo = apps.get_model("purchases", "SolicitudInsumo")
    for idx, solicitud in enumerate(SolicitudInsumo.objects.order_by("id"), start=1):
        solicitud.numero = idx
        solicitud.save(update_fields=["numero"])


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0009_alter_solicituddetalle_cantidad_inicial"),
    ]

    operations = [
        migrations.AddField(
            model_name="solicitudinsumo",
            name="numero",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Número correlativo visible en listados (#1, #2…).",
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(asignar_numeros_iniciales, migrations.RunPython.noop),
    ]
