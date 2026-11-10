# -*- coding: utf-8 -*-
"""
Tapa el texto de la imagen SVG que Power BI muestra al pasar el mouse por las tarjetas.

Una tabla (tableEx) con una medida `ImageUrl` muestra el texto de la imagen como tooltip nativo de la celda, y
`visualTooltip.show = false` no lo quita. La solución es poner encima de la tarjeta un botón transparente (sin acción ni
tooltip): el mouse toca el botón y no la celda.

Esta receta agrega ese botón sobre cada tarjeta SVG que no tiene uno.

Qué tapa: tableEx con una medida ImageUrl en su consulta, sin columnas (una tabla con columna, como las de destinos y fases,
filtra al hacer clic y un botón encima le quitaría el clic) y sin botón o forma encima (más del 50 % del área).
No toca los gráficos, los segmentadores ni las tarjetas que ya tienen botón.

El botón se llama `tapa_<id de la tabla>`, va en la misma posición (y grupo) y con z = z de la tabla + 1. Si la tabla se mueve
o cambia de tamaño, volver a correr la receta mueve su tapa.

    python generador/tapar_hover_svg.py                    # simulación
    python generador/tapar_hover_svg.py --aplicar          # escribe (Power BI Desktop debe estar cerrado)
    python generador/tapar_hover_svg.py --revertir --aplicar   # borra todas las tapas
    python generador/tapar_hover_svg.py --raiz RUTA        # otra copia del proyecto
"""
import argparse
import copy
import glob
import io
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from escritura_segura import escribir  # noqa: E402
from guardia_desktop import desktop_abierto  # noqa: E402

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
PREFIJO = "tapa_"
ESQUEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json"


def leer(p):
    with io.open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()


def _lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def _apagado(*objetos):
    return {o: [{"properties": {"show": _lit("false")}}] for o in objetos}


# botón transparente, sin visualLink: no navega ni muestra tooltip
BOTON = {
    "visualType": "actionButton",
    "objects": {
        "icon": [{"properties": {"shapeType": _lit("'blank'")}, "selector": {"id": "default"}}],
        "text": [{"properties": {"show": _lit("false")}, "selector": {"id": "default"}}],
        "fill": [{"properties": {"show": _lit("true"),
                                 "fillColor": {"solid": {"color": _lit("'#000000'")}},
                                 "transparency": _lit("100D")},
                  "selector": {"id": "default"}}],
        "outline": [{"properties": {"show": _lit("false")}}],
    },
    "visualContainerObjects": _apagado("title", "background", "border", "dropShadow", "visualHeader", "visualTooltip"),
    "drillFilterOtherVisuals": True,
}


def medidas_imagen(tablas_dir):
    """{(tabla, medida)} con dataCategory: ImageUrl en el TMDL."""
    img = set()
    for f in glob.glob(os.path.join(tablas_dir, "*.tmdl")):
        tabla = med = None
        for ln in leer(f).splitlines():
            m = re.match(r"^table\s+(?:'([^']+)'|(\S+))", ln)
            if m:
                tabla = m.group(1) or m.group(2)
            m = re.match(r"^\tmeasure\s+(?:'((?:[^']|'')+)'|([^\s=]+))", ln)
            if m:
                med = (m.group(1) or m.group(2)).replace("''", "'")
            elif re.match(r"^\t\S", ln):
                med = None
            if med and re.match(r"^\t\tdataCategory:\s*ImageUrl", ln):
                img.add((tabla, med))
    return img


def _refs(o, out):
    if isinstance(o, dict):
        for k in ("Measure", "Column"):
            if isinstance(o.get(k), dict) and "Property" in o[k]:
                out.append((k, o[k]["Expression"]["SourceRef"].get("Entity"), o[k]["Property"]))
        for v in o.values():
            _refs(v, out)
    elif isinstance(o, list):
        for v in o:
            _refs(v, out)


