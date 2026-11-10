# -*- coding: utf-8 -*-
"""Renders del diseño del proyecto 03-governance-bi-as-code (informe «Gobernanza_uso_reportes», 6 páginas).

Genera en 03-governance-bi-as-code/capturas/ una imagen por página del informe:
  resumen.png (Resumen) · vistas.png (Vistas) · vistas_por_semana.png (Vistas por semana) ·
  sin_uso.png (Sin uso, recortada al contenido) · detalle.png (Detalle) · calidad.png (Calidad)

NO son capturas de Power BI Desktop: son renders dibujados con Pillow que siguen la disposición, el tema y los campos
del informe (desarrollo/generar_reporte.py) y calculan sus cifras con los CSV sintéticos de datos_sinteticos/csv/
(mismas reglas que el modelo: cuentas excluidas fuera, filas sin aperturas ni vistas fuera, estado del reporte).

Uso:  python cap_03.py        (se puede ejecutar desde cualquier carpeta)
"""
import csv
import json
import math
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from lib_render import Lienzo, LOGO_BLANCO, fmt  # noqa: E402

PROYECTO = AQUI.parents[1] / "03-governance-bi-as-code"
CSV_DIR = PROYECTO / "datos_sinteticos" / "csv"
SALIDA = PROYECTO / "capturas"
LEYENDA = "Render del diseño · datos sintéticos · Minera Demo"

# Tema del informe (generar_reporte.py): azul medianoche en paneles, página más oscura, semáforos solo en estados
MEDIANOCHE, AZUL, VIOLETA = "#1B2A41", "#4F9DDE", "#7B61C9"
FONDO, OSCURO, BORDE, FILA_ALTERNA = "#0F1827", "#142033", "#33476B", "#22344F"
BLANCO, TEXTO, TEXTO_TENUE = "#FFFFFF", "#D5DEEA", "#9FB0C8"
ROJO, AZUL_CLARO, AZUL_MAPA = "#FF8A80", "#9CCBF0", "#2F6FB5"
PX = 4 / 3   # 1 pt = 1,333 px en un lienzo de 1920x1080 (96 ppp)
AVISO = "DATOS SINTÉTICOS · empresa ficticia Minera Demo · 03-03-2025 al 31-05-2025"
LIMITACIONES = (
    "1) los datos son sintéticos y no describen ninguna operación real; 2) el informe de métricas de uso del servicio "
    "guarda unos 30 días, por lo que un histórico más largo necesita una extracción periódica (ver docs/GUIA.md); "
    "3) las aperturas no equivalen a vistas de página; 4) una persona puede tener más de una cuenta "
    "(por ejemplo una interna y una externa).")
REPORTE_DETALLE = "Tablero Movimiento Mina"   # el reporte en uso que destaca esperados.json
AREA_DETALLE = "Operaciones Mina"


