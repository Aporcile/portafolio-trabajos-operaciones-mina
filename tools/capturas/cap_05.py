# -*- coding: utf-8 -*-
"""Renders de la app de lienzo «Agenda del equipo» (05-power-apps-codegen).

Genera dos imágenes de 1366 x 768 (el lienzo de la app) dibujadas con Pillow, NO capturas de Power Apps Studio:
  - capturas/tablero.png : pestaña «Por área» (vista de arranque), matriz área x estado.
  - capturas/persona.png : pestaña «Por persona», una columna por integrante y una de «Sin responsable».

Fuentes del diseño:
  - posiciones, tamaños y textos: los YAML de agenda-equipo/yaml (y el generador que los produce);
  - colores, estados, áreas y personas: agenda-equipo/generador (lib.py, comun.py, contrato.py);
  - datos: CSV de agenda-equipo/datos_sinteticos (se agregan aquí con la biblioteca estándar).

Las alturas de texto (líneas de las etiquetas de altura automática) son una aproximación con Segoe UI;
Power Apps las mide con su propio motor. Se puede ejecutar desde cualquier carpeta.
"""
import csv
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
PROYECTO = RAIZ / "05-power-apps-codegen"
APP = PROYECTO / "agenda-equipo"
DATOS = APP / "datos_sinteticos"
SALIDA = PROYECTO / "capturas"

sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(APP / "generador"))
from lib_render import Lienzo, LOGO_BLANCO, ICONO  # noqa: E402
from contrato import AREAS, ESTADOS as ESTADOS_CONTRATO, FILTRO_TODOS  # noqa: E402
from lib import C  # noqa: E402
from comun import _CHIP, ESTADOS as ESTADOS_LINEA  # noqa: E402  (chip de cada estado; línea de color de cada columna del Tablero)

W, H = 1366, 768
SS = 3


# ------------------------------------------------------------------------------------------------ colores
def rgba(s):
    """'RGBA(27, 42, 65, 1)' -> (27, 42, 65, 255)."""
    m = re.match(r"RGBA\((\d+), (\d+), (\d+), ([\d.]+)\)", s)
    return int(m[1]), int(m[2]), int(m[3]), round(float(m[4]) * 255)


BG, PANEL, CARD, CELL = rgba(C["bg"]), rgba(C["panel"]), rgba(C["card"]), rgba(C["cell"])
BORDE, TEXTO, TEXTO2, MUTED = rgba(C["border"]), rgba(C["text"]), rgba(C["text2"]), rgba(C["muted"])
ACENTO, LINK, ALERTA, CIELO = rgba(C["accent"]), rgba(C["link"]), rgba(C["alerta"]), rgba(C["cielo"])
INK, DASH = rgba(C["ink"]), rgba(C["dash"])
VERDE, ROJO = rgba(C["verde"]), rgba(C["rojo"])
HINT = (133, 141, 150, 255)          # texto de ayuda («Buscar…», «dd-mm-aaaa»)
ALTA_BG, ALTA_FG, SIN_BG, SIN_FG = rgba(C["altaBg"]), rgba(C["altaFg"]), rgba(C["sinBg"]), rgba(C["sinFg"])
CLARO = (205, 218, 235, 255)         # texto secundario sobre la franja oscura (gen_encabezado.py)
RESALTE = (184, 168, 240, 255)       # #b8a8f0, negritas del resumen
TEXTO_HTML = (205, 218, 235, 255)    # #cddaeb
VIVO = (76, 195, 138, 255)
CHIP = {k: (rgba(v[0]), rgba(v[1])) for k, v in _CHIP.items()}

