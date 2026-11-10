"""Valida los YAML de las pantallas de `app/pantallas/`.

Para cada pantalla informa: número de controles, nombres de control duplicados dentro de la pantalla y fórmulas con
paréntesis, corchetes o llaves desbalanceados (se ignoran los textos entre comillas y los comentarios //). Al final lista
los nombres de control repetidos entre pantallas (en Power Apps el nombre de cada control es único en toda la app).

Uso:  python validar_pantallas.py [carpeta_de_pantallas]
"""
import itertools
import re
import sys
from pathlib import Path

import yaml

PANTALLAS = (("scrInicio.yaml", "scrInicio"), ("scrVisor.yaml", "scrVisor"), ("scrEditor.yaml", "scrEditor"))


def revisar_formula(valor, contexto, malas):
    if not isinstance(valor, str):
        return
    s = re.sub(r'"(?:[^"]|"")*"', '""', valor)
    s = re.sub(r'//[^\n]*', '', s)
    for a, b in ("()", "[]", "{}"):
        if s.count(a) != s.count(b):
            malas.append((contexto, a, s.count(a), s.count(b)))


def recorrer(controles, nombres, malas):
    for control in controles:
        for nombre, cuerpo in control.items():
            nombres.append(nombre)
            for prop, valor in cuerpo.get("Properties", {}).items():
                revisar_formula(valor, f"{nombre}.{prop}", malas)
            if "Children" in cuerpo:
                recorrer(cuerpo["Children"], nombres, malas)


def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "pantallas"
    por_pantalla = {}
    for archivo, pantalla in PANTALLAS:
        datos = yaml.safe_load((base / archivo).read_text(encoding="utf-8"))
        scr = datos["Screens"][pantalla]
        nombres, malas = [], []
        recorrer(scr["Children"], nombres, malas)
        for prop, valor in scr["Properties"].items():
            revisar_formula(valor, f"scr.{prop}", malas)
        duplicados = sorted({n for n in nombres if nombres.count(n) > 1})
        print(archivo, "controles:", len(nombres), "| duplicados internos:", duplicados, "| desbalances:", malas)
        por_pantalla[archivo] = set(nombres)
    for a, b in itertools.combinations(por_pantalla, 2):
        print("repetidos", a, b, sorted(por_pantalla[a] & por_pantalla[b]))


if __name__ == "__main__":
    main()
