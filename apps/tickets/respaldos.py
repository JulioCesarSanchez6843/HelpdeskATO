import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

PREFIJO = "helpdesk"
PATRON = re.compile(rf"^{PREFIJO}_(\d{{4}})(\d{{2}})(\d{{2}})_(\d{{6}})\.zip$")


class ErrorRespaldo(Exception):
    pass


def _ejecutable(nombre, ruta_config):
    if ruta_config:
        ruta = Path(ruta_config)
        if ruta.is_dir():
            for candidato in (nombre, nombre + ".exe"):
                if (ruta / candidato).exists():
                    return str(ruta / candidato)
        elif ruta.exists():
            return str(ruta)
    encontrado = shutil.which(nombre)
    if not encontrado:
        raise ErrorRespaldo(
            f"No encuentro '{nombre}'. Agrega la carpeta bin de PostgreSQL al PATH "
            "o pon PG_BIN en el .env."
        )
    return encontrado


def _sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def _entorno_pg(bd):
    entorno = os.environ.copy()
    entorno["PGPASSWORD"] = str(bd.get("PASSWORD") or "")
    return entorno


def _args_conexion(bd):
    return [
        "-h", str(bd.get("HOST") or "localhost"),
        "-p", str(bd.get("PORT") or "5432"),
        "-U", str(bd.get("USER") or "postgres"),
    ]


def _correr(comando, entorno):
    resultado = subprocess.run(comando, env=entorno, capture_output=True, text=True)
    if resultado.returncode != 0:
        raise ErrorRespaldo(
            f"Falló {Path(comando[0]).name} (código {resultado.returncode}): "
            f"{(resultado.stderr or resultado.stdout).strip()}"
        )
    return resultado


