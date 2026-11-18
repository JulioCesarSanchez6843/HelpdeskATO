from django.db.models import OuterRef, Subquery


def entero_positivo(valor):
    valor = (valor or "").strip()
    if valor.isascii() and valor.isdigit() and len(valor) <= 9:
        return int(valor)
    return None


def foto_de(campo):
    from .models import FotoPerfil

    return Subquery(
        FotoPerfil.objects.filter(usuario_id=OuterRef(campo)).values("actualizada_en")[:1]
    )