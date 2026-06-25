from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import Role

ROLES_ESCRITURA_PRODUCTOS_INVENTARIO = frozenset(
    {Role.COMPRAS, Role.CONTABLE, Role.ADMINISTRADOR}
)


class IsNotFuncionario(BasePermission):
    """Inventario, estadísticas de stock y similares: sin acceso para Funcionario."""

    message = "Los funcionarios no tienen acceso a inventario ni a indicadores de stock."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role != Role.FUNCIONARIO


class InventoryAccess(BasePermission):
    """
    Funcionario: sin acceso.
    Gerencia: solo lectura de movimientos y stock.
    Compras, Contable y Administrador: lectura y registro de movimientos.
    """

    message = "No tiene permiso para registrar movimientos de inventario."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        role = request.user.role
        if role == Role.FUNCIONARIO:
            return False
        if request.method == "DELETE":
            return role == Role.ADMINISTRADOR
        if request.method in SAFE_METHODS:
            return True
        return role in ROLES_ESCRITURA_PRODUCTOS_INVENTARIO


class ProductoProveedorWriteOrReadOnly(BasePermission):
    """
    Funcionario y Gerencia: solo lectura.
    Compras, Contable y Administrador: lectura y escritura.
    """

    message = "Su rol solo puede consultar el catálogo; no crear ni editar productos o proveedores."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method == "DELETE":
            return request.user.role == Role.ADMINISTRADOR
        if request.user.role in (Role.FUNCIONARIO, Role.GERENCIA):
            return request.method in SAFE_METHODS
        return True
