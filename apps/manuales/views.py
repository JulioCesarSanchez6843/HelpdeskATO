from django.contrib import messages
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from apps.accounts.decorators import (
    admin_required,
    personal_required,
    superadmin_required,
)

from .forms import ManualForm
from .models import CategoriaManual, Manual


def _categorias():
    nombres = set(CategoriaManual.objects.values_list("nombre", flat=True))
    nombres.update(Manual.objects.values_list("categoria", flat=True))
    return sorted(nombres, key=str.lower)


def _visibles(usuario):
    manuales = Manual.objects.select_related("subido_por", "eliminacion_solicitada_por")
    if usuario.es_superadmin:
        return manuales
    if usuario.es_encargado:
        return manuales.filter(
            Q(estado=Manual.Estado.APROBADO) | Q(subido_por=usuario)
        )
    return manuales.filter(estado=Manual.Estado.APROBADO)


def _por_revisar(usuario):
    if not usuario.es_superadmin:
        return 0
    return Manual.objects.filter(
        Q(estado=Manual.Estado.PENDIENTE)
        | Q(estado=Manual.Estado.APROBADO, eliminacion_solicitada_en__isnull=False)
    ).count()


def _destino(request, defecto):
    siguiente = request.POST.get("next", "")
    if siguiente and url_has_allowed_host_and_scheme(
        siguiente,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return siguiente
    return reverse(defecto)


@personal_required
def lista(request):
    aprobados = _visibles(request.user).filter(estado=Manual.Estado.APROBADO)
    categorias = (
        Manual.objects.filter(estado=Manual.Estado.APROBADO)
        .order_by("categoria")
        .values_list("categoria", flat=True)
        .distinct()
    )
    return render(
        request,
        "manuales/lista.html",
        {
            "aprobados": aprobados,
            "categorias": categorias,
            "por_revisar": _por_revisar(request.user),
        },
    )


@admin_required
def gestion(request):
    usuario = request.user
    contexto = {"por_revisar": _por_revisar(usuario)}
    manuales = Manual.objects.select_related(
        "subido_por", "eliminacion_solicitada_por"
    )
    if usuario.es_superadmin:
        contexto["por_aprobar"] = manuales.filter(
            estado=Manual.Estado.PENDIENTE
        ).order_by("subido_en")
        contexto["solicitudes"] = manuales.filter(
            estado=Manual.Estado.APROBADO,
            eliminacion_solicitada_en__isnull=False,
        ).order_by("eliminacion_solicitada_en")
    else:
        propios = manuales.filter(subido_por=usuario).order_by("-subido_en")
        contexto["en_revision"] = propios.filter(estado=Manual.Estado.PENDIENTE)
        contexto["publicados"] = propios.filter(
            estado=Manual.Estado.APROBADO,
            eliminacion_solicitada_en__isnull=True,
        )
        contexto["con_solicitud"] = propios.filter(
            estado=Manual.Estado.APROBADO,
            eliminacion_solicitada_en__isnull=False,
        )
    return render(request, "manuales/gestion.html", contexto)


@xframe_options_sameorigin
@personal_required
def ver(request, pk):
    manual = get_object_or_404(_visibles(request.user), pk=pk)
    nombre = f"{slugify(manual.titulo) or 'manual'}.pdf"
    try:
        respuesta = FileResponse(
            manual.archivo.open("rb"),
            content_type="application/pdf",
            as_attachment=bool(request.GET.get("descargar")),
            filename=nombre,
        )
    except (FileNotFoundError, ValueError):
        raise Http404
    respuesta["X-Content-Type-Options"] = "nosniff"
    respuesta["Cache-Control"] = "private, max-age=3600"
    return respuesta


@admin_required
def nuevo(request):
    if request.method == "POST":
        form = ManualForm(request.POST, request.FILES)
        if form.is_valid():
            manual = form.save(commit=False)
            manual.subido_por = request.user
            if request.user.es_superadmin:
                manual.estado = Manual.Estado.APROBADO
                manual.aprobado_por = request.user
                manual.aprobado_en = timezone.now()
                mensaje = f"Manual «{manual.titulo}» subido y publicado."
            else:
                manual.estado = Manual.Estado.PENDIENTE
                mensaje = (
                    f"Manual «{manual.titulo}» enviado. Será visible cuando "
                    "un super administrador lo apruebe."
                )
            manual.save()
            messages.success(request, mensaje)
            return redirect(
                "lista_manuales" if request.user.es_superadmin else "gestion_manuales"
            )
    else:
        form = ManualForm()
    return render(
        request,
        "manuales/form.html",
        {"form": form, "titulo": "Nuevo manual", "categorias": _categorias()},
    )


@superadmin_required
def editar(request, pk):
    manual = get_object_or_404(Manual, pk=pk)
    anterior = manual.archivo.name
    if request.method == "POST":
        form = ManualForm(request.POST, request.FILES, instance=manual)
        if form.is_valid():
            manual = form.save()
            if anterior and anterior != manual.archivo.name:
                manual.archivo.storage.delete(anterior)
            messages.success(request, f"Manual «{manual.titulo}» actualizado.")
            return redirect("lista_manuales")
    else:
        form = ManualForm(instance=manual)
    return render(
        request,
        "manuales/form.html",
        {"form": form, "titulo": "Editar manual", "categorias": _categorias()},
    )


@superadmin_required
@require_POST
def eliminar(request, pk):
    manual = get_object_or_404(Manual, pk=pk)
    titulo = manual.titulo
    manual.archivo.delete(save=False)
    manual.delete()
    messages.success(request, f"Manual «{titulo}» eliminado.")
    return redirect(_destino(request, "lista_manuales"))


@superadmin_required
@require_POST
def aprobar(request, pk):
    manual = get_object_or_404(Manual, pk=pk)
    if manual.estado != Manual.Estado.APROBADO:
        manual.estado = Manual.Estado.APROBADO
        manual.aprobado_por = request.user
        manual.aprobado_en = timezone.now()
        manual.save(
            update_fields=["estado", "aprobado_por", "aprobado_en", "actualizado_en"]
        )
        messages.success(request, f"Manual «{manual.titulo}» aprobado y publicado.")
    return redirect("gestion_manuales")


@admin_required
@require_POST
def cancelar(request, pk):
    manual = get_object_or_404(
        Manual,
        pk=pk,
        subido_por=request.user,
        estado=Manual.Estado.PENDIENTE,
    )
    titulo = manual.titulo
    manual.archivo.delete(save=False)
    manual.delete()
    messages.success(request, f"Manual «{titulo}» cancelado.")
    return redirect("gestion_manuales")


@admin_required
@require_POST
def solicitar_eliminacion(request, pk):
    manual = get_object_or_404(
        Manual,
        pk=pk,
        subido_por=request.user,
        estado=Manual.Estado.APROBADO,
    )
    motivo = request.POST.get("motivo", "").strip()[:300]
    if not motivo:
        messages.error(
            request,
            "Escribe el motivo de la eliminación para enviar la solicitud.",
        )
        return redirect("gestion_manuales")
    if manual.eliminacion_solicitada_en is None:
        manual.eliminacion_solicitada_por = request.user
        manual.eliminacion_solicitada_en = timezone.now()
        manual.motivo_eliminacion = motivo
        manual.save(
            update_fields=[
                "eliminacion_solicitada_por",
                "eliminacion_solicitada_en",
                "motivo_eliminacion",
                "actualizado_en",
            ]
        )
        messages.success(
            request,
            f"Solicitud de eliminación de «{manual.titulo}» enviada.",
        )
    return redirect("gestion_manuales")


@superadmin_required
@require_POST
def rechazar_solicitud(request, pk):
    manual = get_object_or_404(Manual, pk=pk)
    manual.eliminacion_solicitada_por = None
    manual.eliminacion_solicitada_en = None
    manual.motivo_eliminacion = ""
    manual.save(
        update_fields=[
            "eliminacion_solicitada_por",
            "eliminacion_solicitada_en",
            "motivo_eliminacion",
            "actualizado_en",
        ]
    )
    messages.success(request, f"Solicitud rechazada. «{manual.titulo}» se conserva.")
    return redirect("gestion_manuales")