# -*- coding: utf-8 -*-
"""Valida report.json, pages.json, page.json y visual.json del informe PBIR contra los esquemas oficiales de Microsoft.

Los esquemas se descargan desde la URL que cada archivo declara en `$schema` (hace falta conexión a internet) y se validan con
`jsonschema`. Requiere: pip install jsonschema referencing

    python generador/validar_esquemas.py                      # todas las páginas del informe
    REDISENO_PAGINAS=id1,id2 python generador/validar_esquemas.py   # solo esas páginas (ids de carpeta)
    python generador/validar_esquemas.py --raiz RUTA
"""
import argparse
import glob
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from jsonschema.validators import validator_for
from referencing import Registry, Resource

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
_cache = {}


def bajar(uri):
    if uri not in _cache:
        with urllib.request.urlopen(uri, timeout=30) as r:
            _cache[uri] = json.loads(r.read().decode("utf-8"))
    return _cache[uri]


registro = Registry(retrieve=lambda uri: Resource.from_contents(bajar(uri)))


def validar(ruta):
    """Devuelve la lista de errores, o None si el esquema declarado todavía no está publicado (HTTP 404)."""
    doc = json.load(open(ruta, encoding="utf-8"))
    try:
        esquema = bajar(doc["$schema"])
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    val = validator_for(esquema)(esquema, registry=registro)
    return [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:180]}" for e in val.iter_errors(doc)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", default=str(RAIZ_PROYECTO))
    a = ap.parse_args()
    raiz = Path(a.raiz).resolve()
    rep = next(raiz.glob("pbip/*.Report")) / "definition"
    pages_json = rep / "pages" / "pages.json"
    with open(pages_json, encoding="utf-8-sig") as f:
        paginas = json.load(f).get("pageOrder", [])
    if os.environ.get("REDISENO_PAGINAS"):
        paginas = [p.strip() for p in os.environ["REDISENO_PAGINAS"].split(",") if p.strip()]
    archivos = [str(rep / "report.json"), str(pages_json)]
    for p in paginas:
        base = rep / "pages" / p
        archivos.append(str(base / "page.json"))
        archivos += sorted(glob.glob(str(base / "visuals" / "*" / "visual.json")))
    total = 0
    omitidos = 0
    for arch in archivos:
        errores = validar(arch)
        if errores is None:
            omitidos += 1
            continue
        total += len(errores)
        if errores:
            print("X", os.path.relpath(arch, raiz))
            for e in errores[:8]:
                print("     ", e)
    print(f"{len(archivos) - omitidos} archivos validados · {total} errores de esquema"
          + (f" · {omitidos} omitidos (su esquema declarado aún no está publicado)" if omitidos else ""))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