# ------------------------------------------------------------------------------------------------- datos
def leer_datos():
    """Agrega los CSV con las mismas reglas del modelo (Fact_Uso, Dim_Reporte, Dim_Usuario, Dim_Fecha, Dim_Area)."""
    cfg = json.loads((PROYECTO / "desarrollo" / "config_datos.json").read_text(encoding="utf-8"))
    excluidos = {u.strip().lower() for u in cfg["usuarios_excluidos"]}

    with open(CSV_DIR / "dim_reporte.csv", encoding="utf-8", newline="") as f:
        inventario = list(csv.DictReader(f))
    with open(CSV_DIR / "fact_uso.csv", encoding="utf-8", newline="") as f:
        filas = [r for r in csv.DictReader(f)]
    with open(CSV_DIR / "lecturas_area.csv", encoding="utf-8", newline="") as f:
        lecturas = {r["workspace_id"]: r["ultima_lectura"] for r in csv.DictReader(f)}
    filas = [r for r in filas if r["usuario"].strip().lower() not in excluidos
             and (int(r["aperturas"]) != 0 or int(r["vistas_pagina"]) != 0)]

    def area_de(ws):   # "WS-DEMO-Operaciones_Mina-PROD" -> "Operaciones Mina"
        return ws.removeprefix("WS-DEMO-").removesuffix("-PROD").replace("_", " ").strip()

    nombres = defaultdict(int)
    for d in inventario:
        nombres[d["report_nombre"].lower()] += 1
    reportes = {}
    ultima_lectura = {}
    for d in inventario:
        area = area_de(d["workspace_nombre"])
        etiqueta = d["report_nombre"] + (f" · {area}" if nombres[d["report_nombre"].lower()] > 1 else "")
        reportes[d["report_id"]] = {"id": d["report_id"], "area": area, "reporte": etiqueta, "nombre": d["report_nombre"],
                                    "ap": 0, "vi": 0, "ap_sin_vistas": 0, "usu": set(), "ultima": None}
        ultima_lectura[area] = lecturas[d["workspace_id"]]

    registros = []   # (report_id, usuario, fecha, aperturas, vistas)
    por_dia = defaultdict(lambda: {"ap": 0, "vi": 0, "usu": set()})
    por_usuario = defaultdict(lambda: {"ap": 0, "vi": 0})
    for r in filas:
        rep = reportes[r["report_id"]]
        ap, vi, dia, usu = int(r["aperturas"]), int(r["vistas_pagina"]), r["fecha"], r["usuario"].strip().lower()
        registros.append((r["report_id"], usu, date.fromisoformat(dia), ap, vi))
        rep["ap"] += ap
        rep["vi"] += vi
        rep["ap_sin_vistas"] += ap if vi == 0 else 0
        rep["usu"].add(usu)
        rep["ultima"] = max(rep["ultima"] or dia, dia)
        d = por_dia[dia]
        d["ap"] += ap
        d["vi"] += vi
        d["usu"].add(usu)
        por_usuario[usu]["ap"] += ap
        por_usuario[usu]["vi"] += vi

    f0, f1 = min(por_dia), max(por_dia)
    f0, f1 = date.fromisoformat(f0), date.fromisoformat(f1)
    dias = [f0 + timedelta(days=i) for i in range((f1 - f0).days + 1)]   # calendario continuo (Dim_Fecha)
    serie = {k: [(por_dia[x.isoformat()][k] if k != "usu" else len(por_dia[x.isoformat()]["usu"]))
                 if x.isoformat() in por_dia else 0 for x in dias] for k in ("ap", "vi", "usu")}

    for rep in reportes.values():
        rep["estado"] = "En uso" if rep["vi"] >= 1 else ("Solo aperturas" if rep["ap"] > 0 else "Sin uso")
        rep["dias_desde"] = (f1 - date.fromisoformat(rep["ultima"])).days if rep["ultima"] else None

    lista = list(reportes.values())
    estados = {e: sum(1 for r in lista if r["estado"] == e) for e in ("En uso", "Solo aperturas", "Sin uso")}
    por_area = defaultdict(lambda: {"En uso": 0, "Solo aperturas": 0, "Sin uso": 0, "total": 0, "ap": 0, "vi": 0})
    for r in lista:
        por_area[r["area"]][r["estado"]] += 1
        por_area[r["area"]]["total"] += 1
        por_area[r["area"]]["ap"] += r["ap"]
        por_area[r["area"]]["vi"] += r["vi"]

    datos = {"reportes": lista, "dias": dias, "serie": serie, "estados": estados, "por_area": dict(por_area),
             "ap": sum(r["ap"] for r in lista), "vi": sum(r["vi"] for r in lista), "usuarios": len(por_usuario),
             "primera": f0, "ultima": f1, "registros": registros, "por_usuario": dict(por_usuario),
             "dias_con_datos": len(por_dia), "ultima_lectura": ultima_lectura,
             "ap_sin_vistas": sum(r["ap_sin_vistas"] for r in lista)}

    # Coherencia con el informe: los esperados que deja generar_datos.py
    esp = json.loads((PROYECTO / "datos_sinteticos" / "esperados.json").read_text(encoding="utf-8"))
    assert datos["ap"] == esp["aperturas"] and datos["vi"] == esp["vistas_pagina"], "no coinciden con esperados.json"
    assert estados == {"En uso": esp["reportes_en_uso"], "Solo aperturas": esp["reportes_solo_aperturas"],
                       "Sin uso": esp["reportes_sin_uso"]}, "estados distintos de esperados.json"
    assert len(lista) == esp["reportes"] and datos["usuarios"] == esp["usuarios"]
    assert datos["ap_sin_vistas"] == esp["aperturas_sin_vistas"], "aperturas sin vistas distintas de esperados.json"
    assert len(dias) == esp["dias"] and str(f0) == esp["datos_desde"] and str(f1) == esp["ultima_actividad"]
    assert len(por_area) == esp["areas"]
    for a, v in por_area.items():
        e = esp["por_area"][a]
        assert (v["ap"], v["vi"], v["total"]) == (e["ap"], e["vi"], e["total"]), f"área {a} distinta de esperados.json"
    ext = {u for u in por_usuario if u.startswith("ext.")}
    assert len(ext) == esp["usuarios_externos"]
    assert sum(por_usuario[u]["ap"] for u in ext) == esp["aperturas_externos"]
    assert sum(por_usuario[u]["vi"] for u in ext) == esp["vistas_externos"]
    assert datos["ap"] - esp["aperturas_externos"] == esp["aperturas_internos"]
    assert [r["reporte"] for r in lista if r["nombre"].lower() in {n.lower() for n in esp["nombres_repetidos"]}]
    assert round(datos["vi"] / datos["ap"], 1) == esp["paginas_por_apertura"]
    return datos


def lunes(f):
    return f - timedelta(days=f.weekday())


def etiqueta_semana(ini, d):
    """Etiqueta de Dim_Fecha[Semana]: «dd-MM al dd-MM-aaaa», con «(parcial)» si los datos no cubren los 7 días."""
    desde, hasta = max(ini, d["primera"]), min(ini + timedelta(days=6), d["ultima"])
    lineas = [desde.strftime("%d-%m") + " al", hasta.strftime("%d-%m-%Y")]
    return lineas + (["(parcial)"] if (hasta - desde).days < 6 else [])


# ------------------------------------------------------------------------------------------------- piezas
def ticks(maximo, n=4):
    """Marcas «bonitas» del eje de valores, de 0 hacia arriba."""
    crudo = max(maximo, 1) / n
    mag = 10 ** math.floor(math.log10(crudo))
    paso = next(m * mag for m in (1, 2, 5, 10) if m * mag >= crudo)
    return [i * paso for i in range(math.ceil(maximo / paso) + 1)]


def num(v, dec=0):
    return fmt(v, dec)


def fecha_txt(f):
    return f.strftime("%d-%m-%Y")


