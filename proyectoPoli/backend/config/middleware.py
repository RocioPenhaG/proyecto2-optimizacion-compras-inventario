"""
Middleware que devuelve errores 500 en JSON para rutas /api/ cuando DEBUG=True.
Así el frontend puede mostrar el mensaje real del backend.
"""
import traceback
from django.http import JsonResponse
from django.conf import settings


class ApiExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if not request.path.startswith("/api/"):
            return None
        if not settings.DEBUG:
            return None
        return JsonResponse(
            {
                "detail": str(exception),
                "traceback": traceback.format_exc(),
            },
            status=500,
        )
