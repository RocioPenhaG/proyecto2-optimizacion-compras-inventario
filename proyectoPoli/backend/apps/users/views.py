from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django.conf import settings

from .models import User
from .serializers import UserSerializer


class MeView(generics.RetrieveAPIView):
    """Devuelve el usuario autenticado y su rol."""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class CustomTokenObtainPairView(TokenObtainPairView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except Exception as e:
            if settings.DEBUG:
                import traceback
                return Response(
                    {
                        "detail": str(e),
                        "traceback": traceback.format_exc(),
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            raise
