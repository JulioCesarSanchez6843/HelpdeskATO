import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet():
    base = getattr(settings, "CLAVE_PASSWORDS", "") or settings.SECRET_KEY
    clave = base64.urlsafe_b64encode(hashlib.sha256(base.encode()).digest())
    return Fernet(clave)


def cifrar(texto):
    if not texto:
        return ""
    return _fernet().encrypt(texto.encode()).decode()


def descifrar(token):
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return ""