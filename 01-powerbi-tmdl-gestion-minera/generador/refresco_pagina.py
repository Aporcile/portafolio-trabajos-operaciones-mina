# -*- coding: utf-8 -*-
"""
Refresco automático de página para un informe que se deja abierto en una pantalla de monitoreo.

Power BI solo ofrece el refresco automático de página (APR) si el modelo tiene una fuente DirectQuery; con todo en importación
la página abierta no se entera de que el modelo se actualizó. La receta:

  1. Tabla oculta `Rd Pulso`: una fila con la hora del servidor, sin leer ninguna tabla de negocio.
       --origen csv           (por defecto) partición de importación desde pulso.csv: sirve para abrir el proyecto de
                              ejemplo, pero NO activa el refresco automático (no hay DirectQuery).
       --origen directquery   partición DirectQuery contra el servidor ficticio `srv-despacho-demo`; cambia servidor y
                              base por los de tu entorno.
  2. En cada página, un visual pequeño e invisible (dentro de la barra del encabezado) que consulta [Rd Pulso Ahora]: así la
     página siempre tiene una consulta DirectQuery.
  3. pageRefresh en cada página: intervalo fijo (APR) de 10 minutos. Cada intervalo la página vuelve a consultar todos sus
     visuales y muestra los datos de la última actualización del modelo. En el servicio, el mínimo lo fija la capacidad.

Los datos nuevos siguen llegando con la actualización programada del modelo; este refresco solo hace que la página abierta los
muestre sin recargar.

    python generador/refresco_pagina.py                          # simulación
    python generador/refresco_pagina.py --aplicar                # escribe (Power BI Desktop debe estar cerrado)
    python generador/refresco_pagina.py --origen directquery --aplicar
    python generador/refresco_pagina.py --intervalo PT1M --aplicar   # ensayo: refresco cada minuto

Es idempotente: si la tabla, los visuales y el refresco ya están, no cambia nada.
"""
import argparse
import copy
import hashlib
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from escritura_segura import escribir  # noqa: E402
from guardia_desktop import desktop_abierto  # noqa: E402

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
TABLA = "Rd Pulso"
MEDIDA = "Rd Pulso Ahora"
MEDIDA_PLANTILLA = "Rd SVG Última Actualización"
COLOR_BARRA = "#1B2A41"          # color de la barra del encabezado: el visual del pulso se pinta de ese color y no se ve


def particion(origen):
    if origen == "directquery":
        return ("\tpartition 'Rd Pulso' = m\n\t\tmode: directQuery\n\t\tsource =\n\t\t\t\tlet\n"
                "\t\t\t\t    Origen = Sql.Database(\"srv-despacho-demo\", \"despacho_demo\", [Query = \"SELECT GETDATE() AS Ahora\"])\n"
                "\t\t\t\tin\n\t\t\t\t    Origen\n")
    return ("\tpartition 'Rd Pulso' = m\n\t\tmode: import\n\t\tsource =\n\t\t\t\tlet\n"
            "\t\t\t\t    Origen = Csv.Document(File.Contents(RutaDatos & \"pulso.csv\"), [Delimiter = \",\", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),\n"
            "\t\t\t\t    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),\n"
            "\t\t\t\t    Tipos = Table.TransformColumnTypes(Encabezados, {{\"Ahora\", type datetime}}, \"en-US\")\n"
            "\t\t\t\tin\n\t\t\t\t    Tipos\n")


def leer(p):
    with io.open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()


def volcar(d, raw):
    eol = "\r\n" if "\r\n" in raw else "\n"
    t = json.dumps(d, indent=2, ensure_ascii=False).replace("\n", eol)
    return t + eol if raw.endswith("\n") or not raw else t


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def color(c):
    return {"solid": {"color": lit(f"'{c}'")}}


def usa_medida(d, medida):
    s = json.dumps(d, ensure_ascii=False)
    return f'"Property": "{medida}"' in s


