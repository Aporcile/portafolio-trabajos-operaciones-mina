# -*- coding: utf-8 -*-
"""Biblioteca para generar informes Power BI en formato PBIR (JSON) y piezas de modelo TMDL.

Contiene:
  - identificadores deterministas (lineageTag, ids de página y de visual),
  - constructores de expresiones PBIR (literales, campos, proyecciones, filtros),
  - la clase `Pagina`, con las piezas básicas: texto, rectángulo, logo, botón de navegación, tarjeta de una medida,
    gráficos (columnas, barras, combinado) y tabla,
  - emisión de medidas y tablas calculadas en TMDL.

Los identificadores salen de un hash del nombre: regenerar el informe no los cambia.
"""
import hashlib
import json
import re
import uuid
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
RECURSOS = RAIZ_PROYECTO / "recursos"
LOGO = "logo_minera_demo_blanco.png"
LOGO_AREA = "icono_minera_demo.png"
TEMA_BASE = "CY26SU07"
TEMA_PROPIO = "MineraDemo.json"
MT = "Medidas RD"                      # tabla que solo aloja medidas
NS = uuid.UUID("6a1d3c52-8f4e-4b27-9c0a-3e7d5b91a4f0")

# Paleta Minera Demo. Verde, ámbar y rojo solo se usan como semáforo (verde >= plan, ámbar >= 95 % del plan).
MEDIANOCHE, CIELO, VIOLETA, ACERO, ROSA, SALVIA = "#1B2A41", "#4F9DDE", "#7B61C9", "#2F6FB5", "#C26B8E", "#A3B18A"
PLOMO, NIQUEL, ZINC, PLATA = "#3A4352", "#B4BAC4", "#C5CBD6", "#E6E9EE"
MEDIANOCHE_50, CIELO_60, VIOLETA_60 = "#8D949F", "#95C4EB", "#B0A0DF"
VERDE, AMBAR, ROJO = "#2E7D32", "#F28C28", "#C62828"
GRIS, BORDE, FONDO_CARD, CUADRICULA = PLOMO, ZINC, PLATA, PLATA
COLORES_TEMA = [MEDIANOCHE, CIELO, VIOLETA, ACERO, SALVIA, ROSA, PLOMO, NIQUEL, MEDIANOCHE_50, CIELO_60, VIOLETA_60, ZINC]

VIS = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json"
PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
PAGES = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"


# ---------------------------------------------------------------------------------------------------------------------
# Identificadores y archivos
# ---------------------------------------------------------------------------------------------------------------------

def tag(*k):
    """GUID determinista (lineageTag, relaciones, logicalId)."""
    return str(uuid.uuid5(NS, "/".join(k)))


def hid(*k):
    """Id de 20 caracteres para páginas y visuales."""
    return hashlib.md5(("minera-demo/" + "/".join(k)).encode("utf-8")).hexdigest()[:20]


def q(name):
    """Nombre TMDL: entre comillas simples si no es un identificador simple."""
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else "'" + name.replace("'", "''") + "'"


def escribir(ruta, texto, crlf=False):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    texto = texto.replace("\r\n", "\n")
    if crlf:
        texto = texto.replace("\n", "\r\n")
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        fh.write(texto)


def escribir_json(ruta, datos):
    escribir(ruta, json.dumps(datos, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------------------------------------------------------------
# Expresiones PBIR
# ---------------------------------------------------------------------------------------------------------------------

def L(v):
    return {"expr": {"Literal": {"Value": v}}}


def S(s):
    return L("'" + s.replace("'", "''") + "'")


def B(b):
    return L("true" if b else "false")


def Dn(n):
    return L(f"{n}D")


def C(hexc):
    return {"solid": {"color": S(hexc)}}


def MF(tbl, m):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": tbl}}, "Property": m}}


def CF(tbl, c):
    return {"Column": {"Expression": {"SourceRef": {"Entity": tbl}}, "Property": c}}


def CM(m, tbl=MT):
    """Color tomado del valor de una medida (formato condicional)."""
    return {"solid": {"color": {"expr": MF(tbl, m)}}}


def qref(field):
    k = next(iter(field))
    return f"{field[k]['Expression']['SourceRef']['Entity']}.{field[k]['Property']}"


def proj(field, name=None, active=False):
    k = next(iter(field))
    p = {"field": field, "queryRef": qref(field), "nativeQueryRef": field[k]["Property"]}
    if name:
        p["displayName"] = name
    if active:
        p["active"] = True
    return p


def cat_filter(name, tbl, col, values):
    return {"name": name, "field": CF(tbl, col), "type": "Categorical",
            "filter": {"Version": 2, "From": [{"Name": "x", "Entity": tbl, "Type": 0}],
                       "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "x"}},
                                                                                   "Property": col}}],
                                                        "Values": [[{"Literal": {"Value": v}}] for v in values]}}}]},
            "howCreated": "User"}


