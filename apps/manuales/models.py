import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def ruta_manual(instancia, nombre):
    return f"manuales/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.pdf"


class Manual(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de aprobación"
        APROBADO = "APROBADO", "Aprobado"

    titulo = models.CharField(max_length=150)
    descripcion = models.CharField(max_length=300, blank=True)
    categoria = models.CharField(max_length=80, default="General")
    archivo = models.FileField(upload_to=ruta_manual)
    nombre_original = models.CharField(max_length=150, blank=True)
    tamano = models.PositiveIntegerField(default=0)
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    aprobado_en = models.DateTimeField(null=True, blank=True)
    eliminacion_solicitada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    eliminacion_solicitada_en = models.DateTimeField(null=True, blank=True)
    motivo_eliminacion = models.CharField(max_length=300, blank=True, default="")
    subido_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["categoria", "titulo"]
        verbose_name = "Manual"
        verbose_name_plural = "Manuales"

    def __str__(self):
        return self.titulo