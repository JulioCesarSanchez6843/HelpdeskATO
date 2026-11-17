from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, Count, F, IntegerField, Prefetch, Q, Value, When
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST
from django.contrib.auth import login

from apps.accounts.decorators import admin_required, personal_required
from apps.accounts.models import Usuario
from apps.accounts.utilidades import entero_positivo, foto_de
from apps.catalog.models import Area, Categoria, Sucursal

from . import acceso, services
from .forms import (
    AdjuntosComentarioForm,
    AsignarTicketForm,
    EscalarTicketForm,
    TicketForm,
    TicketGestionForm,
)
from .imagenes import ImagenInvalida
from .models import AdjuntoTicket, EncuestaSatisfaccion, Historial, Ticket


ESTADOS_VALIDOS = {valor for valor, _ in Ticket.Estado.choices}
PRIORIDADES_VALIDAS = {valor for valor, _ in Ticket.Prioridad.choices}

TICKETS_POR_PAGINA = 15

LIMITE_COLUMNA_KANBAN = 20

ESTADOS_EN_COLA = (
    Ticket.Estado.ABIERTO,
    Ticket.Estado.EN_PROCESO,
    Ticket.Estado.EN_ESPERA,
)

ORDENES_COLA = (
    ("sla", "SLA: por vencer primero"),
    ("prioridad", "Prioridad: más alta primero"),
    ("recientes", "Más recientes"),
)
ORDENES_VALIDOS = {valor for valor, _ in ORDENES_COLA}

CLASES_ESTADO_KANBAN = {
    Ticket.Estado.ABIERTO: "stat-abiertos",
    Ticket.Estado.EN_PROCESO: "stat-proceso",
    Ticket.Estado.EN_ESPERA: "stat-total",
    Ticket.Estado.POR_CONFIRMAR: "stat-confirmar",
    Ticket.Estado.CERRADO: "stat-cerrados",
}


def _tickets_visibles(usuario):
    tickets = Ticket.objects.select_related(
        "area", "categoria", "creado_por", "sucursal", "asignado_a", "resuelto_por"
    )

    if usuario.es_superadmin:
        return tickets

    if usuario.es_encargado or usuario.es_becario:
        return tickets.filter(sucursal_id=usuario.sucursal_id)

    return tickets.filter(creado_por=usuario)

def _ordenar_cola(tickets, orden):
    if orden == "recientes":
        return tickets.order_by("-creado_en", "-id")

    rango_prioridad = Case(
        When(prioridad=Ticket.Prioridad.CRITICA, then=Value(0)),
        When(prioridad=Ticket.Prioridad.ALTA, then=Value(1)),
        When(prioridad=Ticket.Prioridad.MEDIA, then=Value(2)),
        When(prioridad=Ticket.Prioridad.BAJA, then=Value(3)),
        default=Value(4),
        output_field=IntegerField(),
    )
    grupo_cola = Case(
        When(estado__in=ESTADOS_EN_COLA, then=Value(0)),
        default=Value(1),
        output_field=IntegerField(),
    )
    tickets = tickets.annotate(
        grupo_cola=grupo_cola,
        rango_prioridad=rango_prioridad,
    )
    sla = F("sla_vence_en").asc(nulls_last=True)

    if orden == "prioridad":
        return tickets.order_by("grupo_cola", "rango_prioridad", sla, "creado_en", "id")

    return tickets.order_by("grupo_cola", sla, "rango_prioridad", "creado_en", "id")

