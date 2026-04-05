from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import Role


class IsNotFuncionario(BasePermission):
    """Inventario, estadísticas de stock y similares: sin acceso para Funcionario."""

    message = "Los funcionarios no tienen acceso a inventario ni a indicadores de stock."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role != Role.FUNCIONARIO


class ProductoProveedorWriteOrReadOnly(BasePermission):
    """
    Funcionario: solo lectura (catálogo para armar solicitudes).
    Demás roles autenticados: lectura y escritura.
    """

    message = "Los funcionarios solo pueden consultar el catálogo; no crear ni editar productos o proveedores."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role == Role.FUNCIONARIO:
            return request.method in SAFE_METHODS
        return True
