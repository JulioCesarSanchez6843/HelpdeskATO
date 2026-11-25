from django.conf import settings
from django.db.models import Q
from django.urls import reverse

from apps.tickets import emails as correos

from .models import Usuario
from .permisos import puede_cambiar_password

CARPETA = "emails"


def administradores_de(solicitante):
    candidatos = Usuario.objects.filter(activo=True).filter(
        Q(is_superuser=True)
        | Q(rol=Usuario.Rol.SUPERADMIN)
        | Q(rol=Usuario.Rol.ENCARGADO, sucursal_id=solicitante.sucursal_id)
    )
    return [a for a in candidatos if puede_cambiar_password(a, solicitante)]


def _url_login():
    return settings.SITE_URL + reverse("login")


def correo_solicitud(solicitante):
    mensajes = correos.construir(
        administradores_de(solicitante),
        f"Solicitud de contraseña: {solicitante.nombre}",
        "solicitud_password",
        {
            "solicitante": solicitante,
            "url_usuario": settings.SITE_URL
            + reverse("editar_usuario", args=[solicitante.pk]),
        },
        carpeta=CARPETA,
    )
    correos.enviar_tras_commit(mensajes)
    return len(mensajes)


def correo_cambio(usuario, administrador):
    mensajes = correos.construir(
        [usuario],
        "Tu contraseña fue cambiada",
        "password_cambiada",
        {
            "usuario": usuario,
            "administrador": administrador,
            "url_login": _url_login(),
        },
        carpeta=CARPETA,
    )
    correos.enviar_tras_commit(mensajes)
    return bool(mensajes)