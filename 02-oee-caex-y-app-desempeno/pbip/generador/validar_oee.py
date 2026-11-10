# -*- coding: utf-8 -*-
"""Validación estática del PBIP «OEE CAEX Demo» (sin abrir Power BI Desktop).

Verifica:
  1. Cada tabla importada tiene su CSV en datos_sinteticos/oee/ con las mismas columnas y en el mismo orden que el TMDL.
  2. Las relaciones apuntan a columnas que existen y con el mismo tipo de dato.
  3. Toda referencia de las medidas DAX (Tabla[Columna], 'Tabla'[Columna] y [Medida]) existe en el modelo.
  4. Todo campo que usan los visuales (columnas, medidas, formato condicional, filtros) existe; ningún visual sale del lienzo;
     los botones de navegación apuntan a páginas del informe y las imágenes a recursos registrados.
  5. El id de página que usa el visor de la app (app/herramientas/gen_visor.py) es el de la página «OEE Transporte».

Con --consultas CARPETA escribe, para cada visual con datos, una consulta DAX (SUMMARIZECOLUMNS con sus campos, las medidas de su
formato condicional, sus filtros y el periodo elegido) para ejecutarla en la vista de consultas DAX de Power BI Desktop o en
DAX Studio y revisar filas, tiempos y medidas en blanco.

Uso:
    python pbip/generador/validar_oee.py
    python pbip/generador/validar_oee.py --consultas salida_consultas --periodo SEMANAL
Código de salida: 0 = sin problemas, 1 = hay problemas.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

NOMBRE = "OEE CAEX Demo"
RAIZ = Path(__file__).resolve().parent.parent
SM = RAIZ / f"{NOMBRE}.SemanticModel" / "definition"
INFORME = RAIZ / f"{NOMBRE}.Report" / "definition"
DATOS = RAIZ.parent / "datos_sinteticos" / "oee"
ANCHO, ALTO = 1280, 720


def sin_comillas(s):
    return s[1:-1].replace("''", "'") if s.startswith("'") else s


def leer_modelo():
    """Devuelve {tabla: {'columnas': [(nombre, dataType, sourceColumn)], 'medidas': {nombre: expr}, 'csv': bool}}."""
    modelo = {}
    for p in sorted((SM / "tables").glob("*.tmdl")):
        txt = p.read_text(encoding="utf-8").replace("\r\n", "\n")
        tabla = sin_comillas(re.search(r"(?m)^table (.+?)\s*$", txt).group(1))
        cols, medidas = [], {}
        bloques = re.split(r"(?m)^(?=\t(?:column|measure|partition|annotation) )", txt)
        for b in bloques:
            m = re.match(r"\tcolumn (.+?)(?: = .*)?\n", b)
            if m:
                tipo = re.search(r"\t\tdataType: (\w+)", b)
                src = re.search(r"\t\tsourceColumn: (.+)", b)
                cols.append((sin_comillas(m.group(1)), tipo.group(1) if tipo else None, src.group(1).strip() if src else None))
            m = re.match(r"\tmeasure (.+?) =(.*?)\n((?:\t\t\t.*\n|\n)*)", b)
            if m:
                expr = (m.group(2) + "\n" + m.group(3)).strip()
                medidas[sin_comillas(m.group(1))] = expr
        modelo[tabla] = {"columnas": cols, "medidas": medidas, "csv": "Csv.Document" in txt, "texto": txt}
    return modelo


def validar_csv(modelo, problemas):
    n = 0
    for tabla, d in modelo.items():
        if not d["csv"]:
            continue
        ruta = DATOS / f"{tabla}.csv"
        if not ruta.exists():
            problemas.append(f"CSV faltante: {ruta.name}")
            continue
        with ruta.open(encoding="utf-8", newline="") as f:
            cab = next(csv.reader(f))
        esperadas = [c[2] for c in d["columnas"] if c[2] and not c[2].startswith("[")]
        if cab != esperadas:
            problemas.append(f"{tabla}: columnas del CSV {cab} distintas de las del modelo {esperadas}")
        tipos = re.findall(r'\{"([^"]+)", (?:type \w+|Int64\.Type)\}', d["texto"].split("Tipos = ")[-1])
        if tipos != esperadas:
            problemas.append(f"{tabla}: los tipos de la partición M no cubren las columnas en orden")
        n += 1
    return n


def validar_relaciones(modelo, problemas):
    txt = (SM / "relationships.tmdl").read_text(encoding="utf-8")
    rels = re.findall(r"fromColumn: (.+)\n\s*toColumn: (.+)", txt.replace("\r\n", "\n"))
    for de, a in rels:
        tipos = []
        for ref in (de, a):
            tabla, _, columna = ref.strip().partition(".")
            tabla, columna = sin_comillas(tabla), sin_comillas(columna)
            fila = next((c for c in modelo.get(tabla, {}).get("columnas", []) if c[0] == columna), None)
            if fila is None:
                problemas.append(f"relación {de} -> {a}: no existe {ref}")
                break
            tipos.append(fila[1])
        else:
            if tipos[0] != tipos[1]:
                problemas.append(f"relación {de} -> {a}: tipos distintos {tipos}")
    return len(rels)


def validar_dax(modelo, problemas):
    todas = {m for d in modelo.values() for m in d["medidas"]}
    n = 0
    for tabla, d in modelo.items():
        for nombre, expr in d["medidas"].items():
            n += 1
            e = re.sub(r'"(?:[^"]|"")*"', '""', expr)
            for m in re.finditer(r"(?:'((?:[^']|'')+)'|\b([A-Za-z_]\w*))?\[([^\]]+)\]", e):
                tabla_ref = m.group(1) or m.group(2)
                objeto = m.group(3)
                if tabla_ref:
                    tabla_ref = tabla_ref.replace("''", "'")
                    if tabla_ref not in modelo:
                        problemas.append(f"medida '{nombre}': tabla desconocida {tabla_ref}")
                        continue
                    t = modelo[tabla_ref]
                    if objeto not in {c[0] for c in t["columnas"]} and objeto not in t["medidas"]:
                        problemas.append(f"medida '{nombre}': no existe {tabla_ref}[{objeto}]")
                elif objeto not in todas and not any(objeto == c[0] for t in modelo.values() for c in t["columnas"]):
                    problemas.append(f"medida '{nombre}': no existe [{objeto}]")
    return n


def campos_de(x, out):
    """Recorre un JSON PBIR y junta (tabla, propiedad, 'Measure'|'Column') de cada campo."""
    if isinstance(x, dict):
        for k in ("Measure", "Column"):
            v = x.get(k)
            if isinstance(v, dict) and "Property" in v:
                ent = v["Expression"]["SourceRef"].get("Entity")
                if ent:
                    out.append((ent, v["Property"], k))
        for v in x.values():
            campos_de(v, out)
    elif isinstance(x, list):
        for v in x:
            campos_de(v, out)
    return out


def cargar_visuales():
    paginas = {}
    for pj in sorted((INFORME / "pages").glob("*/page.json")):
        page = json.loads(pj.read_text(encoding="utf-8"))
        vis = [json.loads(v.read_text(encoding="utf-8")) for v in sorted((pj.parent / "visuals").glob("*/visual.json"))]
        paginas[page["name"]] = (page, vis)
    return paginas


def validar_informe(modelo, problemas):
    paginas = cargar_visuales()
    ids_paginas = set(paginas)
    reporte = json.loads((INFORME / "report.json").read_text(encoding="utf-8"))
    recursos = {i["name"] for p in reporte["resourcePackages"] if p["name"] == "RegisteredResources" for i in p["items"]}
    carpeta_rec = RAIZ / f"{NOMBRE}.Report" / "StaticResources" / "RegisteredResources"
    for r in recursos:
        if not (carpeta_rec / r).exists():
            problemas.append(f"recurso registrado sin archivo: {r}")
    nvis = 0
    for pid, (page, vis) in paginas.items():
        nombres = [v["name"] for v in vis]
        if len(nombres) != len(set(nombres)):
            problemas.append(f"{page['displayName']}: nombres de visual repetidos")
        for v in vis:
            nvis += 1
            etiqueta = f"{page['displayName']}/{v['name']}"
            for ent, prop, tipo in campos_de(v, []):
                t = modelo.get(ent)
                if t is None:
                    problemas.append(f"{etiqueta}: tabla desconocida {ent}")
                elif tipo == "Measure" and prop not in t["medidas"]:
                    problemas.append(f"{etiqueta}: no existe la medida {ent}[{prop}]")
                elif tipo == "Column" and prop not in {c[0] for c in t["columnas"]}:
                    problemas.append(f"{etiqueta}: no existe la columna {ent}[{prop}]")
            pos = v["position"]
            if pos["x"] < 0 or pos["y"] < 0 or pos["x"] + pos["width"] > ANCHO + 0.5 or pos["y"] + pos["height"] > ALTO + 0.5:
                problemas.append(f"{etiqueta}: fuera del lienzo {pos}")
            texto = json.dumps(v, ensure_ascii=False)
            for destino in re.findall(r"navigationSection.{0,40}?'([0-9a-f]{20})'", texto):
                if destino not in ids_paginas:
                    problemas.append(f"{etiqueta}: navega a una página que no existe ({destino})")
            for img in re.findall(r"\"ItemName\": \"([^\"]+)\"", texto):
                if img not in recursos:
                    problemas.append(f"{etiqueta}: imagen sin recurso registrado ({img})")
    # La app abre la primera página del informe: su id debe coincidir con el que usa el visor (gen_visor.py)
    visor = RAIZ.parent / "app" / "herramientas" / "gen_visor.py"
    if visor.exists():
        m = re.search(r"PBI_OEE_PAGINA\s*=\s*'([0-9a-f]{20})'", visor.read_text(encoding="utf-8"))
        primera = json.loads((INFORME / "pages" / "pages.json").read_text(encoding="utf-8"))["pageOrder"][0]
        if not m or m.group(1) != primera:
            problemas.append(f"gen_visor.py: PBI_OEE_PAGINA ({m.group(1) if m else 'no encontrado'}) no coincide con la página "
                             f"«OEE Transporte» del informe ({primera})")
    return len(paginas), nvis


# ---------------------------------------------------------------------------------------------------------------------
# Consultas DAX por visual
# ---------------------------------------------------------------------------------------------------------------------
def ref(tbl, prop):
    return f"'{tbl.replace(chr(39), chr(39) * 2)}'[{prop}]"


def literal(v):
    if v.startswith("'"):
        return '"' + v[1:-1].replace("''", "'").replace('"', '""') + '"'
    if v[-1:] in ("L", "D"):
        return v[:-1]
    return v.upper() if v in ("true", "false") else v


def medidas_en(x, out):
    if isinstance(x, dict):
        m = x.get("Measure")
        if isinstance(m, dict) and "Property" in m:
            r = ref(m["Expression"]["SourceRef"]["Entity"], m["Property"])
            if r not in out:
                out.append(r)
        for v in x.values():
            medidas_en(v, out)
    elif isinstance(x, list):
        for v in x:
            medidas_en(v, out)
    return out


def filtros(lista):
    """Filtros de columna (para SUMMARIZECOLUMNS) y, aparte, los de medida (se aplican después con FILTER)."""
    de_col, de_medida = [], []
    for f in lista or []:
        cond = f["filter"]["Where"][0]["Condition"]
        if "Measure" in f["field"]:
            c = cond["Comparison"]
            op = {0: "=", 1: ">", 2: ">=", 3: "<", 4: "<="}[c["ComparisonKind"]]
            m = f["field"]["Measure"]
            de_medida.append((ref(m["Expression"]["SourceRef"]["Entity"], m["Property"]), op, literal(c["Right"]["Literal"]["Value"])))
            continue
        col = f["field"]["Column"]
        r = ref(col["Expression"]["SourceRef"]["Entity"], col["Property"])
        vals = ", ".join(literal(v[0]["Literal"]["Value"]) for v in cond["In"]["Values"])
        de_col.append(f"TREATAS({{{vals}}}, {r})")
    return de_col, de_medida


def consulta(v, periodo):
    vis = v["visual"]
    qs = vis.get("query", {}).get("queryState", {})
    if not qs or vis["visualType"] == "slicer":
        return None
    grupos, meds = [], []
    for d in qs.values():
        for p in d["projections"]:
            k = next(iter(p["field"]))
            r = ref(p["field"][k]["Expression"]["SourceRef"]["Entity"], p["field"][k]["Property"])
            (grupos if k == "Column" else meds).append(r)
    medidas_en(vis.get("objects", {}), meds)
    fl = [f'TREATAS({{"{periodo}"}}, \'Periodo RD\'[Periodo])']
    de_col, de_medida = filtros(v.get("filterConfig", {}).get("filters"))
    fl += de_col
    defs = "\n".join(f"VAR __f{i} = {f}" for i, f in enumerate(fl))
    args = grupos + [f"__f{i}" for i in range(len(fl))] + [f'"m{i}", {m}' for i, m in enumerate(meds)]
    args += [f'"mf{i}", {m}' for i, (m, _, _) in enumerate(de_medida)]
    q = "SUMMARIZECOLUMNS(\n    " + ",\n    ".join(args) + "\n)"
    if de_medida:
        q = "FILTER(\n" + q + ",\n" + " && ".join(f"[mf{i}] {op} {val}" for i, (_, op, val) in enumerate(de_medida)) + ")"
    return f"DEFINE\n{defs}\nEVALUATE\n" + q


def escribir_consultas(carpeta, periodo):
    carpeta.mkdir(parents=True, exist_ok=True)
    n = 0
    for _, (page, vis) in cargar_visuales().items():
        for v in vis:
            c = consulta(v, periodo)
            if c:
                nombre = re.sub(r"[^A-Za-z0-9]+", "_", page["displayName"]) + "__" + v["name"] + ".dax"
                (carpeta / nombre).write_text(f"// {page['displayName']} · {v['visual']['visualType']} · periodo {periodo}\n{c}\n",
                                              encoding="utf-8", newline="\n")
                n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--consultas", help="carpeta donde escribir una consulta DAX por visual")
    ap.add_argument("--periodo", default="SEMANAL", choices=["JUE-DOM", "SEMANAL", "MENSUAL"])
    a = ap.parse_args()
    problemas = []
    modelo = leer_modelo()
    ncsv = validar_csv(modelo, problemas)
    nrel = validar_relaciones(modelo, problemas)
    nmed = validar_dax(modelo, problemas)
    npag, nvis = validar_informe(modelo, problemas)
    print(f"Tablas: {len(modelo)} ({ncsv} con CSV) · relaciones: {nrel} · medidas: {nmed} · páginas: {npag} · visuales: {nvis}")
    if a.consultas:
        print(f"Consultas DAX escritas: {escribir_consultas(Path(a.consultas), a.periodo)} en {a.consultas}")
    if problemas:
        print(f"PROBLEMAS: {len(problemas)}")
        for p in problemas:
            print("  -", p)
        return 1
    print("Problemas: ninguno")
    return 0


if __name__ == "__main__":
    sys.exit(main())
