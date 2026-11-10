# -*- coding: utf-8 -*-
"""Verificador de coherencia del proyecto PBIP (modelo TMDL + informe PBIR + datos sintéticos).

Verifica, sin necesidad de Power BI Desktop:
  1. JSON válido en todo el informe y el modelo (.json, .platform, .pbir, .pbip, .pbism).
  2. Modelo: cada `ref table` tiene su archivo, una partición por tabla, nombres únicos, relaciones con
     tablas/columnas existentes y tipos compatibles.
  3. DAX: toda referencia `Tabla[Columna]`, `[Medida]` o `'Tabla'` apunta a un objeto que existe; sin ciclos entre
     medidas; sin comentarios heredados.
  4. Datos: cada partición M lee un CSV que existe y cuyo encabezado contiene las columnas del modelo; los literales
     con los que el DAX filtra una columna (`Tabla[Col] = "valor"`, etiquetas de historiador) existen en el CSV.
  5. Informe: todos los campos de los visuales existen en el modelo, los ids de visual/grupo/interacción son
     coherentes y los recursos (logos, tema) existen.

Uso:
    python tools_proyecto/verificar_modelo.py                 # raíz = carpeta del proyecto
    python tools_proyecto/verificar_modelo.py --raiz RUTA     # otra copia del proyecto
Código de salida: 0 = todo coherente, 1 = hay errores.
"""
import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

RAIZ_DEF = Path(__file__).resolve().parent.parent
ERRORES = []
AVISOS = []


def err(donde, msg):
    ERRORES.append(f"[{donde}] {msg}")


def aviso(donde, msg):
    AVISOS.append(f"[{donde}] {msg}")


