from django.contrib.auth.models import Group, User
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from .serializers import RoleSerializer, RoleAssignSerializer
from .permissions import IsComprasGroup


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    u = request.user
    roles = list(u.groups.values_list("name", flat=True))
    return Response({
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "is_staff": u.is_staff,
        "roles": roles,
    })


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def roles(request):
    # GET: cualquiera autenticado puede ver roles
    if request.method == "GET":
        qs = Group.objects.all().order_by("name")
        return Response(RoleSerializer(qs, many=True).data)

    # POST: solo staff/admin puede crear roles
    if not request.user.is_staff:
        return Response({"detail": "No autorizado."}, status=status.HTTP_403_FORBIDDEN)

    name = (request.data.get("name") or "").strip()
    if not name:
        return Response({"detail": "Falta 'name'."}, status=status.HTTP_400_BAD_REQUEST)

    g, created = Group.objects.get_or_create(name=name)
    return Response(
        RoleSerializer(g).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )


@api_view(["POST"])
@permission_classes([IsAdminUser])  # staff/admin
def assign_role(request):
    ser = RoleAssignSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    username = ser.validated_data["username"]
    role = ser.validated_data["role"]

    user = User.objects.get(username=username)
    group = Group.objects.get(name=role)

    user.groups.add(group)
    return Response({"ok": True, "username": username, "role": role})


@api_view(["GET"])
@permission_classes([IsComprasGroup])
def compras_ping(request):
    return Response({"ok": True, "msg": "Solo COMPRAS o ADMIN puede ver esto."})