# ------------------------------------------------------------------------------------------------ tipografía
_FUENTES = {
    "n": ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"],
    "sb": ["seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "b": ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "sym": ["seguisym.ttf", "segoeui.ttf", "DejaVuSans.ttf"],
}
_cache = {}


def fuente(px, peso):
    clave = (round(px), peso)
    if clave not in _cache:
        for nombre in _FUENTES[peso]:
            try:
                _cache[clave] = ImageFont.truetype(nombre, round(px))
                break
            except OSError:
                continue
        else:
            _cache[clave] = ImageFont.load_default()
    return _cache[clave]


def px_de(pt):
    """Power Apps expresa el tamaño en puntos; en el lienzo (96 ppp) equivale a pt x 4/3 píxeles."""
    return pt * 4 / 3


def alto_linea(pt):
    return round(px_de(pt) * 1.33)


def ancho_texto(c, txt, pt, peso="n"):
    return c.d.textlength(txt, font=fuente(px_de(pt) * c.ss, peso)) / c.ss


def texto(c, x, y, txt, pt, color, peso="n", ancla="lm"):
    c.d.text((x * c.ss, y * c.ss), txt, font=fuente(px_de(pt) * c.ss, peso), fill=color, anchor=ancla)


def envolver(c, txt, pt, w, peso="n"):
    """Partición en líneas por palabras (como el ajuste de línea de una etiqueta)."""
    lineas, actual = [], ""
    for palabra in str(txt).split(" "):
        candidata = palabra if not actual else actual + " " + palabra
        if actual and ancho_texto(c, candidata, pt, peso) > w:
            lineas.append(actual)
            actual = palabra
        else:
            actual = candidata
    lineas.append(actual)
    return lineas


def etiqueta(c, x, y, w, h, txt, pt, color, peso="n", auto=False, alinear="l", pad_l=0, dibujar=True):
    """Etiqueta de Power Apps. Con auto=True la altura es la de sus líneas; si no, el texto se centra en vertical.

    Devuelve la altura final del control.
    """
    lh = alto_linea(pt)
    lineas = [ln for p in str(txt).split("\n") for ln in envolver(c, p, pt, w - pad_l, peso)] if txt else [""]
    alto = len(lineas) * lh if auto else h
    if dibujar:
        top = y if auto else y + (alto - len(lineas) * lh) / 2
        for i, ln in enumerate(lineas):
            cy = top + lh * (i + 0.5)
            if alinear == "c":
                texto(c, x + w / 2, cy, ln, pt, color, peso, "mm")
            else:
                texto(c, x + pad_l, cy, ln, pt, color, peso, "lm")
    return alto


def chip(c, x, y, w, h, txt, pt, fill, fg, r):
    c.caja(x, y, w, h, fill=fill, r=r)
    texto(c, x + w / 2, y + h / 2, txt, pt, fg, "b", "mm")


# ------------------------------------------------------------------------------------------------ datos
def leer(nombre):
    with open(DATOS / nombre, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


ACTIVIDADES = leer("actividades.csv")
PERSONAS = leer("personas.csv")
POR_REVISAR = leer("por_revisar.csv")
HIGHLIGHTS = leer("highlights_lowlights.csv")
ESTADOS = [(cod, nombre) for cod, nombre in ESTADOS_CONTRATO]
INICIALES = {p["Nombre"]: p["Iniciales"] for p in PERSONAS}


def rank_est(r):
    return {"Bloqueada": 1, "En curso": 2, "En revisión": 3, "Por hacer": 4}.get(r["Estado"], 5)


def rank_prio(r):
    return {"Alta": 1, "Media": 2}.get(r["Prioridad"], 3)


def sub_texto(r):
    """Mismo criterio que SUB en comun.py: motivo del bloqueo, status actual o «Sin responsable»."""
    if r["Estado"] == "Bloqueada" and r["Bloqueo"]:
        return r["Bloqueo"]
    return r["StatusActual"] or r["Bloqueo"] or ("" if r["Responsable"] else "Sin responsable")


def sub_color(r):
    """Mismo criterio que SUB_COLOR en comun.py."""
    if r["Estado"] == "Bloqueada" or not r["Responsable"] or (not r["StatusActual"] and r["Bloqueo"]):
        return ALERTA
    return MUTED


def iniciales(r):
    return "?" if not r["Responsable"] else INICIALES.get(r["Responsable"], r["Responsable"][:2].upper())


# ------------------------------------------------------------------------------------------------ cromo común
# (texto, clave de vista, x, ancho) de gen_pestanas_y_vistas.py
PESTANAS = [("Tablero", "tablero", 32, 84), ("Por área", "area", 120, 88), ("Lista", "lista", 212, 64),
            ("Por persona", "persona", 280, 108), ("Highlights y Lowlights", "hl", 392, 180),
            ("Por revisar", "revisar", 576, 108), ("Historial", "historial", 688, 96)]


def cromo(c, vista):
    """Fondo, franja superior, pestañas, buscador y filtro de responsable (01_encabezado.yaml y 01b_pestanas.yaml)."""
    c.caja(0, 0, W, H, fill=BG)
    c.caja(0, 0, W, 64, fill=ACENTO)
    c.pegar(LOGO_BLANCO, 24, 12, w=150)
    c.pegar(ICONO, 190, 10, w=44)
    # El título cabe justo en su etiqueta de 190 px (190,05 px con Segoe UI Bold): se dibuja en una sola línea
    texto(c, 250, 32, "Agenda del equipo", 16, INK, "b")
    c.caja(444, 28, 8, 8, fill=VIVO)
    etiqueta(c, 456, 18, 60, 28, "En vivo", 9, CLARO, pad_l=2)

    # Resumen (HtmlViewer): activas, bloqueadas y sin responsable en negrita violeta claro, por revisar
    activas = sum(r["Estado"] != "Terminada" for r in ACTIVIDADES)
    bloq = sum(r["Estado"] == "Bloqueada" for r in ACTIVIDADES)
    sin = sum((not r["Responsable"]) and r["Estado"] != "Terminada" for r in ACTIVIDADES)
    rev = sum(r["Decision"] == "Por decidir" for r in POR_REVISAR)
    tramos = [(f"{activas} activas · ", "n", TEXTO_HTML), (f"{bloq} bloqueadas", "b", RESALTE), (" · ", "n", TEXTO_HTML),
              (f"{sin} sin responsable", "b", RESALTE), (f" · {rev} por revisar", "n", TEXTO_HTML)]
    x = 524
    for t, peso, col in tramos:
        c.d.text((x * SS, (15 + 6 + 8.5) * SS), t, font=fuente(13 * SS, peso), fill=col, anchor="lm")
        x += c.d.textlength(t, font=fuente(13 * SS, peso)) / SS

    # Botones de la franja
    c.caja(1018, 12, 134, 40, fill=(255, 255, 255, 20), borde=(255, 255, 255, 89), r=8)
    px = px_de(10)
    ancho_sim = c.d.textlength("↻", font=fuente(px * SS, "sym")) / SS
    ancho_txt = ancho_texto(c, "  Actualizar", 10, "sb")
    x0 = 1018 + (134 - ancho_sim - ancho_txt) / 2
    c.d.text((x0 * SS, 32 * SS), "↻", font=fuente(px * SS, "sym"), fill=INK, anchor="lm")
    texto(c, x0 + ancho_sim, 32, "  Actualizar", 10, INK, "sb")
    c.caja(1164, 12, 170, 40, fill=INK, r=8)
    texto(c, 1164 + 85, 32, "+ Nueva actividad", 11, ACENTO, "sb", "mm")

    # Pestañas con subrayado en la activa; línea fina bajo ellas
    for t, clave, x, w in PESTANAS:
        texto(c, x + w / 2, 92, t, 10.5, ACENTO if clave == vista else TEXTO2, "sb", "mm")
        if clave == vista:
            c.caja(x, 110, w, 2, fill=CIELO)
    c.caja(32, 112, 1302, 1, fill=BORDE)

    # Buscador y filtro de responsable
    c.caja(898, 74, 220, 34, fill=INK, borde=BORDE, r=8)
    texto(c, 898 + 12, 91, "Buscar…", 10, HINT)
    c.caja(1126, 74, 208, 34, fill=INK, borde=BORDE)
    texto(c, 1126 + 12, 91, FILTRO_TODOS, 10, TEXTO)
    cx, cy = 1334 - 20, 91
    c.linea([(cx - 4, cy - 2), (cx, cy + 2), (cx + 4, cy - 2)], TEXTO2, 1.4)


def barra_scroll(c, x, y, alto_vista, alto_total):
    """Pulgar discreto de la barra de desplazamiento de una galería con más contenido que su alto."""
    if alto_total <= alto_vista:
        return
    th = max(36, alto_vista * alto_vista / alto_total)
    c.caja(x, y + 4, 6, th - 8, fill=(158, 169, 184, 255), r=3)


# ------------------------------------------------------------------------------------------------ vista «Por área»
CELL_X = (206, 425, 644, 863, 1082)      # gen_tablero_por_area.py
CELL_W = 211


def tarjeta_area(c, x, y, w, r, dibujar=True):
    """Tarjeta de una celda (variante «tab»): ID, prioridad alta, iniciales, título y status; devuelve su alto."""
    lw = w - 16
    th = etiqueta(c, 0, 0, lw, 17, r["Actividad"], 9, TEXTO, "b", auto=True, dibujar=False)
    sub = sub_texto(r)
    sh = etiqueta(c, 0, 0, lw, 15, sub, 8, MUTED, auto=True, dibujar=False) if sub else 0
    sub_y = 22 + th + 2
    alto = (sub_y + sh if sub else 22 + th) + 8
    if dibujar:
        c.caja(x, y, w, alto, fill=CARD, borde=BORDE, r=6)
        etiqueta(c, x + 8, y + 5, 54, 16, r["ID"], 8, MUTED)
        if r["Prioridad"] == "Alta":
            chip(c, x + 58, y + 6, 30, 14, "Alta", 7, ALTA_BG, ALTA_FG, 4)
        sin = not r["Responsable"]
        chip(c, x + w - 28, y + 5, 20, 20, iniciales(r), 6.5, SIN_BG if sin else LINK, SIN_FG if sin else INK, 10)
        etiqueta(c, x + 8, y + 22, lw, 17, r["Actividad"], 9, TEXTO, "b", auto=True)
        if sub:
            etiqueta(c, x + 8, y + sub_y, lw, 15, sub, 8, sub_color(r), auto=True)
    return alto


def fila_area(c, x, y, area, acts, dibujar=True):
    """Fila de un área: panel, nombre, conteos y una celda por estado (2 tarjetas como máximo + «+N más»).

    Devuelve el alto del panel (el elemento de la galería mide 8 más por la separación).
    """
    celdas = []
    for (cod, estado), cx in zip(ESTADOS, CELL_X):
        todas = [r for r in acts if r["Estado"] == estado]
        mostradas = todas[:2]
        alto_tarj = [tarjeta_area(c, 0, 0, CELL_W - 12, r, dibujar=False) for r in mostradas]
        gal_h = sum(a + 6 for a in alto_tarj) + 2 if mostradas else 0
        celdas.append((cx, todas, mostradas, alto_tarj, gal_h))
    nombre_h = alto_linea(12)
    fila_b_y = 14 + nombre_h + 2 + 20
    alto = max(fila_b_y + 34, *[g + 28 + (30 if len(t) > 2 else 0) for _, t, _, _, g in celdas])
    if not dibujar:
        return alto

    nbq = sum(r["Estado"] == "Bloqueada" for r in acts)
    c.caja(x, y, 1302, alto, fill=PANEL, borde=BORDE, r=10)
    etiqueta(c, x + 16, y + 14, 180, 24, area, 12, TEXTO, "b", auto=True)
    n = len(acts)
    etiqueta(c, x + 16, y + 14 + nombre_h + 2, 180, 20, f"{n} actividad" + ("" if n == 1 else "es"), 9, MUTED)
    if nbq:
        etiqueta(c, x + 16, y + fila_b_y, 180, 20, f"{nbq} bloqueada" + ("" if nbq == 1 else "s"), 9, ALERTA)
    for cx, todas, mostradas, alto_tarj, gal_h in celdas:
        c.caja(x + cx, y + 8, CELL_W, alto - 16, fill=CELL, r=8)
        yy = y + 14
        for r, a in zip(mostradas, alto_tarj):
            tarjeta_area(c, x + cx + 6, yy, CELL_W - 12, r)
            yy += a + 6
        if not todas:
            etiqueta(c, x + cx, y + 16, CELL_W, 20, "—", 9, DASH, alinear="c")
        if len(todas) > 2:
            texto(c, x + cx + 2 + 6, y + 14 + gal_h + 6 + 12, f"+{len(todas) - 2} más ↓", 8, LINK, "sb")
    return alto


def dibujar_por_area():
    c = Lienzo(W, H, BG, ss=SS)
    cromo(c, "area")
    # Títulos de columna (los conteos son de toda la tabla Actividades)
    etiqueta(c, 32, 124, 190, 24, "ÁREA", 9, MUTED, "b")
    for (cod, estado), x in zip(ESTADOS, (238, 457, 676, 895, 1114)):
        n = sum(r["Estado"] == estado for r in ACTIVIDADES)
        etiqueta(c, x, 124, 211, 24, f"{estado.upper()} · {n}", 9, MUTED, "b")

    # Galería de áreas: áreas del catálogo + «Sin área», ordenadas por total descendente (empate: orden del catálogo)
    nombres = list(AREAS) + ["Sin área"]
    grupos = {a: [r for r in ACTIVIDADES if (r["Area"] or "Sin área") == a] for a in nombres}
    orden = sorted((a for a in nombres if grupos[a]), key=lambda a: -len(grupos[a]))
    gal = Lienzo(1332, 600, BG, ss=SS)
    y, total = 0, 0
    for a in orden:
        alto = fila_area(gal, 0, y, a, grupos[a])
        y += alto + 8
        total = y
    c.im.paste(gal.im, (32 * SS, 152 * SS))
    barra_scroll(c, 32 + 1332 - 12, 152, 600, total)
    return c


# ------------------------------------------------------------------------------------------------ vista «Por persona»
def tarjeta_persona(c, x, y, w, r, dibujar=True, variante="per"):
    """Tarjeta de galería de act_card (comun.py).

    variante «per» (Por persona): chip de estado a la derecha y solo el área en azul.
    variante «tab» (Tablero): iniciales del responsable a la derecha y «área · responsable» en azul.
    """
    lw = w - 16
    th = etiqueta(c, 0, 0, lw, 16, r["Actividad"], 9, TEXTO, "b", auto=True, dibujar=False)
    area = r["Area"] or "Sin área"
    if variante == "tab" and r["Responsable"]:
        area += "  ·  " + r["Responsable"]
    ah = etiqueta(c, 0, 0, lw, 14, area, 8, LINK, auto=True, dibujar=False)
    sub = sub_texto(r)
    sh = etiqueta(c, 0, 0, lw, 14, sub, 8, MUTED, auto=True, dibujar=False) if sub else 0
    area_y = 24 + th + 1
    sub_y = area_y + ah + 1
    alto = (sub_y + sh if sub else area_y + ah) + 8
    if dibujar:
        c.caja(x, y, w, alto, fill=CARD, borde=BORDE, r=6)
        etiqueta(c, x + 8, y + 6, 54, 16, r["ID"], 8, MUTED)
        if r["Prioridad"] == "Alta":
            chip(c, x + 58, y + 7, 30, 14, "Alta", 7, ALTA_BG, ALTA_FG, 4)
        if variante == "tab":
            sin = not r["Responsable"]
            chip(c, x + w - 30, y + 5, 22, 22, iniciales(r), 6.5, SIN_BG if sin else LINK, SIN_FG if sin else INK, 11)
        else:
            fondo, fg = CHIP[r["Estado"]]
            chip(c, x + w - 88, y + 6, 80, 16, r["Estado"], 7, fondo, fg, 8)
        etiqueta(c, x + 8, y + 24, lw, 16, r["Actividad"], 9, TEXTO, "b", auto=True)
        etiqueta(c, x + 8, y + area_y, lw, 14, area, 8, LINK, auto=True)
        if sub:
            etiqueta(c, x + 8, y + sub_y, lw, 14, sub, 8, sub_color(r), auto=True)
    return alto


def dibujar_persona():
    c = Lienzo(W, H, BG, ss=SS)
    cromo(c, "persona")
    pw = 315
    columnas = [(p["NombreCompleto"], p["Iniciales"], [r for r in ACTIVIDADES if r["Responsable"] == p["Nombre"]], False)
                for p in PERSONAS]
    columnas.append(("Sin responsable", "?", [r for r in ACTIVIDADES if not r["Responsable"]], True))
    for i, (nombre, ini, acts, sin) in enumerate(columnas):
        x = 32 + i * (pw + 14)
        c.caja(x, 124, pw, 632, fill=CELL, r=10)
        chip(c, x + 14, 136, 32, 32, ini, 9, SIN_BG if sin else LINK, SIN_FG if sin else INK, 16)
        etiqueta(c, x + 56, 134, pw - 70, 22, nombre, 11, TEXTO, "b")
        activas = sum(r["Estado"] != "Terminada" for r in acts)
        bloq = sum(r["Estado"] == "Bloqueada" for r in acts)
        term = sum(r["Estado"] == "Terminada" for r in acts)
        etiqueta(c, x + 56, 156, pw - 66, 16, f"{activas} activas  ·  {bloq} bloqueadas  ·  {term} terminadas", 8, MUTED)

        # Galería: orden por estado (bloqueadas primero) y prioridad; tarjetas de TemplateWidth - 30 de ancho
        ordenadas = sorted(acts, key=lambda r: rank_est(r) * 10 + rank_prio(r))
        gal = Lienzo(307, 566, CELL, ss=SS)
        y = 0
        for r in ordenadas:
            y += tarjeta_persona(gal, 0, y, 307 - 30, r) + 8
        c.im.paste(gal.im, ((x + 6) * SS, 184 * SS))
        barra_scroll(c, x + 6 + 307 - 12, 184, 566, y)
    return c


# ------------------------------------------------------------------------------------------------ utilidades comunes
LEYENDA = "Render del diseño · datos sintéticos · Minera Demo"
HOY = "2025-05-27"      # «hoy» simulado: dentro del periodo de los datos (los CSV llegan hasta 2025-05-31)


def ddmmaaaa(iso):
    """'2025-04-22' -> '22-04-2025' (Text(DateValue(...), "dd-mm-yyyy") de la app)."""
    if not iso:
        return ""
    a, m, d = iso.split("-")
    return f"{d}-{m}-{a}"


def galeria(c, x, y, w, h, fondo, pintar):
    """Galería con recorte: pintar(g) dibuja sobre un lienzo de w x h (origen en la galería) y devuelve el alto total."""
    g = Lienzo(w, h, fondo, ss=c.ss)
    total = pintar(g)
    c.im.paste(g.im, (x * c.ss, y * c.ss))
    barra_scroll(c, x + w - 12, y, h, total)


def boton(c, x, y, w, h, txt, tipo, pt=10.5):
    """Botón de panel (lib.button): primary = azul medianoche, danger = borde rojo, ghost = blanco con borde."""
    if tipo == "primary":
        c.caja(x, y, w, h, fill=ACENTO, r=8)
        col = INK
    elif tipo == "danger":
        c.caja(x, y, w, h, borde=ROJO, r=8)
        col = ALTA_FG
    else:
        c.caja(x, y, w, h, fill=PANEL, borde=BORDE, r=8)
        col = TEXTO
    texto(c, x + w / 2, y + h / 2, txt, pt, col, "sb", "mm")


def chevron(c, cx, cy):
    c.linea([(cx - 4, cy - 2), (cx, cy + 2), (cx + 4, cy - 2)], TEXTO2, 1.4)


# ------------------------------------------------------------------------------------------------ vista «Tablero» (por estado)
def dibujar_tablero_estados():
    """04_vista_tablero.yaml: cinco columnas por estado, con su línea de color; tarjetas ordenadas por prioridad."""
    c = Lienzo(W, H, BG, ss=SS)
    cromo(c, "tablero")
    cw, gap = 250, 13
    for i, ((cod, estado), (_, _, color)) in enumerate(zip(ESTADOS, ESTADOS_LINEA)):
        x = 32 + i * (cw + gap)
        acts = sorted((r for r in ACTIVIDADES if r["Estado"] == estado), key=rank_prio)
        c.caja(x, 124, cw, 632, fill=CELL, r=10)
        etiqueta(c, x + 12, 132, cw - 24, 20, f"{estado.upper()} · {len(acts)}", 9, MUTED, "b")
        c.caja(x + 12, 156, cw - 24, 2, fill=rgba(color))

        def pintar(g, acts=acts):
            y = 0
            for r in acts:
                y += tarjeta_persona(g, 0, y, cw - 8 - 30, r, variante="tab") + 8
            return y

        galeria(c, x + 6, 164, cw - 8, 586, CELL, pintar)
    return c


# ------------------------------------------------------------------------------------------------ vista «Lista»
LISTA_COLS = [("id", "ID", 44), ("actividad", "ACTIVIDAD", 104), ("area", "ÁREA", 474), ("responsable", "RESPONSABLE", 654),
              ("prioridad", "PRIORIDAD", 784), ("estado", "ESTADO", 862), ("inicio", "INICIO", 980), ("status", "STATUS / BLOQUEO", 1080)]


def fila_lista(c, x, y, r, dibujar=True):
    """Fila de la Lista (05_vista_lista.yaml); devuelve su alto. Cada dato se centra en vertical dentro de la fila."""
    area = r["Area"] or "Sin área"
    sub = sub_texto(r)
    a_h = etiqueta(c, 0, 0, 360, 16, r["Actividad"], 9, TEXTO, "b", auto=True, dibujar=False)
    ar_h = etiqueta(c, 0, 0, 170, 16, area, 9, LINK, auto=True, dibujar=False)
    s_h = etiqueta(c, 0, 0, 230, 16, sub, 8.5, MUTED, auto=True, dibujar=False) if sub else 0
    rh = max(a_h, s_h, ar_h, 20) + 24
    if not dibujar:
        return rh
    cy = lambda h: y + (rh - h) / 2
    c.caja(x, y, 1302, rh, fill=PANEL, borde=BORDE, r=8)
    etiqueta(c, x + 12, cy(15), 56, 15, r["ID"], 8.5, MUTED, auto=True)
    etiqueta(c, x + 72, cy(a_h), 360, 16, r["Actividad"], 9, TEXTO, "b", auto=True)
    etiqueta(c, x + 442, cy(ar_h), 170, 16, area, 9, LINK, auto=True)
    sin = not r["Responsable"]
    chip(c, x + 622, cy(20), 20, 20, iniciales(r), 6.5, SIN_BG if sin else LINK, SIN_FG if sin else INK, 10)
    etiqueta(c, x + 648, cy(16), 100, 16, r["Responsable"] or "Sin asignar", 9, SIN_FG if sin else TEXTO, auto=True)
    if r["Prioridad"] == "Alta":
        chip(c, x + 752, cy(18), 40, 18, "Alta", 7.5, ALTA_BG, ALTA_FG, 9)
    else:
        etiqueta(c, x + 752, cy(16), 70, 16, r["Prioridad"] or "—", 9, MUTED, auto=True)
    fondo, fg = CHIP[r["Estado"]]
    chip(c, x + 830, cy(18), 96, 18, r["Estado"], 7.5, fondo, fg, 9)
    etiqueta(c, x + 948, cy(16), 90, 16, ddmmaaaa(r["FechaInicio"]) or "—", 9, TEXTO2, auto=True)
    if sub:
        etiqueta(c, x + 1048, cy(s_h), 230, 16, sub, 8.5, sub_color(r), auto=True)
    return rh


def dibujar_lista(orden_clave="id"):
    """Lista con el encabezado «ID ▲» activo (un clic en el encabezado ordena; aquí, por ID ascendente)."""
    c = Lienzo(W, H, BG, ss=SS)
    cromo(c, "lista")
    for clave, t, x in LISTA_COLS:
        activo = clave == orden_clave
        texto(c, x, 136, t + (" ▲" if activo else ""), 8.5, ACENTO if activo else MUTED, "b")
    filas = sorted(ACTIVIDADES, key=lambda r: r["ID"][-2:] + r["ID"][:4])

    def pintar(g):
        y = 0
        for r in filas:
            y += fila_lista(g, 0, y, r) + 6
        return y

    galeria(c, 32, 152, 1332, 604, BG, pintar)
    return c


# ------------------------------------------------------------------------------------------------ vista «Highlights y Lowlights»
def tarjeta_hl(c, x, y, w, r, dibujar=True):
    """Tarjeta de Highlight/Lowlight (07_vista_highlights.yaml): barra de color, tema, fecha, detalle, impacto/acción, responsable."""
    es_low = r["Tipo"] == "Lowlight"
    color = ROJO if es_low else VERDE
    lw = w - 32
    detalle = r["Detalle"] or "Sin detalle"
    imp = "\n".join(p for p in ((("Impacto: " + r["Impacto"]) if r["Impacto"] else ""), (("Acción: " + r["Accion"]) if r["Accion"] else "")) if p)
    t_h = etiqueta(c, 0, 0, w - 130, 20, r["Tema"], 10.5, TEXTO, "b", auto=True, dibujar=False)
    d_h = etiqueta(c, 0, 0, lw, 20, detalle, 9, TEXTO2, auto=True, dibujar=False)
    i_h = etiqueta(c, 0, 0, lw, 16, imp, 8.5, ALERTA, auto=True, dibujar=False) if imp else 0
    d_y = 10 + t_h + 4
    i_y = d_y + d_h + 6
    r_y = (i_y + i_h if imp else d_y + d_h) + 6
    r_h = alto_linea(8)
    alto = r_y + r_h + 10
    if dibujar:
        c.caja(x, y, w, alto, fill=CARD, borde=BORDE, r=6)
        c.caja(x, y + 12, 3, alto - 24, fill=color)
        etiqueta(c, x + 16, y + 10, w - 130, 20, r["Tema"], 10.5, TEXTO, "b", auto=True)
        texto(c, x + w - 12, y + 19, ddmmaaaa(r["Fecha"]), 8.5, MUTED, ancla="rm")
        etiqueta(c, x + 16, y + d_y, lw, 20, detalle, 9, DASH if not r["Detalle"] else TEXTO2, auto=True)
        if imp:
            etiqueta(c, x + 16, y + i_y, lw, 16, imp, 8.5, ALERTA if es_low else LINK, auto=True)
        sin = not r["Responsable"]
        etiqueta(c, x + 16, y + r_y, lw, 16, r["Responsable"] or "Sin responsable", 8, SIN_FG if sin else MUTED, auto=True)
    return alto


def dibujar_highlights():
    c = Lienzo(W, H, BG, ss=SS)
    cromo(c, "hl")
    for tipo, x, color, titulo in (("Highlight", 32, VERDE, "HIGHLIGHTS"), ("Lowlight", 694, ROJO, "LOWLIGHTS")):
        regs = sorted((r for r in HIGHLIGHTS if r["Tipo"] == tipo), key=lambda r: r["Fecha"], reverse=True)
        c.caja(x, 124, 640, 632, fill=CELL, r=10)
        etiqueta(c, x + 16, 134, 300, 22, f"{titulo} · {len(regs)}", 9.5, color, "b")
        boton(c, x + 528, 130, 96, 28, "+ Agregar", "ghost", 9.5)

        def pintar(g, regs=regs):
            y = 0
            for r in regs:
                y += tarjeta_hl(g, 0, y, 630 - 30, r) + 8
            return y

        galeria(c, x + 8, 168, 630, 582, CELL, pintar)
    return c


# ------------------------------------------------------------------------------------------------ vista «Por revisar»
def meta_revisar(r):
    """META de gen_revisar.py: contraparte, quién propone y fecha."""
    return ((f"Contraparte: {r['Contraparte']}  ·  " if r["Contraparte"] else "") + "Propone: " + (r["ResponsablePropuesto"] or "sin asignar")
            + (f"  ·  {ddmmaaaa(r['Fecha'])}" if r["Fecha"] else ""))


def tarjeta_rev_a(c, x, y, w, r, dibujar=True):
    """Tema por decidir: texto a la izquierda y acciones (Crear actividad, Descartar, Posponer) a la derecha."""
    tw = w - 330
    detalle = r["Detalle"] or "Sin detalle"
    t_h = etiqueta(c, 0, 0, tw, 20, r["Tema"], 10.5, TEXTO, "b", auto=True, dibujar=False)
    d_h = etiqueta(c, 0, 0, tw, 16, detalle, 9, TEXTO2, auto=True, dibujar=False)
    m_h = etiqueta(c, 0, 0, tw, 16, meta_revisar(r), 8, MUTED, auto=True, dibujar=False)
    d_y = 8 + t_h + 3
    m_y = d_y + d_h + 5
    alto = max(m_y + m_h + 10, 90)
    if dibujar:
        c.caja(x, y, w, alto, fill=CARD, borde=BORDE, r=6)
        etiqueta(c, x + 14, y + 8, tw, 20, r["Tema"], 10.5, TEXTO, "b", auto=True)
        etiqueta(c, x + 14, y + d_y, tw, 16, detalle, 9, DASH if not r["Detalle"] else TEXTO2, auto=True)
        etiqueta(c, x + 14, y + m_y, tw, 16, meta_revisar(r), 8, MUTED, auto=True)
        boton(c, x + w - 296, y + 10, 158, 30, "Crear actividad", "primary", 9.5)
        boton(c, x + w - 130, y + 10, 116, 30, "Descartar", "ghost", 9.5)
        boton(c, x + w - 296, y + 50, 158, 28, "Posponer", "ghost", 9.5)
    return alto


def tarjeta_rev_b(c, x, y, w, r, dibujar=True):
    """Tema ya decidido: chip con la decisión, meta y detalle."""
    t_h = etiqueta(c, 0, 0, w - 120, 20, r["Tema"], 9.5, TEXTO, "b", auto=True, dibujar=False)
    m_h = etiqueta(c, 0, 0, w - 24, 16, meta_revisar(r), 8, MUTED, auto=True, dibujar=False)
    m_y = 8 + t_h + 3
    d_h = etiqueta(c, 0, 0, w - 24, 16, r["Detalle"], 8, TEXTO2, auto=True, dibujar=False) if r["Detalle"] else 0
    d_y = m_y + m_h + 3
    alto = (d_y + d_h if r["Detalle"] else m_y + m_h) + 10
    if dibujar:
        c.caja(x, y, w, alto, fill=CARD, borde=BORDE, r=6)
        etiqueta(c, x + 12, y + 8, w - 120, 20, r["Tema"], 9.5, TEXTO, "b", auto=True)
        dec = r["Decision"]
        fondo, fg = {"Aprobado": ((225, 241, 226, 255), VERDE), "Pospuesto": (SIN_BG, SIN_FG)}.get(dec, (rgba(C["chip"]), TEXTO2))
        chip(c, x + w - 100, y + 9, 88, 18, dec, 7.5, fondo, fg, 9)
        etiqueta(c, x + 12, y + m_y, w - 24, 16, meta_revisar(r), 8, MUTED, auto=True)
        if r["Detalle"]:
            etiqueta(c, x + 12, y + d_y, w - 24, 16, r["Detalle"], 8, TEXTO2, auto=True)
    return alto


def dibujar_por_revisar():
    c = Lienzo(W, H, BG, ss=SS)
    cromo(c, "revisar")
    por_decidir = [r for r in POR_REVISAR if (r["Decision"] or "Por decidir") == "Por decidir"]
    resueltos = [r for r in POR_REVISAR if (r["Decision"] or "Por decidir") != "Por decidir"]
    c.caja(32, 124, 800, 632, fill=CELL, r=10)
    etiqueta(c, 48, 134, 400, 22, f"POR DECIDIR · {len(por_decidir)}", 9.5, SIN_FG, "b")
    boton(c, 696, 130, 124, 28, "+ Agregar tema", "ghost", 9.5)

    def pintar_a(g):
        y = 0
        for r in por_decidir:
            y += tarjeta_rev_a(g, 0, y, 792 - 30, r) + 8
        return y

    galeria(c, 38, 168, 792, 582, CELL, pintar_a)
    c.caja(846, 124, 488, 632, fill=CELL, r=10)
    etiqueta(c, 862, 134, 300, 22, f"RESUELTOS · {len(resueltos)}", 9.5, VERDE, "b")

    def pintar_b(g):
        y = 0
        for r in resueltos:
            y += tarjeta_rev_b(g, 0, y, 480 - 30, r) + 8
        return y

    galeria(c, 852, 168, 480, 582, CELL, pintar_b)
    return c


# ------------------------------------------------------------------------------------------------ vista «Historial»
def fila_historial(c, x, y, r, dibujar=True):
    """Fila de una actividad terminada (09_vista_historial.yaml); devuelve su alto."""
    area = r["Area"] or "Sin área"
    sub = r["StatusActual"] or r["Bloqueo"]
    a_h = etiqueta(c, 0, 0, 330, 16, r["Actividad"], 9, TEXTO, "b", auto=True, dibujar=False)
    ar_h = etiqueta(c, 0, 0, 150, 16, area, 9, LINK, auto=True, dibujar=False)
    s_h = etiqueta(c, 0, 0, 370, 16, sub, 8.5, MUTED, auto=True, dibujar=False) if sub else 0
    rh = max(a_h, s_h, ar_h, 20) + 24
    if not dibujar:
        return rh
    cy = lambda h: y + (rh - h) / 2
    c.caja(x, y, 1302, rh, fill=PANEL, borde=BORDE, r=8)
    etiqueta(c, x + 12, cy(15), 56, 15, r["ID"], 8.5, MUTED, auto=True)
    etiqueta(c, x + 72, cy(a_h), 330, 16, r["Actividad"], 9, TEXTO, "b", auto=True)
    etiqueta(c, x + 412, cy(ar_h), 150, 16, area, 9, LINK, auto=True)
    sin = not r["Responsable"]
    chip(c, x + 572, cy(20), 20, 20, iniciales(r), 6.5, SIN_BG if sin else LINK, SIN_FG if sin else INK, 10)
    etiqueta(c, x + 598, cy(16), 100, 16, r["Responsable"] or "Sin asignar", 9, SIN_FG if sin else TEXTO, auto=True)
    etiqueta(c, x + 702, cy(16), 90, 16, ddmmaaaa(r["FechaInicio"]) or "—", 9, TEXTO2, auto=True)
    etiqueta(c, x + 802, cy(16), 90, 16, ddmmaaaa(r["FechaTermino"]) or "—", 9, VERDE, auto=True)
    if sub:
        etiqueta(c, x + 902, cy(s_h), 370, 16, sub, 8.5, MUTED, auto=True)
    return rh


def dibujar_historial():
    c = Lienzo(W, H, BG, ss=SS)
    cromo(c, "historial")
    terminadas = sorted((r for r in ACTIVIDADES if r["Estado"] == "Terminada"), key=lambda r: r["FechaTermino"] or "0000", reverse=True)
    etiqueta(c, 44, 124, 500, 20, f"ACTIVIDADES TERMINADAS · {len(terminadas)}", 9.5, VERDE, "b")
    for t, x in (("ID", 44), ("ACTIVIDAD", 104), ("ÁREA", 444), ("RESPONSABLE", 604), ("INICIO", 734), ("TÉRMINO", 834), ("STATUS FINAL", 934)):
        texto(c, x, 160, t, 8.5, MUTED, "b")

    def pintar(g):
        y = 0
        for r in terminadas:
            y += fila_historial(g, 0, y, r) + 6
        return y

    galeria(c, 32, 174, 1332, 582, BG, pintar)
    return c


# ------------------------------------------------------------------------------------------------ paneles de edición (diálogos)
def sombra(c, x, y, w, h, r, desenfoque=22, dy=8, alpha=130):
    """Sombra suave bajo un panel (DropShadow.ExtraBold)."""
    s = c.ss
    m = Image.new("L", c.im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([x * s, (y + dy) * s, (x + w) * s, (y + h + dy) * s], r * s, fill=alpha)
    m = m.filter(ImageFilter.GaussianBlur(desenfoque * s / 2))
    c.im.paste((0, 0, 0), mask=m)


def panel(c, x, y, w, h):
    """Velo (recVelo, negro al 45 %) y panel blanco con borde y sombra."""
    c.caja(0, 0, W, H, fill=(0, 0, 0, 115))
    sombra(c, x, y, w, h, 12)
    c.caja(x, y, w, h, fill=PANEL, borde=BORDE, r=12)


def campo_etiqueta(c, ox, oy, x, y, txt, w=324, color=MUTED):
    etiqueta(c, ox + x, oy + y, w, 20, txt, 9, color)


def entrada(c, ox, oy, x, y, w, h, valor="", multi=False, deshabilitado=False):
    """TextInput clásico: blanco con borde y radio 8 (gris si está deshabilitado); multilínea con relleno superior de 8."""
    x, y = ox + x, oy + y
    c.caja(x, y, w, h, fill=BG if deshabilitado else INK, borde=BORDE, r=8)
    col = TEXTO2 if deshabilitado else TEXTO
    if multi:
        lh = alto_linea(10)
        lineas = [ln for p in valor.split("\n") for ln in envolver(c, p, 10, w - 24)] if valor else []
        for i, ln in enumerate(lineas):
            texto(c, x + 12, y + 8 + lh * (i + 0.5), ln, 10, col)
    elif valor:
        texto(c, x + 12, y + h / 2, valor, 10, col)


def desplegable(c, ox, oy, x, y, w, valor=""):
    """DropDown clásico (alto 38, sin radio) con chevron."""
    x, y = ox + x, oy + y
    c.caja(x, y, w, 38, fill=INK, borde=BORDE)
    if valor:
        texto(c, x + 12, y + 19, valor, 10, TEXTO)
    chevron(c, x + w - 20, y + 19)


def selector_fecha(c, ox, oy, x, y, w, valor=""):
    """DatePicker clásico: fecha dd-mm-yyyy o texto de ayuda «dd-mm-aaaa», con icono de calendario."""
    x, y = ox + x, oy + y
    c.caja(x, y, w, 38, fill=INK, borde=BORDE)
    texto(c, x + 12, y + 19, valor or "dd-mm-aaaa", 10, TEXTO if valor else HINT)
    cx, cy = x + w - 22, y + 19
    c.caja(cx - 7, cy - 6, 14, 13, borde=TEXTO2, r=2)
    c.caja(cx - 7, cy - 6, 14, 4, fill=TEXTO2, r=2)
    c.caja(cx - 4, cy - 9, 1.5, 4, fill=TEXTO2)
    c.caja(cx + 3, cy - 9, 1.5, 4, fill=TEXTO2)


def siguiente_id(hoy=HOY):
    """NEXT_ID de ids.py con el «hoy» simulado: siguiente correlativo del año en curso."""
    yy = hoy[2:4]
    usados = [(ord(r["ID"][0]) - 65) * 100 + int(r["ID"][2:4]) for r in ACTIVIDADES if re.fullmatch(r"[A-Z]-\d{2}-\d{2}", r["ID"]) and r["ID"][-2:] == yy]
    n = (max(usados) if usados else 0) + 1
    return f"{chr(65 + n // 100)}-{n % 100:02d}-{yy}"


def pie_botones(c, ox, oy, y, edicion):
    boton(c, ox + 24, oy + y, 110, 38, "Guardar", "primary")
    boton(c, ox + 144, oy + y, 110, 38, "Cancelar", "ghost")
    if edicion:
        boton(c, ox + 566, oy + y, 130, 38, "Eliminar", "danger")


def dibujar_panel_actividad(r=None):
    """03_paneles.yaml / panel_actividad.py. r=None: «Nueva actividad» sobre «Por área»; con r: edición sobre «Lista»."""
    c = dibujar_lista() if r else dibujar_por_area()
    ox, oy = 323, 68
    panel(c, ox, oy, 720, 632)
    texto(c, ox + 24, oy + 33, r["Actividad"] if r else "Nueva actividad", 13, TEXTO, "b")
    v = (lambda k: r[k]) if r else (lambda k: "")
    campo_etiqueta(c, ox, oy, 24, 56, "ID (automático)", 140)
    entrada(c, ox, oy, 24, 78, 140, 38, r["ID"] if r else siguiente_id(), deshabilitado=True)
    campo_etiqueta(c, ox, oy, 176, 56, "Actividad *", 520)
    entrada(c, ox, oy, 176, 78, 520, 38, v("Actividad"))
    campo_etiqueta(c, ox, oy, 24, 124, "Descripción / alcance")
    entrada(c, ox, oy, 24, 146, 672, 56, v("Descripcion"), multi=True)
    campo_etiqueta(c, ox, oy, 24, 210, "Área")
    desplegable(c, ox, oy, 24, 232, 324, v("Area"))
    campo_etiqueta(c, ox, oy, 372, 210, "Responsable (uno solo)")
    desplegable(c, ox, oy, 372, 232, 324, v("Responsable"))
    campo_etiqueta(c, ox, oy, 24, 278, "Contraparte / externos")
    entrada(c, ox, oy, 24, 300, 324, 38, v("Contraparte"))
    campo_etiqueta(c, ox, oy, 372, 278, "Prioridad")
    desplegable(c, ox, oy, 372, 300, 324, v("Prioridad"))
    campo_etiqueta(c, ox, oy, 24, 346, "Estado", 208)
    estado = r["Estado"] if r else "Por hacer"
    desplegable(c, ox, oy, 24, 368, 208, estado)
    campo_etiqueta(c, ox, oy, 248, 346, "Fecha inicio", 208)
    selector_fecha(c, ox, oy, 248, 368, 208, ddmmaaaa(r["FechaInicio"]) if r else ddmmaaaa(HOY))
    campo_etiqueta(c, ox, oy, 472, 346, "Fecha término", 224)
    selector_fecha(c, ox, oy, 472, 368, 224, ddmmaaaa(v("FechaTermino")))
    campo_etiqueta(c, ox, oy, 24, 414, "Status actual / pendientes")
    entrada(c, ox, oy, 24, 436, 672, 56, v("StatusActual"), multi=True)
    bloq = estado == "Bloqueada"
    campo_etiqueta(c, ox, oy, 24, 500, "Bloqueo / dependencia" + (" *" if bloq else ""), 400, ALERTA if bloq else MUTED)
    entrada(c, ox, oy, 24, 522, 672, 44, v("Bloqueo"), multi=True)
    pie_botones(c, ox, oy, 576, bool(r))
    return c


def dibujar_panel_hl(r):
    """panel_highlights.py: «Editar registro» sobre la vista Highlights y Lowlights."""
    c = dibujar_highlights()
    ox, oy = 323, 84
    panel(c, ox, oy, 720, 600)
    texto(c, ox + 24, oy + 33, "Editar registro", 13, TEXTO, "b")
    campo_etiqueta(c, ox, oy, 24, 56, "Tipo")
    desplegable(c, ox, oy, 24, 78, 324, r["Tipo"])
    campo_etiqueta(c, ox, oy, 372, 56, "Fecha")
    selector_fecha(c, ox, oy, 372, 78, 324, ddmmaaaa(r["Fecha"]))
    campo_etiqueta(c, ox, oy, 24, 124, "Tema *")
    entrada(c, ox, oy, 24, 146, 672, 38, r["Tema"])
    campo_etiqueta(c, ox, oy, 24, 192, "Detalle")
    entrada(c, ox, oy, 24, 214, 672, 72, r["Detalle"], multi=True)
    campo_etiqueta(c, ox, oy, 24, 294, "Impacto")
    entrada(c, ox, oy, 24, 316, 672, 56, r["Impacto"], multi=True)
    campo_etiqueta(c, ox, oy, 24, 380, "Acción")
    entrada(c, ox, oy, 24, 402, 672, 56, r["Accion"], multi=True)
    campo_etiqueta(c, ox, oy, 24, 466, "Responsable")
    desplegable(c, ox, oy, 24, 488, 324, r["Responsable"])
    pie_botones(c, ox, oy, 546, True)
    return c


def dibujar_panel_revisar(r):
    """panel_revisar.py: «Editar tema por revisar» sobre la vista Por revisar."""
    c = dibujar_por_revisar()
    ox, oy = 323, 149
    panel(c, ox, oy, 720, 470)
    texto(c, ox + 24, oy + 33, "Editar tema por revisar", 13, TEXTO, "b")
    campo_etiqueta(c, ox, oy, 24, 56, "Tema *")
    entrada(c, ox, oy, 24, 78, 672, 38, r["Tema"])
    campo_etiqueta(c, ox, oy, 24, 124, "Detalle")
    entrada(c, ox, oy, 24, 146, 672, 72, r["Detalle"], multi=True)
    campo_etiqueta(c, ox, oy, 24, 226, "Contraparte")
    entrada(c, ox, oy, 24, 248, 324, 38, r["Contraparte"])
    campo_etiqueta(c, ox, oy, 372, 226, "Responsable propuesto")
    desplegable(c, ox, oy, 372, 248, 324, r["ResponsablePropuesto"])
    campo_etiqueta(c, ox, oy, 24, 294, "Decisión")
    desplegable(c, ox, oy, 24, 316, 324, r["Decision"] or "Por decidir")
    campo_etiqueta(c, ox, oy, 372, 294, "Fecha")
    selector_fecha(c, ox, oy, 372, 316, 324, ddmmaaaa(r["Fecha"]))
    pie_botones(c, ox, oy, 396, True)
    return c


# ------------------------------------------------------------------------------------------------ salida
def registro(lista, campo, valor):
    return next(r for r in lista if r[campo] == valor)


def salvar(c, nombre, veladas=False, tope_kb=600):
    """Guarda con leyenda; si el PNG supera tope_kb lo reduce a 256 colores.

    Con 350 KB de tope, el cuantizado desplazaba colores poco frecuentes (el azul del logo y de la pestaña viraba a verde azulado);
    ningún render pasa hoy de 600 KB, así que se guardan todos a color completo.
    """
    ruta = SALIDA / nombre
    c.guardar(ruta, LEYENDA, color_leyenda="#14181F" if veladas else "#6C757D")
    cuantizado = False
    if ruta.stat().st_size / 1024 > tope_kb:
        c.guardar(ruta, None, cuantizar=True)
        cuantizado = True
    return ruta, cuantizado


def pantallas():
    """(archivo, pantalla, función que la dibuja, ¿lleva velo?)."""
    bloqueada = registro(ACTIVIDADES, "ID", "A-93-25")
    lowlight = registro(HIGHLIGHTS, "Tema", "Retraso en la entrega de insumos de la contraparte")
    tema = registro(POR_REVISAR, "Tema", "Reducir pasos del flujo de aprobación")
    return [
        ("tablero.png", "Por área", dibujar_por_area, False),
        ("tablero_estados.png", "Tablero", dibujar_tablero_estados, False),
        ("lista.png", "Lista", dibujar_lista, False),
        ("persona.png", "Por persona", dibujar_persona, False),
        ("highlights.png", "Highlights y Lowlights", dibujar_highlights, False),
        ("por_revisar.png", "Por revisar", dibujar_por_revisar, False),
        ("historial.png", "Historial", dibujar_historial, False),
        ("nueva_actividad.png", "Nueva actividad", lambda: dibujar_panel_actividad(), True),
        ("editar_actividad.png", "Editar actividad", lambda: dibujar_panel_actividad(bloqueada), True),
        ("editar_registro.png", "Editar registro (Highlights y Lowlights)", lambda: dibujar_panel_hl(lowlight), True),
        ("editar_tema_revisar.png", "Editar tema por revisar", lambda: dibujar_panel_revisar(tema), True),
    ]


if __name__ == "__main__":
    for archivo, nombre, dibujar, velada in pantallas():
        ruta, cuant = salvar(dibujar(), archivo, velada)
        print(f"{archivo:26s} {nombre:42s} {round(ruta.stat().st_size / 1024):4d} KB" + ("  (256 colores)" if cuant else ""))
