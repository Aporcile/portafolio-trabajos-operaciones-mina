# -*- coding: utf-8 -*-
"""Verificador de coherencia del proyecto PBIP (modelo semántico + informe + datos sintéticos).

No necesita Power BI Desktop ni dependencias externas: lee los archivos TMDL, los JSON del informe (PBIR) y los CSV.

Qué verifica
  1. JSON válido en todo el proyecto (.json, .pbir, .platform, .pbip).
  2. Modelo: tablas, columnas, medidas, particiones y relaciones (extremos existentes, tipos compatibles,
     sin relaciones duplicadas, claves del lado «uno» sin repetidos y sin huérfanos en los datos).
  3. DAX: cada referencia Tabla[Columna] o [Medida] existe; no hay ciclos entre medidas.
  4. Particiones M: el CSV existe, trae las columnas que el modelo espera y sus valores respetan el tipo.
  5. Informe: cada campo de cada visual, filtro y selector existe en el modelo (y como medida o columna según
     corresponda); grupos, interacciones, páginas y recursos (imágenes, tema) existen.

Uso:
  python herramientas/verificar_modelo.py
  python herramientas/verificar_modelo.py --pbip RUTA/pbip --datos RUTA/datos_sinteticos
Código de salida: 0 = coherente, 1 = hay errores.
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

FUNCIONES_DAX_VARIABLE = {"VAR", "RETURN"}


class Resultado:
    def __init__(self):
        self.errores = []
        self.avisos = []
        self.cuentas = Counter()

    def error(self, donde, mensaje):
        self.errores.append(f"[{donde}] {mensaje}")

    def aviso(self, donde, mensaje):
        self.avisos.append(f"[{donde}] {mensaje}")


# ---------------------------------------------------------------------------------------------------------------
# 1. JSON
# ---------------------------------------------------------------------------------------------------------------
def verificar_json(pbip, res):
    for p in sorted(pbip.rglob("*")):
        if p.is_file() and (p.suffix in {".json", ".pbir", ".platform", ".pbip", ".pbism"}):
            res.cuentas["json"] += 1
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except (ValueError, UnicodeDecodeError) as e:
                res.error("json", f"{p.relative_to(pbip)}: {e}")


# ---------------------------------------------------------------------------------------------------------------
# 2. Lectura de TMDL
# ---------------------------------------------------------------------------------------------------------------
def sin_comillas(n):
    n = n.strip()
    if len(n) >= 2 and n[0] == "'" and n[-1] == "'":
        return n[1:-1].replace("''", "'")
    return n


R_MIEMBRO = re.compile(r"^\t(column|measure|partition)\s+('(?:[^']|'')+'|[^\s=]+)\s*(?:=\s*(.*))?$")


def sangria(linea):
    return len(linea) - len(linea.lstrip("\t"))


def leer_tabla(texto, ruta):
    lineas = texto.split("\n")
    m = re.match(r"^table\s+(.+?)\s*$", lineas[0] if lineas[0].startswith("table") else next(
        (l for l in lineas if l.startswith("table ")), ""))
    if not m:
        raise ValueError(f"{ruta}: sin cabecera 'table'")
    tabla = {"nombre": sin_comillas(m.group(1)), "columnas": {}, "medidas": {}, "particiones": []}
    i = 0
    while i < len(lineas):
        mm = R_MIEMBRO.match(lineas[i])
        if not mm:
            i += 1
            continue
        tipo, nombre, inline = mm.group(1), sin_comillas(mm.group(2)), mm.group(3)
        j = i + 1
        bloque = []
        while j < len(lineas):
            l = lineas[j]
            if l.strip() and sangria(l) <= 1:
                break
            bloque.append(l)
            j += 1
        props, expr, fmt_expr = {}, [], None
        if inline is not None:
            expr.append(inline.strip())
        for l in bloque:
            if not l.strip():
                expr.append("") if expr else None
                continue
            s = sangria(l)
            txt = l.strip()
            if s == 2 and not txt.startswith("//"):
                if txt.startswith("formatStringDefinition"):
                    fmt_expr = txt.split("=", 1)[1].strip()
                    continue
                if txt.startswith("annotation") or txt.startswith("changedProperty") or txt.startswith("extendedProperty"):
                    continue
                if tipo == "partition" and txt.startswith("source"):
                    props["_source"] = True
                    continue
                k, _, v = txt.partition(":")
                props[k.strip()] = v.strip() if _ else True
            elif s >= 3:
                expr.append(txt)
        texto_expr = "\n".join(x for x in expr if x != "```" and not x.startswith("```")).strip()
        texto_expr = texto_expr.replace("```", "").strip()
        if tipo == "column":
            tabla["columnas"][nombre] = {
                "dataType": props.get("dataType"), "sourceColumn": (props.get("sourceColumn") or "").strip("[]") or None,
                "calculada": inline is not None and texto_expr != "" and props.get("sourceColumn") is None,
                "oculta": "isHidden" in props, "expr": texto_expr}
        elif tipo == "measure":
            tabla["medidas"][nombre] = {"expr": texto_expr, "fmt": fmt_expr, "oculta": "isHidden" in props}
        else:
            tabla["particiones"].append({"nombre": nombre, "tipo": (inline or "").strip(), "expr": texto_expr})
        i = j
    return tabla


def leer_relaciones(texto):
    rels, actual = [], None
    for l in texto.split("\n"):
        m = re.match(r"^relationship\s+(.+)$", l)
        if m:
            actual = {"nombre": sin_comillas(m.group(1)), "from": None, "to": None, "activa": True}
            rels.append(actual)
        elif actual is not None:
            t = l.strip()
            if t.startswith("fromColumn:"):
                actual["from"] = t.split(":", 1)[1].strip()
            elif t.startswith("toColumn:"):
                actual["to"] = t.split(":", 1)[1].strip()
            elif t.startswith("isActive:"):
                actual["activa"] = t.split(":", 1)[1].strip().lower() != "false"
    return rels


def partir_extremo(s):
    m = re.match(r"^(?:'((?:[^']|'')+)'|([^.]+))\.(.+)$", s)
    if not m:
        return None, None
    tabla = (m.group(1) or m.group(2)).replace("''", "'")
    return tabla, sin_comillas(m.group(3))


def leer_parametros(texto):
    out = {}
    for m in re.finditer(r"^expression\s+(\S+)\s*=\s*(.+?)\s+meta\s*\[", texto, flags=re.M):
        out[m.group(1)] = m.group(2).strip()
    return out


# ---------------------------------------------------------------------------------------------------------------
# 3. DAX
# ---------------------------------------------------------------------------------------------------------------
R_CADENA = re.compile(r'"(?:[^"]|"")*"')
R_COMENT = re.compile(r"(//[^\n]*|--[^\n]*)")
R_REF_TABLA = re.compile(r"(?:'((?:[^']|'')+)'|\b([A-Za-z_][A-Za-z0-9_]*))\[([^\]]+)\]")
R_REF_BARE = re.compile(r"(?<![A-Za-z0-9_'\]])\[([^\]]+)\]")


def limpiar_dax(expr):
    """Devuelve (texto sin cadenas ni comentarios, conjunto de literales usados como nombres locales)."""
    sin_coment = []
    for linea in expr.split("\n"):
        # el comentario no puede estar dentro de una cadena: se quita primero la parte entre comillas
        tmp = R_CADENA.sub(lambda m: '"' + "x" * (len(m.group(0)) - 2) + '"', linea)
        k = min([p for p in (tmp.find("//"), tmp.find("--")) if p >= 0], default=-1)
        sin_coment.append(linea if k < 0 else linea[:k])
    texto = "\n".join(sin_coment)
    literales = {m.group(0)[1:-1].replace('""', '"') for m in R_CADENA.finditer(texto)}
    return R_CADENA.sub('""', texto), literales


def verificar_dax(modelo, res):
    tablas = modelo["tablas"]
    medidas_global = {}
    for t in tablas.values():
        for nombre in t["medidas"]:
            medidas_global.setdefault(nombre, []).append(t["nombre"])
    dependencias = defaultdict(set)
    usadas = set()

    def revisar(donde, tabla_ctx, expr, es_columna_calc=False):
        if not expr:
            return
        texto, literales = limpiar_dax(expr)
        for m in R_REF_TABLA.finditer(texto):
            tn = (m.group(1) or m.group(2)).replace("''", "'")
            mn = m.group(3)
            res.cuentas["ref_dax"] += 1
            if tn not in tablas:
                res.error(donde, f"tabla inexistente en referencia {tn}[{mn}]")
                continue
            t = tablas[tn]
            if mn in t["medidas"]:
                dependencias[donde].add((tn, mn))
                usadas.add((tn, mn))
            elif mn not in t["columnas"]:
                res.error(donde, f"{tn}[{mn}] no existe (ni columna ni medida)")
        # referencias sin tabla: se consideran medidas (o columnas de la propia tabla en columnas calculadas)
        quitado = R_REF_TABLA.sub("", texto)
        for m in R_REF_BARE.finditer(quitado):
            nombre = m.group(1)
            res.cuentas["ref_dax"] += 1
            if nombre in literales or nombre == "Value":
                continue
            if nombre in medidas_global:
                for tn in medidas_global[nombre]:
                    dependencias[donde].add((tn, nombre))
                    usadas.add((tn, nombre))
                continue
            if tabla_ctx and nombre in tablas[tabla_ctx]["columnas"]:
                continue
            res.error(donde, f"[{nombre}] no es una medida del modelo ni una columna de la tabla")

    for t in tablas.values():
        for nombre, med in t["medidas"].items():
            revisar(f"medida {t['nombre']}[{nombre}]", t["nombre"], med["expr"])
            if med["fmt"]:
                revisar(f"formato {t['nombre']}[{nombre}]", t["nombre"], med["fmt"])
            res.cuentas["medidas"] += 1
        for nombre, col in t["columnas"].items():
            if col["calculada"]:
                revisar(f"columna {t['nombre']}[{nombre}]", t["nombre"], col["expr"], True)
                res.cuentas["columnas_calculadas"] += 1
        for p in t["particiones"]:
            if p["tipo"] == "calculated":
                revisar(f"tabla calculada {t['nombre']}", t["nombre"], p["expr"])
    # ciclos entre medidas
    estado = {}

    def visita(nodo, ruta):
        estado[nodo] = 1
        for d in dependencias.get(f"medida {nodo[0]}[{nodo[1]}]", ()):
            if estado.get(d) == 1:
                res.error("dax", "ciclo entre medidas: " + " -> ".join(f"{a}[{b}]" for a, b in ruta + [nodo, d]))
            elif d not in estado:
                visita(d, ruta + [nodo])
        estado[nodo] = 2

    for t in tablas.values():
        for nombre in t["medidas"]:
            if (t["nombre"], nombre) not in estado:
                visita((t["nombre"], nombre), [])
    return usadas


# ---------------------------------------------------------------------------------------------------------------
# 4. Datos (CSV) y particiones M
# ---------------------------------------------------------------------------------------------------------------
def leer_csv(ruta):
    with open(ruta, encoding="utf-8", newline="") as fh:
        lector = csv.reader(fh)
        cab = next(lector)
        return cab, list(lector)


def tipo_ok(valor, tipo):
    if valor == "":
        return True
    try:
        if tipo == "Int64.Type":
            int(valor)
        elif tipo == "type number":
            float(valor)
        elif tipo == "type datetime":
            datetime.fromisoformat(valor)
        elif tipo == "type date":
            date.fromisoformat(valor[:10])
        elif tipo == "type time":
            datetime.strptime(valor, "%H:%M:%S")
        elif tipo == "type logical":
            return valor.lower() in ("true", "false")
    except ValueError:
        return False
    return True


def verificar_particiones(modelo, carpeta_datos, res, parametros):
    tablas = modelo["tablas"]
    csv_cache = {}
    for t in tablas.values():
        for p in t["particiones"]:
            if p["tipo"] != "m":
                continue
            res.cuentas["particiones_m"] += 1
            expr = p["expr"]
            m = re.search(r'RutaDatos\s*&\s*"([^"]+)"', expr)
            if not m:
                ref = re.search(r"Origen\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*$", expr, flags=re.M)
                if ref and ref.group(1) in tablas:
                    continue
                if "Table.FromRecords" in expr or "List.Dates" in expr:
                    continue
                res.error(f"partición {t['nombre']}", "no lee un CSV vía RutaDatos ni referencia otra tabla")
                continue
            for par in re.findall(r"\b(RutaDatos|FechaReferencia|DiasHistoriaGPS|DiasHistoria)\b", expr):
                if par not in parametros:
                    res.error(f"partición {t['nombre']}", f"parámetro inexistente: {par}")
            archivo = carpeta_datos / m.group(1)
            if not archivo.exists():
                res.error(f"partición {t['nombre']}", f"falta el CSV {m.group(1)}")
                continue
            cab, filas = csv_cache.setdefault(archivo, leer_csv(archivo))
            res.cuentas["csv"] += 1
            tipos = dict(re.findall(r'\{"([^"]+)",\s*([A-Za-z0-9_. ]+?)\}', expr.split("Table.TransformColumnTypes", 1)[-1]
                                    .split("\n", 1)[0]))
            for col, tipo in tipos.items():
                if col not in cab:
                    res.error(f"partición {t['nombre']}", f"el CSV no trae la columna «{col}»")
                    continue
                idx = cab.index(col)
                malos = [f[idx] for f in filas if not tipo_ok(f[idx], tipo)]
                if malos:
                    res.error(f"partición {t['nombre']}", f"columna «{col}»: {len(malos)} valores no son {tipo} (p. ej. {malos[0]!r})")
            # columnas del modelo (no calculadas) frente a las que produce la consulta
            agregadas = set(re.findall(r'Table\.AddColumn\([^,]+,\s*"([^"]+)"', expr))
            renombradas = dict(re.findall(r'\{"([^"]+)",\s*"([^"]+)"\}', expr.split("Table.RenameColumns", 1)[-1])) \
                if "Table.RenameColumns" in expr else {}
            producidas = {renombradas.get(c, c) for c in cab} | agregadas
            for nombre, col in t["columnas"].items():
                if col["calculada"]:
                    continue
                origen = col["sourceColumn"] or nombre
                if origen not in producidas:
                    res.error(f"partición {t['nombre']}", f"la columna del modelo «{nombre}» no la produce la consulta")
            extra = [c for c in producidas if c not in {(col["sourceColumn"] or n) for n, col in t["columnas"].items()}]
            if extra:
                res.aviso(f"partición {t['nombre']}", f"columnas del CSV sin columna en el modelo: {', '.join(sorted(extra))}")


def valores_de(modelo, carpeta_datos, tabla, columna, cache):
    """Valores (no vacíos) de una columna, leída del CSV de su partición; None si no se puede resolver."""
    t = modelo["tablas"].get(tabla)
    if t is None:
        return None
    col = t["columnas"].get(columna)
    if col is None:
        return None
    clave = (tabla, columna)
    if clave in cache:
        return cache[clave]
    out = None
    csv_nombre = None
    for p in t["particiones"]:
        m = re.search(r'RutaDatos\s*&\s*"([^"]+)"', p["expr"])
        if m:
            csv_nombre = m.group(1)
        else:
            ref = re.search(r"Origen\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*$", p["expr"], flags=re.M)
            if ref and ref.group(1) in modelo["tablas"]:
                out = valores_de(modelo, carpeta_datos, ref.group(1), columna, cache)
                cache[clave] = out
                return out
    if csv_nombre and (carpeta_datos / csv_nombre).exists():
        cab, filas = leer_csv(carpeta_datos / csv_nombre)
        origen = col["sourceColumn"] or columna
        if origen in cab:
            i = cab.index(origen)
            out = [f[i] for f in filas if f[i] != ""]
        elif columna == "Orden_Hora_Dia" and "HoraTurno" in cab and "Turno" in cab:
            # columna calculada: HoraTurno (1-12) + 12 si el turno es B
            i_h, i_t = cab.index("HoraTurno"), cab.index("Turno")
            out = [str(int(f[i_h]) + (0 if f[i_t] == "A" else 12)) for f in filas if f[i_h] != ""]
        elif columna == "Orden_Hora_Dia" and "Hora" in cab and "Turno" in cab:
            # columna calculada: Hora (índice 0-11 dentro del turno) + 1, más 12 si el turno es B
            i_h, i_t = cab.index("Hora"), cab.index("Turno")
            out = [str(int(f[i_h]) + (1 if f[i_t] == "A" else 13)) for f in filas if f[i_h] != ""]
    cache[clave] = out
    return out


def dominio_calendario(parametros):
    """Fechas que genera Dim_Tiempo: de FechaReferencia - (DiasHistoria + 2) a FechaReferencia + 5."""
    m = re.search(r"#date\((\d+),\s*(\d+),\s*(\d+)\)", parametros.get("FechaReferencia", ""))
    d = re.search(r"^(\d+)", parametros.get("DiasHistoria", ""))
    if not m or not d:
        return None
    ref = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return {(ref - timedelta(days=k)).isoformat() for k in range(-5, int(d.group(1)) + 3)}


def verificar_relaciones(modelo, carpeta_datos, res, parametros):
    tablas = modelo["tablas"]
    vistas = Counter()
    cache = {}
    calendario = dominio_calendario(parametros)
    for r in modelo["relaciones"]:
        res.cuentas["relaciones"] += 1
        tf, cf = partir_extremo(r["from"] or "")
        tt, ct = partir_extremo(r["to"] or "")
        donde = f"relación {r['nombre']}"
        if not tf or not tt:
            res.error(donde, "extremos ilegibles")
            continue
        ok = True
        for t, c in ((tf, cf), (tt, ct)):
            if t not in tablas:
                res.error(donde, f"tabla inexistente: {t}")
                ok = False
            elif c not in tablas[t]["columnas"]:
                res.error(donde, f"columna inexistente: {t}.{c}")
                ok = False
        if not ok:
            continue
        vistas[(tf, cf, tt, ct)] += 1
        df, dt = tablas[tf]["columnas"][cf]["dataType"], tablas[tt]["columnas"][ct]["dataType"]
        if df and dt and df != dt:
            res.error(donde, f"tipos distintos: {tf}.{cf}={df} / {tt}.{ct}={dt}")
        # integridad con los datos
        valores_uno = valores_de(modelo, carpeta_datos, tt, ct, cache)
        if valores_uno is None and ct == "Fecha" and calendario is not None:
            valores_uno = list(calendario)
        if valores_uno is None and tt == "Dim_Hora_Operacional":
            valores_uno = [str(k) for k in list(range(1, 25)) + [96, 97, 98, 99]]
        if valores_uno is not None:
            repetidos = [v for v, n in Counter(valores_uno).items() if n > 1]
            if repetidos:
                res.error(donde, f"el lado «uno» {tt}.{ct} tiene valores repetidos (p. ej. {repetidos[0]!r})")
            valores_f = valores_de(modelo, carpeta_datos, tf, cf, cache)
            if valores_f is not None:
                conj = set(valores_uno)
                if ct == "Fecha":
                    conj = {v[:10] for v in conj}
                    valores_f = [v[:10] for v in valores_f]
                huerfanos = sorted({v for v in valores_f if v not in conj})
                if huerfanos:
                    res.error(donde, f"{len(huerfanos)} valores de {tf}.{cf} no existen en {tt}.{ct} (p. ej. {huerfanos[0]!r})")
    for k, n in vistas.items():
        if n > 1:
            res.error("relaciones", f"relación duplicada {k[0]}.{k[1]} -> {k[2]}.{k[3]}")


# ---------------------------------------------------------------------------------------------------------------
# 5. Informe (PBIR)
# ---------------------------------------------------------------------------------------------------------------
def campos_de(obj, alias, salida):
    """Recorre un nodo JSON y agrega (tipo, entidad, propiedad) por cada Column/Measure/Hierarchy referenciado."""
    if isinstance(obj, dict):
        if "From" in obj and isinstance(obj["From"], list):
            alias = dict(alias)
            for f in obj["From"]:
                if isinstance(f, dict) and "Name" in f and "Entity" in f:
                    alias[f["Name"]] = f["Entity"]
        for clave in ("Column", "Measure"):
            v = obj.get(clave)
            if isinstance(v, dict) and "Property" in v and isinstance(v.get("Expression"), dict):
                ref = v["Expression"].get("SourceRef", {})
                ent = ref.get("Entity") or alias.get(ref.get("Source"))
                salida.append((clave, ent, v["Property"]))
        for v in obj.values():
            campos_de(v, alias, salida)
    elif isinstance(obj, list):
        for v in obj:
            campos_de(v, alias, salida)


def verificar_informe(pbip, modelo, res, usadas_en_informe):
    tablas = modelo["tablas"]
    carpetas = [p for p in pbip.iterdir() if p.is_dir() and p.name.endswith(".Report")]
    if not carpetas:
        res.error("informe", "no hay carpeta .Report")
        return
    rep = carpetas[0]
    D = rep / "definition"
    report = json.loads((D / "report.json").read_text(encoding="utf-8"))
    recursos = {}
    for pk in report.get("resourcePackages", []):
        for it in pk.get("items", []):
            recursos[(pk["name"], it["name"])] = it["path"]
            ruta = rep / "StaticResources" / pk["name"] / it["path"]
            if not ruta.exists():
                res.error("informe", f"recurso declarado y ausente: {pk['name']}/{it['path']}")
    tema = report.get("themeCollection", {}).get("customTheme", {}).get("name")
    if tema and ("RegisteredResources", tema) not in recursos:
        res.error("informe", f"el tema personalizado {tema} no está en resourcePackages")
    pages = json.loads((D / "pages" / "pages.json").read_text(encoding="utf-8"))
    for pid in pages.get("pageOrder", []):
        if not (D / "pages" / pid / "page.json").exists():
            res.error("informe", f"página {pid} sin page.json")
    if pages.get("activePageName") not in pages.get("pageOrder", []):
        res.error("informe", "activePageName no está en pageOrder")
    for pid in pages.get("pageOrder", []):
        pagina = json.loads((D / "pages" / pid / "page.json").read_text(encoding="utf-8"))
        res.cuentas["paginas"] += 1
        if pagina.get("name") != pid:
            res.error(f"página {pid}", "el nombre no coincide con la carpeta")
        visuales = {}
        for vd in sorted((D / "pages" / pid / "visuals").iterdir()):
            vj = json.loads((vd / "visual.json").read_text(encoding="utf-8"))
            if vj.get("name") != vd.name:
                res.error(f"visual {vd.name}", "el nombre no coincide con la carpeta")
            visuales[vd.name] = vj
        res.cuentas["visuales"] += len(visuales)
        grupos = {n for n, v in visuales.items() if "visualGroup" in v}
        for n, v in visuales.items():
            g = v.get("parentGroupName")
            if g and g not in grupos:
                res.error(f"visual {n}", f"grupo padre inexistente: {g}")
        for it in pagina.get("visualInteractions", []):
            for k in ("source", "target"):
                if it[k] not in visuales:
                    res.error(f"página {pid}", f"interacción hacia un visual inexistente: {it[k]}")
        # campos en visuales y página
        nodos = [(f"página {pid}", pagina)] + [(f"visual {n}", v) for n, v in visuales.items()]
        for donde, nodo in nodos:
            refs = []
            campos_de(nodo, {}, refs)
            for clave, ent, prop in refs:
                res.cuentas["campos_informe"] += 1
                if ent not in tablas:
                    res.error(donde, f"entidad inexistente: {ent}.{prop}")
                    continue
                t = tablas[ent]
                if clave == "Measure":
                    if prop not in t["medidas"]:
                        res.error(donde, f"medida inexistente: {ent}[{prop}]")
                    else:
                        usadas_en_informe.add((ent, prop))
                elif prop not in t["columnas"]:
                    if prop in t["medidas"]:
                        res.error(donde, f"{ent}[{prop}] es una medida usada como columna")
                    else:
                        res.error(donde, f"columna inexistente: {ent}[{prop}]")
            texto = json.dumps(nodo, ensure_ascii=False)
            for ent, prop in re.findall(r'"metadata":\s*"([A-Za-z_][A-Za-z0-9_]*)\.([^"]+)"', texto):
                if ent in tablas and prop not in tablas[ent]["columnas"] and prop not in tablas[ent]["medidas"]:
                    res.error(donde, f"selector con campo inexistente: {ent}.{prop}")
            for item in re.findall(r'"ItemName":\s*"([^"]+)"', texto):
                if ("RegisteredResources", item) not in recursos:
                    res.error(donde, f"imagen no registrada en report.json: {item}")


# ---------------------------------------------------------------------------------------------------------------
def cargar_modelo(pbip, res):
    carpetas = [p for p in pbip.iterdir() if p.is_dir() and p.name.endswith(".SemanticModel")]
    if not carpetas:
        res.error("modelo", "no hay carpeta .SemanticModel")
        return None
    D = carpetas[0] / "definition"
    tablas = {}
    for f in sorted((D / "tables").glob("*.tmdl")):
        try:
            t = leer_tabla(f.read_text(encoding="utf-8"), f.name)
        except ValueError as e:
            res.error("modelo", str(e))
            continue
        if t["nombre"] != f.stem:
            res.error("modelo", f"{f.name}: la tabla se llama {t['nombre']}")
        tablas[t["nombre"]] = t
        res.cuentas["tablas"] += 1
    mod = (D / "model.tmdl").read_text(encoding="utf-8")
    declaradas = set(re.findall(r"^ref table\s+(.+)$", mod, flags=re.M))
    for n in {sin_comillas(x) for x in declaradas} ^ set(tablas):
        res.error("modelo", f"tabla declarada en model.tmdl y sin archivo (o al revés): {n}")
    relaciones = leer_relaciones((D / "relationships.tmdl").read_text(encoding="utf-8"))
    parametros = leer_parametros((D / "expressions.tmdl").read_text(encoding="utf-8"))
    return {"tablas": tablas, "relaciones": relaciones, "parametros": parametros}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pbip", default=str(RAIZ / "pbip"))
    ap.add_argument("--datos", default=str(RAIZ / "datos_sinteticos"))
    a = ap.parse_args()
    pbip, datos = Path(a.pbip), Path(a.datos)
    res = Resultado()
    verificar_json(pbip, res)
    modelo = cargar_modelo(pbip, res)
    if modelo:
        usadas_dax = verificar_dax(modelo, res)
        verificar_particiones(modelo, datos, res, modelo["parametros"])
        verificar_relaciones(modelo, datos, res, modelo["parametros"])
        usadas_informe = set()
        verificar_informe(pbip, modelo, res, usadas_informe)
        sin_uso = [(t, m) for t in modelo["tablas"] for m in modelo["tablas"][t]["medidas"]
                   if (t, m) not in usadas_dax and (t, m) not in usadas_informe]
        if sin_uso:
            res.aviso("medidas", f"{len(sin_uso)} medidas no las usa ningún visual ni otra medida: "
                      + ", ".join(f"{t}[{m}]" for t, m in sin_uso[:12]) + (" ..." if len(sin_uso) > 12 else ""))
    c = res.cuentas
    print("Verificación de coherencia del proyecto PBIP")
    print(f"  JSON: {c['json']} | tablas: {c['tablas']} | medidas: {c['medidas']} | columnas calculadas: "
          f"{c['columnas_calculadas']} | relaciones: {c['relaciones']}")
    print(f"  particiones M: {c['particiones_m']} (CSV leídos: {c['csv']}) | referencias DAX: {c['ref_dax']}")
    print(f"  páginas: {c['paginas']} | visuales: {c['visuales']} | campos de informe verificados: {c['campos_informe']}")
    for av in res.avisos:
        print("  aviso", av)
    if res.errores:
        print(f"ERRORES: {len(res.errores)}")
        for e in res.errores[:80]:
            print("  -", e)
        return 1
    print("COHERENTE: 0 errores")
    return 0


if __name__ == "__main__":
    sys.exit(main())
