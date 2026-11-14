from rest_framework import serializers

from apps.accounts.models import Usuario


class UsuarioSerializer(serializers.ModelSerializer):
    sucursal = serializers.StringRelatedField()
    area = serializers.StringRelatedField()
    puesto = serializers.StringRelatedField()

    class Meta:
        model = Usuario
        fields = [
            "id", "nombre", "correo", "rol",
            "sucursal", "area", "puesto", "debe_cambiar_password",
        ]