def medida_filter(name, medida, minimo):
    """Filtro avanzado: medida >= mínimo (ComparisonKind 2)."""
    return {"name": name, "field": MF(MT, medida), "type": "Advanced",
            "filter": {"Version": 2, "From": [{"Name": "m", "Entity": MT, "Type": 0}],
                       "Where": [{"Condition": {"Comparison": {
                           "ComparisonKind": 2,
                           "Left": {"Measure": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": medida}},
                           "Right": {"Literal": {"Value": f"{minimo}L"}}}}}]},
            "howCreated": "User"}


def caja(title=None, borde=True, fondo="#FFFFFF", subtitulo=None):
    """Contenedor de un visual: fondo, borde, título y subtítulo opcional (texto, color)."""
    vco = {"background": [{"properties": {"show": B(True), "color": C(fondo), "transparency": Dn(0)}}],
           "dropShadow": [{"properties": {"show": B(False)}}]}
    if subtitulo:
        vco["subTitle"] = [{"properties": {"show": B(True), "text": S(subtitulo[0]), "fontSize": Dn(9),
                                           "fontColor": C(subtitulo[1])}}]
    else:
        vco["subTitle"] = [{"properties": {"show": B(False)}}]
    if borde:
        vco["border"] = [{"properties": {"show": B(True), "color": C(BORDE), "radius": Dn(6)}}]
    if title:
        vco["title"] = [{"properties": {"show": B(True), "text": S(title), "fontSize": Dn(11), "fontColor": C(MEDIANOCHE),
                                        "bold": B(True)}}]
    else:
        vco["title"] = [{"properties": {"show": B(False)}}]
    return vco


# ---------------------------------------------------------------------------------------------------------------------
# Página PBIR
# ---------------------------------------------------------------------------------------------------------------------

class Pagina:
    def __init__(self, key, nombre, alto=720):
        self.key, self.nombre, self.id, self.alto = key, nombre, hid("pagina", key), alto
        self.visuales = []
        self.z = 0

    def add(self, key, x, y, w, h, visual, extra=None):
        # Un visual no admite dos campos distintos con el mismo nombre visible: los repetidos se distinguen con
        # espacios al final, que no se ven.
        vistos = {}
        for d in visual.get("query", {}).get("queryState", {}).values():
            for p in d["projections"]:
                n = p.get("displayName")
                if n is None or vistos.get(n) == p["queryRef"]:
                    continue
                while n in vistos:
                    n += " "
                p["displayName"] = n
                vistos[n] = p["queryRef"]
        self.z += 1000
        d = {"$schema": VIS, "name": hid(self.key, key),
             "position": {"x": x, "y": y, "z": self.z, "height": h, "width": w, "tabOrder": self.z}, "visual": visual}
        if extra:
            d.update(extra)
        self.visuales.append(d)
        return d

    # -- piezas básicas --
    def rect(self, key, x, y, w, h, fill, radius=0):
        objs = {"shape": [{"properties": {"tileShape": S("rectangle" if not radius else "roundedRectangle")}}],
                "rotation": [{"properties": {"shapeAngle": L("0L")}}],
                "fill": [{"properties": {"fillColor": C(fill)}, "selector": {"id": "default"}}],
                "outline": [{"properties": {"show": B(False)}, "selector": {"id": "default"}}]}
        if radius:
            objs["shape"][0]["properties"]["roundEdge"] = Dn(radius)
        return self.add(key, x, y, w, h, {"visualType": "shape", "objects": objs, "drillFilterOtherVisuals": True},
                        {"howCreated": "InsertVisualButton"})

    def texto(self, key, x, y, w, h, text, size=12, color=MEDIANOCHE, bold=False, align="left", sin_margen=False):
        style = {"fontSize": f"{size}pt", "color": color}
        if bold:
            style["fontWeight"] = "bold"
        para = {"textRuns": [{"value": text, "textStyle": style}]}
        if align != "left":
            para["horizontalTextAlignment"] = align
        relleno = {"top": Dn(0), "bottom": Dn(0)}
        if sin_margen:
            relleno.update({"left": Dn(0), "right": Dn(0)})
        return self.add(key, x, y, w, h, {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": [para]}}]},
                                          "visualContainerObjects": {"background": [{"properties": {"show": B(False)}}],
                                                                     "padding": [{"properties": relleno}]},
                                          "drillFilterOtherVisuals": True})

    def logo(self, key, x, y, w, h, recurso=LOGO, nombre="Logo Minera Demo"):
        img = {"sourceFile": {"image": {"name": S(nombre),
                                        "url": {"expr": {"ResourcePackageItem": {"PackageName": "RegisteredResources", "PackageType": 1,
                                                                                 "ItemName": recurso}}},
                                        "scaling": S("Normal")}},
               "fit": S("Fit")}
        return self.add(key, x, y, w, h, {"visualType": "image", "objects": {"image": [{"properties": img}]},
                                          "visualContainerObjects": {"background": [{"properties": {"show": B(False)}}]},
                                          "drillFilterOtherVisuals": True})

    def boton(self, key, x, y, w, h, destino, text=None, icon=None, fg="#FFFFFF", size=11, hover=CIELO, align="left"):
        """Botón transparente que navega a otra página (destino = id de la página)."""
        objs = {"fill": [{"properties": {"show": B(True), "fillColor": C("#FFFFFF"), "transparency": Dn(100)}, "selector": {"id": "default"}},
                         {"properties": {"show": B(True), "fillColor": C(hover), "transparency": Dn(78)}, "selector": {"id": "hover"}}],
                "outline": [{"properties": {"show": B(False)}, "selector": {"id": "default"}}],
                "icon": [{"properties": ({"show": B(True), "shapeType": S(icon), "lineColor": C(fg)} if icon else {"show": B(False)}),
                          "selector": {"id": "default"}}],
                "text": [{"properties": ({"show": B(True), "text": S(text), "fontColor": C(fg), "fontSize": Dn(size), "bold": B(True),
                                          "horizontalAlignment": S(align)} if text else {"show": B(False)}),
                          "selector": {"id": "default"}}]}
        apagado = [{"properties": {"show": B(False)}}]
        vis = {"visualType": "actionButton", "objects": objs,
               "visualContainerObjects": {"title": apagado, "background": apagado, "border": apagado, "dropShadow": apagado,
                                          "visualHeader": apagado, "visualTooltip": apagado,
                                          "visualLink": [{"properties": {"show": B(True), "type": S("PageNavigation"),
                                                                         "navigationSection": S(destino)}}]},
               "drillFilterOtherVisuals": True}
        return self.add(key, x, y, w, h, vis, {"howCreated": "InsertVisualButton"})

    def texto_medida(self, key, x, y, w, h, medida, size=11, color=GRIS, color_medida=None, semibold=False):
        """Una línea con el valor de una medida (tarjeta clásica sin etiqueta)."""
        apagado = [{"properties": {"show": B(False)}}]
        objs = {"labels": [{"properties": {"color": CM(color_medida) if color_medida else C(color), "fontSize": Dn(size),
                                           "fontFamily": S("Segoe UI Semibold" if semibold else "Segoe UI")}}],
                "categoryLabels": apagado, "wordWrap": apagado}
        vco = {"title": apagado, "background": apagado, "border": apagado, "dropShadow": apagado, "visualHeader": apagado,
               "visualTooltip": apagado,
               "padding": [{"properties": {"top": Dn(0), "bottom": Dn(0), "left": Dn(0), "right": Dn(0)}}]}
        vis = {"visualType": "card", "query": {"queryState": {"Values": {"projections": [proj(MF(MT, medida), medida)]}}},
               "objects": objs, "visualContainerObjects": vco, "drillFilterOtherVisuals": True}
        return self.add(key, x, y, w, h, vis)

    def grafico(self, key, x, y, w, h, tipo, titulo, categoria=None, valores=(), serie=None, valores2=(), orden=None,
                colores=None, color_medida=None, colores_serie=None, filtros=None, etiquetas=True, leyenda=False,
                eje_categorico=False, tooltips=(), pos_leyenda="Top", miles=False, subtitulo=None):
        qs = {}
        if categoria:
            qs["Category"] = {"projections": [proj(categoria, active=True)]}
        qs["Y"] = {"projections": [proj(f, n) for f, n in valores]}
        if valores2:
            qs["Y2"] = {"projections": [proj(f, n) for f, n in valores2]}
        if serie:
            qs["Series"] = {"projections": [proj(serie)]}
        if tooltips:
            qs["Tooltips"] = {"projections": [proj(f, n) for f, n in tooltips]}
        query = {"queryState": qs}
        if orden:
            campo, direccion = orden
            query["sortDefinition"] = {"sort": [{"field": campo, "direction": direccion}]}
        eje = {"fontSize": Dn(9), "showAxisTitle": B(False)}
        if eje_categorico:
            eje["axisType"] = S("Categorical")
        valor = {"fontSize": Dn(9), "showAxisTitle": B(False)}
        if valores2:
            valor["secShow"] = B(False)  # el plan (Y2) comparte el eje del real
        etiq = {"show": B(etiquetas), "fontSize": Dn(9)}
        if miles:
            etiq["labelDisplayUnits"] = Dn(1000)
        objs = {"labels": [{"properties": etiq}],
                "legend": [{"properties": {"show": B(leyenda), "position": S(pos_leyenda), "fontSize": Dn(9)}}],
                "categoryAxis": [{"properties": eje}],
                "valueAxis": [{"properties": valor}]}
        # Sin etiqueta en la línea del plan: su valor queda a la altura del real y las etiquetas se pisarían
        for f, _ in valores2:
            objs["labels"].append({"properties": {"show": B(False)}, "selector": {"metadata": qref(f)}})
        dp = []
        if colores or color_medida:
            primera = qref(valores[0][0]) if valores else None
            base = next((c for f, c in (colores or []) if qref(f) == primera), CIELO)
            dp.append({"properties": {"defaultColor": C(base)}})
        if color_medida:
            dp.append({"properties": {"fill": CM(color_medida)}, "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}})
        for f, c in (colores or []):
            dp.append({"properties": {"fill": C(c)}, "selector": {"metadata": qref(f)}})
        for campo, valor_, c in (colores_serie or []):
            dp.append({"properties": {"fill": C(c)}, "selector": {"data": [{"scopeId": {"Comparison": {
                "ComparisonKind": 0, "Left": campo, "Right": {"Literal": {"Value": valor_}}}}}]}})
        if dp:
            objs["dataPoint"] = dp
        if valores2:
            objs["lineStyles"] = [{"properties": {"strokeWidth": Dn(2), "showMarker": B(True)}, "selector": {"metadata": qref(f)}}
                                  for f, _ in valores2]
        vis = {"visualType": tipo, "query": query, "objects": objs, "visualContainerObjects": caja(titulo, subtitulo=subtitulo),
               "drillFilterOtherVisuals": True}
        return self.add(key, x, y, w, h, vis, {"filterConfig": {"filters": filtros}} if filtros else None)

    def tabla(self, key, x, y, w, h, campos, anchos=None, alineacion=None, cf=None, orden=None, font=11, padding=6,
              cabecera=MEDIANOCHE, titulo=None, filtros=None, borde=True, autoajuste=False):
        """Tabla simple (tableEx): sin jerarquía de filas y con todas las filas del mismo alto."""
        query = {"queryState": {"Values": {"projections": [proj(f, n) for f, n in campos]}}}
        if orden:
            query["sortDefinition"] = {"sort": [{"field": f, "direction": d} for f, d in orden]}
        objs = {"columnHeaders": [{"properties": {"fontSize": Dn(font - 1), "fontColor": C("#FFFFFF"), "backColor": C(cabecera),
                                                  "bold": B(True), "alignment": S("Center"), "wordWrap": B(False),
                                                  "autoSizeColumnWidth": B(autoajuste)}}],
                "values": [{"properties": {"fontSize": Dn(font), "fontColorPrimary": C(MEDIANOCHE), "backColorPrimary": C("#FFFFFF"),
                                           "fontColorSecondary": C(MEDIANOCHE), "backColorSecondary": C("#FFFFFF"),
                                           "wordWrap": B(False)}}],
                "grid": [{"properties": {"rowPadding": Dn(padding), "gridHorizontal": B(True), "gridHorizontalColor": C(CUADRICULA),
                                         "gridVertical": B(False), "outlineColor": C(CUADRICULA)}}],
                "total": [{"properties": {"totals": B(False)}}]}
        for campo, medida_fondo, medida_texto in (cf or []):
            props = {}
            if medida_fondo:
                props["backColor"] = CM(medida_fondo)
            if medida_texto:
                props["fontColor"] = CM(medida_texto)
            objs["values"].append({"properties": props, "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                                                       "metadata": qref(campo)}})
        if anchos:
            objs["columnWidth"] = [{"properties": {"value": Dn(a)}, "selector": {"metadata": qref(f)}} for f, a in anchos]
        if alineacion:
            objs["columnFormatting"] = [{"properties": {"alignment": S(a)}, "selector": {"metadata": qref(f)}} for f, a in alineacion]
        vis = {"visualType": "tableEx", "query": query, "objects": objs, "visualContainerObjects": caja(titulo, borde=borde),
               "drillFilterOtherVisuals": True}
        return self.add(key, x, y, w, h, vis, {"filterConfig": {"filters": filtros}} if filtros else None)

    def json(self):
        return {"$schema": PAGE, "name": self.id, "displayName": self.nombre,
                "displayOption": "FitToPage" if self.alto <= 720 else "FitToWidth", "height": self.alto, "width": 1280,
                "objects": {"background": [{"properties": {"color": C("#FFFFFF"), "transparency": Dn(0)}}]}}


def filtros_equipo(pag, key, tipo):
    """Solo equipos del tipo pedido (Truck) y activos en los indicadores."""
    return [cat_filter(hid(pag.key, key, "tipo"), "Dim_Equipo", "TipoEquipo", [f"'{tipo}'"]),
            cat_filter(hid(pag.key, key, "activo"), "Dim_Equipo", "Activo_KPI", ["1L"])]


# ---------------------------------------------------------------------------------------------------------------------
# TMDL
# ---------------------------------------------------------------------------------------------------------------------

def rango_txt(ini, fin):
    """Medida de texto «lun 02 a dom 08-06» a partir de dos fechas."""
    return (f'VAR i = {ini}\nVAR f = {fin}\nRETURN\n    IF(ISBLANK(i), BLANK(),\n'
            '        SUBSTITUTE(FORMAT(i, "ddd dd"), ".", "") & " a " & SUBSTITUTE(FORMAT(f, "ddd dd-mm"), ".", ""))')


def medida_tmdl(m):
    out = []
    if m.get("desc"):
        out.append(f"\t/// {m['desc']}")
    expr = m["expr"].strip("\n")
    if "\n" in expr:
        out.append(f"\tmeasure {q(m['name'])} =")
        out += ["\t\t\t" + ln for ln in expr.split("\n")]
    else:
        out.append(f"\tmeasure {q(m['name'])} = {expr}")
    if m.get("fmt"):
        out.append(f"\t\tformatString: {m['fmt']}")
    if m.get("hidden"):
        out.append("\t\tisHidden")
    if m.get("folder"):
        out.append(f"\t\tdisplayFolder: {m['folder']}")
    out.append(f"\t\tlineageTag: {m['tag']}")
    out.append("")
    return out


def columna_tmdl(tabla, nombre, dtype, fmt=None, sort_by=None, hidden=False, inferida=True):
    """Columna de una tabla calculada (DATATABLE)."""
    out = [f"\tcolumn {q(nombre)}", f"\t\tdataType: {dtype}"]
    if hidden:
        out.append("\t\tisHidden")
    if fmt:
        out.append(f"\t\tformatString: {fmt}")
    out += [f"\t\tlineageTag: {tag('col', tabla, nombre)}", "\t\tsummarizeBy: none"]
    if inferida:
        out.append("\t\tisNameInferred")
    out.append(f"\t\tsourceColumn: [{nombre}]")
    if sort_by:
        out.append(f"\t\tsortByColumn: {q(sort_by)}")
    out += ["", "\t\tannotation SummarizationSetBy = Automatic", ""]
    return out


def tabla_calculada(nombre, desc, cols, fuente):
    """cols: [(nombre, dtype, fmt, sort_by, hidden)]; fuente: expresión DAX de la partición."""
    out = [f"/// {desc}", f"table {q(nombre)}", f"\tlineageTag: {tag('table', nombre)}", ""]
    for c in cols:
        out += columna_tmdl(nombre, *c)
    out += [f"\tpartition {q(nombre)} = calculated", "\t\tmode: import", "\t\tsource ="]
    out += ["\t\t\t\t" + ln for ln in fuente.strip("\n").split("\n")]
    out.append("")
    return "\n".join(out) + "\n"
