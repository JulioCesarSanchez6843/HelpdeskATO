from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .serializers import UsuarioSerializer


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    correo = (request.data.get("correo") or "").strip()
    password = request.data.get("password") or ""
    usuario = authenticate(request, username=correo, password=password)
    if usuario is None:
        return Response(
            {"detail": "Correo o contraseña incorrectos."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    token, _ = Token.objects.get_or_create(user=usuario)
    return Response({"token": token.key, "usuario": UsuarioSerializer(usuario).data})


@api_view(["POST"])
def logout(request):
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def me(request):
    return Response(UsuarioSerializer(request.user).data)