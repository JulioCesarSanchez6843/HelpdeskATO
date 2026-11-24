from pathlib import Path

from django import forms
from django.core.files.uploadedfile import UploadedFile

from apps.accounts.forms import BootstrapFormMixin

from .models import Manual

MAX_BYTES = 20 * 1024 * 1024


class ManualForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Manual
        fields = ["titulo", "categoria", "descripcion", "archivo"]
        labels = {"archivo": "Archivo PDF"}
        widgets = {
            "archivo": forms.FileInput(
                attrs={"accept": "application/pdf,.pdf", "class": "visually-hidden"}
            ),
            "categoria": forms.TextInput(
                attrs={
                    "autocomplete": "off",
                    "maxlength": 80,
                    "placeholder": "Elige o escribe una nueva",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["archivo"].required = False
            self.fields["archivo"].help_text = "Déjalo vacío para conservar el PDF actual."

    def clean_categoria(self):
        valor = " ".join(self.cleaned_data.get("categoria", "").split())
        existente = (
            Manual.objects.filter(categoria__iexact=valor)
            .values_list("categoria", flat=True)
            .first()
        )
        return existente or valor

    def clean_archivo(self):
        archivo = self.cleaned_data.get("archivo")
        if not isinstance(archivo, UploadedFile):
            return archivo
        if not archivo.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Solo se permiten archivos PDF.")
        if archivo.size > MAX_BYTES:
            raise forms.ValidationError("El PDF no puede pesar más de 20 MB.")
        archivo.seek(0)
        cabecera = archivo.read(5)
        archivo.seek(0)
        if cabecera != b"%PDF-":
            raise forms.ValidationError("El archivo no es un PDF válido.")
        return archivo

    def save(self, commit=True):
        manual = super().save(commit=False)
        nuevo = self.cleaned_data.get("archivo")
        if isinstance(nuevo, UploadedFile):
            manual.nombre_original = Path(nuevo.name).name[:150]
            manual.tamano = nuevo.size
        if commit:
            manual.save()
        return manual