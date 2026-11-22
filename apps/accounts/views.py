import hashlib

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from django.contrib.auth.decorators import login_required

from datetime import timedelta

from django.utils import timezone
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.actividad.models import Evento
from apps.actividad.registro import registrar as registrar_evento
from apps.tickets import emails as correos
from apps.tickets.models import ConfiguracionSistema, CorreoPendiente, Notificacion, Ticket
from apps.tickets.views import _tickets_visibles

from . import correos_password
from .contenido_ayuda import ayuda_para
from .decorators import admin_required
from .utilidades import entero_positivo
from .forms import (
    CambiarPasswordForm,
    FotoPerfilForm,
    PreferenciasForm,
    UsuarioCrearForm,
    UsuarioEditarForm,
)
from .models import FotoPerfil, PreferenciasUsuario, Usuario
from .permisos import (
    puede_cambiar_password,
    usuarios_gestionables as _usuarios_gestionables,
    usuarios_visibles,
)
from apps.catalog.models import Area, Puesto, Sucursal

LOGIN_MAX_INTENTOS = 5
LOGIN_BLOQUEO_SEGUNDOS = 15 * 60
USUARIOS_POR_PAGINA = 20
OLVIDE_ESPERA_SEGUNDOS = 10 * 60
OLVIDE_MAX_POR_IP = 10

def _clave_login(request, correo):
    huella = hashlib.sha256(
        f"{request.META.get('REMOTE_ADDR', '')}|{correo.lower()}".encode()
    ).hexdigest()
    return f"login-fallos:{huella}"


def login_view(request):
    if request.user.is_authenticated:
        return redirect(PreferenciasUsuario.de(request.user).url_inicio)

    siguiente = request.POST.get("next") or request.GET.get("next") or ""
    contexto = {"next": siguiente}

    if request.method == "POST":
        correo = request.POST.get("correo", "").strip()
        clave = _clave_login(request, correo)
        if cache.get(clave, 0) >= LOGIN_MAX_INTENTOS:
            contexto["error"] = (
                "Demasiados intentos fallidos. Espera 15 minutos e inténtalo de nuevo."
            )
            return render(request, "accounts/login.html", contexto, status=429)
        user = authenticate(
            request,
            username=correo,
            password=request.POST.get("password", ""),
        )
        if user is not None:
            cache.delete(clave)
            login(request, user)
            destino_seguro = url_has_allowed_host_and_scheme(
                siguiente, allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            )
            if siguiente and destino_seguro:
                return redirect(siguiente)
            return redirect(PreferenciasUsuario.de(request.user).url_inicio)
        cache.set(clave, cache.get(clave, 0) + 1, LOGIN_BLOQUEO_SEGUNDOS)
        contexto["error"] = "Correo o contraseña incorrectos."

    return render(request, "accounts/login.html", contexto)

def olvide_password(request):
    if request.user.is_authenticated:
        return redirect(PreferenciasUsuario.de(request.user).url_inicio)

    if request.method == "POST":
        clave_ip = f"olvide-ip:{request.META.get('REMOTE_ADDR', '')}"
        if cache.get(clave_ip, 0) >= OLVIDE_MAX_POR_IP:
            return render(
                request,
                "accounts/olvide_password.html",
                {"error": "Demasiadas solicitudes. Inténtalo más tarde."},
                status=429,
            )
        cache.set(clave_ip, cache.get(clave_ip, 0) + 1, OLVIDE_ESPERA_SEGUNDOS)

        correo = request.POST.get("correo", "").strip()
        tipo = "recordar" if request.POST.get("tipo") == "recordar" else "cambio"
        huella = hashlib.sha256(correo.lower().encode()).hexdigest()
        usuario = Usuario.objects.filter(correo__iexact=correo, activo=True).first()
        roles_permitidos = {
            Usuario.Rol.USUARIO,
            Usuario.Rol.BECARIO,
            Usuario.Rol.ENCARGADO,
        }
        if (
            usuario is not None
            and usuario.rol in roles_permitidos
            and not usuario.is_superuser
            and cache.add(f"olvide-correo:{huella}", 1, OLVIDE_ESPERA_SEGUNDOS)
        ):
            correos_password.correo_solicitud(usuario, tipo)
            registrar_evento(
                Evento.Tipo.PASSWORD_SOLICITADO,
                usuario,
                afectado=usuario,
                detalle=(
                    "Solicitó que se le cambie la contraseña."
                    if tipo == "cambio"
                    else "Solicitó que se le recuerde la contraseña."
                ),
            )
        messages.success(
            request,
            "Si el correo está registrado, se avisó a los administradores. Te contactarán pronto.",
        )
        return redirect("login")

    return render(request, "accounts/olvide_password.html")