def mezcla(c0, c1, t):
    a = [int(c0[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02X%02X%02X" % tuple(round(p + (q - p) * t) for p, q in zip(a, b))


def envolver(c, txt, tam, ancho):
    """Parte un texto en líneas que caben en `ancho` px (por palabras)."""
    lineas, act = [], ""
    for p in txt.split():
        intento = (act + " " + p).strip()
        if act and c.ancho_texto(intento, tam) > ancho:
            lineas.append(act)
            act = p
        else:
            act = intento
    return lineas + [act]


def cabecera(c, titulo, extra=None):
    """Banda del título (fondo azul medianoche, marca violeta), aviso rojo de datos sintéticos y logo."""
    c.caja(16, 8, 1888, 50, fill=MEDIANOCHE, borde=BORDE, r=8)
    c.caja(30, 19, 5, 28, fill=VIOLETA, r=2)
    c.texto(46, 33, titulo, 18 * PX, BLANCO, bold=True, ancla="lm")
    if extra:
        c.texto(46 + c.ancho_texto(titulo, 18 * PX, True) + 24, 33, extra, 12 * PX, TEXTO_TENUE, ancla="lm")
    tam = 11 * PX
    fin = 1722
    c.texto(fin, 33, AVISO, tam, ROJO, bold=True, ancla="rm")
    x0 = fin - c.ancho_texto(AVISO, tam, True) - 26   # triángulo de aviso (el glifo ⚠ no está en Segoe UI)
    c.poligono([(x0 + 9, 24), (x0 + 18, 41), (x0, 41)], fill=ROJO)
    c.texto(x0 + 9, 38.5, "!", 11, MEDIANOCHE, bold=True, ancla="ms")
    c.pegar(LOGO_BLANCO, 1742, 13, w=150)


def panel(c, x, y, w, h, titulo=None):
    c.caja(x, y, w, h, fill=MEDIANOCHE, borde=BORDE, r=8)
    if titulo:
        c.texto(x + 12, y + 22, titulo.upper(), 14 * PX, TEXTO, bold=True, ancla="lm")


def tarjeta(c, x, y, w, h, titulo, valor, color=BLANCO):
    panel(c, x, y, w, h, titulo)
    c.texto(x + w / 2, y + 68, valor, 34 * PX, color, bold=True, ancla="mm")


def segmentacion(c, x, y, w, h, titulo, valor="Todas"):
    """Segmentación en modo desplegable (valor «Todas» = sin selección)."""
    panel(c, x, y, w, h, titulo)
    bx, bw = x + 12, w - 24
    by, bh = (y + 48, 38) if h >= 100 else (y + 38, 30)
    c.caja(bx, by, bw, bh, fill=MEDIANOCHE, borde=TEXTO_TENUE, r=3)
    c.texto(bx + 12, by + bh / 2, valor, 12 * PX, BLANCO, ancla="lm")
    cx, cy = bx + bw - 22, by + bh / 2
    c.linea([(cx - 6, cy - 3), (cx, cy + 3), (cx + 6, cy - 3)], TEXTO_TENUE, 2)


def leyenda(c, cx, y, items):
    """Leyenda superior centrada: círculo de color + nombre de la medida."""
    tam = 12 * PX
    anchos = [c.ancho_texto(n, tam) + 17 for n, _ in items]
    total = sum(anchos) + 22 * (len(items) - 1)
    x = cx - total / 2
    for (nombre, col), a in zip(items, anchos):
        c.elipse(x + 4.5, y, 4.5, fill=col)
        c.texto(x + 17, y, nombre, tam, TEXTO, ancla="lm")
        x += a + 22


def leyenda_derecha(c, x, cy, items):
    """Leyenda a la derecha, centrada en vertical (posición RightCenter)."""
    tam = 12 * PX
    y = cy - (len(items) - 1) * 12
    for nombre, col in items:
        c.elipse(x + 4.5, y, 4.5, fill=col)
        c.texto(x + 17, y, nombre, tam, TEXTO, ancla="lm")
        y += 24


def grafico_lineas(c, x, y, w, h, titulo, dias, series, tope, cats=None, ley_der=False, n_marcas=4, paso_x=28):
    """Líneas con eje de fechas continuo (cats=None) o de categorías de texto (cats: lista de listas de líneas).
    series: [(nombre, valores, color)]; leyenda solo con 2 o más series (arriba, o a la derecha con ley_der)."""
    panel(c, x, y, w, h, titulo)
    tam = 12 * PX
    arriba = y + 56
    der = x + w - 22
    if len(series) > 1:
        items = [(n, col) for n, _, col in series]
        if ley_der:
            ancho_ley = max(c.ancho_texto(n, tam) for n, _ in items) + 17
            leyenda_derecha(c, der - ancho_ley, y + h / 2 + 8, items)
            der -= ancho_ley + 28
            arriba = y + 48
        else:
            leyenda(c, x + w / 2, y + 56, items)
            arriba = y + 74
    marcas = ticks(tope, n_marcas)
    izq = x + 14 + max(c.ancho_texto(num(m), tam) for m in marcas) + 8
    if not cats:
        izq = max(izq, x + 12 + c.ancho_texto("00-00-0000", tam) / 2)   # la primera fecha (centrada) no sale del panel
    pie = 38 if not cats else 8 + 16 * max(len(k) for k in cats) + 6
    abajo = y + h - pie
    top = marcas[-1]
    for m in marcas:
        yy = abajo - (abajo - arriba) * m / top
        c.linea([(izq, yy), (der, yy)], BORDE, 1)
        c.texto(izq - 8, yy, num(m), tam, TEXTO_TENUE, ancla="rm")
    n = len(dias) - 1
    if cats:   # categorías: cada punto en el centro de su banda
        banda = (der - izq) / len(cats)
        xs = [izq + banda * (i + 0.5) for i in range(len(cats))]
        for xx, lineas in zip(xs, cats):
            for k, ln in enumerate(lineas):
                c.texto(xx, abajo + 8 + 16 * k, ln, tam, TEXTO_TENUE, ancla="ma")
    else:
        xs = [izq + (der - izq) * i / n for i in range(n + 1)]
        for i in range(0, n + 1, paso_x):
            c.texto(xs[i], abajo + 9, dias[i].strftime("%d-%m-%Y"), tam, TEXTO_TENUE, ancla="ma")
    for _, vals, col in series:
        c.linea([(xx, abajo - (abajo - arriba) * v / top) for xx, v in zip(xs, vals)], col, 2.5)


def grafico_barras_estado(c, x, y, w, h, titulo, por_area):
    """Barras horizontales apiladas: reportes en uso / solo aperturas / sin uso por área."""
    panel(c, x, y, w, h, titulo)
    series = [("Reportes en uso", "En uso", AZUL), ("Reportes solo aperturas", "Solo aperturas", VIOLETA),
              ("Reportes sin uso", "Sin uso", ROJO)]
    leyenda(c, x + w / 2, y + 56, [(n, col) for n, _, col in series])
    # Orden por defecto de Power BI: por la primera medida, de mayor a menor
    areas = sorted(por_area, key=lambda a: (-por_area[a]["En uso"], a))
    tam = 12 * PX
    izq = x + 14 + max(c.ancho_texto(a, tam) for a in areas) + 10
    der, arriba, abajo = x + w - 24, y + 84, y + h - 40
    marcas = ticks(max(sum(por_area[a][e] for e in ("En uso", "Solo aperturas", "Sin uso")) for a in areas))
    top = marcas[-1]
    for m in marcas:
        xx = izq + (der - izq) * m / top
        c.linea([(xx, arriba), (xx, abajo)], BORDE, 1)
        c.texto(xx, abajo + 9, num(m), tam, TEXTO_TENUE, ancla="ma")
    banda = (abajo - arriba) / len(areas)
    grosor = banda * 0.7
    for i, a in enumerate(areas):
        y0 = arriba + banda * i + (banda - grosor) / 2
        c.texto(izq - 10, y0 + grosor / 2, a, tam, TEXTO_TENUE, ancla="rm")
        acum = 0
        for _, estado, col in series:
            v = por_area[a][estado]
            if v:
                xa = izq + (der - izq) * acum / top
                xb = izq + (der - izq) * (acum + v) / top
                c.caja(xa, y0, xb - xa, grosor, fill=col)
                acum += v


def grafico_columnas(c, x, y, w, h, titulo, items, color):
    """Columnas con el valor sobre cada barra (sin eje de valores) y los nombres envueltos bajo cada una."""
    panel(c, x, y, w, h, titulo)
    tam = 12 * PX
    izq, der = x + 20, x + w - 20
    banda = (der - izq) / len(items)
    lineas = [envolver(c, n, tam, banda - 14) for n, _ in items]
    base = y + h - 16 - 20 * max(len(k) for k in lineas)
    arriba = y + 70
    top = max(v for _, v in items)
    c.linea([(izq, base), (der, base)], BORDE, 1)
    for i, ((_, v), ls) in enumerate(zip(items, lineas)):
        cx = izq + banda * (i + 0.5)
        bw = banda * 0.7
        bh = (base - arriba) * v / top
        c.caja(cx - bw / 2, base - bh, bw, bh, fill=color, r=2)
        c.texto(cx, base - bh - 6, num(v), tam, BLANCO, ancla="ms")
        for k, ln in enumerate(ls):
            c.texto(cx, base + 9 + 20 * k, ln, tam, TEXTO_TENUE, ancla="ma")


def barra_desplazamiento(c, x, y0, y1, visibles, total):
    """Barra vertical de desplazamiento: el contenido supera el alto del visual."""
    c.caja(x, y0, 6, y1 - y0, fill="#223552", r=3)
    c.caja(x, y0, 6, (y1 - y0) * visibles / total, fill="#5B6F90", r=3)


def tabla(c, x, y, w, h, titulo, cols, filas, total=None, tam=14, alto_fila=31, alto_enc=34, sangria=10):
    """Tabla (tableEx): encabezado oscuro, filas alternas y fila de total opcional. Si no caben todas las filas,
    se muestran las primeras con barra de desplazamiento (la fila de total queda al final, fuera de la vista).
    cols: [(encabezado, ancho en px, 'l'|'r')]; filas: listas de textos."""
    panel(c, x, y, w, h, titulo)
    tx, ty = x + sangria, y + 46
    ancho_total = sum(a for _, a, _ in cols)
    xs = [tx]
    for _, a, _ in cols:
        xs.append(xs[-1] + a)
    disp = h - 46 - alto_enc - 8
    n_vis = int(disp // alto_fila)
    desborda = len(filas) + (1 if total else 0) > n_vis

    def fila(yy, valores, fondo, color, bold, alto):
        c.caja(tx, yy, ancho_total, alto, fill=fondo)
        for (_, a, al), v, x0 in zip(cols, valores, xs):
            if v == "" or v is None:
                continue
            if al == "r":
                c.texto(x0 + a - 10, yy + alto / 2, v, tam, color, bold=bold, ancla="rm")
            else:
                c.texto(x0 + 10, yy + alto / 2, v, tam, color, bold=bold, ancla="lm")
        c.linea([(tx, yy + alto), (tx + ancho_total, yy + alto)], BORDE, 1)

    fila(ty, [e for e, _, _ in cols], OSCURO, BLANCO, True, alto_enc)
    yy = ty + alto_enc
    for i, f in enumerate(filas[:n_vis] if desborda else filas):
        fila(yy, f, MEDIANOCHE if i % 2 == 0 else FILA_ALTERNA, BLANCO, False, alto_fila)
        yy += alto_fila
    if total and not desborda:
        fila(yy, total, OSCURO, BLANCO, True, alto_fila)
    if desborda:
        barra_desplazamiento(c, x + w - 9, ty + alto_enc, ty + alto_enc + n_vis * alto_fila, n_vis,
                             len(filas) + (1 if total else 0))


def matriz(c, x, y, w, h, titulo, filas, cols, valores, totales, ancho_cab=290, ancho_tot=80, tam=13.5):
    """Matriz (pivotTable) de un nivel con mapa de calor en el fondo de las celdas (azul medianoche -> azul del mapa) y
    columna de total sin colorear. Si las filas no caben, se ven las primeras con barra de desplazamiento.
    cols: lista de listas de líneas del encabezado; valores[i][j]; totales[i]."""
    panel(c, x, y, w, h, titulo)
    mx, my = x + 10, y + 46
    mw = w - 20
    alto_enc = 18 * max(len(k) for k in cols) + 10
    ancho_col = (mw - ancho_cab - ancho_tot) / len(cols)
    disp = h - 46 - alto_enc - 8
    n_vis = min(len(filas), int(disp // 25))
    alto = disp / n_vis if n_vis < len(filas) else 25
    vmin = min(min(f) for f in valores)
    vmax = max(max(f) for f in valores)
    xs = [mx + ancho_cab + ancho_col * j for j in range(len(cols) + 1)]
    xt = xs[-1]
    c.caja(mx, my, mw, alto_enc, fill=OSCURO)
    for j, lineas in enumerate(cols):
        for k, ln in enumerate(lineas):
            c.texto(xs[j + 1] - 8, my + 5 + 9 + 18 * k + (alto_enc - 10 - 18 * len(lineas)) / 2, ln, tam, BLANCO,
                    bold=True, ancla="rm")
    c.texto(xt + ancho_tot - 8, my + alto_enc / 2, "Total", tam, BLANCO, bold=True, ancla="rm")
    for i in range(n_vis):
        yy = my + alto_enc + alto * i
        c.caja(mx, yy, ancho_cab, alto, fill=MEDIANOCHE)
        c.texto(mx + 8, yy + alto / 2, filas[i], tam, BLANCO, ancla="lm")
        for j in range(len(cols)):
            v = valores[i][j]
            c.caja(xs[j], yy, ancho_col, alto, fill=mezcla(MEDIANOCHE, AZUL_MAPA, (v - vmin) / ((vmax - vmin) or 1)))
            c.texto(xs[j + 1] - 8, yy + alto / 2, num(v), tam, BLANCO, ancla="rm")
        c.caja(xt, yy, ancho_tot, alto, fill=OSCURO)
        c.texto(xt + ancho_tot - 8, yy + alto / 2, num(totales[i]), tam, BLANCO, bold=True, ancla="rm")
    ybase = my + alto_enc + alto * n_vis
    for i in range(n_vis + 1):
        c.linea([(mx, my + alto_enc + alto * i), (mx + mw, my + alto_enc + alto * i)], BORDE, 1)
    for xx in [mx + ancho_cab] + xs[1:]:
        c.linea([(xx, my), (xx, ybase)], BORDE, 1)
    if n_vis < len(filas):
        barra_desplazamiento(c, x + w - 9, my + alto_enc, ybase, n_vis, len(filas) + 1)


# ------------------------------------------------------------------------------------------------- páginas
def pagina_resumen(d):
    c = Lienzo(1920, 1080, FONDO)
    cabecera(c, "Gobernanza de uso de reportes Power BI — workspaces PROD")
    e = d["estados"]
    tarjeta(c, 16, 64, 364, 100, "Reportes monitoreados", str(len(d["reportes"])))
    tarjeta(c, 396, 64, 364, 100, "En uso", str(e["En uso"]), AZUL)
    tarjeta(c, 776, 64, 364, 100, "Solo aperturas", str(e["Solo aperturas"]), VIOLETA)
    tarjeta(c, 1156, 64, 364, 100, "Sin uso", str(e["Sin uso"]), ROJO)
    segmentacion(c, 1536, 64, 368, 100, "Área de trabajo")

    s = d["serie"]
    grafico_lineas(c, 16, 180, 560, 240, "Aperturas y vistas de página por día", d["dias"],
                   [("Aperturas", s["ap"], VIOLETA), ("Vistas de página", s["vi"], AZUL)], max(s["ap"] + s["vi"]))
    grafico_lineas(c, 16, 436, 560, 220, "Usuarios únicos por día", d["dias"],
                   [("Usuarios únicos", s["usu"], AZUL_CLARO)], max(s["usu"]))
    grafico_barras_estado(c, 16, 672, 560, 392, "Estado de los reportes por área", d["por_area"])

    # Tabla de detalle: más vistas primero (a igualdad, más aperturas)
    orden = sorted(d["reportes"], key=lambda r: (-r["vi"], -r["ap"], r["reporte"]))
    cols = [("Área", 190, "l"), ("Reporte", 380, "l"), ("Aperturas", 120, "r"), ("Vistas de página", 150, "r"),
            ("Usuarios únicos", 150, "r"), ("Págs. por apertura", 160, "r"), ("Estado del reporte", 142, "l")]
    filas = [[r["area"], r["reporte"], num(r["ap"]), num(r["vi"]), num(len(r["usu"])),
              num(r["vi"] / r["ap"] if r["ap"] else 0, 1), r["estado"]] for r in orden]
    total = ["Total", "", num(d["ap"]), num(d["vi"]), num(d["usuarios"]), num(d["vi"] / d["ap"], 1), ""]
    tabla(c, 592, 180, 1312, 884, "Detalle por reporte (más vistas primero)", cols, filas, total)
    return c


def datos_matrices(d, por_semana):
    """Filas (reportes por nombre), columnas, vistas y usuarios únicos por celda, y totales por reporte.
    Por día: solo los últimos 28 días (filtro Ultimos28); por semana: todo el histórico, de lunes a domingo."""
    if por_semana:
        ini = sorted({lunes(f) for f in d["dias"]})
        cols = [etiqueta_semana(i, d) for i in ini]
        clave = lambda f: lunes(f)   # noqa: E731
        claves = ini
        ventana = lambda f: True     # noqa: E731
    else:
        claves = [f for f in d["dias"] if (d["ultima"] - f).days < 28]
        cols = [[f.strftime("%d-%m")] for f in claves]
        clave = lambda f: f          # noqa: E731
        ventana = lambda f: (d["ultima"] - f).days < 28   # noqa: E731
    por_rep = sorted(d["reportes"], key=lambda r: r["reporte"].lower())
    vis = {(r["id"], k): 0 for r in por_rep for k in claves}
    usu = defaultdict(set)
    tot_vi = defaultdict(int)
    tot_usu = defaultdict(set)
    for rid, u, f, ap, vi in d["registros"]:
        if not ventana(f):
            continue
        vis[(rid, clave(f))] += vi
        usu[(rid, clave(f))].add(u)
        tot_vi[rid] += vi
        tot_usu[rid].add(u)
    filas = [r["reporte"] for r in por_rep]
    v_vi = [[vis[(r["id"], k)] for k in claves] for r in por_rep]
    v_us = [[len(usu[(r["id"], k)]) for k in claves] for r in por_rep]
    return (filas, cols, v_vi, [tot_vi[r["id"]] for r in por_rep], v_us, [len(tot_usu[r["id"]]) for r in por_rep])


def pagina_vistas(d, por_semana=False):
    grano = "semana" if por_semana else "día"
    c = Lienzo(1920, 1080, FONDO)
    cabecera(c, f"Vistas y usuarios por {grano}")
    segmentacion(c, 16, 64, 320, 76, "Área de trabajo")
    segmentacion(c, 16, 148, 320, 76, "Tipo de usuario")

    s = d["serie"]
    if por_semana:
        ini = sorted({lunes(f) for f in d["dias"]})
        suma = lambda k: [sum(v for f, v in zip(d["dias"], s[k]) if lunes(f) == i) for i in ini]   # noqa: E731
        grafico_lineas(c, 352, 64, 1552, 160, "Tendencia semanal de la selección", ini,
                       [("Vistas de página", suma("vi"), AZUL), ("Aperturas", suma("ap"), VIOLETA)],
                       max(suma("vi") + suma("ap")), cats=[etiqueta_semana(i, d) for i in ini], ley_der=True,
                       n_marcas=2)
    else:
        grafico_lineas(c, 352, 64, 1552, 160, "Tendencia diaria de la selección (todo el histórico)", d["dias"],
                       [("Vistas de página", s["vi"], AZUL), ("Aperturas", s["ap"], VIOLETA)],
                       max(s["vi"] + s["ap"]), ley_der=True, n_marcas=2, paso_x=14)

    filas, cols, v_vi, t_vi, v_us, t_us = datos_matrices(d, por_semana)
    ancho_cab, ancho_tot = (290, 80) if not por_semana else (290, 80)
    periodo = "" if por_semana else ", últimos 28 días"
    matriz(c, 16, 240, 1888, 404, f"Vistas de página por reporte y {grano}{periodo}", filas, cols, v_vi, t_vi,
           ancho_cab, ancho_tot)
    matriz(c, 16, 660, 1888, 404, f"Usuarios únicos por reporte y {grano}{periodo} (los totales no se suman)",
           filas, cols, v_us, t_us, ancho_cab, ancho_tot)
    return c


def pagina_sin_uso(d):
    # Imagen recortada al contenido (cabecera + tarjetas + tabla): el panel cierra bajo la última fila, no a 884 px
    ALTO_FILA, ALTO_ENC = 44, 46
    n_filas = sum(1 for r in d["reportes"] if r["vi"] < 1)
    alto_panel = 46 + ALTO_ENC + n_filas * ALTO_FILA + 12
    c = Lienzo(1920, 180 + alto_panel + 30, FONDO)
    cabecera(c, "Reportes sin uso")
    e = d["estados"]
    tarjeta(c, 16, 64, 460, 100, "Sin uso", str(e["Sin uso"]), ROJO)
    tarjeta(c, 492, 64, 460, 100, "Solo aperturas", str(e["Solo aperturas"]), VIOLETA)
    segmentacion(c, 968, 64, 460, 100, "Área de trabajo")

    # Filtro estructural del visual: Vistas de página < 1. Orden: aperturas de mayor a menor
    sin_vistas = sorted((r for r in d["reportes"] if r["vi"] < 1), key=lambda r: (-r["ap"], r["area"], r["reporte"]))
    cols = [("Área", 260, "l"), ("Reporte", 470, "l"), ("Estado del reporte", 240, "l"), ("Aperturas", 180, "r"),
            ("Vistas de página", 210, "r"), ("Última actividad", 240, "r"), ("Días desde última actividad", 258, "r")]
    filas = [[r["area"], r["reporte"], r["estado"], num(r["ap"]), num(r["vi"]),
              r["ultima"] and date.fromisoformat(r["ultima"]).strftime("%d-%m-%Y") or "",
              "" if r["dias_desde"] is None else num(r["dias_desde"])] for r in sin_vistas]
    tabla(c, 16, 180, 1888, alto_panel, "Reportes sin vistas de página (candidatos a revisar)", cols, filas,
          tam=16, alto_fila=ALTO_FILA, alto_enc=ALTO_ENC)
    return c


def pagina_detalle(d):
    """Detalle con una selección: área «Operaciones Mina» y reporte «Tablero Movimiento Mina» (el reporte en uso que
    destaca esperados.json). Con un área elegida, el gráfico de columnas muestra los reportes de esa área."""
    rep = next(r for r in d["reportes"] if r["nombre"] == REPORTE_DETALLE and r["area"] == AREA_DETALLE)
    mios = [r for r in d["registros"] if r[0] == rep["id"]]
    dia_vi = defaultdict(int)
    dia_ap = defaultdict(int)
    dia_usu = defaultdict(set)
    por_usu = defaultdict(lambda: [0, 0])
    for _, u, f, ap, vi in mios:
        dia_vi[f] += vi
        dia_ap[f] += ap
        dia_usu[f].add(u)
        por_usu[u][0] += ap
        por_usu[u][1] += vi
    assert sum(dia_ap.values()) == rep["ap"] and sum(dia_vi.values()) == rep["vi"]

    c = Lienzo(1920, 1080, FONDO)
    cabecera(c, "Detalle por reporte", "Elija un reporte para ver su uso diario y sus usuarios.")
    segmentacion(c, 16, 64, 400, 100, "Área de trabajo", AREA_DETALLE)
    segmentacion(c, 432, 64, 704, 100, "Reporte", REPORTE_DETALLE)
    tarjeta(c, 1152, 64, 240, 100, "Aperturas", num(rep["ap"]), VIOLETA)
    tarjeta(c, 1408, 64, 240, 100, "Vistas de página", num(rep["vi"]), AZUL)
    tarjeta(c, 1664, 64, 240, 100, "Págs. por apertura", num(rep["vi"] / rep["ap"], 1))

    dias = d["dias"]
    vi = [dia_vi.get(f, 0) for f in dias]
    ap = [dia_ap.get(f, 0) for f in dias]
    grafico_lineas(c, 16, 180, 1032, 260, "Uso diario del reporte seleccionado", dias,
                   [("Vistas de página", vi, AZUL), ("Aperturas", ap, VIOLETA)], max(vi + ap), paso_x=14)
    us = [len(dia_usu.get(f, ())) for f in dias]
    grafico_lineas(c, 16, 456, 1032, 230, "Usuarios únicos por día", dias, [("Usuarios únicos", us, AZUL_CLARO)],
                   max(us), paso_x=14)

    del_area = sorted((r for r in d["reportes"] if r["area"] == AREA_DETALLE and r["ap"] > 0),
                      key=lambda r: (-r["ap"], r["reporte"]))
    grafico_columnas(c, 16, 702, 1032, 362, f"Aperturas por reporte en {AREA_DETALLE} (de más a menos)",
                     [(r["reporte"], r["ap"]) for r in del_area], VIOLETA)

    usuarios = sorted(por_usu.items(), key=lambda kv: (-kv[1][1], kv[0]))
    cols = [("Usuario", 300, "l"), ("Tipo de usuario", 140, "l"), ("Aperturas", 100, "r"),
            ("Vistas de página", 140, "r"), ("Págs. por apertura", 140, "r")]
    filas = [[u, "Externo" if u.startswith("ext.") else "Interno", num(a), num(v), num(v / a if a else 0, 1)]
             for u, (a, v) in usuarios]
    total = ["Total", "", num(rep["ap"]), num(rep["vi"]), num(rep["vi"] / rep["ap"], 1)]
    tabla(c, 1064, 180, 840, 884, "Usuarios del reporte (más vistas primero)", cols, filas, total,
          tam=11 * PX, alto_fila=36, alto_enc=40)
    return c


def pagina_calidad(d):
    c = Lienzo(1920, 1080, FONDO)
    cabecera(c, "Calidad de los datos")
    tarjeta(c, 16, 64, 460, 100, "Días de histórico", num((d["ultima"] - d["primera"]).days + 1))
    tarjeta(c, 492, 64, 460, 100, "Días con datos", num(d["dias_con_datos"]))
    tarjeta(c, 968, 64, 460, 100, "Datos desde", fecha_txt(d["primera"]))
    segmentacion(c, 1444, 64, 460, 100, "Área de trabajo")

    # Aperturas sin vistas: solo reportes que tienen alguna; de más a menos aperturas sin vistas
    con = sorted((r for r in d["reportes"] if r["ap_sin_vistas"] > 0), key=lambda r: (-r["ap_sin_vistas"], r["reporte"]))
    cols = [("Área", 220, "l"), ("Reporte", 400, "l"), ("Aperturas", 120, "r"), ("Aperturas sin vistas", 170, "r"),
            ("Vistas de página", 130, "r")]
    filas = [[r["area"], r["reporte"], num(r["ap"]), num(r["ap_sin_vistas"]), num(r["vi"])] for r in con]
    total = ["Total", "", num(sum(r["ap"] for r in con)), num(sum(r["ap_sin_vistas"] for r in con)),
             num(sum(r["vi"] for r in con))]
    tabla(c, 16, 180, 1060, 812, "Aperturas sin vistas de página (posible acceso automatizado)", cols, filas, total,
          alto_fila=30)

    # Cobertura por área: la última lectura de la extracción; Planta Chancado se quedó atrás
    pa = d["por_area"]
    areas = sorted(pa)
    cols = [("Área", 180, "l"), ("Reportes", 100, "r"), ("En uso", 90, "r"), ("Solo aperturas", 150, "r"),
            ("Sin uso", 90, "r"), ("Última lectura", 182, "r")]
    lect = lambda a: date.fromisoformat(d["ultima_lectura"][a][:10])   # noqa: E731
    filas = [[a, num(pa[a]["total"]), num(pa[a]["En uso"]), num(pa[a]["Solo aperturas"]), num(pa[a]["Sin uso"]),
              fecha_txt(lect(a))] for a in areas]
    total = ["Total", num(sum(pa[a]["total"] for a in areas)), num(d["estados"]["En uso"]),
             num(d["estados"]["Solo aperturas"]), num(d["estados"]["Sin uso"]), fecha_txt(max(lect(a) for a in areas))]
    tabla(c, 1092, 180, 812, 330, "Cobertura por área", cols, filas, total, alto_fila=34)

    # Nombres de reporte repetidos
    cnt = defaultdict(int)
    for r in d["reportes"]:
        cnt[r["nombre"]] += 1
    rep = [(n, k) for n, k in sorted(cnt.items()) if k > 1]
    filas = [[n, num(k)] for n, k in rep]
    tabla(c, 1092, 526, 812, 170, "Nombres de reporte usados por más de un reporte",
          [("Nombre del reporte", 560, "l"), ("Reportes con ese nombre", 232, "r")], filas,
          ["Total", num(sum(k for _, k in rep))], tam=16, alto_fila=34, alto_enc=36)

    # Páginas por apertura según usuario: de menor a mayor (solo usuarios con aperturas)
    us = sorted(((u, v["ap"], v["vi"]) for u, v in d["por_usuario"].items() if v["ap"] > 0),
                key=lambda t: (t[2] / t[1], t[0]))
    cols = [("Usuario", 290, "l"), ("Tipo de usuario", 130, "l"), ("Aperturas", 95, "r"), ("Vistas de página", 140, "r"),
            ("Págs. por apertura", 137, "r")]
    filas = [[u, "Externo" if u.startswith("ext.") else "Interno", num(a), num(v), num(v / a, 1)] for u, a, v in us]
    total = ["Total", "", num(sum(a for _, a, _ in us)), num(sum(v for _, _, v in us)),
             num(sum(v for _, _, v in us) / sum(a for _, a, _ in us), 1)]
    tabla(c, 1092, 712, 812, 280, "Páginas por apertura según usuario (menor primero)", cols, filas, total,
          alto_fila=25, alto_enc=28)

    # Cuadro de texto de limitaciones (mismo texto del informe), con fondo y borde como la banda del título
    c.caja(16, 1008, 1888, 56, fill=MEDIANOCHE, borde=BORDE, r=8)
    tam = 12 * PX
    palabras = [("Limitaciones:", True, TEXTO)] + [(p, False, TEXTO_TENUE) for p in LIMITACIONES.split()]
    x, yy, ancho_max = 30, 1019, 1888 - 28
    for p, bold, col in palabras:
        w_p = c.ancho_texto(p, tam, bold)
        if x + w_p > 16 + ancho_max:
            x, yy = 30, yy + 22
        c.texto(x, yy, p, tam, col, bold=bold, ancla="la")
        x += w_p + c.ancho_texto(" ", tam, bold)
    return c


# El mapa de calor y los degradados pesan más: se cuantiza cuando el PNG pasa de ~350 KB y no daña el texto
PAGINAS = [("resumen.png", pagina_resumen), ("vistas.png", pagina_vistas),
           ("vistas_por_semana.png", lambda d: pagina_vistas(d, True)), ("sin_uso.png", pagina_sin_uso),
           ("detalle.png", pagina_detalle), ("calidad.png", pagina_calidad)]
CUANTIZAR = {"resumen.png", "detalle.png"}   # en las matrices con mapa de calor y en calidad la paleta de 256 colores
                                              # deslustra el violeta y el rojo de la marca: allí se guarda a todo color


def main():
    d = leer_datos()
    for nombre, pagina in PAGINAS:
        ruta = pagina(d).guardar(SALIDA / nombre, LEYENDA, cuantizar=nombre in CUANTIZAR)
        print(f"{ruta}  {ruta.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