def planear(raiz, revertir):
    tablas = next(raiz.glob("pbip/*.SemanticModel")) / "definition" / "tables"
    pages = next(raiz.glob("pbip/*.Report")) / "definition" / "pages"
    img = medidas_imagen(str(tablas))
    if not img:
        raise RuntimeError(f"no encontré medidas ImageUrl en {tablas}")
    pend, resumen = [], []
    for pag in json.loads(leer(pages / "pages.json"))["pageOrder"]:
        nombre_pag = json.loads(leer(pages / pag / "page.json"))["displayName"]
        vs = {}
        for f in glob.glob(str(pages / pag / "visuals" / "*" / "visual.json")):
            t = leer(f)
            j = json.loads(t)
            vs[j["name"]] = (f, t, j)

        def absol(n):
            j = vs[n][2]
            x, y = j["position"]["x"], j["position"]["y"]
            g = j.get("parentGroupName")
            while g:
                x += vs[g][2]["position"]["x"]
                y += vs[g][2]["position"]["y"]
                g = vs[g][2].get("parentGroupName")
            return x, y, j["position"]["width"], j["position"]["height"]

        if revertir:
            for n, (f, t, j) in vs.items():
                if n.startswith(PREFIJO):
                    pend.append((f, t, None))
            continue
        botones = [absol(n) for n, (_, _, j) in vs.items()
                   if not n.startswith(PREFIJO) and j.get("visual", {}).get("visualType") in ("actionButton", "shape")]
        zs = set(j["position"].get("z") for n, (_, _, j) in vs.items() if not n.startswith(PREFIJO))
        esquema = next((j["$schema"] for _, _, j in vs.values()
                        if j.get("visual", {}).get("visualType") == "actionButton"), ESQUEMA)
        quedan = set(n for n in vs if n.startswith(PREFIJO))
        for n, (f, t, j) in sorted(vs.items()):
            v = j.get("visual", {})
            if n.startswith(PREFIJO) or v.get("visualType") != "tableEx":
                continue
            r = []
            _refs(v.get("query", {}), r)
            if not any(k == "Measure" and (e, p) in img for k, e, p in r):
                continue
            if any(k == "Column" for k, _, _ in r):
                continue        # filtra al hacer clic: un botón encima le quita el clic
            x, y, w, h = absol(n)
            tapada = False
            for bx, by, bw, bh in botones:
                ix = max(0, min(x + w, bx + bw) - max(x, bx))
                iy = max(0, min(y + h, by + bh) - max(y, by))
                if w * h and ix * iy / float(w * h) > 0.5:
                    tapada = True
            if tapada:
                continue
            tn = PREFIJO + n
            quedan.discard(tn)
            z = j["position"].get("z", 0) + 1
            while z in zs:
                z += 1
            pos = {"x": j["position"]["x"], "y": j["position"]["y"], "z": z,
                   "height": j["position"]["height"], "width": j["position"]["width"], "tabOrder": z}
            d = {"$schema": esquema, "name": tn, "position": pos, "visual": copy.deepcopy(BOTON)}
            if j.get("parentGroupName"):
                d["parentGroupName"] = j["parentGroupName"]
            p = str(pages / pag / "visuals" / tn / "visual.json")
            t0 = vs[tn][1] if tn in vs else None
            if t0 is not None:
                act = json.loads(t0)
                d["$schema"] = act.get("$schema", esquema)
                act["position"].pop("z", None)
                act["position"].pop("tabOrder", None)
                comp = copy.deepcopy(d)
                comp["position"].pop("z", None)
                comp["position"].pop("tabOrder", None)
                if act == comp:
                    continue    # Power BI Desktop renumera z / tabOrder al guardar: solo cuenta posición y contenido
                pos["z"], pos["tabOrder"] = json.loads(t0)["position"].get("z", z), json.loads(t0)["position"].get("tabOrder", z)
            eol = "\r\n" if t0 is not None and "\r\n" in t0 else "\n"
            pend.append((p, t0, json.dumps(d, indent=2, ensure_ascii=False).replace("\n", eol) + eol))
            resumen.append(f"{nombre_pag}: {n}")
        for tn in sorted(quedan):    # tapa cuya tabla ya no existe o ya no la necesita
            pend.append((vs[tn][0], vs[tn][1], None))
    return pend, resumen


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", default=str(RAIZ_PROYECTO))
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--revertir", action="store_true")
    a = ap.parse_args()
    raiz = Path(a.raiz).resolve()
    print(f"raíz: {raiz}")
    pend, resumen = planear(raiz, a.revertir)
    for r in resumen:
        print("  tapa: " + r)
    for p, t0, t1 in pend:
        print(f"  -> {os.path.relpath(p, raiz)}: {'crear' if t0 is None else ('borrar' if t1 is None else 'modificar')}")
    print(f"archivos a escribir: {len(pend)}")
    if not pend:
        print("sin cambios.")
        return 0
    if not a.aplicar:
        print("(simulación: no se escribió nada; agrega --aplicar)")
        return 0
    if desktop_abierto(str(raiz)):
        print("ABORTADO: Power BI Desktop tiene abierto un informe de esta carpeta. Guarda, cierra y vuelve a ejecutar.")
        return 1
    conflictos = 0
    for p, t0, t1 in pend:
        if t1 is None:
            os.remove(p)
            if not os.listdir(os.path.dirname(p)):
                os.rmdir(os.path.dirname(p))
        elif t0 is None:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with io.open(p, "w", encoding="utf-8", newline="") as f:
                f.write(t1)
        elif escribir(p, t0, t1, newline="") == "conflicto":
            print(f"  CONFLICTO (otro proceso lo cambió): {p}")
            conflictos += 1
    print("listo." if not conflictos else f"listo con {conflictos} conflictos.")
    return 1 if conflictos else 0


if __name__ == "__main__":
    sys.exit(main())
