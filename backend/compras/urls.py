from django.urls import path
from .views import (
    solicitudes,
    enviar_solicitud,
    aprobar_solicitud,
    rechazar_solicitud,
    items,
    borrar_item,
    flujo_estados,
)

urlpatterns = [
    path("solicitudes/", solicitudes),
    path("solicitudes/<int:pk>/enviar/", enviar_solicitud),
    path("solicitudes/<int:pk>/aprobar/", aprobar_solicitud),
    path("solicitudes/<int:pk>/rechazar/", rechazar_solicitud),
    path("solicitudes/<int:pk>/items/", items),
    path("solicitudes/<int:pk>/items/<int:item_id>/", borrar_item),
    path("flujo/", flujo_estados),
    path("solicitudes/<int:pk>/", editar_solicitud),
]