@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")

@admin_required
def lista_usuarios(request):
    q = request.GET.get("q", "").strip()
    rol = request.GET.get("rol", "")
    estado = request.GET.get("estado", "")
    area = request.GET.get("area", "")
    puesto = request.GET.get("puesto", "")
    sucursal = request.GET.get("sucursal", "")
    desde = request.GET.get("desde", "")
    hasta = request.GET.get("hasta", "")

    usuarios = (
        usuarios_visibles(request.user)
        .select_related("sucursal", "area", "puesto")
        .annotate(
            foto_actualizada=Subquery(
                FotoPerfil.objects.filter(usuario=OuterRef("pk")).values("actualizada_en")[:1]
            )
        )
    )

    if q:
        usuarios = usuarios.filter(
            Q(nombre__icontains=q)
            | Q(correo__icontains=q)
            | Q(sucursal__nombre__icontains=q)
            | Q(area__nombre__icontains=q)
            | Q(puesto__nombre__icontains=q)
        )

    if rol in {valor for valor, _ in Usuario.Rol.choices}:
        usuarios = usuarios.filter(rol=rol)
    else:
        rol = ""

    if estado == "activo":
        usuarios = usuarios.filter(activo=True)
    elif estado == "inactivo":
        usuarios = usuarios.filter(activo=False)
    else:
        estado = ""

    area_id = entero_positivo(area)
    if area_id is not None:
        usuarios = usuarios.filter(area_id=area_id)
    else:
        area = ""

    puesto_id = entero_positivo(puesto)
    if puesto_id is not None:
        usuarios = usuarios.filter(puesto_id=puesto_id)
    else:
        puesto = ""

    sucursal_id = entero_positivo(sucursal) if request.user.es_superadmin else None
    if sucursal_id is not None:
        usuarios = usuarios.filter(sucursal_id=sucursal_id)
    else:
        sucursal = ""

    fecha_desde = parse_date(desde) if desde else None
    fecha_hasta = parse_date(hasta) if hasta else None

    if fecha_desde and fecha_hasta:
        if fecha_desde > fecha_hasta:
            fecha_desde, fecha_hasta = fecha_hasta, fecha_desde
        usuarios = usuarios.filter(creado_en__date__range=(fecha_desde, fecha_hasta))
    elif fecha_desde:
        usuarios = usuarios.filter(creado_en__date=fecha_desde)
        hasta = ""
    else:
        desde = ""
        hasta = ""

    pagina = Paginator(usuarios, USUARIOS_POR_PAGINA).get_page(request.GET.get("page"))
    pagina.object_list = list(pagina.object_list)
    ids_gestionables = set(
        _usuarios_gestionables(request.user)
        .filter(pk__in=[u.pk for u in pagina.object_list])
        .values_list("pk", flat=True)
    )
    for u in pagina.object_list:
        u.puede_gestionar = u.pk in ids_gestionables
        u.password_mostrada = u.password_visible
    parametros = request.GET.copy()
    parametros.pop("page", None)

    return render(request, "accounts/usuarios.html", {
        "page_obj": pagina,
        "querystring": parametros.urlencode(),
        "q": q,
        "rol_sel": rol,
        "estado_sel": estado,
        "area_sel": area,
        "puesto_sel": puesto,
        "sucursal_sel": sucursal,
        "desde": desde,
        "hasta": hasta,
        "roles": Usuario.Rol.choices,
        "areas": Area.objects.visibles_para(request.user),
        "puestos": Puesto.objects.visibles_para(request.user),
        "sucursales": Sucursal.objects.all(),
    })


@admin_required
def nuevo_usuario(request):
    if request.method == "POST":
        form = UsuarioCrearForm(request.POST, solicitante=request.user)
        if form.is_valid():
            usuario = form.save()
            registrar_evento(
                Evento.Tipo.USUARIO_CREADO,
                request.user,
                afectado=usuario,
                detalle=f"Cuenta creada con rol {usuario.get_rol_display()}.",
            )
            messages.success(request, f"Usuario «{usuario.nombre}» creado.")
            return redirect("lista_usuarios")
    else:
        form = UsuarioCrearForm(solicitante=request.user)
    return render(request, "accounts/usuario_form.html", {"form": form, "titulo": "Nuevo usuario"})


