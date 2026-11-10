# -*- coding: utf-8 -*-
"""Utilidad opcional: parte los YAML grandes en trozos que no superan un tamaño máximo, cortando solo entre controles.

Sirve si al pegar un archivo muy grande Studio se pone lento o lo rechaza. Cada trozo queda con controles completos
(cada control empieza en una línea «- nombre:» sin sangría), así que se pueden pegar uno tras otro en el mismo orden.
Salida en ../yaml_trozos/ (no se versiona). 01_encabezado y 02_tablero_por_area se omiten por defecto: el primero lleva
los logos incrustados y el segundo es una sola galería; se pegan enteros.

Uso:  python trocear_yaml.py [bytes_maximos]      (por defecto 28000)
"""
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "yaml"
SALIDA = RAIZ / "yaml_trozos"
OMITIR = {"01_encabezado.yaml", "02_tablero_por_area.yaml"}


def trocear(texto, limite):
    bloques = [b for b in re.split(r"(?m)^(?=- )", texto) if b.strip()]
    trozos, actual = [], ""
    for b in bloques:
        if actual and len((actual + b).encode("utf-8")) > limite:
            trozos.append(actual)
            actual = ""
        actual += b
    if actual:
        trozos.append(actual)
    return trozos


def main():
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else 28000
    SALIDA.mkdir(exist_ok=True)
    indice = {}
    for ruta in sorted(ENTRADA.glob("*.yaml")):
        if ruta.name in OMITIR:
            continue
        trozos = trocear(ruta.read_text(encoding="utf-8"), limite)
        nombres = []
        for i, t in enumerate(trozos, 1):
            nombre = f"{ruta.stem}__{i}.yaml"
            (SALIDA / nombre).write_text(t, encoding="utf-8", newline="\n")
            nombres.append(nombre)
        indice[ruta.name] = nombres
        print(ruta.name, "->", len(trozos), "trozo(s)")
    (SALIDA / "indice.json").write_text(json.dumps(indice, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
