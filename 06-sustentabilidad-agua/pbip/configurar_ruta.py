# -*- coding: utf-8 -*-
"""Apunta el parámetro RutaDatos del modelo a la carpeta datos_sinteticos de ESTA copia del repositorio.

El modelo trae un marcador (<RUTA_DEL_REPO>) porque Power Query necesita una ruta absoluta para leer los CSV.
Ejecuta este script una vez después de clonar el repositorio y antes de abrir el .pbip:

    python pbip/configurar_ruta.py              (escribe la ruta de tu copia local)
    python pbip/configurar_ruta.py --restaurar  (vuelve al marcador antes de hacer commit)

También puedes cambiar el parámetro a mano en Power BI Desktop: Transformar datos > Administrar parámetros > RutaDatos.
"""
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
DATOS = AQUI.parent / "datos_sinteticos"
EXPRESIONES = AQUI / "gestion-agua-demo.SemanticModel" / "definition" / "expressions.tmdl"
MARCADOR = "\\".join(["<RUTA_DEL_REPO>", "06-sustentabilidad-agua", "datos_sinteticos", ""])


def main():
    texto = EXPRESIONES.read_text(encoding="utf-8")
    nueva = MARCADOR if "--restaurar" in sys.argv else str(DATOS) + "\\"
    nuevo, n = re.subn(r'(expression RutaDatos = ")[^"]*(")', lambda m: m.group(1) + nueva + m.group(2), texto)
    if n != 1:
        sys.exit("No se encontró la expresión RutaDatos en expressions.tmdl")
    if not DATOS.is_dir() and "--restaurar" not in sys.argv:
        sys.exit(f"No existe la carpeta de datos: {DATOS}")
    EXPRESIONES.write_text(nuevo, encoding="utf-8", newline="\n")
    print("RutaDatos =", nueva)


if __name__ == "__main__":
    main()
