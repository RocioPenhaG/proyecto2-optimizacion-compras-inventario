from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include


def root(request):
    """API root: enlaces a admin y API."""
    return JsonResponse({
        "message": "Backend Segupak — API",
        "admin": "/admin/",
        "api": "/api/",
    })


urlpatterns = [
    path("", root),
    path("admin/", admin.site.urls),
    path("api/", include("apps.users.urls")),
    path("api/products/", include("apps.products.urls")),
    path("api/inventory/", include("apps.inventory.urls")),
    path("api/purchases/", include("apps.purchases.urls")),
    path("api/dashboard/", include("apps.dashboard.urls")),
    path("api/analytics/", include("apps.analytics.urls")),
]
