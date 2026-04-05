"""
Comando para crear un usuario de prueba por cada rol del sistema.
Uso: python manage.py create_roles_users
Contraseña por defecto: segupak123 (o SECRET_KEY si se define DEV_USERS_PASSWORD en el entorno).
"""
import os

from django.core.management.base import BaseCommand
from django.conf import settings

from apps.users.models import User, Role


DEFAULT_PASSWORD = "segupak123"

ROLE_USERS = [
    ("funcionario", "Funcionario", "Funcionario", Role.FUNCIONARIO),
    ("compras", "Compras", "Área de Compras", Role.COMPRAS),
    ("gerencia", "Gerencia", "Gerencia", Role.GERENCIA),
    ("contable", "Contable", "Área Contable", Role.CONTABLE),
]


class Command(BaseCommand):
    help = "Crea un usuario de prueba por cada rol (Funcionario, Compras, Gerencia, Contable). No crea Administrador; usa createsuperuser para eso."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            type=str,
            default=os.environ.get("DEV_USERS_PASSWORD", DEFAULT_PASSWORD),
            help="Contraseña común para todos los usuarios de prueba (por defecto: segupak123)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Si el usuario ya existe, actualizar su rol y contraseña.",
        )

    def handle(self, *args, **options):
        password = options["password"]
        force = options["force"]

        for username, first_name, _display, role in ROLE_USERS:
            user = User.objects.filter(username=username).first()
            if user:
                if not force:
                    self.stdout.write(
                        self.style.WARNING(f"Usuario '{username}' ya existe. Usa --force para actualizar.")
                    )
                    continue
                user.role = role
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Actualizado: {username} ({role})"))
            else:
                User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    role=role,
                    is_staff=(role == Role.ADMINISTRADOR),
                    is_superuser=(role == Role.ADMINISTRADOR),
                )
                self.stdout.write(self.style.SUCCESS(f"Creado: {username} ({role})"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nContraseña usada para todos: {password}\n"
                "Puedes iniciar sesión en el frontend o en /admin/ con cada usuario."
            )
        )
