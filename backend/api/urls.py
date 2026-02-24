from django.urls import path
from .views import health, me, roles, assign_role, compras_ping

urlpatterns = [
    path("health/", health),
    path("me/", me),
    path("roles/", roles),
    path("roles/assign/", assign_role),
    path("compras/ping/", compras_ping),

]