@login_required
def lista_tickets(request):
    es_personal = request.user.es_personal
    base = _tickets_visibles(request.user)

    conteos = base.aggregate(
        total=Count("id"),
        abiertos=Count("id", filter=Q(estado=Ticket.Estado.ABIERTO)),
        en_proceso=Count("id", filter=Q(estado=Ticket.Estado.EN_PROCESO)),
        en_espera=Count("id", filter=Q(estado=Ticket.Estado.EN_ESPERA)),
        por_confirmar=Count("id", filter=Q(estado=Ticket.Estado.POR_CONFIRMAR)),
        cerrados=Count("id", filter=Q(estado=Ticket.Estado.CERRADO)),
    )
    conteos["activos"] = (
        conteos["abiertos"]
        + conteos["en_proceso"]
        + conteos["en_espera"]
        + conteos["por_confirmar"]
    )

    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "")
    area = request.GET.get("area", "")
    categoria = request.GET.get("categoria", "")
    prioridad = request.GET.get("prioridad", "")
    asignado = request.GET.get("asignado", "")
    sucursal = request.GET.get("sucursal", "")
    desde = request.GET.get("desde", "")
    hasta = request.GET.get("hasta", "")

    tickets = base.annotate(
        creado_por_foto=foto_de("creado_por_id"),
        asignado_a_foto=foto_de("asignado_a_id"),
    )

    if q:
        filtro = (
            Q(titulo__icontains=q)
            | Q(area__nombre__icontains=q)
            | Q(categoria__nombre__icontains=q)
        )

        if q.lstrip("#").isdigit():
            filtro |= Q(pk=int(q.lstrip("#")))

        if es_personal:
            filtro |= (
                Q(creado_por__nombre__icontains=q)
                | Q(sucursal__nombre__icontains=q)
                | Q(asignado_a__nombre__icontains=q)
            )

        tickets = tickets.filter(filtro)

    if estado in ESTADOS_VALIDOS:
        tickets = tickets.filter(estado=estado)
    else:
        estado = ""

    if es_personal and prioridad == "sin":
        tickets = tickets.filter(prioridad="")
    elif es_personal and prioridad in PRIORIDADES_VALIDAS:
        tickets = tickets.filter(prioridad=prioridad)
    else:
        prioridad = ""

    asignado_id = entero_positivo(asignado) if es_personal else None
    if es_personal and asignado == "sin":
        tickets = tickets.filter(asignado_a__isnull=True)
    elif asignado_id is not None:
        tickets = tickets.filter(asignado_a_id=asignado_id)
    else:
        asignado = ""

    area_id = entero_positivo(area) if es_personal else None
    if area_id is not None:
        tickets = tickets.filter(area_id=area_id)
    else:
        area = ""

    categoria_id = entero_positivo(categoria) if es_personal else None
    if categoria_id is not None:
        tickets = tickets.filter(categoria_id=categoria_id)
    else:
        categoria = ""

    sucursal_id = entero_positivo(sucursal) if request.user.es_superadmin else None
    if sucursal_id is not None:
        tickets = tickets.filter(sucursal_id=sucursal_id)
    else:
        sucursal = ""

    fecha_desde = parse_date(desde) if desde else None
    fecha_hasta = parse_date(hasta) if hasta else None

    if fecha_desde and fecha_hasta:
        if fecha_desde > fecha_hasta:
            fecha_desde, fecha_hasta = fecha_hasta, fecha_desde
        tickets = tickets.filter(creado_en__date__range=(fecha_desde, fecha_hasta))
    elif fecha_desde:
        tickets = tickets.filter(creado_en__date=fecha_desde)
        hasta = ""
    else:
        desde = ""
        hasta = ""

    orden = request.GET.get("orden", "")
    if orden not in ORDENES_VALIDOS:
        orden = "sla"

    if es_personal:
        tickets = _ordenar_cola(tickets, orden)

    pagina = Paginator(tickets, TICKETS_POR_PAGINA).get_page(request.GET.get("page"))

    parametros = request.GET.copy()
    parametros.pop("page", None)

    contexto = {
        "page_obj": pagina,
        "conteos": conteos,
        "q": q,
        "estado_sel": estado,
        "area_sel": area,
        "categoria_sel": categoria,
        "sucursal_sel": sucursal,
        "desde": desde,
        "hasta": hasta,
        "estados": Ticket.Estado.choices,
        "prioridad_sel": prioridad,
        "asignado_sel": asignado,
        "prioridades": Ticket.Prioridad.choices,
        "querystring": parametros.urlencode(),
        "orden_sel": orden,
        "ordenes": ORDENES_COLA,
    }

    if es_personal:
        contexto["areas"] = Area.objects.visibles_para(request.user)
        contexto["categorias"] = Categoria.objects.visibles_para(request.user)
        contexto["sucursales"] = Sucursal.objects.all()
        contexto["asignados"] = Usuario.objects.filter(
            Q(pk__in=base.filter(asignado_a__isnull=False).values("asignado_a_id"))
            | Q(pk=request.user.pk)
        ).order_by("nombre")
        contexto["mis_activos"] = (
            base.filter(asignado_a=request.user)
            .exclude(estado=Ticket.Estado.CERRADO)
            .count()
        )
        plantilla = "tickets/panel_admin.html"
    else:
        plantilla = "tickets/mis_tickets.html"

    return render(request, plantilla, contexto)


