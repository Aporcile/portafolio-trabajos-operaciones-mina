# -*- coding: utf-8 -*-
"""Valida cada JSON del informe tal como está EN DISCO contra el esquema que declara en "$schema".

A diferencia de "generar_reporte.py --solo-validar" (que valida lo que el generador escribiría), esto revisa los
archivos reales, incluidos los que guarda Power BI Desktop (marcadores, visuales movidos, formato).

Uso:  python validar_disco.py [carpeta_del_proyecto] [--esquemas CARPETA]
Los esquemas se extraen de la instalación local de Power BI Desktop con extraer_esquemas.py (por defecto en
desarrollo/esquemas_pbir/, que no se versiona).

Sale con 0 si todo valida; con 1 si algún archivo no es un objeto JSON, no valida, no declara "$schema"
(obligatorio bajo definition/) o declara una versión de esquema MÁS NUEVA que las disponibles (Desktop se actualizó:
corre extraer_esquemas.py); con 3 si falta jsonschema o los esquemas (no se pudo validar). Una versión más ANTIGUA
que la instalación ya no trae solo da un aviso.
"""
import argparse
import json
import os
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AQUI = pathlib.Path(__file__).resolve().parent
PROYECTO = "Gobernanza_uso_reportes"
TEMPORALES = {"_gen_nuevo", "_gen_anterior"}  # restos de una corrida cortada de generar_reporte.py
VERSION = re.compile(r"/definition/([^/]+)/(\d+)\.(\d+)\.(\d+)/schema\.json$")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("proyecto", nargs="?", default=str(AQUI.parent))
    ap.add_argument("--esquemas", default=str(AQUI / "esquemas_pbir"))
    a = ap.parse_args()
    raiz = pathlib.Path(os.path.abspath(a.proyecto))
    carpeta_esquemas = pathlib.Path(a.esquemas)

    try:
        from jsonschema import Draft7Validator
        from referencing import Registry, Resource
    except ImportError:
        print("SIN JSONSCHEMA: no se validaron los esquemas (pip install jsonschema)")
        return 3
    if not carpeta_esquemas.is_dir() or not list(carpeta_esquemas.glob("*.json")):
        print(f"SIN ESQUEMAS: no hay esquemas en {carpeta_esquemas} (python extraer_esquemas.py)")
        return 3

    esquemas = {}
    for f in carpeta_esquemas.glob("*.json"):
        obj = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(obj, dict) and "$id" in obj:
            esquemas[obj["$id"]] = obj
    registro = Registry().with_resources([(k, Resource.from_contents(v)) for k, v in esquemas.items()])
    # El tema (StaticResources/RegisteredResources) no declara "$schema": se valida con el esquema de temas de Desktop,
    # que tampoco tiene $id (la versión más alta de reportThemeSchema-*.json)
    temas = sorted(carpeta_esquemas.glob("reportThemeSchema-*.json"), key=lambda f: [int(n) for n in re.findall(r"\d+", f.stem)])
    esquema_tema = json.loads(temas[-1].read_text(encoding="utf-8")) if temas else None
    # Versión más alta disponible de cada tipo de esquema (visualContainer, page, ...)
    maxima = {}
    for sid in esquemas:
        m = VERSION.search(sid)
        if m:
            v = tuple(int(x) for x in m.groups()[1:])
            maxima[m.group(1)] = max(maxima.get(m.group(1), v), v)

    dir_rep = raiz / f"{PROYECTO}.Report"
    if not dir_rep.is_dir():
        print(f"FALLA   no existe {dir_rep}")
        return 1
    avisos, fallos = [], []
    for t in sorted(TEMPORALES):
        if (dir_rep / t).exists():
            avisos.append(f"quedó la carpeta temporal {t}/ de una corrida cortada: la próxima corrida de "
                          "generar_reporte.py la limpia (o bórrala a mano)")
    # .pbi/ son ajustes locales de Desktop (sin esquema PBIR); las carpetas temporales no se validan
    archivos = sorted(p for p in dir_rep.rglob("*.json")
                      if not {".pbi"} & set(p.relative_to(dir_rep).parts) and not TEMPORALES & set(p.relative_to(dir_rep).parts))

    validados, sin_esquema = 0, []
    for p in archivos:
        rel = p.relative_to(raiz).as_posix()
        bajo_definition = "definition" in p.relative_to(dir_rep).parts
        try:
            obj = json.loads(p.read_text(encoding="utf-8-sig"))
        except (ValueError, UnicodeDecodeError) as e:
            fallos.append(f"{rel}: no es JSON válido ({e})")
            continue
        except OSError as e:
            fallos.append(f"{rel}: no se pudo leer ({e})")
            continue
        if not isinstance(obj, dict):
            fallos.append(f"{rel}: no es un objeto JSON")
            continue
        id_esquema = obj.get("$schema")
        if not isinstance(id_esquema, str) or not id_esquema:
            if bajo_definition:
                fallos.append(f"{rel}: falta \"$schema\" (obligatorio en definition/)")
            elif esquema_tema is not None and "RegisteredResources" in p.relative_to(dir_rep).parts:
                errores = sorted(Draft7Validator(esquema_tema).iter_errors(obj), key=lambda e: list(e.path))
                for e in errores[:5]:
                    fallos.append(f"{rel}: {'/'.join(str(x) for x in e.path) or '(raiz)'}: {e.message[:200]} (esquema de temas)")
                validados += 1
            else:
                sin_esquema.append(rel)
            continue
        esquema = esquemas.get(id_esquema)
        if esquema is None:
            m = VERSION.search(id_esquema)
            v = tuple(int(x) for x in m.groups()[1:]) if m else None
            if m and m.group(1) in maxima and v < maxima[m.group(1)]:
                avisos.append(f"{rel}: no validado, usa {m.group(1)} {'.'.join(map(str, v))}, una versión "
                              "anterior que esta instalación de Desktop ya no trae")
            else:
                fallos.append(f"{rel}: usa el esquema {id_esquema}, que no está entre los extraídos "
                              "(si Desktop se actualizó, corre: python extraer_esquemas.py --reemplazar)")
            continue
        errores = sorted(Draft7Validator(esquema, registry=registro).iter_errors(obj), key=lambda e: list(e.path))
        for e in errores[:5]:
            fallos.append(f"{rel}: {'/'.join(str(x) for x in e.path) or '(raiz)'}: {e.message[:200]}")
        validados += 1

    for aviso in avisos[:20]:
        print(f"AVISO   {aviso}")
    for f in fallos:
        print(f"FALLA   {f}")
    print(f"{validados} archivo(s) JSON validados en disco contra su esquema; "
          f"{len(sin_esquema)} sin esquema declarado; {len(avisos)} aviso(s); {len(fallos)} falla(s).")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