def crear_respaldo(bd, media_root, destino, pg_bin="", env_path=None, log=print, origen="manual"):
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    media_root = Path(media_root)
    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    final = destino / f"{PREFIJO}_{sello}.zip"
    parcial = destino / f"{final.name}.parcial"

    pg_dump = _ejecutable("pg_dump", pg_bin)
    pg_restore = _ejecutable("pg_restore", pg_bin)
    entorno = _entorno_pg(bd)

    with tempfile.TemporaryDirectory(prefix="respaldo_") as tmp:
        dump = Path(tmp) / "base_de_datos.dump"
        log("Respaldando la base de datos...")
        _correr(
            [pg_dump, *_args_conexion(bd), "-Fc", "--no-owner", "-f", str(dump), bd["NAME"]],
            entorno,
        )
        _correr([pg_restore, "--list", str(dump)], entorno)

        manifiesto = {
            "creado": datetime.now().isoformat(timespec="seconds"),
            "base_de_datos": bd["NAME"],
            "origen": origen,
            "dump_bytes": dump.stat().st_size,
            "dump_sha256": _sha256(dump),
            "archivos_media": 0,
            "media_bytes": 0,
        }

        log("Empaquetando archivos...")
        try:
            with zipfile.ZipFile(parcial, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
                z.write(dump, "base_de_datos.dump")
                if media_root.is_dir():
                    for archivo in sorted(media_root.rglob("*")):
                        if archivo.is_file():
                            z.write(archivo, "media/" + archivo.relative_to(media_root).as_posix())
                            manifiesto["archivos_media"] += 1
                            manifiesto["media_bytes"] += archivo.stat().st_size
                if env_path and Path(env_path).is_file():
                    z.write(env_path, "env_respaldo.txt")
                    manifiesto["incluye_env"] = True
                z.writestr("manifiesto.json", json.dumps(manifiesto, indent=2, ensure_ascii=False))

            with zipfile.ZipFile(parcial) as z:
                malo = z.testzip()
                if malo:
                    raise ErrorRespaldo(f"El zip quedó dañado en: {malo}")
            parcial.replace(final)
        finally:
            if parcial.exists():
                parcial.unlink()

    log(
        f"Respaldo listo: {final.name} ({final.stat().st_size / 1024 / 1024:.1f} MB, "
        f"{manifiesto['archivos_media']} archivos de media)"
    )
    return final


def listar(destino):
    destino = Path(destino)
    if not destino.is_dir():
        return []
    salida = []
    for archivo in destino.iterdir():
        m = PATRON.match(archivo.name)
        if m:
            fecha = datetime.strptime("".join(m.groups()), "%Y%m%d%H%M%S")
            salida.append((fecha, archivo))
    return sorted(salida, reverse=True)


def hay_respaldo_de_hoy(destino):
    hoy = date.today()
    return any(f.date() == hoy for f, _ in listar(destino))


def rotar(destino, diarios=7, semanales=4, mensuales=6, log=print):
    respaldos = listar(destino)
    if not respaldos:
        return []
    hoy = date.today()
    conservar = {respaldos[0][1]}
    limite_diario = hoy - timedelta(days=diarios)
    limite_semanal = hoy - timedelta(weeks=semanales)
    limite_mensual = hoy - timedelta(days=31 * mensuales)

    por_semana, por_mes = {}, {}
    for fecha, ruta in sorted(respaldos):
        if fecha.date() > limite_diario:
            conservar.add(ruta)
        por_semana.setdefault(fecha.isocalendar()[:2], (fecha, ruta))
        por_mes.setdefault((fecha.year, fecha.month), (fecha, ruta))
    for fecha, ruta in por_semana.values():
        if fecha.date() > limite_semanal:
            conservar.add(ruta)
    for fecha, ruta in por_mes.values():
        if fecha.date() > limite_mensual:
            conservar.add(ruta)

    borrados = []
    for _, ruta in respaldos:
        if ruta not in conservar:
            ruta.unlink()
            borrados.append(ruta)
            log(f"Respaldo viejo eliminado: {ruta.name}")
    return borrados

def leer_origen(ruta):
    try:
        with zipfile.ZipFile(ruta) as z:
            manifiesto = json.loads(z.read("manifiesto.json").decode("utf-8"))
        return manifiesto.get("origen", "desconocido")
    except (zipfile.BadZipFile, KeyError, ValueError, OSError):
        return "desconocido"

def copiar_a_carpeta(archivo, carpeta, log=print, **rotacion):
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    temporal = carpeta / (archivo.name + ".parcial")
    shutil.copy2(archivo, temporal)
    temporal.replace(carpeta / archivo.name)
    log(f"Copia guardada en {carpeta}")
    rotar(carpeta, log=log, **rotacion)

def restaurar(archivo_zip, bd, media_root, pg_bin="", solo_bd=False, solo_media=False, log=print):
    pg_restore = _ejecutable("pg_restore", pg_bin)
    entorno = _entorno_pg(bd)
    with tempfile.TemporaryDirectory(prefix="restaurar_") as tmp:
        with zipfile.ZipFile(archivo_zip) as z:
            if z.testzip():
                raise ErrorRespaldo("El zip está dañado, prueba con otro respaldo.")
            z.extractall(tmp)
        tmp = Path(tmp)
        if not solo_media:
            log("Restaurando la base de datos...")
            _correr(
                [pg_restore, *_args_conexion(bd), "--clean", "--if-exists", "--no-owner",
                 "-d", bd["NAME"], str(tmp / "base_de_datos.dump")],
                entorno,
            )
        if not solo_bd and (tmp / "media").is_dir():
            log(f"Restaurando archivos en {media_root}...")
            shutil.copytree(tmp / "media", media_root, dirs_exist_ok=True)
    log("Restauración terminada.")

def validar_zip(ruta):
    try:
        with zipfile.ZipFile(ruta) as z:
            nombres = z.namelist()
            for nombre in nombres:
                partes = Path(nombre.replace("\\", "/")).parts
                if nombre.startswith(("/", "\\")) or ".." in partes or re.match(r"^[A-Za-z]:", nombre):
                    raise ErrorRespaldo("El zip contiene rutas no permitidas.")
            if "base_de_datos.dump" not in nombres or "manifiesto.json" not in nombres:
                raise ErrorRespaldo(
                    "No parece un respaldo de Helpdesk: faltan base_de_datos.dump o manifiesto.json."
                )
            if z.testzip():
                raise ErrorRespaldo("El zip está dañado, prueba con otro respaldo.")
            manifiesto = json.loads(z.read("manifiesto.json").decode("utf-8"))
            h = hashlib.sha256()
            with z.open("base_de_datos.dump") as f:
                for bloque in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(bloque)
    except zipfile.BadZipFile:
        raise ErrorRespaldo("El archivo no es un .zip válido.")
    except (ValueError, UnicodeDecodeError):
        raise ErrorRespaldo("El manifiesto del respaldo no se puede leer.")

    if h.hexdigest() != manifiesto.get("dump_sha256"):
        raise ErrorRespaldo(
            "La base de datos del respaldo no coincide con su huella: el archivo está alterado o dañado."
        )
    try:
        fecha = datetime.fromisoformat(manifiesto["creado"])
    except (KeyError, ValueError, TypeError):
        raise ErrorRespaldo("El manifiesto no trae una fecha de creación válida.")
    return manifiesto, fecha


def guardar_subido(archivo_subido, destino, max_bytes=None):
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    if max_bytes and archivo_subido.size > max_bytes:
        raise ErrorRespaldo(f"El archivo pesa más del máximo permitido ({max_bytes // 1024 // 1024} MB).")

    fd, temporal = tempfile.mkstemp(dir=destino, prefix="subida_", suffix=".parcial")
    temporal = Path(temporal)
    try:
        with os.fdopen(fd, "wb") as f:
            for bloque in archivo_subido.chunks():
                f.write(bloque)
        manifiesto, fecha = validar_zip(temporal)
        final = destino / f"{PREFIJO}_{fecha:%Y%m%d_%H%M%S}.zip"
        if final.exists():
            raise ErrorRespaldo(f"Ya existe en el servidor un respaldo con esa fecha ({final.name}).")
        temporal.replace(final)
        return final, manifiesto
    finally:
        if temporal.exists():
            temporal.unlink()


@contextmanager
def bloqueo_restauracion(destino):
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    candado = destino / ".restaurando"
    if candado.exists() and time.time() - candado.stat().st_mtime > 3600:
        candado.unlink()
    try:
        os.close(os.open(candado, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        raise ErrorRespaldo("Ya hay una restauración en curso. Espera a que termine.")
    try:
        yield
    finally:
        candado.unlink(missing_ok=True)