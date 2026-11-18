from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.catalog.models import Categoria
from apps.tickets import services
from apps.tickets.forms import AsignarTicketForm, TicketForm
from apps.tickets.imagenes import ImagenInvalida
from apps.tickets.models import Ticket
from apps.tickets.views import _tickets_visibles

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