from rest_framework.permissions import BasePermission

class IsInGroup(BasePermission):
    """
    Permite acceso si el usuario está autenticado y pertenece al grupo indicado
    (case-insensitive) o si es staff/superuser.
    """
    group_name = None  # se define en subclasses

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        # Admin pasa todo
        if user.is_staff or user.is_superuser:
            return True

        if not self.group_name:
            return False

        wanted = str(self.group_name).lower()
        return user.groups.filter(name__iexact=wanted).exists()


class IsAdminGroup(IsInGroup):
    group_name = "admin"


class IsComprasGroup(IsInGroup):
    group_name = "compras"
