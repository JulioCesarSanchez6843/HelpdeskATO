from django.db.models import Q

from .models import Usuario


def roles_asignables(actor):
    if actor is None:
        return []
    if actor.es_maestro:
        return [
            Usuario.Rol.SUPERADMIN,
            Usuario.Rol.ENCARGADO,
            Usuario.Rol.BECARIO,
            Usuario.Rol.USUARIO,
        ]
    if actor.es_superadmin:
        return [Usuario.Rol.ENCARGADO, Usuario.Rol.BECARIO, Usuario.Rol.USUARIO]
    if actor.es_encargado:
        return [Usuario.Rol.BECARIO, Usuario.Rol.USUARIO]
    return []


def usuarios_gestionables(actor):
    usuarios = Usuario.objects.select_related("area", "puesto", "sucursal")
    if actor is None:
        return usuarios.none()
    if actor.es_maestro:
        return usuarios
    if actor.es_superadmin:
        return usuarios.filter(
            Q(pk=actor.pk)
            | (~Q(rol=Usuario.Rol.SUPERADMIN) & Q(is_superuser=False))
        )
    if actor.es_encargado:
        return usuarios.filter(sucursal_id=actor.sucursal_id).filter(
            Q(pk=actor.pk)
            | (
                Q(rol__in=[Usuario.Rol.BECARIO, Usuario.Rol.USUARIO])
                & Q(is_superuser=False)
            )
        )
    return usuarios.none()


def puede_cambiar_password(actor, objetivo):
    if actor is None or objetivo is None or objetivo.pk is None:
        return False
    if actor.pk == objetivo.pk:
        return False
    return usuarios_gestionables(actor).filter(pk=objetivo.pk).exists()

def usuarios_visibles(actor):
    usuarios = Usuario.objects.select_related("area", "puesto", "sucursal")
    if actor is None:
        return usuarios.none()
    if actor.es_superadmin:
        return usuarios
    if actor.es_encargado:
        return usuarios.filter(
            sucursal_id=actor.sucursal_id, is_superuser=False
        ).exclude(rol=Usuario.Rol.SUPERADMIN)
    return usuarios.none()


def puede_ver_password(actor, objetivo):
    if actor is None or objetivo is None or objetivo.pk is None:
        return False
    if actor.pk == objetivo.pk:
        return True
    return usuarios_visibles(actor).filter(pk=objetivo.pk).exists()