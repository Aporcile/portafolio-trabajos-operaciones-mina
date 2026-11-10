# -*- coding: utf-8 -*-
"""Verificador de coherencia del proyecto (modelo TMDL + reporte PBIR + CSV sintéticos).

No necesita Power BI Desktop. Valida, con la biblioteca estándar:
  1. JSON válido en todos los archivos del reporte y del modelo (.json, .pbir, .pbip, .pbism, .platform).
  2. Modelo: tablas, columnas y medidas únicas; cada `ref table` tiene su archivo; lineageTag sin repetirse.
  3. DAX: toda referencia `Tabla[Columna]` y `[Medida]` existe; los literales comparados contra columnas de
     catálogo (Tipo, Medicion, Fuente, Parametro, Sistema...) existen en los CSV.
  4. Particiones: el CSV existe y su encabezado coincide con las columnas del modelo y con el cambio de tipos de M.
  5. Relaciones: columnas existentes, clave única en el lado «uno» e integridad referencial en los CSV.
  6. Reporte: páginas y carpetas consistentes; cada campo de cada visual (proyecciones, filtros, orden, formato
     condicional) apunta a una columna o medida que existe del tipo correcto; los selectores `metadata` y los
     filtros por valor coinciden con proyecciones y datos; los recursos (logos, tema) existen.

Uso:
    python tools/verificar_coherencia.py            (desde la raíz del proyecto o cualquier carpeta)
Código de salida: 0 = coherente, 1 = hay errores.
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PBIP = RAIZ / "pbip"
DATOS = RAIZ / "datos_sinteticos"
errores = []
avisos = []


def err(msg):
    errores.append(msg)


# --------------------------------------------------------------------------------------------
# 1. JSON válido
# --------------------------------------------------------------------------------------------
def cargar_json(ruta):
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        err(f"JSON inválido: {ruta.relative_to(RAIZ).as_posix()} ({e})")
        return None


n_json = 0
for p in sorted(PBIP.rglob("*")):
    if p.is_file() and (p.suffix in {".json", ".pbir", ".pbip", ".pbism"} or p.name == ".platform"):
        n_json += 1
        cargar_json(p)

# --------------------------------------------------------------------------------------------
# 2. Modelo semántico (TMDL)
# --------------------------------------------------------------------------------------------
carpetas_modelo = list(PBIP.glob("*.SemanticModel"))
carpetas_reporte = list(PBIP.glob("*.Report"))
if len(carpetas_modelo) != 1 or len(carpetas_reporte) != 1:
    print("ERROR: se esperaba un SemanticModel y un Report en pbip/")
    sys.exit(1)
MODELO = carpetas_modelo[0] / "definition"
REPORTE = carpetas_reporte[0]


def nombre_tmdl(s):
    s = s.strip()
    return s[1:-1].replace("''", "'") if s.startswith("'") else s


class Tabla:
    def __init__(self, nombre):
        self.nombre = nombre
        self.columnas = {}       # nombre -> dict(dataType, sourceColumn, oculta)
        self.medidas = {}        # nombre -> expresión
        self.particion = ""      # texto de la partición
        self.tipo_part = ""
        self.lineage = []


def parsear_tabla(ruta):
    lineas = ruta.read_text(encoding="utf-8").split("\n")
    t = None
    i = 0
    while i < len(lineas):
        l = lineas[i]
        m = re.match(r"^table (.+)$", l)
        if m:
            t = Tabla(nombre_tmdl(m.group(1)))
        elif t is not None:
            m = re.match(r"^\tcolumn (.+)$", l)
            if m:
                nombre = nombre_tmdl(m.group(1).split(" = ")[0])
                props = {}
                i += 1
                while i < len(lineas) and (lineas[i].startswith("\t\t") or lineas[i] == ""):
                    s = lineas[i].strip()
                    if s.startswith("dataType:"):
                        props["dataType"] = s.split(":", 1)[1].strip()
                    elif s.startswith("sourceColumn:"):
                        props["sourceColumn"] = s.split(":", 1)[1].strip()
                    elif s == "isHidden":
                        props["oculta"] = True
                    elif s.startswith("sortByColumn:"):
                        props["sortBy"] = nombre_tmdl(s.split(":", 1)[1])
                    elif s.startswith("lineageTag:"):
                        t.lineage.append(s.split(":", 1)[1].strip())
                    if lineas[i] == "" and i + 1 < len(lineas) and not lineas[i + 1].startswith("\t\t"):
                        break
                    i += 1
                t.columnas[nombre] = props
                continue
            m = re.match(r"^\tmeasure (.+?) =\s*(.*)$", l)
            if m:
                nombre = nombre_tmdl(m.group(1))
                cuerpo = [m.group(2)]
                i += 1
                while i < len(lineas) and lineas[i].startswith("\t\t\t"):
                    cuerpo.append(lineas[i])
                    i += 1
                while i < len(lineas) and lineas[i].startswith("\t\t") and not lineas[i].startswith("\t\t\t"):
                    if lineas[i].strip().startswith("lineageTag:"):
                        t.lineage.append(lineas[i].split(":", 1)[1].strip())
                    i += 1
                if nombre in t.medidas:
                    err(f"Medida duplicada en {t.nombre}: {nombre}")
                t.medidas[nombre] = "\n".join(cuerpo)
                continue
            m = re.match(r"^\tpartition (.+?) = (\w+)", l)
            if m:
                t.tipo_part = m.group(2)
                i += 1
                bloque = []
                while i < len(lineas) and (lineas[i].startswith("\t\t") or lineas[i] == ""):
                    bloque.append(lineas[i])
                    i += 1
                t.particion = "\n".join(bloque)
                continue
            if l.startswith("\tlineageTag:"):
                t.lineage.append(l.split(":", 1)[1].strip())
        elif l.startswith("\tlineageTag:") and t is not None:
            t.lineage.append(l.split(":", 1)[1].strip())
        i += 1
    return t


tablas = {}
for ruta in sorted((MODELO / "tables").glob("*.tmdl")):
    t = parsear_tabla(ruta)
    if t is None:
        err(f"{ruta.name}: no declara ninguna tabla")
        continue
    if t.nombre in tablas:
        err(f"Tabla duplicada: {t.nombre}")
    tablas[t.nombre] = t
    if ruta.stem != t.nombre:
        err(f"El archivo {ruta.name} declara la tabla {t.nombre}")
    for c in t.columnas:
        if c in t.medidas:
            err(f"{t.nombre}: «{c}» es columna y medida a la vez")

texto_modelo = (MODELO / "model.tmdl").read_text(encoding="utf-8")
for nombre in re.findall(r"^ref table (.+)$", texto_modelo, flags=re.M):
    if nombre_tmdl(nombre) not in tablas:
        err(f"model.tmdl: ref table {nombre} sin archivo")
for nombre in tablas:
    if f"ref table {nombre}" not in texto_modelo and f"ref table '{nombre}'" not in texto_modelo:
        err(f"model.tmdl: la tabla {nombre} no está referenciada")

todos_lineage = [x for t in tablas.values() for x in t.lineage]
dup = {x for x in todos_lineage if todos_lineage.count(x) > 1}
if dup:
    err(f"lineageTag repetidos: {len(dup)}")

expr_texto = (MODELO / "expressions.tmdl").read_text(encoding="utf-8")
expresiones = set(re.findall(r"^expression (\w+) =", expr_texto, flags=re.M))
medidas_todas = {m: t.nombre for t in tablas.values() for m in t.medidas}

# --------------------------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------------------------
csv_cache = {}


def leer_csv(nombre):
    if nombre not in csv_cache:
        ruta = DATOS / nombre
        if not ruta.exists():
            err(f"CSV inexistente: datos_sinteticos/{nombre}")
            csv_cache[nombre] = ([], [])
        else:
            with open(ruta, encoding="utf-8", newline="") as f:
                r = csv.reader(f)
                cab = next(r)
                csv_cache[nombre] = (cab, [dict(zip(cab, fila)) for fila in r])
    return csv_cache[nombre]


tabla_csv = {}   # tabla -> archivo
for t in tablas.values():
    m = re.search(r'File\.Contents\(RutaDatos & "([^"]+\.csv)"\)', t.particion)
    if m:
        tabla_csv[t.nombre] = m.group(1)
tabla_csv["Mediciones"] = "mediciones_horarias.csv"   # lee la expresión MedicionesCsv
if "MedicionesCsv" in expresiones and "mediciones_horarias.csv" not in expr_texto:
    err("La expresión MedicionesCsv no lee mediciones_horarias.csv")

# 4. particiones CSV
for nombre, archivo in tabla_csv.items():
    t = tablas[nombre]
    cab, filas = leer_csv(archivo)
    calc = {"Hora", "HorasAtras", "Fecha"} if nombre == "Mediciones" else set()
    esperadas = [c for c, p in t.columnas.items() if c not in calc]
    if nombre == "Mediciones":
        esperadas = ["Tag", "FechaHora", "Valor"]
    if cab != esperadas:
        err(f"{archivo}: encabezado {cab} distinto de las columnas del modelo {esperadas}")
    if nombre == "Mediciones":
        bloque_m = re.search(r"expression MedicionesCsv =.*?(?=\n/// |\Z)", expr_texto, flags=re.S).group(0)
    else:
        bloque_m = t.particion
    tipos_m = re.findall(r'\{"(\w+)", (type \w+|Int64\.Type)\}', bloque_m)
    for col, tp in tipos_m:
        if col not in cab:
            err(f"{archivo}: el tipo de M apunta a la columna inexistente {col}")
            continue
        if tp in ("type number", "Int64.Type"):
            malos = [f[col] for f in filas if f[col] != "" and not re.fullmatch(r"-?\d+(\.\d+)?", f[col])]
            if malos:
                err(f"{archivo}.{col}: valores no numéricos, p. ej. {malos[0]!r}")
        if tp == "type date":
            malos = [f[col] for f in filas if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", f[col])]
            if malos:
                err(f"{archivo}.{col}: fechas no ISO, p. ej. {malos[0]!r}")
        if tp == "type datetime":
            malos = [f[col] for f in filas if not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?", f[col])]
            if malos:
                err(f"{archivo}.{col}: fecha-hora no ISO, p. ej. {malos[0]!r}")

valores = {}   # (tabla, columna) -> conjunto de valores


def valores_de(tabla, columna):
    k = (tabla, columna)
    if k not in valores:
        if tabla == "Config" and columna == "Parametro":
            s = {f["Parametro"] for f in leer_csv("config.csv")[1]}
            s |= set(re.findall(r'\{"([^"]+)", (?:ZonaHorariaUTC|if )', tablas["Config"].particion))
            valores[k] = s
        elif tabla in tabla_csv:
            _, filas = leer_csv(tabla_csv[tabla])
            valores[k] = {f.get(columna, "") for f in filas}
        elif tabla == "Semaforo" and columna == "Sistema":
            valores[k] = set(re.findall(r'\{ "([^"]+)", \d+ \}', tablas["Semaforo"].particion))
        elif tabla == "FiltroEstado" and columna == "Estado":
            valores[k] = set(re.findall(r'\{ "([^"]+)", \d+ \}', tablas["FiltroEstado"].particion))
        else:
            valores[k] = None
    return valores[k]


# 5. relaciones
rel_texto = (MODELO / "relationships.tmdl").read_text(encoding="utf-8")
relaciones = re.findall(r"fromColumn: (\S+)\n\ttoColumn: (\S+)", rel_texto)
for desde, hacia in relaciones:
    (td, cd), (th, ch) = desde.split("."), hacia.split(".")
    for t_, c_ in ((td, cd), (th, ch)):
        if t_ not in tablas or c_ not in tablas[t_].columnas:
            err(f"Relación {desde} -> {hacia}: {t_}[{c_}] no existe")
    vd, vh = valores_de(td, cd), valores_de(th, ch)
    if td in tabla_csv and th in tabla_csv:
        filas_h = leer_csv(tabla_csv[th])[1]
        claves = [f[ch] for f in filas_h]
        if len(claves) != len(set(claves)):
            err(f"Relación {desde} -> {hacia}: la clave {hacia} no es única")
        if vd is not None and vh is not None and not vd <= vh:
            err(f"Relación {desde} -> {hacia}: valores sin pareja, p. ej. {sorted(vd - vh)[:3]}")

# --------------------------------------------------------------------------------------------
# 3. DAX
# --------------------------------------------------------------------------------------------
RX_CADENA = re.compile(r'"(?:[^"]|"")*"')
n_medidas = 0
for t in tablas.values():
    exprs = [(f"{t.nombre}[{m}]", e) for m, e in t.medidas.items()]
    if t.tipo_part == "calculated":
        exprs.append((f"{t.nombre} (tabla calculada)", t.particion))
    for etiqueta, e in exprs:
        n_medidas += 1 if "tabla calculada" not in etiqueta else 0
        sin_cadenas = RX_CADENA.sub('""', e)
        for m in re.finditer(r"(?:'([^']+)'|\b([A-Za-z_]\w*))\[([^\]]+)\]", sin_cadenas):
            tabla_ref = m.group(1) or m.group(2)
            col = m.group(3)
            if col.startswith("@"):
                continue
            if tabla_ref not in tablas:
                err(f"{etiqueta}: la tabla {tabla_ref} no existe ({tabla_ref}[{col}])")
            elif col not in tablas[tabla_ref].columnas and col not in tablas[tabla_ref].medidas:
                err(f"{etiqueta}: {tabla_ref}[{col}] no existe")
        for m in re.finditer(r"(?<![\w'\]])\[([^\]]+)\]", sin_cadenas):
            nombre = m.group(1)
            if nombre.startswith("@"):
                continue
            if nombre not in medidas_todas and not any(nombre in x.columnas for x in tablas.values() if x.tipo_part == "calculated"):
                err(f"{etiqueta}: la medida [{nombre}] no existe")
        # literales comparados contra columnas de catálogo
        for m in re.finditer(r"(?:'([^']+)'|\b([A-Za-z_]\w*))\[(\w+)\]\s*(=|IN)\s*(\{[^}]*\}|\"(?:[^\"]|\"\")*\")", e):
            tabla_ref, col = m.group(1) or m.group(2), m.group(3)
            lits = re.findall(r'"((?:[^"]|"")*)"', m.group(5))
            vals = valores_de(tabla_ref, col) if tabla_ref in tablas else None
            if vals is None:
                continue
            for lit in lits:
                if lit not in vals:
                    err(f"{etiqueta}: el literal «{lit}» no existe en {tabla_ref}[{col}]")
    if t.nombre == "Medidas":
        for nombre in ("Sem cod", "Sem detalle"):
            lits = re.findall(r'^\s+"([^"]+)", \[Sem [^\]]+\]', t.medidas.get(nombre, ""), flags=re.M)
            vals = valores_de("Semaforo", "Sistema")
            for lit in lits:
                if lit not in vals:
                    err(f"Medidas[{nombre}]: el sistema «{lit}» no existe en Semaforo[Sistema]")
            if vals and set(lits) != vals:
                err(f"Medidas[{nombre}]: cubre {len(lits)} de {len(vals)} sistemas del semáforo")

# --------------------------------------------------------------------------------------------
# 6. Reporte
# --------------------------------------------------------------------------------------------
def tipo_campo(entidad, prop):
    t = tablas.get(entidad)
    if t is None:
        return None
    if prop in t.medidas:
        return "Measure"
    if prop in t.columnas:
        return "Column"
    return None


def revisar_campos(obj, contexto, alias):
    """Recorre un objeto JSON y valida cada Column/Measure/Aggregation. alias: nombre -> entidad."""
    n = 0
    if isinstance(obj, dict):
        for k in ("Column", "Measure", "HierarchyLevel"):
            if k in obj and isinstance(obj[k], dict) and "Expression" in obj[k] and "Property" in obj[k]:
                src = obj[k]["Expression"].get("SourceRef", {})
                ent = src.get("Entity") or alias.get(src.get("Source"))
                if ent is None:
                    err(f"{contexto}: referencia sin entidad ({obj[k].get('Property')})")
                else:
                    real = tipo_campo(ent, obj[k]["Property"])
                    if real is None:
                        err(f"{contexto}: {ent}[{obj[k]['Property']}] no existe en el modelo")
                    elif k != "HierarchyLevel" and real != k:
                        err(f"{contexto}: {ent}[{obj[k]['Property']}] es {real} y el visual lo trata como {k}")
                    n += 1
        for v in obj.values():
            n += revisar_campos(v, contexto, alias)
    elif isinstance(obj, list):
        for v in obj:
            n += revisar_campos(v, contexto, alias)
    return n


report = cargar_json(REPORTE / "definition" / "report.json") or {}
recursos = {i["name"] for p in report.get("resourcePackages", []) for i in p.get("items", [])}
for p in report.get("resourcePackages", []):
    if p["name"] == "RegisteredResources":
        for i in p["items"]:
            if not (REPORTE / "StaticResources" / "RegisteredResources" / i["path"]).exists():
                err(f"Recurso registrado sin archivo: {i['path']}")
    if p["name"] == "SharedResources":
        for i in p["items"]:
            if not (REPORTE / "StaticResources" / "SharedResources" / i["path"]).exists():
                err(f"Recurso compartido sin archivo: {i['path']}")

pages_json = cargar_json(REPORTE / "definition" / "pages" / "pages.json") or {}
orden = pages_json.get("pageOrder", [])
carpetas_pag = sorted(p.name for p in (REPORTE / "definition" / "pages").iterdir() if p.is_dir())
if sorted(orden) != carpetas_pag:
    err("pages.json: pageOrder no coincide con las carpetas de páginas")
if pages_json.get("activePageName") not in orden:
    err("pages.json: activePageName no está en pageOrder")

n_vis = n_campos = 0
nombres_vis = set()
for pid in orden:
    pj = cargar_json(REPORTE / "definition" / "pages" / pid / "page.json") or {}
    if pj.get("name") != pid:
        err(f"Página {pid}: el nombre del JSON ({pj.get('name')}) no coincide con la carpeta")
    vis_dirs = {d.name for d in (REPORTE / "definition" / "pages" / pid / "visuals").iterdir()}
    for it in pj.get("visualInteractions", []):
        for extremo in ("source", "target"):
            if it.get(extremo) not in vis_dirs:
                err(f"Página {pj.get('displayName')}: la interacción apunta a un visual inexistente ({it.get(extremo)})")
    for vd in sorted((REPORTE / "definition" / "pages" / pid / "visuals").iterdir()):
        v = cargar_json(vd / "visual.json")
        if v is None:
            continue
        n_vis += 1
        ctx = f"{pj.get('displayName')}/{vd.name[:6]} ({v.get('visual', {}).get('visualType')})"
        if v.get("name") != vd.name:
            err(f"{ctx}: el nombre del visual no coincide con su carpeta")
        if v.get("name") in nombres_vis:
            err(f"{ctx}: nombre de visual repetido")
        nombres_vis.add(v.get("name"))
        qs = v.get("visual", {}).get("query", {}).get("queryState", {})
        refs = set()
        for rol, d in qs.items():
            for p in d.get("projections", []):
                f = p["field"]
                kind = "Measure" if "Measure" in f else ("Column" if "Column" in f else None)
                if kind:
                    ent = f[kind]["Expression"]["SourceRef"]["Entity"]
                    prop = f[kind]["Property"]
                    if p.get("queryRef") != f"{ent}.{prop}":
                        err(f"{ctx}: queryRef {p.get('queryRef')!r} distinto de {ent}.{prop}")
                    refs.add(p.get("queryRef"))
        n_campos += revisar_campos(v.get("visual", {}).get("query", {}), ctx, {})
        n_campos += revisar_campos(v.get("visual", {}).get("objects", {}), ctx, {})
        n_campos += revisar_campos(v.get("visual", {}).get("visualContainerObjects", {}), ctx, {})
        # selectores de formato: metadata debe ser una proyección del visual
        for k, lst in v.get("visual", {}).get("objects", {}).items():
            for e in lst:
                meta = (e.get("selector") or {}).get("metadata")
                if meta and meta not in refs:
                    err(f"{ctx}: el selector de {k} apunta a {meta}, que no es una proyección del visual")
        # filtros
        for f in v.get("filterConfig", {}).get("filters", []):
            alias = {x["Name"]: x["Entity"] for x in f.get("filter", {}).get("From", [])}
            n_campos += revisar_campos(f, ctx, alias)
            try:
                cond = f["filter"]["Where"][0]["Condition"]["In"]
                col = cond["Expressions"][0]["Column"]
                ent = alias[col["Expression"]["SourceRef"]["Source"]]
                vals = valores_de(ent, col["Property"])
                if vals is not None:
                    for x in cond["Values"]:
                        lit = x[0]["Literal"]["Value"]
                        if lit.startswith("'") and lit[1:-1] not in vals:
                            err(f"{ctx}: el filtro {ent}[{col['Property']}] usa «{lit[1:-1]}», que no existe en los datos")
            except (KeyError, IndexError, TypeError):
                pass
        # recursos de imagen
        txt = json.dumps(v)
        for item in re.findall(r'"ItemName": "([^"]+)"', txt):
            if item not in recursos:
                err(f"{ctx}: recurso de imagen {item} no está en report.json")

# columnas de tablas CSV: toda columna oculta de ordenación existe
for t in tablas.values():
    for c, p in t.columnas.items():
        if "sortBy" in p and p["sortBy"] not in t.columnas:
            err(f"{t.nombre}[{c}]: sortByColumn {p['sortBy']} no existe")

# catálogo: cada señal con datos, cada activo con señales (aviso)
tags_csv = leer_csv("catalogo_senales.csv")[1]
med_tags = {f["Tag"] for f in leer_csv("mediciones_horarias.csv")[1]}
sin_datos = [t["Tag"] for t in tags_csv if t["Tag"] not in med_tags]
if sin_datos:
    err(f"{len(sin_datos)} señales del catálogo sin mediciones, p. ej. {sin_datos[:3]}")

print(f"JSON revisados: {n_json} | tablas: {len(tablas)} | medidas: {sum(len(t.medidas) for t in tablas.values())} | relaciones: {len(relaciones)}")
print(f"Páginas: {len(orden)} | visuales: {n_vis} | referencias a campos validadas: {n_campos} | CSV: {len(csv_cache)}")
if errores:
    print(f"ERRORES: {len(errores)}")
    for e in errores[:80]:
        print("  -", e)
    sys.exit(1)
print("COHERENTE: 0 errores")