def visual_pulso(plantilla, vid, tab):
    d = copy.deepcopy(plantilla)
    d["name"] = vid
    d.pop("parentGroupName", None)
    d["position"] = {"x": 345, "y": 46, "z": 1, "height": 44, "width": 110, "tabOrder": tab}
    campo = {"Measure": {"Expression": {"SourceRef": {"Entity": TABLA}}, "Property": MEDIDA}}
    v = d["visual"]
    v["query"] = {"queryState": {"Values": {"projections": [
        {"field": campo, "queryRef": f"{TABLA}.{MEDIDA}", "nativeQueryRef": MEDIDA, "displayName": " "}]}}}
    o = v["objects"]
    g = o["grid"][0]["properties"]
    for k in ("imageHeight", "imageWidth"):
        g.pop(k, None)
    g["textSize"] = lit("8D")
    g["outlineColor"] = color(COLOR_BARRA)
    o["values"][0]["properties"] = {"fontColorPrimary": color(COLOR_BARRA), "backColorPrimary": color(COLOR_BARRA),
                                    "fontColorSecondary": color(COLOR_BARRA), "backColorSecondary": color(COLOR_BARRA)}
    v["visualContainerObjects"]["visualTooltip"] = [{"properties": {"show": lit("false")}}]
    return d


def refresco(intervalo):
    return [{"properties": {"show": lit("true"), "refreshType": lit("'APR'"), "duration": lit(f"'{intervalo}'")}}]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", default=str(RAIZ_PROYECTO))
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--origen", choices=("csv", "directquery"), default="csv")
    ap.add_argument("--intervalo", default="PT10M", help="intervalo ISO 8601 del refresco (por defecto PT10M)")
    a = ap.parse_args()
    raiz = Path(a.raiz).resolve()
    sm = next(raiz.glob("pbip/*.SemanticModel")) / "definition"
    rep = next(raiz.glob("pbip/*.Report")) / "definition"
    escrituras, nuevos, cambios = [], [], []
    # 1. tabla del pulso: solo se revisa/cambia la partición
    p_tabla = sm / "tables" / f"{TABLA}.tmdl"
    if not p_tabla.exists():
        raise RuntimeError(f"no existe {p_tabla.name}: crea la tabla con `{TABLA}` (columna Ahora) y la medida [{MEDIDA}]")
    t0 = leer(p_tabla)
    nueva = particion(a.origen)
    m = re.search(r"\tpartition 'Rd Pulso' = m\n.*?(?=\n\tannotation|\Z)", t0, re.S)
    if m is None:
        raise RuntimeError("no encuentro la partición de Rd Pulso")
    actual = m.group(0).rstrip("\n") + "\n"
    if actual != nueva:
        escrituras.append((p_tabla, t0, t0.replace(m.group(0), nueva.rstrip("\n"))))
        cambios.append(f"tables/{p_tabla.name}: partición {a.origen}")
    # 2 y 3. visual del pulso y refresco en cada página
    pages = json.loads(leer(rep / "pages" / "pages.json"))
    for n, pid in enumerate(pages["pageOrder"]):
        base = rep / "pages" / pid
        pagina = json.loads(leer(base / "page.json"))
        plantilla = None
        existe = False
        for vj in sorted((base / "visuals").glob("*/visual.json")):
            d = json.loads(leer(vj))
            if usa_medida(d, MEDIDA):
                existe = True
            if usa_medida(d, MEDIDA_PLANTILLA) and plantilla is None and d.get("visual", {}).get("visualType") == "tableEx":
                plantilla = d
        if not existe:
            if plantilla is None:
                raise RuntimeError(f"página {pagina['displayName']}: no hay visual plantilla ({MEDIDA_PLANTILLA})")
            vid = hashlib.sha1(f"pulso:{pid}".encode()).hexdigest()[:20]
            nuevo = json.dumps(visual_pulso(plantilla, vid, 90000 + n), indent=2, ensure_ascii=False) + "\n"
            nuevos.append((base / "visuals" / vid / "visual.json", nuevo))
            cambios.append(f"nuevo visual del pulso en {pagina['displayName']}")
        p_pag = base / "page.json"
        raw = leer(p_pag)
        d = json.loads(raw)
        if volcar(d, raw) != raw:
            raise RuntimeError(f"{p_pag}: el JSON no tiene el formato de Power BI Desktop")
        if d.setdefault("objects", {}).get("pageRefresh") != refresco(a.intervalo):
            d["objects"]["pageRefresh"] = refresco(a.intervalo)
            escrituras.append((p_pag, raw, volcar(d, raw)))
            cambios.append(f"{pagina['displayName']}: refresco automático cada {a.intervalo}")
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
    for p, contenido in nuevos:
        p.parent.mkdir(parents=True, exist_ok=True)
        with io.open(p, "x", encoding="utf-8", newline="") as f:
            f.write(contenido)
        print(f"{p.name}: creado")
    for p, raw, nuevo in escrituras:
        print(f"{p.name}: {escribir(str(p), raw, nuevo, newline='')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