@admin_required
def editar_usuario(request, pk):
    usuario = get_object_or_404(_usuarios_gestionables(request.user), pk=pk)
    es_el_mismo = usuario.pk == request.user.pk
    rol_anterior = usuario.rol
    puede_password = puede_cambiar_password(request.user, usuario)
    ver_password = es_el_mismo or puede_password

    if request.method == "POST":
        form = UsuarioEditarForm(
            request.POST, instance=usuario,
            editando_a_si_mismo=es_el_mismo, solicitante=request.user,
        )
        if form.is_valid():
            usuario = form.save()
            nueva = form.nueva_password
            if nueva:
                usuario.asignar_password(nueva)
                usuario.save(update_fields=["password", "password_cifrada"])
                registrar_evento(
                    Evento.Tipo.PASSWORD_CAMBIADO,
                    request.user,
                    afectado=usuario,
                    detalle=f"{request.user.nombre} cambió la contraseña de {usuario.nombre}.",
                )
                correos_password.correo_cambio(usuario, request.user)
                messages.success(request, f"Usuario «{usuario.nombre}» actualizado. Se cambió su contraseña.")
            else:
                messages.success(request, f"Usuario «{usuario.nombre}» actualizado.")
            if usuario.rol != rol_anterior:
                registrar_evento(
                    Evento.Tipo.ROL_CAMBIADO,
                    request.user,
                    afectado=usuario,
                    detalle=(
                        f"Rol cambiado de «{Usuario.Rol(rol_anterior).label}» "
                        f"a «{usuario.get_rol_display()}»."
                    ),
                )
            return redirect("lista_usuarios")
    else:
        form = UsuarioEditarForm(
            instance=usuario, editando_a_si_mismo=es_el_mismo, solicitante=request.user,
        )
    return render(request, "accounts/usuario_form.html", {
        "form": form, "titulo": f"Editar usuario — {usuario.nombre}",
        "es_el_mismo": es_el_mismo,
        "sin_permiso_password": not es_el_mismo and not puede_password,
        "mostrar_password": ver_password,
        "password_actual": usuario.password_visible if ver_password else "",
    })


@admin_required
@require_POST
def cambiar_estado_usuario(request, pk):
    usuario = get_object_or_404(_usuarios_gestionables(request.user), pk=pk)
    if usuario.pk == request.user.pk:
        messages.error(request, "No puedes desactivar tu propia cuenta.")
    elif not usuario.activo and usuario.sucursal_id is None and not usuario.es_superadmin:
        messages.error(
            request,
            "Este usuario no tiene sucursal. Edítalo y asígnale una antes de activarlo.",
        )
    elif not usuario.activo and usuario.sucursal_id and not usuario.sucursal.activa:
        messages.error(
            request,
            "La sucursal de este usuario está desactivada. Actívala antes de activar al usuario.",
        )
    else:
        usuario.activo = not usuario.activo
        usuario.save(update_fields=["activo"])
        estado = "activado" if usuario.activo else "desactivado"
        registrar_evento(
            Evento.Tipo.USUARIO_ESTADO,
            request.user,
            afectado=usuario,
            detalle=f"Cuenta {estado}.",
        )
        messages.success(request, f"Usuario «{usuario.nombre}» {estado}.")
    return redirect("lista_usuarios")

@admin_required
@require_POST
def enviar_correo_password(request, pk):
    usuario = get_object_or_404(_usuarios_gestionables(request.user), pk=pk)
    if not puede_cambiar_password(request.user, usuario):
        messages.error(request, "No tienes permiso para enviar la contraseña de este usuario.")
        return redirect("lista_usuarios")

    if not usuario.password_visible:
        messages.error(
            request,
            "Este usuario no tiene una contraseña disponible. Asígnale una nueva primero.",
        )
        return redirect("editar_usuario", pk=usuario.pk)
    enviado = correos_password.correo_recordatorio(usuario, request.user)
    detalle = f"{request.user.nombre} envió por correo la contraseña a {usuario.nombre}."

    if not enviado:
        messages.error(request, "No se pudo enviar el correo.")
        return redirect("editar_usuario", pk=usuario.pk)

    registrar_evento(
        Evento.Tipo.PASSWORD_ENVIADO,
        request.user,
        afectado=usuario,
        detalle=detalle,
    )
    messages.success(request, f"Correo enviado a {usuario.correo}.")
    return redirect("editar_usuario", pk=usuario.pk)