@personal_required
def mis_asignados(request):
    propios = _tickets_visibles(request.user).filter(asignado_a=request.user)

    conteos = {
        fila["estado"]: fila["total"]
        for fila in propios.values("estado").annotate(total=Count("id")).order_by()
    }

    con_foto = propios.annotate(creado_por_foto=foto_de("creado_por_id"))

    columnas = []
    for valor, etiqueta in Ticket.Estado.choices:
        if valor == Ticket.Estado.CERRADO:
            orden = ("-cerrado_en", "-id")
        else:
            orden = (F("sla_vence_en").asc(nulls_last=True), "creado_en")

        tickets = list(
            con_foto.filter(estado=valor).order_by(*orden)[:LIMITE_COLUMNA_KANBAN]
        )
        total = conteos.get(valor, 0)
        columnas.append(
            {
                "valor": valor,
                "etiqueta": etiqueta,
                "clase": CLASES_ESTADO_KANBAN[valor],
                "total": total,
                "tickets": tickets,
                "hay_mas": total > len(tickets),
            }
        )

    mis_activos = sum(
        total for valor, total in conteos.items() if valor != Ticket.Estado.CERRADO
    )

    return render(
        request,
        "tickets/mis_asignados.html",
        {
            "columnas": columnas,
            "total": sum(conteos.values()),
            "mis_activos": mis_activos,
        },
    )


