# -*- coding: utf-8 -*-
"""Verificación estática de los YAML generados. No sustituye a Power Apps Studio, pero atrapa errores típicos antes de pegar.

Verifica:
  1. Que cada archivo sea YAML válido y que cada control tenga «Control» y «Properties».
  2. Que los nombres de controles sean únicos entre todos los archivos (todos van a la misma pantalla).
  3. Que cada propiedad sea una fórmula (empiece con «=») y tenga paréntesis, llaves y corchetes balanceados.
  4. Que las fórmulas solo usen las tablas y columnas del contrato (contrato.py).
  5. Que los logos incrustados (data URI) sean PNG válidos.

Uso:  python verificar_yaml.py [carpeta_yaml]
"""
import base64
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

import contrato

CARPETA = Path(__file__).resolve().parent.parent / "yaml"
TABLAS = set(contrato.TABLAS)
COLUMNAS = {c for cols in contrato.TABLAS.values() for c in cols} | set(contrato.COLUMNAS_CALCULADAS)
# Variables locales de las fórmulas (With, ForAll…) y de registros temporales
LOCALES = {"q", "r", "x", "a", "f", "c", "yy", "letras", "n", "nid", "nueva", "reg", "base"}
FUENTES_LOCALES = {"f", "base", "Acts", "ThisItem"}
R_TEXTO = re.compile(r'"(?:[^"]|"")*"')
# Primer argumento «simple» (un nombre, no una llamada anidada) de las funciones que operan sobre una fuente de datos
R_FUENTE = re.compile(r"\b(Filter|Patch|Remove|Refresh|Defaults|Errors|LookUp|Index)\(\s*([A-Za-z_]\w*)(?![\w(])")
R_COLUMNA_REG = re.compile(r"\b(ThisItem|varAct|varHL|varRev)\.(\w+)")
R_COLUMNA_X = re.compile(r"\bx\.(\w+)")
R_CLAVE_REGISTRO = re.compile(r"(?:^|[{,])\s*([A-Za-z_]\w*)\s*:(?!=)", re.M)
R_DATA_URI = re.compile(r'data:image/png;base64,([A-Za-z0-9+/=]+)')


def recorrer(controles, archivo, nombres, errores, formulas):
    for item in controles or []:
        if not isinstance(item, dict) or len(item) != 1:
            errores.append(f"{archivo}: elemento de lista inesperado: {str(item)[:60]}")
            continue
        nombre, cuerpo = next(iter(item.items()))
        nombres.append((nombre, archivo))
        if not isinstance(cuerpo, dict) or "Control" not in cuerpo or "Properties" not in cuerpo:
            errores.append(f"{archivo}: el control {nombre} no tiene Control/Properties")
            continue
        for prop, valor in cuerpo["Properties"].items():
            formulas.append((archivo, nombre, prop, str(valor)))
        recorrer(cuerpo.get("Children"), archivo, nombres, errores, formulas)


def revisar_formula(archivo, nombre, prop, valor, errores):
    donde = f"{archivo}:{nombre}.{prop}"
    if not valor.startswith("="):
        errores.append(f"{donde}: la propiedad no empieza con «=»")
        return
    for m in R_DATA_URI.finditer(valor):
        try:
            if not base64.b64decode(m.group(1))[:8].startswith(b"\x89PNG"):
                errores.append(f"{donde}: el data URI no es un PNG")
        except ValueError:
            errores.append(f"{donde}: base64 inválido")
    sin_texto = R_TEXTO.sub('""', valor)
    for a, b in ("()", "{}", "[]"):
        if sin_texto.count(a) != sin_texto.count(b):
            errores.append(f"{donde}: delimitadores {a}{b} desbalanceados")
    if sin_texto.count('"') % 2:
        errores.append(f"{donde}: comillas sin cerrar")
    for fn, fuente in R_FUENTE.findall(sin_texto):
        if fuente not in TABLAS and fuente not in FUENTES_LOCALES and not fuente.startswith("gal"):
            errores.append(f"{donde}: {fn}({fuente}…) no es una tabla del contrato")
    for obj, col in R_COLUMNA_REG.findall(sin_texto):
        validas = set(contrato.TABLAS["Actividades"]) if obj == "varAct" else COLUMNAS
        if col not in validas:
            errores.append(f"{donde}: {obj}.{col} no existe en el contrato")
    for col in R_COLUMNA_X.findall(sin_texto):
        if col not in contrato.TABLAS["Actividades"]:
            errores.append(f"{donde}: x.{col} no existe en Actividades")
    if "Patch(" in sin_texto:
        for clave in R_CLAVE_REGISTRO.findall(sin_texto):
            if clave not in COLUMNAS and clave not in LOCALES:
                errores.append(f"{donde}: la clave de registro «{clave}» no es una columna del contrato")


def verificar(carpeta=CARPETA):
    errores, nombres, formulas = [], [], []
    archivos = sorted(carpeta.glob("*.yaml"))
    if not archivos:
        return ["no hay archivos .yaml (ejecuta generar_todo.py primero)"], 0, 0
    for ruta in archivos:
        try:
            datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            errores.append(f"{ruta.name}: YAML inválido: {e}")
            continue
        if not isinstance(datos, list):
            errores.append(f"{ruta.name}: se esperaba una lista de controles")
            continue
        recorrer(datos, ruta.name, nombres, errores, formulas)
    for nombre, n in Counter(n for n, _ in nombres).items():
        if n > 1:
            errores.append(f"nombre de control repetido ({n} veces): {nombre}")
    for archivo, nombre, prop, valor in formulas:
        revisar_formula(archivo, nombre, prop, valor, errores)
    return errores, len(archivos), len(nombres)


def main():
    carpeta = Path(sys.argv[1]) if len(sys.argv) > 1 else CARPETA
    errores, n_archivos, n_controles = verificar(carpeta)
    print(f"Archivos: {n_archivos} | controles: {n_controles}")
    if errores:
        print(f"ERRORES: {len(errores)}")
        for e in errores[:80]:
            print("  -", e)
        return 1
    print("YAML OK: estructura, nombres únicos, fórmulas balanceadas y referencias al contrato")
    return 0


if __name__ == "__main__":
    sys.exit(main())