@login_required
def mi_perfil(request):
    if request.method == "POST":
        if request.POST.get("accion") == "eliminar":
            foto = FotoPerfil.objects.filter(usuario=request.user).first()
            if foto:
                foto.archivo.delete(save=False)
                foto.delete()
            messages.success(request, "Foto de perfil eliminada.")
            return redirect("mi_perfil")
        form = FotoPerfilForm(request.POST, request.FILES)
        if form.is_valid():
            foto, _ = FotoPerfil.objects.get_or_create(usuario=request.user)
            if foto.archivo:
                foto.archivo.delete(save=False)
            foto.archivo.save(
                "foto.jpg", ContentFile(form.cleaned_data["foto"]), save=False
            )
            foto.save()
            messages.success(request, "Foto de perfil actualizada.")
            return redirect("mi_perfil")
    else:
        form = FotoPerfilForm()
    logos_sucursales = []
    if request.user.es_superadmin:
        logos_sucursales = list(
            Sucursal.objects.filter(
                activa=True, logo_actualizado_en__isnull=False
            )
        )
    return render(request, "accounts/perfil.html", {
        "form": form,
        "logos_sucursales": logos_sucursales,
    })

@login_required
def ajustes(request):
    preferencias = PreferenciasUsuario.de(request.user)
    if request.method == "POST":
        if request.POST.get("accion") == "restablecer":
            PreferenciasUsuario.objects.filter(usuario=request.user).delete()
            messages.success(request, "Ajustes restablecidos a los valores originales.")
            return redirect("ajustes")
        form = PreferenciasForm(request.POST, instance=preferencias)
        if form.is_valid():
            guardada = form.save(commit=False)
            guardada.usuario = request.user
            guardada.save()
            messages.success(request, "Ajustes guardados.")
            return redirect("ajustes")
    else:
        form = PreferenciasForm(instance=preferencias)
    return render(request, "accounts/ajustes.html", {"form": form})

@login_required
def ayuda(request):
    return render(request, "accounts/ayuda.html", ayuda_para(request.user))

@login_required
def inicio(request):
    return redirect(PreferenciasUsuario.de(request.user).url_inicio)

def _inicio_encargado(usuario, ahora):
    estado = Ticket.Estado
    vivos = [estado.ABIERTO, estado.EN_PROCESO, estado.EN_ESPERA]
    abiertos = vivos + [estado.POR_CONFIRMAR]
    equipo = (
        Usuario.objects.filter(
            activo=True,
            sucursal_id=usuario.sucursal_id,
            rol__in=[Usuario.Rol.BECARIO, Usuario.Rol.ENCARGADO],
        )
        .annotate(
            activos=Count(
                "tickets_asignados",
                filter=Q(tickets_asignados__estado__in=abiertos),
            ),
            vencidos=Count(
                "tickets_asignados",
                filter=Q(
                    tickets_asignados__estado__in=vivos,
                    tickets_asignados__sla_vence_en__lt=ahora,
                ),
            ),
        )
        .order_by("-activos", "nombre")
    )
    return {
        "equipo": equipo,
        "actividad": Evento.objects.filter(sucursal_id=usuario.sucursal_id)[:6],
    }


def _inicio_superadmin(ahora):
    estado = Ticket.Estado
    vivos = [estado.ABIERTO, estado.EN_PROCESO, estado.EN_ESPERA]
    abiertos = vivos + [estado.POR_CONFIRMAR]
    por_sucursal = (
        Sucursal.objects.filter(activa=True)
        .annotate(
            activos=Count("tickets", filter=Q(tickets__estado__in=abiertos)),
            sin_asignar=Count(
                "tickets",
                filter=Q(
                    tickets__estado=estado.ABIERTO,
                    tickets__asignado_a__isnull=True,
                ),
            ),
            vencidos=Count(
                "tickets",
                filter=Q(
                    tickets__estado__in=vivos,
                    tickets__sla_vence_en__lt=ahora,
                ),
            ),
        )
        .order_by("-vencidos", "-sin_asignar", "nombre")
    )
    personas = Usuario.objects.filter(activo=True).aggregate(
        total=Count("id"),
        encargados=Count("id", filter=Q(rol=Usuario.Rol.ENCARGADO)),
        becarios=Count("id", filter=Q(rol=Usuario.Rol.BECARIO)),
        usuarios=Count("id", filter=Q(rol=Usuario.Rol.USUARIO)),
    )
    correos = CorreoPendiente.objects.aggregate(
        pendientes=Count("id", filter=Q(estado=CorreoPendiente.Estado.PENDIENTE)),
        errores=Count("id", filter=Q(estado=CorreoPendiente.Estado.ERROR)),
    )
    return {
        "por_sucursal": por_sucursal,
        "personas": personas,
        "correos": correos,
        "sistema": ConfiguracionSistema.actual(),
        "actividad": Evento.objects.select_related("sucursal")[:6],
    }

