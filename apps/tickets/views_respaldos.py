import hmac
from datetime import datetime

from decouple import config
from django.conf import settings
from django.contrib import messages
from django.core.management import call_command
from django.db import connections
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.decorators import superadmin_required
from apps.actividad.models import Evento

from . import respaldos
from .management.commands import respaldar
ORIGENES = {
    "manual": "Manual",
    "automatico": "Automático",
    "seguridad": "Previo a restaurar",
}


def _carpeta():
    return respaldar.opciones_por_defecto()["destino"]


def _buscar(nombre):
    for _, ruta in respaldos.listar(_carpeta()):
        if ruta.name == nombre:
            return ruta
    raise Http404

def _fecha(texto):
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None

def _token_valido(request):
    esperado = config("BACKUP_TOKEN", default="")
    if not esperado:
        return False
    enviado = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    return hmac.compare_digest(enviado, esperado)

@superadmin_required
def lista_respaldos(request):
    opciones = respaldar.opciones_por_defecto()
    q = request.GET.get("q", "").strip()
    desde = _fecha(request.GET.get("desde"))
    hasta = _fecha(request.GET.get("hasta"))
    if not desde:
        hasta = None
    if desde and hasta and desde > hasta:
        desde, hasta = hasta, desde
    fin = hasta or desde

    origen_sel = request.GET.get("origen", "")
    if origen_sel not in ORIGENES:
        origen_sel = ""

    ordenes = {
        "nuevos": (lambda i: i["fecha"], True),
        "antiguos": (lambda i: i["fecha"], False),
        "grandes": (lambda i: i["bytes"], True),
        "chicos": (lambda i: i["bytes"], False),
    }
    orden = request.GET.get("orden", "nuevos")
    if orden not in ordenes:
        orden = "nuevos"

    todos = respaldos.listar(opciones["destino"])
    items = []
    for fecha, ruta in todos:
        if desde and not (desde <= fecha.date() <= fin):
            continue
        if q and q.lower() not in ruta.name.lower():
            continue
        origen = respaldos.leer_origen(ruta)
        if origen_sel and origen != origen_sel:
            continue
        tamano = ruta.stat().st_size
        items.append({
            "nombre": ruta.name,
            "fecha": fecha,
            "bytes": tamano,
            "mb": round(tamano / 1024 / 1024, 2),
            "origen": origen,
            "origen_texto": ORIGENES.get(origen, "Sin origen"),
        })

    clave, inverso = ordenes[orden]
    items.sort(key=clave, reverse=inverso)

    panel_activo = bool(origen_sel or desde or orden != "nuevos")
    return render(request, "tickets/respaldos.html", {
        "respaldos": items,
        "total": len(todos),
        "carpeta": opciones["destino"],
        "copia": opciones["copia"],
        "diarios": opciones["diarios"],
        "semanales": opciones["semanales"],
        "mensuales": opciones["mensuales"],
        "hora": config("BACKUP_HORA", default="02:00"),
        "automatico": config("BACKUP_ACTIVO", default=True, cast=bool),
        "q": q,
        "desde": desde.isoformat() if desde else "",
        "hasta": hasta.isoformat() if hasta else "",
        "origen_sel": origen_sel,
        "orden": orden,
        "panel_activo": panel_activo,
        "hay_filtros": bool(q or panel_activo),
    })

@superadmin_required
@require_POST
def crear_respaldo(request):
    try:
        avisos = respaldar.ejecutar(**respaldar.opciones_por_defecto(), log=lambda mensaje: None)
    except respaldos.ErrorRespaldo as error:
        messages.error(request, f"No se pudo crear el respaldo: {error}")
        return redirect("lista_respaldos")
    messages.success(request, "Respaldo creado correctamente.")
    for aviso in avisos:
        messages.warning(request, aviso)
    return redirect("lista_respaldos")

@superadmin_required
@require_POST
def subir_respaldo(request):
    archivo = request.FILES.get("archivo")
    if not archivo:
        messages.error(request, "Elige un archivo .zip de respaldo.")
        return redirect("lista_respaldos")
    limite_mb = config("BACKUP_MAX_SUBIDA_MB", default=2048, cast=int)
    try:
        final, manifiesto = respaldos.guardar_subido(
            archivo, _carpeta(), max_bytes=limite_mb * 1024 * 1024
        )
    except respaldos.ErrorRespaldo as error:
        messages.error(request, f"No se pudo subir el respaldo: {error}")
        return redirect("lista_respaldos")
    messages.success(
        request,
        f"Respaldo {final.name} subido y verificado. Ya puedes restaurarlo desde la lista.",
    )
    return redirect("lista_respaldos")


@superadmin_required
@require_POST
def restaurar_respaldo(request, nombre):
    if request.POST.get("confirmacion", "").strip() != "RESTAURAR":
        messages.error(request, "Para restaurar tienes que escribir RESTAURAR en la confirmación.")
        return redirect("lista_respaldos")

    ruta = _buscar(nombre)
    opciones = respaldar.opciones_por_defecto()
    bd = settings.DATABASES["default"]
    actor_nombre = request.user.nombre
    seguridad = None

    try:
        respaldos.validar_zip(ruta)
        with respaldos.bloqueo_restauracion(opciones["destino"]):
            seguridad = respaldos.crear_respaldo(
                bd, settings.MEDIA_ROOT, opciones["destino"],
                pg_bin=opciones["pg_bin"], log=lambda mensaje: None,
                origen="seguridad",
            )
            respaldos.restaurar(
                ruta, bd, settings.MEDIA_ROOT,
                pg_bin=opciones["pg_bin"], log=lambda mensaje: None,
            )
    except respaldos.ErrorRespaldo as error:
        messages.error(request, f"No se pudo restaurar: {error}")
        if seguridad:
            messages.warning(
                request,
                f"El estado anterior quedó guardado en {seguridad.name}. Revisa el sistema antes de reintentar.",
            )
        return redirect("lista_respaldos")

    connections.close_all()
    avisos = []
    try:
        call_command("migrate", interactive=False, verbosity=0)
    except Exception as error:
        avisos.append(
            f"La base se restauró, pero no se pudieron aplicar migraciones pendientes: {error}. "
            "Corre 'python manage.py migrate' en el servidor."
        )
    try:
        Evento.objects.create(
            tipo=Evento.Tipo.CONFIG_CAMBIADA,
            actor=None,
            actor_nombre=actor_nombre,
            detalle=f"Se restauró el respaldo {ruta.name}. Estado previo guardado en {seguridad.name}.",
        )
    except Exception:
        pass

    messages.success(
        request,
        f"Respaldo {ruta.name} restaurado. Inicia sesión de nuevo con un usuario de ese respaldo. "
        f"El estado anterior quedó en {seguridad.name}.",
    )
    for aviso in avisos:
        messages.warning(request, aviso)
    return redirect("login")

@superadmin_required
def descargar_respaldo(request, nombre):
    ruta = _buscar(nombre)
    return FileResponse(open(ruta, "rb"), as_attachment=True, filename=ruta.name)


@require_GET
def api_lista(request):
    if not _token_valido(request):
        raise Http404
    items = [
        {"nombre": ruta.name, "bytes": ruta.stat().st_size, "fecha": fecha.isoformat()}
        for fecha, ruta in respaldos.listar(_carpeta())
    ]
    return JsonResponse({"respaldos": items})


@require_GET
def api_descargar(request, nombre):
    if not _token_valido(request):
        raise Http404
    ruta = _buscar(nombre)
    return FileResponse(open(ruta, "rb"), as_attachment=True, filename=ruta.name)