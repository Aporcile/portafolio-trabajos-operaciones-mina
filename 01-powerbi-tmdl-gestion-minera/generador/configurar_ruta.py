# -*- coding: utf-8 -*-
"""
Fija el parámetro `RutaDatos` del modelo a la carpeta `datos_sinteticos/` de ESTA copia del proyecto.

Power Query necesita una ruta absoluta para `File.Contents`, y cada persona clona el repositorio en una carpeta distinta. El
modelo trae el valor por defecto `datos_sinteticos\\` (relativo, que no resuelve); esta receta lo reemplaza por la ruta
absoluta local, con la barra final. El cambio queda solo en tu copia: no lo subas al repositorio (`--restaurar` lo deja como
estaba).

Alternativa sin script: en Power BI Desktop, Transformar datos > Administrar parámetros > RutaDatos.

    python generador/configurar_ruta.py              # fija la ruta absoluta local
    python generador/configurar_ruta.py --restaurar  # vuelve al valor relativo por defecto
"""
import argparse
import re
import sys
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
PATRON = re.compile(r'^(expression RutaDatos = )"[^"]*"(.*)$', re.M)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", default=str(RAIZ_PROYECTO))
    ap.add_argument("--restaurar", action="store_true")
    a = ap.parse_args()
    raiz = Path(a.raiz).resolve()
    arch = next(raiz.glob("pbip/*.SemanticModel")) / "definition" / "expressions.tmdl"
    t = arch.read_text(encoding="utf-8")
    valor = "datos_sinteticos\\" if a.restaurar else str(raiz / "datos_sinteticos") + "\\"
    nuevo, n = PATRON.subn(lambda m: f'{m.group(1)}"{valor}"{m.group(2)}', t, count=1)
    if n != 1:
        print("no encontré el parámetro RutaDatos en expressions.tmdl")
        return 1
    arch.write_text(nuevo, encoding="utf-8", newline="\n")
    print(f"RutaDatos = {valor}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
