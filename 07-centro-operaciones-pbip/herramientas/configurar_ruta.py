# -*- coding: utf-8 -*-
"""Fija el parámetro RutaDatos del modelo a la carpeta datos_sinteticos/ de tu copia local.

Power Query necesita una ruta absoluta para File.Contents. El repositorio trae el valor relativo `..\\datos_sinteticos\\`,
que no resuelve desde Power BI Desktop. Este script reescribe esa línea de expressions.tmdl con tu ruta; el cambio queda
solo en tu copia (no lo subas: usa --restaurar antes de hacer commit).

Uso:
  python herramientas/configurar_ruta.py              # fija RutaDatos a la carpeta local
  python herramientas/configurar_ruta.py --restaurar  # vuelve al valor por defecto
"""
import argparse
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EXPRESIONES = RAIZ / "pbip" / "CentroOperacionesDemo.SemanticModel" / "definition" / "expressions.tmdl"
POR_DEFECTO = "..\\datos_sinteticos\\"
PATRON = re.compile(r'^(expression RutaDatos = )"[^"\n]*"( meta \[)', re.M)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--restaurar", action="store_true", help="vuelve al valor relativo por defecto")
    a = ap.parse_args()
    valor = POR_DEFECTO if a.restaurar else str(RAIZ / "datos_sinteticos") + "\\"
    texto = EXPRESIONES.read_text(encoding="utf-8")
    nuevo, n = PATRON.subn(lambda m: f'{m.group(1)}"{valor}"{m.group(2)}', texto)
    if n != 1:
        print("No encontré el parámetro RutaDatos en expressions.tmdl", file=sys.stderr)
        return 1
    EXPRESIONES.write_text(nuevo, encoding="utf-8", newline="\n")
    print("RutaDatos =", valor)
    return 0


if __name__ == "__main__":
    sys.exit(main())