@login_required
def detalle_ticket(request, pk):
    ticket = get_object_or_404(
        _tickets_visibles(request.user).annotate(
            creado_por_foto=foto_de("creado_por_id"),
            asignado_a_foto=foto_de("asignado_a_id"),
            resuelto_por_foto=foto_de("resuelto_por_id"),
        ),
        pk=pk,
    )

    es_personal = request.user.es_personal

    form_gestion = (
        TicketGestionForm(instance=ticket, usuario=request.user)
        if es_personal
        else None
    )

    if request.method == "POST" and "guardar_gestion" in request.POST:
        if not es_personal:
            raise PermissionDenied

        guardado = False

        with transaction.atomic():
            instancia = Ticket.objects.select_for_update().get(pk=ticket.pk)
            antes = services.snapshot(instancia)
            form_gestion = TicketGestionForm(
                request.POST, instance=instancia, usuario=request.user
            )

            if form_gestion.is_valid():
                form_gestion.save()
                instancia.refresh_from_db()
                services.registrar_gestion(
                    instancia,
                    request.user,
                    antes,
                    form_gestion.cleaned_data.get("motivo_espera", ""),
                )
                guardado = True

        if guardado:
            if instancia.estado == Ticket.Estado.POR_CONFIRMAR:
                messages.success(
                    request,
                    "Ticket marcado como resuelto. Se le pidió al usuario "
                    "que confirme el cierre.",
                )
            else:
                messages.success(request, "Ticket actualizado.")

            return redirect("detalle_ticket", pk=pk)

    comentarios = (
        ticket.comentarios.select_related("autor")
        .annotate(autor_foto=foto_de("autor_id"))
        .prefetch_related(
            Prefetch("adjuntos", queryset=AdjuntoTicket.objects.defer("contenido"))
        )
    )
    if not es_personal:
        comentarios = comentarios.filter(interno=False)

    historial = ticket.historial.select_related("usuario").annotate(
        usuario_foto=foto_de("usuario_id")
    )
    if not es_personal:
        historial = historial.exclude(tipo=Historial.Tipo.ESCALADO)

    encuesta = EncuestaSatisfaccion.objects.filter(ticket=ticket).first()

    return render(
        request,
        "tickets/detalle_ticket.html",
        {
            "ticket": ticket,
            "encuesta": encuesta,
            "puede_calificar": (
                encuesta is None
                and ticket.estado == Ticket.Estado.CERRADO
                and ticket.creado_por_id == request.user.pk
            ),
            "comentarios": comentarios,
            "puede_comentar": ticket.estado != Ticket.Estado.CERRADO,
            "puede_reabrir": ticket.dentro_de_plazo_reapertura,
            "reabrible_hasta": ticket.reabrible_hasta,
            "historial": historial,
            "adjuntos": ticket.adjuntos.filter(comentario__isnull=True).defer(
                "contenido"
            ),
            "form_gestion": form_gestion,
            "puede_responder_cierre": (
                ticket.esperando_confirmacion
                and ticket.creado_por_id == request.user.pk
            ),
            "form_asignar": (
                AsignarTicketForm(ticket=ticket) if request.user.es_admin else None
            ),
            "form_escalar": (
                EscalarTicketForm(ticket=ticket, actor=request.user)
                if (
                    request.user.es_encargado
                    and not request.user.es_superadmin
                    and ticket.estado != Ticket.Estado.CERRADO
                )
                else None
            ),
            "puede_tomar": (
                es_personal
                and not request.user.es_superadmin
                and ticket.asignado_a_id is None
                and ticket.estado != Ticket.Estado.CERRADO
                and request.user.sucursal_id == ticket.sucursal_id
            ),
        },
    )


@login_required
@require_POST
def comentar_ticket(request, pk):
    ticket = get_object_or_404(_tickets_visibles(request.user), pk=pk)
    contenido = request.POST.get("contenido", "").strip()[:2000]
    interno = request.user.es_personal and request.POST.get("interno") == "on"

    formulario = AdjuntosComentarioForm(request.POST, request.FILES)

    if ticket.estado == Ticket.Estado.CERRADO:
        messages.error(request, "El ticket está cerrado y ya no admite mensajes.")
    elif len(contenido) < 2:
        messages.error(request, "Escribe un mensaje.")
    elif not formulario.is_valid():
        for errores in formulario.errors.values():
            for error in errores:
                messages.error(request, error)
    else:
        try:
            with transaction.atomic():
                services.agregar_comentario(
                    ticket,
                    request.user,
                    contenido,
                    interno,
                    formulario.cleaned_data["imagenes"],
                )
        except ImagenInvalida as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Mensaje enviado.")

    return redirect("detalle_ticket", pk=pk)


@login_required
def nuevo_ticket(request):
    if request.user.es_personal:
        messages.error(request, "Solo los usuarios pueden crear tickets.")
        return redirect("lista_tickets")

    if request.method == "POST":
        form = TicketForm(request.POST, request.FILES)

        if form.is_valid():
            try:
                with transaction.atomic():
                    ticket = form.save(commit=False)
                    ticket.creado_por = request.user
                    ticket.area = request.user.area
                    ticket.sucursal = request.user.sucursal
                    ticket.save()

                    services.guardar_adjuntos(
                        ticket,
                        form.cleaned_data["imagenes"],
                        request.user,
                    )
                    services.registrar_creacion(ticket, request.user)

            except ImagenInvalida as error:
                form.add_error("imagenes", str(error))

            else:
                messages.success(request, "Ticket creado correctamente.")
                return redirect("detalle_ticket", pk=ticket.pk)

    else:
        form = TicketForm()

    return render(request, "tickets/nuevo_ticket.html", {"form": form})


