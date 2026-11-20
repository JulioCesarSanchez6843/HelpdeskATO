from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.tickets import services
from apps.tickets.models import Ticket
from apps.tickets.views import _tickets_visibles

from .serializers import (
    TicketDetalleSerializer,
    TicketListSerializer,
    UsuarioSerializer,
)


def _error(mensaje, codigo=status.HTTP_400_BAD_REQUEST):
    return Response({"detail": mensaje}, status=codigo)


def _detalle(request, pk, codigo=status.HTTP_200_OK):
    ticket = get_object_or_404(_tickets_visibles(request.user), pk=pk)
    datos = TicketDetalleSerializer(ticket, context={"request": request}).data
    return Response(datos, status=codigo)


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    correo = (request.data.get("correo") or "").strip()
    password = request.data.get("password") or ""
    usuario = authenticate(request, username=correo, password=password)
    if usuario is None:
        return Response(
            {"detail": "Correo o contraseña incorrectos."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    token, _ = Token.objects.get_or_create(user=usuario)
    return Response({"token": token.key, "usuario": UsuarioSerializer(usuario).data})


@api_view(["POST"])
def logout(request):
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def me(request):
    return Response(UsuarioSerializer(request.user).data)


class PaginaTickets(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


@api_view(["GET"])
def tickets_lista(request):
    tickets = _tickets_visibles(request.user)

    estado = request.query_params.get("estado")
    if estado in Ticket.Estado.values:
        tickets = tickets.filter(estado=estado)

    texto = (request.query_params.get("q") or "").strip()
    if texto:
        tickets = tickets.filter(
            Q(titulo__icontains=texto) | Q(descripcion__icontains=texto)
        )

    if request.query_params.get("asignados_a_mi") == "1":
        tickets = tickets.filter(asignado_a=request.user)

    paginador = PaginaTickets()
    pagina = paginador.paginate_queryset(tickets, request)
    return paginador.get_paginated_response(
        TicketListSerializer(pagina, many=True).data
    )


@api_view(["GET"])
def ticket_detalle(request, pk):
    return _detalle(request, pk)


@api_view(["POST"])
def ticket_comentar(request, pk):
    ticket = get_object_or_404(_tickets_visibles(request.user), pk=pk)
    contenido = str(request.data.get("contenido") or "").strip()[:2000]
    interno = request.user.es_personal and str(
        request.data.get("interno")
    ).lower() in ("true", "1", "on")

    if ticket.estado == Ticket.Estado.CERRADO:
        return _error("El ticket está cerrado y ya no admite mensajes.")
    if len(contenido) < 2:
        return _error("Escribe un mensaje.")

    with transaction.atomic():
        services.agregar_comentario(ticket, request.user, contenido, interno)
    return _detalle(request, pk, status.HTTP_201_CREATED)


@api_view(["POST"])
def ticket_tomar(request, pk):
    if not request.user.es_personal or request.user.es_superadmin:
        return _error("No tienes permiso para tomar tickets.", status.HTTP_403_FORBIDDEN)

    get_object_or_404(_tickets_visibles(request.user), pk=pk)

    with transaction.atomic():
        ticket = get_object_or_404(Ticket.objects.select_for_update(), pk=pk)

        if request.user.sucursal_id != ticket.sucursal_id:
            return _error(
                "Solo puedes tomar tickets de tu sucursal.", status.HTTP_403_FORBIDDEN
            )
        if ticket.estado == Ticket.Estado.CERRADO:
            return _error("Ese ticket ya está cerrado.")
        if ticket.asignado_a_id is not None:
            return _error(
                "Ese ticket ya fue tomado por otra persona.", status.HTTP_409_CONFLICT
            )
        services.tomar_ticket(ticket, request.user)

    return _detalle(request, pk)