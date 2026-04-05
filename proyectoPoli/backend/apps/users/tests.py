from django.test import TestCase

from apps.users.models import Role, User


class SegupakUserManagerTests(TestCase):
    def test_create_superuser_gets_administrador_role(self):
        user = User.objects.create_superuser(
            username="admin_test",
            email="admin@test.local",
            password="x",
        )
        self.assertEqual(user.role, Role.ADMINISTRADOR)

    def test_superuser_save_keeps_administrador_role(self):
        user = User.objects.create_user(
            username="u1",
            password="x",
            role=Role.FUNCIONARIO,
        )
        user.is_superuser = True
        user.is_staff = True
        user.save()
        user.refresh_from_db()
        self.assertEqual(user.role, Role.ADMINISTRADOR)