# ---------------------------------------------------------------------------------------------- JSON
def verificar_json(raiz):
    n = 0
    for p in sorted(raiz.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() in {".json", ".pbir", ".pbip", ".pbism"} or p.name == ".platform":
            n += 1
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                err(p.relative_to(raiz).as_posix(), f"JSON inválido: {e}")
    return n


# ---------------------------------------------------------------------------------------------- TMDL
R_OBJ = re.compile(r"^\t(measure|column|partition|hierarchy|annotation|calculationGroup)\s+(.*)$")
VIRTUALES_INTEGRADAS = {"value", "value1", "value2", "value3", "date", "item", "key"}


def nombre_y_resto(txt):
    txt = txt.strip()
    if txt.startswith("'"):
        i = 1
        while True:
            j = txt.index("'", i)
            if j + 1 < len(txt) and txt[j + 1] == "'":
                i = j + 2
                continue
            break
        return txt[1:j].replace("''", "'"), txt[j + 1:].strip()
    m = re.match(r"([^\s=:]+)(.*)$", txt)
    return m.group(1), m.group(2).strip()


class Objeto:
    def __init__(self, tipo, nombre, lineas):
        self.tipo, self.nombre, self.lineas = tipo, nombre, lineas

    def props(self):
        d = {}
        for l in self.lineas:
            m = re.match(r"^\t\t(\w+):\s*(.*)$", l)
            if m:
                d[m.group(1)] = m.group(2).strip()
        return d

    def expresion(self):
        """Texto de la expresión (medida/columna calculada) o '' si no tiene."""
        lin = self.lineas
        k = 0
        while lin[k].strip().startswith("///"):
            k += 1
        m = re.match(r"^\t(?:measure|column)\s+(?:'(?:[^']|'')+'|[^\s=:]+)\s*=(.*)$", lin[k])
        if not m:
            return ""
        partes = [m.group(1)]
        for l in lin[k + 1:]:
            if re.match(r"^\t\t(?!\t)", l):
                break
            partes.append(l)
        t = "\n".join(partes).strip()
        if t.startswith("```"):
            t = t[3:].rstrip()
            if t.endswith("```"):
                t = t[:-3]
        return t.strip()

    def fuente_particion(self):
        res, dentro = [], False
        for l in self.lineas:
            if not dentro:
                m = re.match(r"^\t\tsource\s*=(.*)$", l)
                if m:
                    dentro = True
                    if m.group(1).strip():
                        res.append(m.group(1))
                continue
            if re.match(r"^\t\t(?!\t)", l):
                break
            res.append(l)
        return "\n".join(res)


class Tabla:
    def __init__(self, ruta):
        self.ruta = ruta
        lineas = ruta.read_text(encoding="utf-8").split("\n")
        if lineas and lineas[-1] == "":
            lineas.pop()
        assert lineas[0].startswith("table "), ruta
        self.nombre = nombre_y_resto(lineas[0][6:])[0]
        self.objetos = []
        pend, cur = [], None
        for l in lineas[1:]:
            if l.startswith("\t") and not l.startswith("\t\t"):
                m = R_OBJ.match(l)
                if m:
                    cur = Objeto(m.group(1), nombre_y_resto(m.group(2))[0], pend + [l])
                    pend = []
                    self.objetos.append(cur)
                elif l.strip().startswith("///"):
                    pend.append(l)
                    cur = None
                else:
                    cur = None
            elif cur is not None:
                cur.lineas.append(l)

    def de_tipo(self, t):
        return [o for o in self.objetos if o.tipo == t]


def cargar_modelo(sm):
    tablas = {}
    for p in sorted((sm / "definition" / "tables").glob("*.tmdl")):
        t = Tabla(p)
        if t.nombre in tablas:
            err(p.name, f"tabla duplicada {t.nombre}")
        tablas[t.nombre] = t
    return tablas


def parsear_ref_columna(s):
    s = s.strip()
    if s.startswith("'"):
        i = 1
        while True:
            j = s.index("'", i)
            if j + 1 < len(s) and s[j + 1] == "'":
                i = j + 2
                continue
            break
        tabla, resto = s[1:j].replace("''", "'"), s[j + 1:]
    else:
        tabla, resto = s.split(".", 1)[0], "." + s.split(".", 1)[1]
    col = resto[1:]
    if col.startswith("'") and col.endswith("'"):
        col = col[1:-1].replace("''", "'")
    return tabla, col


# ---------------------------------------------------------------------------------------------- DAX
def segmentar(t):
    """(tipo, texto) con tipo en str, qid, br, com, code."""
    segs, buf = [], []
    i, n = 0, len(t)

    def volcar():
        if buf:
            segs.append(("code", "".join(buf)))
            buf.clear()

    while i < n:
        c = t[i]
        if c == '"' or c == "'":
            volcar()
            j = i + 1
            while j < n:
                if t[j] == c:
                    if j + 1 < n and t[j + 1] == c:
                        j += 2
                        continue
                    break
                j += 1
            segs.append(("str" if c == '"' else "qid", t[i:j + 1]))
            i = j + 1
        elif c == "[":
            volcar()
            j = t.find("]", i)
            segs.append(("br", t[i:j + 1]))
            i = j + 1
        elif t.startswith("--", i) or t.startswith("//", i):
            volcar()
            j = t.find("\n", i)
            j = n if j < 0 else j
            segs.append(("com", t[i:j]))
            i = j
        elif t.startswith("/*", i):
            volcar()
            j = t.find("*/", i + 2)
            j = n if j < 0 else j + 2
            segs.append(("com", t[i:j]))
            i = j
        else:
            buf.append(c)
            i += 1
    volcar()
    return segs


def referencias(expr):
    """Devuelve (tablas_calificadas [(tabla, nombre)], solo_corchetes [nombre], tablas_sueltas [nombre], literales [str],
    comentarios [str], pares_literal [(tabla, col, valor)])"""
    segs = segmentar(expr)
    cal, bare, sueltas, lits, coms, pares = [], [], [], [], [], []
    n = len(segs)
    for i, (k, s) in enumerate(segs):
        sig = segs[i + 1] if i + 1 < n else (None, None)
        if k == "com":
            coms.append(s)
        elif k == "str":
            lits.append(s[1:-1].replace('""', '"'))
        elif k == "qid":
            nom = s[1:-1].replace("''", "'")
            if sig[0] == "br":
                cal.append((nom, sig[1][1:-1]))
            else:
                sueltas.append(nom)
        elif k == "code":
            m = re.search(r"([A-Za-z_][A-Za-z0-9_]*)$", s)
            if sig[0] == "br" and m:
                cal.append((m.group(1), sig[1][1:-1]))
        elif k == "br":
            prev = segs[i - 1] if i > 0 else (None, None)
            prev_tabla = prev[0] == "qid" or (prev[0] == "code" and re.search(r"[A-Za-z0-9_]$", prev[1]))
            if not prev_tabla:
                bare.append(s[1:-1])
    # literales de igualdad: Tabla[Col] = "valor"
    plano = []
    for k, s in segs:
        plano.append(s if k != "com" else " ")
    txt = "".join(plano)
    for m in re.finditer(r"(?:'((?:[^']|'')+)'|([A-Za-z_][A-Za-z0-9_]*))\[([^\]]+)\]\s*=\s*\"((?:[^\"]|\"\")*)\"", txt):
        pares.append(((m.group(1) or m.group(2)).replace("''", "'"), m.group(3), m.group(4).replace('""', '"')))
    return cal, bare, sueltas, lits, coms, pares


R_ETIQUETA = re.compile(r"^[A-Z][A-Z0-9_]*(\.[A-Z0-9_]+)+$")


def verificar_dax(tablas, datos):
    etiquetas = datos.etiquetas()
    medidas = {}
    for t in tablas.values():
        for o in t.de_tipo("measure"):
            if o.nombre.lower() in medidas:
                err(t.nombre, f"medida duplicada: {o.nombre}")
            medidas[o.nombre.lower()] = (t.nombre, o)
    columnas = {(t.nombre.lower(), o.nombre.lower()) for t in tablas.values() for o in t.de_tipo("column")}
    tablas_l = {n.lower(): n for n in tablas}
    nombres_tabla_funcion = set()  # identificadores sueltos que no son tablas (palabras clave, VAR, etc.)
    grafo = defaultdict(set)
    n_expr = 0
    for t in tablas.values():
        items = [(o, "medida") for o in t.de_tipo("measure")] + [(o, "columna") for o in t.de_tipo("column")]
        for o in t.de_tipo("partition"):
            if re.search(r"=\s*calculated", o.lineas[0]):
                items.append((o, "partición"))
        for o, clase in items:
            expr = o.fuente_particion() if clase == "partición" else o.expresion()
            if not expr:
                continue
            n_expr += 1
            donde = f"{t.nombre}::{o.nombre}"
            cal, bare, sueltas, lits, coms, pares = referencias(expr)
            if coms:
                err(donde, f"comentario en el DAX ({coms[0][:40]!r}): el repositorio no conserva comentarios históricos")
            virtuales = {x.lower() for x in lits} | VIRTUALES_INTEGRADAS
            for tabla, nom in cal:
                tl = tablas_l.get(tabla.lower())
                if tl is None:
                    err(donde, f"referencia a tabla inexistente: {tabla}[{nom}]")
                    continue
                if (tl.lower(), nom.lower()) in columnas:
                    continue
                if nom.lower() in medidas:
                    if clase == "medida":
                        grafo[(t.nombre, o.nombre)].add(nom.lower())
                    continue
                if nom.lower() in virtuales:
                    continue
                err(donde, f"columna o medida inexistente: {tabla}[{nom}]")
            for nom in bare:
                if nom.lower() in medidas:
                    if clase == "medida":
                        grafo[(t.nombre, o.nombre)].add(nom.lower())
                    continue
                if (t.nombre.lower(), nom.lower()) in columnas or nom.lower() in virtuales:
                    continue
                err(donde, f"referencia sin resolver: [{nom}]")
            # tablas entre comillas usadas como argumento: ALL ( 'Tabla' ), REMOVEFILTERS ( 'Tabla' )
            for nom in set(sueltas):
                if nom.lower() not in tablas_l:
                    err(donde, f"referencia a tabla inexistente: '{nom}'")
            # etiquetas de historiador: todo literal con forma de etiqueta debe existir en los datos
            for lit in set(lits):
                if R_ETIQUETA.match(lit) and lit not in etiquetas:
                    err(donde, f"etiqueta \"{lit}\" sin datos en los CSV")
            # literales de filtro contra los datos
            for tabla, col, val in pares:
                tl = tablas_l.get(tabla.lower())
                if tl is None:
                    continue
                vals = datos.valores(tl, col)
                if vals is not None and val not in vals:
                    err(donde, f"el DAX filtra {tl}[{col}] = \"{val}\" pero ese valor no existe en el CSV")
    # ciclos entre medidas
    estado = {}

    def dfs(k, pila):
        estado[k] = 1
        for dep in grafo.get(k, ()):
            kd = (medidas[dep][0], medidas[dep][1].nombre)
            if estado.get(kd) == 1:
                err("DAX", f"ciclo entre medidas: {' -> '.join(pila + [kd[1]])}")
            elif kd not in estado:
                dfs(kd, pila + [kd[1]])
        estado[k] = 2

    for k in list(grafo):
        if k not in estado:
            dfs(k, [k[1]])
    return medidas, columnas, n_expr


# ---------------------------------------------------------------------------------------------- datos
class Datos:
    """Acceso perezoso a los CSV del proyecto, indexados por tabla del modelo."""

    def __init__(self, carpeta):
        self.carpeta = carpeta
        self.tabla_csv = {}
        self._cache = {}

    def registrar(self, tabla, archivo):
        self.tabla_csv[tabla] = archivo

    def encabezado(self, archivo):
        p = self.carpeta / archivo
        if not p.exists():
            return None
        with p.open(encoding="utf-8", newline="") as f:
            return next(csv.reader(f), [])

    def etiquetas(self):
        """Unión de los valores de las columnas que identifican señales o puntos (nombre_tag, dim_variable.name, Punto)."""
        out = set()
        for tabla in self.tabla_csv:
            for col in ("nombre_tag", "dim_variable.name", "Punto"):
                v = self.valores(tabla, col)
                if v:
                    out |= v
        return out

    def valores(self, tabla, col):
        archivo = self.tabla_csv.get(tabla)
        if not archivo:
            return None
        clave = (archivo, col)
        if clave not in self._cache:
            p = self.carpeta / archivo
            if not p.exists():
                return None
            with p.open(encoding="utf-8", newline="") as f:
                rd = csv.DictReader(f)
                if col not in (rd.fieldnames or []):
                    self._cache[clave] = None
                else:
                    self._cache[clave] = {r[col] for r in rd}
        return self._cache[clave]


def verificar_particiones(tablas, datos_dir, datos):
    for t in tablas.values():
        ps = t.de_tipo("partition")
        if len(ps) != 1:
            err(t.nombre, f"se esperaba 1 partición y hay {len(ps)}")
            continue
        p = ps[0]
        cols = [(o.nombre, o.props()) for o in t.de_tipo("column")]
        if re.search(r"=\s*m\b", p.lineas[0]):
            src = p.fuente_particion()
            if re.search(r"Sql\.Database|OData\.Feed|Excel\.Workbook|SharePoint|AnalysisServices|Web\.Contents", src):
                err(t.nombre, "la partición lee una fuente real; debe leer un CSV sintético")
            m = re.search(r'File\.Contents\(\s*RutaDatos\s*&\s*"([^"]+)"', src)
            if not m:
                err(t.nombre, "la partición M no lee un CSV a través del parámetro RutaDatos")
                continue
            archivo = m.group(1)
            datos.registrar(t.nombre, archivo)
            enc = datos.encabezado(archivo)
            if enc is None:
                err(t.nombre, f"no existe datos_sinteticos/{archivo}")
                continue
            derivadas = set(re.findall(r'Table\.AddColumn\([^,]+,\s*"([^"]+)"', src))
            for nombre, pr in cols:
                sc = pr.get("sourceColumn")
                if sc is None:
                    continue  # columna calculada
                if sc not in enc and sc not in derivadas:
                    err(t.nombre, f"la columna '{nombre}' (sourceColumn {sc}) no está en {archivo}: {enc}")
        else:
            if re.search(r"Sql\.Database", p.fuente_particion()):
                err(t.nombre, "partición calculada con fuente real")


def verificar_modelo(raiz, datos_dir):
    sm = next(raiz.glob("pbip/*.SemanticModel"), None)
    if sm is None:
        err("modelo", "no encuentro pbip/*.SemanticModel")
        return None, None, None
    tablas = cargar_modelo(sm)
    # model.tmdl
    model = (sm / "definition" / "model.tmdl").read_text(encoding="utf-8")
    refs = [nombre_y_resto(l[len("ref table "):])[0] for l in model.split("\n") if l.startswith("ref table ")]
    for r in refs:
        if r not in tablas:
            err("model.tmdl", f"`ref table {r}` sin archivo en tables/")
    for n in tablas:
        if n not in refs:
            err("model.tmdl", f"la tabla {n} no está en `ref table`")
    m = re.search(r"PBI_QueryOrder = (\[.*\])", model)
    if m:
        for q in json.loads(m.group(1)):
            if q not in tablas and q != "RutaDatos":
                err("model.tmdl", f"PBI_QueryOrder menciona {q}, que no existe")
    if "ref expression RutaDatos" not in model or not (sm / "definition" / "expressions.tmdl").exists():
        err("model.tmdl", "falta el parámetro RutaDatos")
    # relaciones
    rel = (sm / "definition" / "relationships.tmdl").read_text(encoding="utf-8")
    tipos = {}
    for t in tablas.values():
        for o in t.de_tipo("column"):
            tipos[(t.nombre, o.nombre)] = o.props().get("dataType", "(calculada)")
    n_rel = 0
    for bloque in re.split(r"\n(?=relationship )", rel.strip()):
        if not bloque.strip():
            continue
        n_rel += 1
        d = dict(re.findall(r"^\t(\w+):\s*(.*)$", bloque, re.M))
        ids = []
        for k in ("fromColumn", "toColumn"):
            t, c = parsear_ref_columna(d[k])
            if t not in tablas or (t, c) not in tipos:
                err("relationships.tmdl", f"{k} apunta a algo que no existe: {t}.{c}")
            ids.append((t, c))
        if len(ids) == 2 and all(i in tipos for i in ids):
            a, b = tipos[ids[0]], tipos[ids[1]]
            if "(calculada)" not in (a, b) and a != b:
                err("relationships.tmdl", f"tipos distintos en la relación {ids[0]} ({a}) -> {ids[1]} ({b})")
    datos = Datos(datos_dir)
    verificar_particiones(tablas, datos_dir, datos)
    medidas, columnas, n_expr = verificar_dax(tablas, datos)
    # etiquetas de historiador usadas como literales
    return tablas, (medidas, columnas, n_rel, n_expr), datos


# ---------------------------------------------------------------------------------------------- informe
def campos_visual(d):
    out = []

    def walk(o, alias):
        if isinstance(o, dict):
            al = dict(alias)
            if isinstance(o.get("From"), list):
                for f in o["From"]:
                    if isinstance(f, dict) and "Name" in f and "Entity" in f:
                        al[f["Name"]] = f["Entity"]
            for k, v in o.items():
                if k in ("Measure", "Column", "HierarchyLevel") and isinstance(v, dict) and "Property" in v:
                    sr = v.get("Expression", {}).get("SourceRef", {})
                    out.append((k, sr.get("Entity") or al.get(sr.get("Source")), v["Property"]))
                walk(v, al)
        elif isinstance(o, list):
            for x in o:
                walk(x, alias)

    walk(d, {})
    return out


def verificar_informe(raiz, tablas, medidas):
    rp = next(raiz.glob("pbip/*.Report"), None)
    if rp is None:
        err("informe", "no encuentro pbip/*.Report")
        return 0, 0
    df = rp / "definition"
    pages = json.loads((df / "pages" / "pages.json").read_text(encoding="utf-8"))
    ids_pagina = []
    n_vis = 0
    n_campos = 0
    nombres_medida = {(t.nombre, o.nombre) for t in tablas.values() for o in t.de_tipo("measure")}
    nombres_col = {(t.nombre, o.nombre) for t in tablas.values() for o in t.de_tipo("column")}
    for pj in sorted((df / "pages").glob("*/page.json")):
        page = json.loads(pj.read_text(encoding="utf-8"))
        pid = page["name"]
        ids_pagina.append(pid)
        if pj.parent.name != pid:
            err(pj.parent.name, "el nombre de carpeta no coincide con page.json:name")
        vis = {}
        for vj in sorted((pj.parent / "visuals").glob("*/visual.json")):
            v = json.loads(vj.read_text(encoding="utf-8"))
            n_vis += 1
            if v["name"] != vj.parent.name:
                err(vj.parent.name, "el nombre de carpeta no coincide con visual.json:name")
            if v["name"] in vis:
                err(page["displayName"], f"visual duplicado {v['name']}")
            vis[v["name"]] = v
        for nom, v in vis.items():
            g = v.get("parentGroupName")
            if g and g not in vis:
                err(f"{page['displayName']}/{nom}", f"parentGroupName {g} no existe en la página")
            for k, ent, prop in campos_visual(v):
                n_campos += 1
                if ent is None:
                    err(f"{page['displayName']}/{nom}", f"campo sin entidad: {prop}")
                elif k == "Measure" and (ent, prop) not in nombres_medida:
                    err(f"{page['displayName']}/{nom}", f"medida inexistente: {ent}[{prop}]")
                elif k == "Column" and (ent, prop) not in nombres_col:
                    if (ent, prop) in nombres_medida:
                        err(f"{page['displayName']}/{nom}", f"{ent}[{prop}] es una medida usada como columna")
                    else:
                        err(f"{page['displayName']}/{nom}", f"columna inexistente: {ent}[{prop}]")
            for proj in re.findall(r'"queryRef":\s*"([^"]+)"', json.dumps(v, ensure_ascii=False)):
                ent = proj.split(".", 1)[0]
                if "(" not in proj and ent not in tablas and not proj.startswith(("Sum(", "Min(", "Max(")):
                    err(f"{page['displayName']}/{nom}", f"queryRef con tabla inexistente: {proj}")
        for it in page.get("visualInteractions", []):
            for k in ("source", "target"):
                if it[k] not in vis:
                    err(page["displayName"], f"visualInteractions.{k} apunta a un visual que no existe: {it[k]}")
    for p in pages["pageOrder"]:
        if p not in ids_pagina:
            err("pages.json", f"pageOrder menciona la página {p}, que no existe")
    if pages["activePageName"] not in pages["pageOrder"]:
        err("pages.json", "activePageName no está en pageOrder")
    for p in ids_pagina:
        if p not in pages["pageOrder"]:
            err("pages.json", f"la página {p} existe pero no está en pageOrder")
    # recursos
    rj = json.loads((df / "report.json").read_text(encoding="utf-8"))
    for pk in rj.get("resourcePackages", []):
        base = rp / "StaticResources" / pk["name"]
        for it in pk.get("items", []):
            if not (base / it["path"]).exists():
                err("report.json", f"recurso inexistente: {pk['name']}/{it['path']}")
    declarados = {it["name"] for pk in rj.get("resourcePackages", []) for it in pk.get("items", [])}
    for vj in (df / "pages").glob("*/visuals/*/visual.json"):
        for item in re.findall(r'"ItemName":\s*"([^"]+)"', vj.read_text(encoding="utf-8")):
            if item not in declarados:
                err(vj.parent.name, f"imagen {item} no declarada en report.json")
    if "filterConfig" in rj:
        for f in rj["filterConfig"].get("filters", []):
            ent = f.get("field", {}).get("Column", {}).get("Expression", {}).get("SourceRef", {}).get("Entity")
            if ent and ent not in tablas:
                err("report.json", f"filtro de informe sobre tabla inexistente: {ent}")
    pbir = json.loads((rp / "definition.pbir").read_text(encoding="utf-8"))
    ruta = (rp / pbir["datasetReference"]["byPath"]["path"]).resolve()
    if not ruta.exists():
        err("definition.pbir", f"datasetReference apunta a una carpeta inexistente: {ruta.name}")
    return n_vis, n_campos


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", default=str(RAIZ_DEF))
    a = ap.parse_args()
    raiz = Path(a.raiz).resolve()
    datos_dir = raiz / "datos_sinteticos"
    n_json = verificar_json(raiz / "pbip")
    tablas, extra, datos = verificar_modelo(raiz, datos_dir)
    n_vis = n_campos = 0
    if tablas is not None:
        medidas, columnas, n_rel, n_expr = extra
        n_vis, n_campos = verificar_informe(raiz, tablas, medidas)
        print(f"JSON válidos: {n_json} | tablas: {len(tablas)} | medidas: {len(medidas)} | relaciones: {n_rel} "
              f"| expresiones DAX revisadas: {n_expr} | visuales: {n_vis} | campos de visual: {n_campos}")
    for a_ in AVISOS:
        print("AVISO", a_)
    if ERRORES:
        print(f"ERRORES: {len(ERRORES)}")
        for e in ERRORES[:80]:
            print("  ", e)
        return 1
    print("MODELO COHERENTE: 0 errores")
    return 0


if __name__ == "__main__":
    sys.exit(main())