@login_required
def panel_inicio(request):
    usuario = request.user
    ahora = timezone.now()
    estado = Ticket.Estado
    tickets = _tickets_visibles(usuario)
    sin_cerrar = ~Q(estado=estado.CERRADO)
    vivos = [estado.ABIERTO, estado.EN_PROCESO, estado.EN_ESPERA]
    local = timezone.localtime(ahora)
    inicio_dia = local.replace(hour=0, minute=0, second=0, microsecond=0)
    inicio_mes = inicio_dia.replace(day=1)

    conteos = tickets.aggregate(
        activos=Count("id", filter=sin_cerrar),
        abiertos=Count("id", filter=Q(estado=estado.ABIERTO)),
        en_proceso=Count("id", filter=Q(estado=estado.EN_PROCESO)),
        por_confirmar=Count("id", filter=Q(estado=estado.POR_CONFIRMAR)),
        sin_asignar=Count(
            "id", filter=Q(estado=estado.ABIERTO, asignado_a__isnull=True)
        ),
        mios=Count("id", filter=sin_cerrar & Q(asignado_a=usuario)),
        vencidos=Count(
            "id", filter=Q(estado__in=vivos, sla_vence_en__lt=ahora)
        ),
        por_vencer=Count(
            "id",
            filter=Q(
                estado__in=vivos,
                sla_vence_en__gte=ahora,
                sla_vence_en__lte=ahora + timedelta(hours=4),
            ),
        ),
        sin_prioridad=Count("id", filter=Q(estado__in=vivos, prioridad="")),
        creados_hoy=Count("id", filter=Q(creado_en__gte=inicio_dia)),
        resueltos_mes=Count("id", filter=Q(resuelto_en__gte=inicio_mes)),
    )

    if usuario.es_superadmin:
        vista = "superadmin"
    elif usuario.es_encargado:
        vista = "encargado"
    elif usuario.es_becario:
        vista = "becario"
    else:
        vista = "usuario"

    if local.hour < 12:
        saludo = "Buenos días"
    elif local.hour < 19:
        saludo = "Buenas tardes"
    else:
        saludo = "Buenas noches"

    contexto = {
        "vista": vista,
        "saludo": saludo,
        "conteos": conteos,
        "pendientes": usuario.notificaciones.filter(leida=False).order_by("-creada_en")[:5],
        "sla": [
            (Ticket.Prioridad(clave).label, horas)
            for clave, horas in settings.SLA_HORAS.items()
        ],
        "reabrir_dias": settings.REABRIR_TICKET_DIAS,
    }

    if vista == "encargado":
        contexto.update(_inicio_encargado(usuario, ahora))
    elif vista == "superadmin":
        contexto.update(_inicio_superadmin(ahora))

    return render(request, "accounts/inicio.html", contexto)

@login_required
def foto_usuario(request, pk):
    foto = get_object_or_404(FotoPerfil, usuario_id=pk)
    if not foto.archivo:
        raise Http404
    try:
        respuesta = FileResponse(foto.archivo.open("rb"), content_type="image/jpeg")
    except FileNotFoundError:
        raise Http404
    respuesta["X-Content-Type-Options"] = "nosniff"
    respuesta["Cache-Control"] = "private, max-age=3600"
    return respuesta

@login_required
def cambiar_password(request):
    if not request.user.es_maestro:
        messages.info(
            request,
            "Tu contraseña la cambia soporte.",
        )
        return redirect("mi_perfil")
    if request.method == "POST":
        form = CambiarPasswordForm(request.user, request.POST)
        if form.is_valid():
            usuario = form.save(commit=False)
            usuario.asignar_password(form.cleaned_data["new_password1"])
            usuario.debe_cambiar_password = False
            usuario.save(update_fields=[
                "password", "password_cifrada", "debe_cambiar_password",
            ])
            update_session_auth_hash(request, usuario)
            registrar_evento(
                Evento.Tipo.PASSWORD_PROPIO,
                usuario,
                afectado=usuario,
                detalle="Cambió su propia contraseña.",
            )
            messages.success(request, "Contraseña actualizada.")
            return redirect("mi_perfil")
    else:
        form = CambiarPasswordForm(request.user)
    return render(request, "accounts/cambiar_password.html", {"form": form})