@login_required
def ver_adjunto(request, pk):
    adjuntos = AdjuntoTicket.objects.all()
    if not request.user.es_personal:
        adjuntos = adjuntos.exclude(comentario__interno=True)
    adjunto = get_object_or_404(adjuntos, pk=pk)

    get_object_or_404(_tickets_visibles(request.user), pk=adjunto.ticket_id)

    respuesta = HttpResponse(
        bytes(adjunto.contenido),
        content_type=adjunto.tipo_contenido,
    )
    respuesta["X-Content-Type-Options"] = "nosniff"
    respuesta["Cache-Control"] = "private, max-age=3600"
    return respuesta


def _aplicar_respuesta(ticket_pk, actor, accion, motivo):
    with transaction.atomic():
        ticket = Ticket.objects.select_for_update().get(pk=ticket_pk)

        if ticket.estado != Ticket.Estado.POR_CONFIRMAR:
            return "ya_respondido"

        if accion == "confirmar":
            services.confirmar_cierre(ticket, actor)
            return "confirmado"

        if accion == "rechazar":
            services.rechazar_cierre(ticket, actor, motivo)
            return "rechazado"

        return "invalida"


def _motivo(request):
    return request.POST.get("motivo", "").strip()[:1000]


@login_required
@require_POST
def responder_cierre(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, creado_por=request.user)

    resultado = _aplicar_respuesta(
        ticket.pk,
        request.user,
        request.POST.get("accion"),
        _motivo(request),
    )

    mensajes = {
        "confirmado": (messages.success, "Gracias, el ticket quedó cerrado."),
        "rechazado": (messages.success, "Listo, el ticket volvió a «En proceso»."),
        "ya_respondido": (messages.info, "Este ticket ya no está esperando confirmación."),
        "invalida": (messages.error, "Acción no válida."),
    }
    nivel, texto = mensajes[resultado]
    nivel(request, texto)

    return redirect("detalle_ticket", pk=pk)


def confirmar_cierre(request, token):
    ticket = services.ticket_desde_token(token)

    if ticket is None:
        return render(
            request,
            "tickets/confirmar_cierre.html",
            {"invalido": True},
            status=400,
        )

    if request.method == "POST":
        resultado = _aplicar_respuesta(
            ticket.pk,
            ticket.creado_por,
            request.POST.get("accion"),
            _motivo(request),
        )
        if resultado == "invalida":
            return render(request, "tickets/confirmar_cierre.html", {"ticket": ticket})
        return render(
            request,
            "tickets/confirmar_cierre.html",
            {"ticket": ticket, "resultado": resultado},
        )

    return render(request, "tickets/confirmar_cierre.html", {"ticket": ticket})


def acceso_directo(request, token):
    usuario, ticket_pk = acceso.datos_desde_token(token)

    if usuario is None or ticket_pk is None:
        messages.info(request, "El enlace venció. Inicia sesión para continuar.")
        return redirect("login")

    if request.user.pk != usuario.pk:
        login(request, usuario, backend="django.contrib.auth.backends.ModelBackend")

    return redirect("detalle_ticket", pk=ticket_pk)


