# -*- coding: utf-8 -*-
"""
Modo «central de monitoreo»: el informe abre siempre en el día en curso.

  1. Los segmentadores de fecha (campo Calendario[Día Reporte]) quedan guardados en «Día actual» en vez de una fecha fija.
     «Día actual» es un rótulo constante que, en cada actualización del modelo, pasa al día de mina en curso: la selección
     guardada sigue al día nuevo sin volver a guardar el informe.
  2. report.json: settings.isPersistentUserStateDisabled = true. En el servicio los usuarios no guardan sus filtros y el
     informe abre como quedó guardado (Día actual), aunque alguien haya mirado otro día antes.
  3. pages.json: la página activa pasa a ser la primera de pageOrder.

Los segmentadores se buscan por contenido (visual `slicer` sobre Calendario[Día Reporte]), no por id.

    python generador/central_monitoreo.py                 # simulación
    python generador/central_monitoreo.py --aplicar       # escribe (Power BI Desktop debe estar cerrado)
    python generador/central_monitoreo.py --raiz RUTA     # otra copia del proyecto

Es idempotente. Edita los JSON por estructura y los vuelve a escribir con el mismo formato que Power BI Desktop (lo verifica
antes de tocar nada).
"""
import argparse
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from escritura_segura import escribir  # noqa: E402
from guardia_desktop import desktop_abierto  # noqa: E402

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
DIA_ACTUAL = "'Día actual'"
CAMPO_FECHA = "Día Reporte"


def leer(p):
    with io.open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()


def volcar(d, raw):
    eol = "\r\n" if "\r\n" in raw else "\n"
    t = json.dumps(d, indent=2, ensure_ascii=False).replace("\n", eol)
    return t + eol if raw.endswith("\n") else t


def cargar(p):
    raw = leer(p)
    d = json.loads(raw)
    if volcar(d, raw) != raw:
        raise RuntimeError(f"{p}: el JSON no tiene el formato de Power BI Desktop; no se toca a mano")
    return raw, d


def es_segmentador_de_fecha(d):
    v = d.get("visual", {})
    if v.get("visualType") != "slicer":
        return False
    return any(p.get("field", {}).get("Column", {}).get("Property") == CAMPO_FECHA
               for q in v.get("query", {}).get("queryState", {}).values() for p in q.get("projections", []))


def literal_del_filtro(d):
    """El literal guardado en el filtro del segmentador (`Día Reporte` In [[valor]])."""
    f = d["visual"]["objects"]["general"][0]["properties"]["filter"]["filter"]
    cond = f["Where"][0]["Condition"]["In"]
    if cond["Expressions"][0]["Column"]["Property"] != CAMPO_FECHA or len(cond["Values"]) != 1:
        raise RuntimeError("el segmentador no filtra un solo valor de Día Reporte")
    return cond["Values"][0][0]["Literal"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", default=str(RAIZ_PROYECTO))
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    raiz = Path(a.raiz).resolve()
    rep = next(raiz.glob("pbip/*.Report")) / "definition"
    pages_json = rep / "pages" / "pages.json"
    cambios, escrituras = [], []
    _, pages = cargar(pages_json)
    for pid in pages["pageOrder"]:
        nombre_pag = json.loads(leer(rep / "pages" / pid / "page.json"))["displayName"]
        for vj in sorted((rep / "pages" / pid / "visuals").glob("*/visual.json")):
            raw, d = cargar(vj)
            if not es_segmentador_de_fecha(d):
                continue
            lit = literal_del_filtro(d)
            if lit["Value"] != DIA_ACTUAL:
                cambios.append(f"segmentador de fecha de {nombre_pag}: {lit['Value']} -> {DIA_ACTUAL}")
                lit["Value"] = DIA_ACTUAL
                escrituras.append((vj, raw, volcar(d, raw)))
    report = rep / "report.json"
    raw, d = cargar(report)
    if d["settings"].get("isPersistentUserStateDisabled") is not True:
        d["settings"]["isPersistentUserStateDisabled"] = True
        cambios.append("report.json: filtros persistentes desactivados")
        escrituras.append((report, raw, volcar(d, raw)))
    raw, d = cargar(pages_json)
    if d["activePageName"] != d["pageOrder"][0]:
        cambios.append(f"pages.json: abre en la primera página (antes {d['activePageName']})")
        d["activePageName"] = d["pageOrder"][0]
        escrituras.append((pages_json, raw, volcar(d, raw)))
    print(f"raíz: {raiz}")
    if not cambios:
        print("sin cambios: ya estaba aplicado.")
        return 0
    for c in cambios:
        print("  " + c)
    if not a.aplicar:
        print("\n(simulación: no se escribió nada; agrega --aplicar)")
        return 0
    if desktop_abierto(str(raiz)):
        print("ABORTADO: Power BI Desktop tiene abierto un informe de esta carpeta. Guarda, cierra y vuelve a ejecutar.")
        return 2
    for p, raw, nuevo in escrituras:
        print(f"{p.relative_to(rep).as_posix()}: {escribir(str(p), raw, nuevo, newline='')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
