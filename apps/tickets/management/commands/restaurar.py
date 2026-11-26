from pathlib import Path

from decouple import config
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.tickets import respaldos


class Command(BaseCommand):
    help = "Restaura un respaldo .zip (base de datos y archivos)."

    def add_arguments(self, parser):
        parser.add_argument("archivo")
        parser.add_argument("--pg-bin", default=config("PG_BIN", default=""))
        parser.add_argument("--solo-bd", action="store_true")
        parser.add_argument("--solo-media", action="store_true")
        parser.add_argument("--si", action="store_true")

    def handle(self, *args, **o):
        archivo = Path(o["archivo"])
        if not archivo.is_file():
            raise CommandError(f"No existe: {archivo}")
        bd = settings.DATABASES["default"]
        if not o["si"]:
            self.stdout.write(
                f"Esto REEMPLAZA los datos de la base '{bd['NAME']}' y mezcla los archivos en "
                f"{settings.MEDIA_ROOT}."
            )
            if input("Escribe SI para continuar: ").strip() != "SI":
                raise CommandError("Cancelado.")
        try:
            respaldos.restaurar(
                archivo, bd, settings.MEDIA_ROOT, pg_bin=o["pg_bin"],
                solo_bd=o["solo_bd"], solo_media=o["solo_media"], log=self.stdout.write,
            )
        except respaldos.ErrorRespaldo as error:
            raise CommandError(str(error))