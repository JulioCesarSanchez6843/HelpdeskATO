from django.db import transaction
from django.utils import timezone

from . import services
from .models import Ticket

ESTADOS_ACTIVOS = (
    Ticket.Estado.ABIERTO,
    Ticket.Estado.EN_PROCESO,
    Ticket.Estado.EN_ESPERA,
)


def _activos():
    return Ticket.objects.filter(
        estado__in=ESTADOS_ACTIVOS,
        resuelto_en__isnull=True,
        sla_vence_en__isnull=False,
    )


def ids_por_vencer(ahora):
    candidatos = _activos().filter(sla_aviso_en__isnull=True, sla_vence_en__gt=ahora)
    return [
        ticket.pk
        for ticket in candidatos
        if ticket.sla_aviso_desde is not None and ahora >= ticket.sla_aviso_desde
    ]


def ids_vencidos(ahora):
    return list(
        _activos()
        .filter(sla_vencido_aviso_en__isnull=True, sla_vence_en__lte=ahora)
        .values_list("pk", flat=True)
    )


def _bloqueado(pk):
    return (
        _activos()
        .select_for_update(of=("self",))
        .select_related("asignado_a", "creado_por", "area", "categoria")
        .filter(pk=pk)
        .first()
    )


def ejecutar(ahora=None, dry_run=False):
    ahora = ahora or timezone.now()
    resultado = {
        "por_vencer": ids_por_vencer(ahora),
        "vencidos": ids_vencidos(ahora),
        "avisados": 0,
        "errores": [],
    }
    if dry_run:
        return resultado

    for vencido, ids in (
        (False, resultado["por_vencer"]),
        (True, resultado["vencidos"]),
    ):
        for pk in ids:
            try:
                with transaction.atomic():
                    ticket = _bloqueado(pk)
                    if ticket is None:
                        continue
                    ya_avisado = (
                        ticket.sla_vencido_aviso_en if vencido else ticket.sla_aviso_en
                    )
                    if ya_avisado is not None:
                        continue
                    services.avisar_sla(ticket, vencido)
                resultado["avisados"] += 1
            except Exception as error:
                resultado["errores"].append(f"Ticket #{pk}: {error}")
    return resultado