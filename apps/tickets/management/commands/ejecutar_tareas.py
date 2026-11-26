import time

from decouple import config
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from apps.tickets import cierre_automatico, emails, respaldos, sla
from apps.tickets.management.commands import respaldar


class Command(BaseCommand):
    help = "Se queda corriendo: envía la cola de correos y cierra tickets vencidos según la hora del servidor."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cada-correos",
            type=int,
            default=10,
            help="Segundos entre revisiones de la cola de correos.",
        )
        parser.add_argument(
            "--cada-cierre",
            type=int,
            default=3600,
            help="Segundos entre revisiones de tickets vencidos.",
        )
        parser.add_argument(
            "--cada-sla",
            type=int,
            default=300,
            help="Segundos entre revisiones de los SLA.",
        )

    def marca(self):
        return timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")

    def tarea_correos(self):
        enviados, fallidos = emails.procesar_pendientes()
        emails.limpiar_enviados()
        if enviados or fallidos:
            self.stdout.write(
                f"[{self.marca()}] Correos enviados: {enviados}. Con error: {fallidos}."
            )

    def tarea_cierre(self):
        resultado = cierre_automatico.ejecutar()
        if not resultado["activo"]:
            return
        if resultado["cerrados"] or resultado["recordatorios"]:
            self.stdout.write(
                f"[{self.marca()}] Tickets cerrados: {resultado['cerrados']}. "
                f"Recordatorios: {resultado['recordatorios']}."
            )
        for error in resultado["errores"]:
            self.stderr.write(f"[{self.marca()}] {error}")

    def tarea_sla(self):
        resultado = sla.ejecutar()
        if resultado["avisados"]:
            self.stdout.write(
                f"[{self.marca()}] Avisos de SLA enviados: {resultado['avisados']}."
            )
        for error in resultado["errores"]:
            self.stderr.write(f"[{self.marca()}] {error}")

    def tarea_respaldo(self):
        if not config("BACKUP_ACTIVO", default=True, cast=bool):
            return
        hora = config("BACKUP_HORA", default="02:00")
        if timezone.localtime().strftime("%H:%M") < hora:
            return
        opciones = respaldar.opciones_por_defecto()
        if respaldos.hay_respaldo_de_hoy(opciones["destino"]):
            return
        avisos = respaldar.ejecutar(
            **opciones,
            incluir_env=config("BACKUP_INCLUIR_ENV", default=False, cast=bool),
            origen="automatico",
            log=lambda m: self.stdout.write(f"[{self.marca()}] {m}"),
        )
        for aviso in avisos:
            self.stderr.write(f"[{self.marca()}] {aviso}")

    def handle(self, *args, **options):
        cada_correos = max(options["cada_correos"], 1)
        cada_cierre = max(options["cada_cierre"], 60)
        cada_sla = max(options["cada_sla"], 60)

        self.stdout.write(
            f"[{self.marca()}] Tareas en marcha. Correos cada {cada_correos}s, "
            f"cierre de tickets cada {cada_cierre}s, SLA cada {cada_sla}s. "
            "Ctrl + C para detener."
        )

        proxima_correos = 0.0
        proxima_cierre = 0.0
        proxima_sla = 0.0
        proxima_respaldo = 0.0

        try:
            while True:
                close_old_connections()
                ahora = time.monotonic()

                if ahora >= proxima_correos:
                    try:
                        self.tarea_correos()
                    except Exception as error:
                        self.stderr.write(f"[{self.marca()}] Error en correos: {error}")
                    proxima_correos = time.monotonic() + cada_correos

                if ahora >= proxima_cierre:
                    try:
                        self.tarea_cierre()
                    except Exception as error:
                        self.stderr.write(f"[{self.marca()}] Error en cierre: {error}")
                    proxima_cierre = time.monotonic() + cada_cierre

                if ahora >= proxima_sla:
                    try:
                        self.tarea_sla()
                    except Exception as error:
                        self.stderr.write(f"[{self.marca()}] Error en SLA: {error}")
                    proxima_sla = time.monotonic() + cada_sla

                if ahora >= proxima_respaldo:
                    try:
                        self.tarea_respaldo()
                    except Exception as error:
                        self.stderr.write(f"[{self.marca()}] Error en respaldo: {error}")
                    proxima_respaldo = time.monotonic() + 600

                time.sleep(1) 
        except KeyboardInterrupt:
            self.stdout.write("Detenido.")