def marcar_en_proceso(request, token):
    ticket, admin = services.ticket_y_admin_desde_token(token)

    if ticket is None:
        return render(
            request,
            "tickets/en_proceso.html",
            {"invalido": True},
            status=400,
        )

    if request.user.pk != admin.pk:
        login(request, admin, backend="django.contrib.auth.backends.ModelBackend")

    if ticket.estado != Ticket.Estado.ABIERTO:
        return render(
            request,
            "tickets/en_proceso.html",
            {"ticket": ticket, "resultado": "ya_atendido"},
        )

    contexto = {
        "ticket": ticket,
        "pide_prioridad": admin.es_admin,
        "prioridades": Ticket.Prioridad.choices,
    }

    if request.method == "POST":
        prioridad = request.POST.get("prioridad", "")
        if admin.es_admin and prioridad not in Ticket.Prioridad.values:
            return render(
                request,
                "tickets/en_proceso.html",
                {**contexto, "error_prioridad": True},
            )
        with transaction.atomic():
            ticket = Ticket.objects.select_for_update().get(pk=ticket.pk)
            if ticket.estado == Ticket.Estado.ABIERTO:
                if admin.es_admin:
                    services.aplicar_prioridad(ticket, admin, prioridad)
                services.poner_en_proceso(ticket, admin)
                resultado = "hecho"
            else:
                resultado = "ya_atendido"
        return render(
            request,
            "tickets/en_proceso.html",
            {"ticket": ticket, "resultado": resultado},
        )

    return render(request, "tickets/en_proceso.html", contexto)


@admin_required
@require_POST
def forzar_cierre(request, pk):
    get_object_or_404(_tickets_visibles(request.user), pk=pk)
    justificacion = request.POST.get("justificacion", "").strip()[:1000]
    if len(justificacion) < 10:
        messages.error(
            request, "Escribe la justificación del cierre (mínimo 10 caracteres)."
        )
        return redirect("detalle_ticket", pk=pk)

    with transaction.atomic():
        ticket = get_object_or_404(Ticket.objects.select_for_update(), pk=pk)

        if ticket.estado == Ticket.Estado.POR_CONFIRMAR:
            services.forzar_cierre(ticket, request.user, justificacion)
            messages.success(request, "Ticket cerrado sin confirmación del usuario.")
        else:
            messages.error(
                request, "Solo se puede cerrar así un ticket que está por confirmar."
            )

    return redirect("detalle_ticket", pk=pk)


@personal_required
@require_POST
def tomar_ticket(request, pk):
    get_object_or_404(_tickets_visibles(request.user), pk=pk)

    with transaction.atomic():
        ticket = get_object_or_404(Ticket.objects.select_for_update(), pk=pk)

        if request.user.es_superadmin:
            messages.error(request, "El super administrador no toma tickets, solo los asigna.")
        elif request.user.sucursal_id != ticket.sucursal_id:
            messages.error(request, "Solo puedes tomar tickets de tu sucursal.")
        elif ticket.estado == Ticket.Estado.CERRADO:
            messages.error(request, "Ese ticket ya está cerrado.")
        elif ticket.asignado_a_id is not None:
            messages.error(request, "Ese ticket ya fue tomado por otra persona.")
        else:
            services.tomar_ticket(ticket, request.user)
            messages.success(request, "Tomaste el ticket.")

    return redirect("detalle_ticket", pk=pk)


@admin_required
@require_POST
def asignar_ticket(request, pk):
    ticket = get_object_or_404(_tickets_visibles(request.user), pk=pk)
    form = AsignarTicketForm(request.POST, ticket=ticket)

    if not form.is_valid():
        mensaje = " ".join(e for errores in form.errors.values() for e in errores)
        messages.error(request, mensaje or "Revisa los datos de la asignación.")
    else:
        destino = form.cleaned_data["asignado_a"]
        prioridad = form.cleaned_data["prioridad"]
        sin_cambio_prioridad = not prioridad or prioridad == ticket.prioridad
        if destino == ticket.asignado_a and sin_cambio_prioridad:
            messages.info(request, "No hubo cambios.")
        else:
            with transaction.atomic():
                if prioridad:
                    services.aplicar_prioridad(ticket, request.user, prioridad)
                if destino != ticket.asignado_a:
                    services.asignar_ticket(ticket, request.user, destino)
            messages.success(request, "Ticket actualizado.")

    return redirect("detalle_ticket", pk=pk)


