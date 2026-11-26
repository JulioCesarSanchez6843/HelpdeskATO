from decouple import config
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.tickets import respaldos


def opciones_por_defecto():
    return {
        "destino": config("BACKUP_DIR", default="") or str(settings.BASE_DIR / "respaldos"),
        "copia": config("BACKUP_COPIA_DIR", default=""),
        "pg_bin": config("PG_BIN", default=""),
        "diarios": config("BACKUP_DIARIOS", default=7, cast=int),
        "semanales": config("BACKUP_SEMANALES", default=4, cast=int),
        "mensuales": config("BACKUP_MENSUALES", default=6, cast=int),
    }


def ejecutar(destino, copia, pg_bin, diarios, semanales, mensuales,
             incluir_env=False, origen="manual", log=print):
    rotacion = {"diarios": diarios, "semanales": semanales, "mensuales": mensuales}
    env_path = settings.BASE_DIR / ".env" if incluir_env else None
    archivo = respaldos.crear_respaldo(
        settings.DATABASES["default"], settings.MEDIA_ROOT, destino,
        pg_bin=pg_bin, env_path=env_path, log=log, origen=origen,
    )
    respaldos.rotar(destino, log=log, **rotacion)

    avisos = []
    if copia:
        try:
            respaldos.copiar_a_carpeta(archivo, copia, log=log, **rotacion)
        except Exception as error:
            avisos.append(f"No se pudo copiar a {copia}: {error}")
    return avisos


class Command(BaseCommand):
    help = "Respalda la base de datos y los archivos (manuales, fotos, adjuntos) en un .zip."

    def add_arguments(self, parser):
        d = opciones_por_defecto()
        parser.add_argument("--destino", default=d["destino"])
        parser.add_argument("--copia", default=d["copia"])
        parser.add_argument("--pg-bin", default=d["pg_bin"])
        parser.add_argument("--diarios", type=int, default=d["diarios"])
        parser.add_argument("--semanales", type=int, default=d["semanales"])
        parser.add_argument("--mensuales", type=int, default=d["mensuales"])
        parser.add_argument("--incluir-env", action="store_true")

    def handle(self, *args, **o):
        try:
            avisos = ejecutar(
                o["destino"], o["copia"], o["pg_bin"],
                o["diarios"], o["semanales"], o["mensuales"],
                incluir_env=o["incluir_env"], log=self.stdout.write,
            )
        except respaldos.ErrorRespaldo as error:
            raise CommandError(str(error))
        for aviso in avisos:
            self.stderr.write(self.style.WARNING(aviso))
        if avisos:
            raise CommandError("El respaldo local quedó bien, pero falló una copia externa.")