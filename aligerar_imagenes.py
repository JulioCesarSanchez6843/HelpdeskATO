import argparse
import shutil
from pathlib import Path

from PIL import Image

EXTENSIONES = {".png", ".jpg", ".jpeg", ".webp"}


def aligerar(carpeta, lado_maximo, calidad):
    origen = Path(carpeta)
    if not origen.is_dir():
        raise SystemExit(f"No existe la carpeta: {origen}")

    respaldo = origen.with_name(origen.name + "_original")
    if respaldo.exists():
        print(f"Ya existe el respaldo {respaldo}, no se vuelve a copiar.")
    else:
        shutil.copytree(origen, respaldo)
        print(f"Respaldo creado en {respaldo}")

    total_antes = 0
    total_despues = 0

    for ruta in sorted(origen.iterdir()):
        if ruta.suffix.lower() not in EXTENSIONES:
            continue

        antes = ruta.stat().st_size
        imagen = Image.open(ruta)
        imagen.load()
        imagen.thumbnail((lado_maximo, lado_maximo))

        if ruta.suffix.lower() == ".png":
            imagen.save(ruta, optimize=True)
        elif ruta.suffix.lower() == ".webp":
            imagen.save(ruta, quality=calidad)
        else:
            imagen.convert("RGB").save(ruta, quality=calidad, optimize=True)

        despues = ruta.stat().st_size
        total_antes += antes
        total_despues += despues
        print(f"{ruta.name}: {antes // 1024} KB -> {despues // 1024} KB")

    print(f"Total: {total_antes // 1024} KB -> {total_despues // 1024} KB")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("carpeta")
    parser.add_argument("--lado", type=int, default=480)
    parser.add_argument("--calidad", type=int, default=85)
    argumentos = parser.parse_args()
    aligerar(argumentos.carpeta, argumentos.lado, argumentos.calidad)