@personal_required
@require_POST
def escalar_ticket(request, pk):
    get_object_or_404(_tickets_visibles(request.user), pk=pk)

    with transaction.atomic():
        ticket = get_object_or_404(Ticket.objects.select_for_update(), pk=pk)

        if not request.user.es_encargado or request.user.es_superadmin:
            messages.error(request, "Solo un encargado puede escalar tickets.")
        elif ticket.estado == Ticket.Estado.CERRADO:
            messages.error(request, "El ticket está cerrado.")
        else:
            form = EscalarTicketForm(
                request.POST, ticket=ticket, actor=request.user
            )
            if form.is_valid():
                services.escalar_ticket(
                    ticket,
                    request.user,
                    form.cleaned_data["destino"],
                    form.cleaned_data["motivo"],
                    form.cleaned_data["prioridad"],
                )
                messages.success(request, "Ticket escalado.")
            else:
                mensaje = " ".join(
                    e for errores in form.errors.values() for e in errores
                )
                messages.error(request, mensaje or "Revisa los datos de la escalada.")

    return redirect("detalle_ticket", pk=pk)


@login_required
def lista_notificaciones(request):
    notificaciones = request.user.notificaciones.select_related("ticket")[:50]

    return render(
        request,
        "tickets/notificaciones.html",
        {"notificaciones": notificaciones},
    )


@login_required
@require_POST
def abrir_notificacion(request, pk):
    notificacion = get_object_or_404(request.user.notificaciones, pk=pk)

    notificacion.marcar_leida()

    if notificacion.ticket_id is None:
        return redirect("lista_notificaciones")

    return redirect("detalle_ticket", pk=notificacion.ticket_id)


@login_required
@require_POST
def marcar_notificacion_leida(request, pk):
    notificacion = get_object_or_404(request.user.notificaciones, pk=pk)

    notificacion.marcar_leida()

    return redirect("lista_notificaciones")


@login_required
@require_POST
def notificaciones_leer_todas(request):
    request.user.notificaciones.filter(leida=False).update(
        leida=True,
        leida_en=timezone.now(),
    )

    return redirect("lista_notificaciones")


@login_required
@require_POST
def reabrir_ticket(request, pk):
    get_object_or_404(_tickets_visibles(request.user), pk=pk)
    motivo = request.POST.get("motivo", "").strip()[:1000]

    if len(motivo) < 5:
        messages.error(
            request, "Escribe el motivo de la reapertura (mínimo 5 caracteres)."
        )
        return redirect("detalle_ticket", pk=pk)

    with transaction.atomic():
        ticket = get_object_or_404(Ticket.objects.select_for_update(), pk=pk)

        if ticket.estado != Ticket.Estado.CERRADO:
            messages.error(request, "Solo se puede reabrir un ticket cerrado.")
        elif not ticket.dentro_de_plazo_reapertura:
            messages.error(request, "El plazo para reabrir este ticket ya venció.")
        else:
            services.reabrir_ticket(ticket, request.user, motivo)
            messages.success(request, "Ticket reabierto.")

    return redirect("detalle_ticket", pk=pk)

@login_required
@require_POST
def responder_encuesta(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, creado_por=request.user)

    if ticket.estado != Ticket.Estado.CERRADO:
        messages.error(request, "Solo puedes calificar un ticket cerrado.")
        return redirect("detalle_ticket", pk=pk)

    try:
        calificacion = int(request.POST.get("calificacion", ""))
    except ValueError:
        calificacion = 0

    if calificacion < 1 or calificacion > 5:
        messages.error(request, "Elige de 1 a 5 estrellas.")
        return redirect("detalle_ticket", pk=pk)

    _, creada = EncuestaSatisfaccion.objects.get_or_create(
        ticket=ticket,
        defaults={
            "calificacion": calificacion,
            "comentario": request.POST.get("comentario", "").strip()[:1000],
            "atendido_por": ticket.resuelto_por,
        },
    )

    if creada:
        messages.success(request, "¡Gracias por tu opinión!")
    else:
        messages.info(request, "Este ticket ya fue calificado.")

    return redirect("detalle_ticket", pk=pk)