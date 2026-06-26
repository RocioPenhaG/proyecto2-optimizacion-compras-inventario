"""
Comando para crear un usuario de prueba por cada rol del sistema.
Uso: python manage.py create_roles_users
Contraseña por defecto: segupak123 (o DEV_USERS_PASSWORD en el entorno).

Para pruebas E2E (funcionario, compras, gerencia):
  python manage.py create_roles_users --e2e
"""
import os

from django.core.management.base import BaseCommand

from apps.users.models import User, Role


DEFAULT_PASSWORD = "segupak123"
COMPRAS_E2E_PASSWORD = os.environ.get("E2E_COMPRAS_PASS", "segupak1234")

# Usuarios requeridos por Playwright (tests/e2e/helpers/credentials.ts)
E2E_USERNAMES = frozenset({"funcionario", "compras", "gerencia"})

E2E_PASSWORDS = {
    "funcionario": DEFAULT_PASSWORD,
    "compras": COMPRAS_E2E_PASSWORD,
    "gerencia": DEFAULT_PASSWORD,
}

ROLE_USERS = [
    ("funcionario", "Funcionario", "Funcionario", Role.FUNCIONARIO),
    ("compras", "Compras", "Área de Compras", Role.COMPRAS),
    ("gerencia", "Gerencia", "Gerencia", Role.GERENCIA),
    ("contable", "Contable", "Área Contable", Role.CONTABLE),
]


class Command(BaseCommand):
    help = (
        "Crea un usuario de prueba por cada rol. "
        "Use --e2e para garantizar funcionario/compras/gerencia activos con contraseña conocida."
    )

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
        parser.add_argument(
            "--e2e",
            action="store_true",
            help=(
                "Garantiza usuarios E2E (funcionario, compras, gerencia): "
                "activos, rol correcto y contraseña de prueba."
            ),
        )

    def _upsert_user(self, username: str, first_name: str, role: str, password: str) -> str:
        user = User.objects.filter(username=username).first()
        if user:
            user.role = role
            user.first_name = first_name
            user.is_active = True
            user.set_password(password)
            user.save()
            return "actualizado"

        User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            role=role,
            is_active=True,
            is_staff=(role == Role.ADMINISTRADOR),
            is_superuser=(role == Role.ADMINISTRADOR),
        )
        return "creado"

    def _expected_password(self, username: str, default_password: str, e2e: bool) -> str:
        if e2e and username in E2E_PASSWORDS:
            return E2E_PASSWORDS[username]
        return default_password

    def handle(self, *args, **options):
        password = options["password"]
        force = options["force"]
        e2e = options["e2e"]

        for username, first_name, _display, role in ROLE_USERS:
            if e2e and username not in E2E_USERNAMES:
                continue

            user = User.objects.filter(username=username).first()
            should_update = force or e2e
            user_password = self._expected_password(username, password, e2e)

            if user and not should_update:
                if not user.is_active:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Usuario '{username}' existe pero está inactivo. "
                            "Use --force o --e2e para corregirlo."
                        )
                    )
                elif not user.check_password(user_password):
                    self.stdout.write(
                        self.style.WARNING(
                            f"Usuario '{username}' existe pero la contraseña no coincide con la de prueba "
                            f"({user_password!r}). Use --force o --e2e para restablecerla."
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Usuario '{username}' ya existe. Usa --force o --e2e para actualizar.")
                    )
                continue

            action = self._upsert_user(username, first_name, role, user_password)
            self.stdout.write(self.style.SUCCESS(f"{action.capitalize()}: {username} ({role})"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nContraseñas E2E: funcionario/gerencia → {DEFAULT_PASSWORD!r}, "
                f"compras → {COMPRAS_E2E_PASSWORD!r}"
            )
        )
