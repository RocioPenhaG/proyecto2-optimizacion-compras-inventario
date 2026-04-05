from django.db import migrations


def sync_superuser_roles(apps, schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(is_superuser=True).update(role="ADMINISTRADOR")


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(sync_superuser_roles, migrations.RunPython.noop),
    ]
