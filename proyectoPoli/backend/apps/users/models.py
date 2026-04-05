from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class Role(models.TextChoices):
    FUNCIONARIO = "FUNCIONARIO", "Funcionario"
    COMPRAS = "COMPRAS", "Área de Compras"
    GERENCIA = "GERENCIA", "Gerencia"
    CONTABLE = "CONTABLE", "Área Contable"
    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"


class SegupakUserManager(UserManager):
    """Superusuarios del admin Django llevan rol de negocio Administrador."""

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", Role.ADMINISTRADOR)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.FUNCIONARIO,
    )

    objects = SegupakUserManager()

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = Role.ADMINISTRADOR
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_username()} ({self.get_role_display()})"
