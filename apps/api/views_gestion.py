from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.catalog.models import Categoria
from apps.tickets import services
from apps.tickets.forms import AsignarTicketForm, TicketForm, TicketGestionForm
from apps.tickets.imagenes import ImagenInvalida
from apps.tickets.models import Ticket
from apps.tickets.views import _aplicar_respuesta, _tickets_visibles

from .views import _detalle, _error


def _errores_form(form):
    return Response(
        {
            "detail": "Revisa los datos.",
            "errores": {
                campo: [str(e) for e in errores]
                for campo, errores in form.errors.items()
            },
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["POST"])
def ticket_nuevo(request):
    form = TicketForm(request.data, request.FILES)
    if not form.is_valid():
        return _errores_form(form)

    try:
        with transaction.atomic():
            ticket = form.save(commit=False)
            ticket.creado_por = request.user
            ticket.area = request.user.area
            ticket.sucursal = request.user.sucursal
            ticket.save()

            services.guardar_adjuntos(
                ticket, form.cleaned_data["imagenes"], request.user
            )
            services.registrar_creacion(ticket, request.user)
    except ImagenInvalida as error:
        return Response(
            {"detail": "Revisa los datos.", "errores": {"imagenes": [str(error)]}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return _detalle(request, ticket.pk, status.HTTP_201_CREATED)


@api_view(["POST"])
def ticket_asignar(request, pk):
    if not request.user.es_admin:
        return _error("No tienes permiso para asignar tickets.", status.HTTP_403_FORBIDDEN)

    ticket = get_object_or_404(_tickets_visibles(request.user), pk=pk)
    form = AsignarTicketForm(request.data, ticket=ticket)
    if not form.is_valid():
        return _errores_form(form)

    destino = form.cleaned_data["asignado_a"]
    prioridad = form.cleaned_data["prioridad"]
    sin_cambio_prioridad = not prioridad or prioridad == ticket.prioridad
    if destino == ticket.asignado_a and sin_cambio_prioridad:
        return _detalle(request, pk)

    with transaction.atomic():
        if prioridad:
            services.aplicar_prioridad(ticket, request.user, prioridad)
        if destino != ticket.asignado_a:
            services.asignar_ticket(ticket, request.user, destino)

    return _detalle(request, pk)


@api_view(["GET"])
def ticket_opciones(request, pk):
    if not request.user.es_personal:
        return _error("No tienes permiso.", status.HTTP_403_FORBIDDEN)

    ticket = get_object_or_404(_tickets_visibles(request.user), pk=pk)

    asignables = []
    if request.user.es_admin:
        form = AsignarTicketForm(ticket=ticket)
        asignables = [
            {"id": u.pk, "nombre": u.nombre, "rol": u.get_rol_display()}
            for u in form.fields["asignado_a"].queryset
        ]

    categorias = (
        Categoria.objects.de_sucursal(ticket.sucursal_id)
        if ticket.sucursal_id
        else Categoria.objects.all()
    )

    return Response(
        {
            "asignables": asignables,
            "prioridades": [
                {"valor": valor, "etiqueta": etiqueta}
                for valor, etiqueta in Ticket.Prioridad.choices
            ],
            "categorias": [{"id": c.pk, "nombre": c.nombre} for c in categorias],
        }
    )

@api_view(["POST"])
def ticket_gestion(request, pk):
    if not request.user.es_personal:
        return _error("No tienes permiso.", status.HTTP_403_FORBIDDEN)

    ticket = get_object_or_404(_tickets_visibles(request.user), pk=pk)

    with transaction.atomic():
        instancia = Ticket.objects.select_for_update().get(pk=ticket.pk)
        antes = services.snapshot(instancia)
        form = TicketGestionForm(request.data, instance=instancia, usuario=request.user)
        if not form.is_valid():
            return _errores_form(form)
        form.save()
        instancia.refresh_from_db()
        services.registrar_gestion(
            instancia,
            request.user,
            antes,
            form.cleaned_data.get("motivo_espera", ""),
        )

    return _detalle(request, pk)


@api_view(["GET"])
def ticket_gestion_opciones(request, pk):
    if not request.user.es_personal:
        return _error("No tienes permiso.", status.HTTP_403_FORBIDDEN)

    ticket = get_object_or_404(_tickets_visibles(request.user), pk=pk)
    form = TicketGestionForm(instance=ticket, usuario=request.user)

    return Response(
        {
            "estados": [
                {"valor": valor, "etiqueta": etiqueta}
                for valor, etiqueta in form.fields["estado"].choices
            ],
            "categorias": [
                {"id": c.pk, "nombre": c.nombre}
                for c in form.fields["categoria"].queryset
            ],
            "puede_priorizar": form.puede_priorizar,
            "prioridades": [
                {"valor": valor, "etiqueta": etiqueta}
                for valor, etiqueta in Ticket.Prioridad.choices
            ],
            "valores": {
                "estado": ticket.estado,
                "prioridad": ticket.prioridad,
                "categoria": ticket.categoria_id,
                "numero_serie": ticket.numero_serie,
                "nota_resolucion": ticket.nota_resolucion,
            },
        }
    )

@api_view(["POST"])
def ticket_responder_cierre(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk, creado_por=request.user)
    accion = str(request.data.get("accion") or "")
    motivo = str(request.data.get("motivo") or "").strip()[:1000]

    resultado = _aplicar_respuesta(ticket.pk, request.user, accion, motivo)

    if resultado == "ya_respondido":
        return _error("Este ticket ya no está esperando confirmación.", status.HTTP_409_CONFLICT)
    if resultado == "invalida":
        return _error("Acción no válida.")
    return _detalle(request, pk)


@api_view(["POST"])
def ticket_reabrir(request, pk):
    get_object_or_404(_tickets_visibles(request.user), pk=pk)
    motivo = str(request.data.get("motivo") or "").strip()[:1000]

    if len(motivo) < 5:
        return _error("Escribe el motivo de la reapertura (mínimo 5 caracteres).")

    with transaction.atomic():
        ticket = get_object_or_404(Ticket.objects.select_for_update(), pk=pk)

        if ticket.estado != Ticket.Estado.CERRADO:
            return _error("Solo se puede reabrir un ticket cerrado.")
        if not ticket.dentro_de_plazo_reapertura:
            return _error("El plazo para reabrir este ticket ya venció.")
        services.reabrir_ticket(ticket, request.user, motivo)

    return _detalle(request, pk)