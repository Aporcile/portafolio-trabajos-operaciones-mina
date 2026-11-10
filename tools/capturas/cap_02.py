# -*- coding: utf-8 -*-
"""Renders del diseño de «02 · OEE de transporte CAEX + app RD Terreno» (Minera Demo, datos 100 % sintéticos).

No son capturas de Power BI Desktop ni de Power Apps Studio: son vistas del diseño dibujadas con Pillow a partir de
- el informe PBIR (posiciones, colores, medidas y reglas de formato de pbip/generador/gen_pbi_oee.py y pbir_lib.py) y los CSV de
  datos_sinteticos/oee/ (las cifras se recalculan aquí con las mismas fórmulas DAX);
- los YAML de la app (app/pantallas/*.yaml: posiciones, colores, tamaños y textos) y los CSV de datos_sinteticos/app/.

Salida: 02-oee-caex-y-app-desempeno/capturas/*.png
    informe (1280×720, periodo MENSUAL):  oee_transporte · disponibilidad · uebd_caex · rendimiento_efectivo · horas_nominales
    app (lienzo 1024×640):                app_inicio · app_editor · app_visor

Uso:  python tools/capturas/cap_02.py [nombre ...]     (sin argumentos, genera todo)
"""
import csv
import json
import math
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_render import ICONO, LOGO_BLANCO, Lienzo  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
PROY = RAIZ / "02-oee-caex-y-app-desempeno"
DATOS = PROY / "datos_sinteticos"
SALIDA = PROY / "capturas"
LEYENDA = "Render del diseño · datos sintéticos · Minera Demo"

# ---------------------------------------------------------------------------------------------------------------------
# Texto: Segoe UI (regular, ligera, semibold, negrita) con los símbolos (✔ ⚠ ✖ ▶ ●) tomados de Segoe UI Symbol
# ---------------------------------------------------------------------------------------------------------------------
FUENTES = {"n": "segoeui.ttf", "l": "segoeuil.ttf", "s": "seguisb.ttf", "b": "segoeuib.ttf"}
SIMB = set("✔⚠✖▶◀●")
_fc = {}


def _f(nombre, px):
    k = (nombre, int(round(px)))
    if k not in _fc:
        try:
            _fc[k] = ImageFont.truetype(nombre, k[1])
        except OSError:
            _fc[k] = ImageFont.truetype("arial.ttf", k[1])
    return _fc[k]


class Tx:
    """Texto sobre un Lienzo. Los tamaños se dan en puntos (Power BI y Power Apps: px = pt × 4/3)."""

    def __init__(self, c):
        self.c, self.ss = c, c.ss

    def _runs(self, s, px, peso):
        out, cur, simb = [], "", None
        for ch in s:
            es = ch in SIMB
            if simb is None or es == simb:
                cur += ch
                simb = es
            else:
                out.append((cur, simb))
                cur, simb = ch, es
        if cur:
            out.append((cur, simb))
        return [(t, _f("seguisym.ttf" if sm else FUENTES[peso], px * self.ss)) for t, sm in out]

    def w(self, s, px, peso="n"):
        return sum(f.getlength(t) for t, f in self._runs(s, px, peso)) / self.ss

    def linea(self, x, yc, s, px, color, peso="n", ancla="l"):
        """Una línea de texto con su centro vertical en yc; ancla l / c / r en x."""
        runs = self._runs(s, px, peso)
        w = sum(f.getlength(t) for t, f in runs) / self.ss
        x0 = x if ancla == "l" else (x - w / 2 if ancla == "c" else x - w)
        asc, desc = _f(FUENTES[peso], px * self.ss).getmetrics()
        base = yc * self.ss + (asc - desc) / 2
        xx = x0 * self.ss
        for t, f in runs:
            self.c.d.text((xx, base), t, font=f, fill=color, anchor="ls")
            xx += f.getlength(t)
        return w

    def envolver(self, s, px, peso, ancho):
        lineas = []
        for par in str(s).split("\n"):
            cur = ""
            for p in par.split(" "):
                t = (cur + " " + p) if cur else p
                if cur and self.w(t, px, peso) > ancho:
                    lineas.append(cur)
                    cur = p
                else:
                    cur = t
            lineas.append(cur)
        return lineas

    def etiqueta(self, x, y, w, h, s, size, color, peso="n", align="l", valign="m", wrap=True, pad=(5, 5, 5, 5), fill=None,
                 lh=1.32, radio=0, borde=None, bw=1):
        """Etiqueta con la lógica de una Label de Power Apps (relleno, alineación, ajuste de línea)."""
        if fill is not None or borde is not None:
            self.c.caja(x, y, w, h, fill=fill, borde=borde, r=radio, ancho=bw)
        px = size * 4 / 3
        pl, pr, pt, pb = pad
        ancho = w - pl - pr
        lineas = self.envolver(s, px, peso, ancho) if wrap else str(s).split("\n")
        alto = len(lineas) * px * lh
        top = y + pt + ((h - pt - pb - alto) / 2 if valign == "m" else 0)
        for i, ln in enumerate(lineas):
            yc = top + (i + 0.5) * px * lh
            if align == "l":
                self.linea(x + pl, yc, ln, px, color, peso, "l")
            elif align == "c":
                self.linea(x + pl + ancho / 2, yc, ln, px, color, peso, "c")
            else:
                self.linea(x + w - pr, yc, ln, px, color, peso, "r")
        return lineas

    def rotado(self, x, y, s, px, color, peso="n"):
        """Texto girado 90° (se lee de abajo hacia arriba), con su final en (x, y) y centrado en x."""
        ss = self.ss
        runs = self._runs(s, px, peso)
        w = sum(f.getlength(t) for t, f in runs)
        alto = int(px * 1.5 * ss)
        tmp = Image.new("RGBA", (int(w) + 6, alto), (0, 0, 0, 0))
        d = ImageDraw.Draw(tmp)
        asc, desc = _f(FUENTES[peso], px * ss).getmetrics()
        base = alto / 2 + (asc - desc) / 2
        xx = 2
        for t, f in runs:
            d.text((xx, base), t, font=f, fill=color, anchor="ls")
            xx += f.getlength(t)
        rot = tmp.rotate(90, expand=True)
        self.c.im.paste(rot, (int(x * ss - rot.width / 2), int(y * ss)), rot)
        return w / ss


def boton(tx, x, y, w, h, texto, size, color, fill, peso="b", r=8, borde=None, bw=1, align="c", padl=5, wrap=False):
    tx.etiqueta(x, y, w, h, texto, size, color, peso, align=align, valign="m", wrap=wrap, pad=(padl, padl, 0, 0), fill=fill,
                radio=min(r, h / 2), borde=borde, bw=bw)


def sombra(c, x, y, w, h, r=12, alpha=34, blur=5, dy=2):
    """Sombra suave bajo un recuadro (DropShadow.Light)."""
    s, m = c.ss, 14
    capa = Image.new("RGBA", (int((w + 2 * m) * s), int((h + 2 * m) * s)), (0, 0, 0, 0))
    ImageDraw.Draw(capa).rounded_rectangle([m * s, m * s, (m + w) * s, (m + h) * s], r * s, fill=(0, 0, 0, alpha))
    capa = capa.filter(ImageFilter.GaussianBlur(blur * s))
    ox, oy = int((x - m) * s), int((y - m + dy) * s)
    base = c.im.crop((ox, oy, ox + capa.width, oy + capa.height)).convert("RGBA")
    c.im.paste(Image.alpha_composite(base, capa).convert("RGB"), (ox, oy))


def pegar_fit(c, ruta, x, y, w, h):
    """Imagen con ImagePosition.Fit: escalada para caber en (w, h) y centrada."""
    img = Image.open(ruta).convert("RGBA")
    k = min(w / img.width, h / img.height)
    nw, nh = img.width * k, img.height * k
    img = img.resize((max(1, round(nw * c.ss)), max(1, round(nh * c.ss))), Image.LANCZOS)
    c.im.paste(img, (round((x + (w - nw) / 2) * c.ss), round((y + (h - nh) / 2) * c.ss)), img)


def guardar(c, nombre, limite_kb=350):
    ruta = SALIDA / nombre
    c.guardar(ruta, LEYENDA, color_leyenda=c.color_leyenda)
    kb = ruta.stat().st_size / 1024
    cuant = False
    if kb > limite_kb:
        c.guardar(ruta, None, cuantizar=True)  # la leyenda ya está dibujada
        cuant = True
        kb = ruta.stat().st_size / 1024
    print(f"{nombre}: {kb:.0f} KB{' (256 colores)' if cuant else ''}")
    return ruta


def fm(v, dec=0):
    """Número con coma decimal y punto de miles (formato es-ES de la cultura del informe)."""
    s = f"{v:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def pct(v, dec=1):
    return fm(v * 100, dec) + "%"


def sgn(v, dec=0):
    return ("+" if v > 0 else "-" if v < 0 else "") + fm(abs(v), dec)


def nice_ticks(vmax, n=5):
    raw = vmax / n
    exp = 10 ** math.floor(math.log10(raw))
    paso = next(m * exp for m in (1, 2, 2.5, 5, 10) if m * exp >= raw)
    top = math.ceil(vmax / paso - 1e-9) * paso
    return [i * paso for i in range(int(round(top / paso)) + 1)]


def squarify(vals, x, y, w, h):
    tot = sum(vals)
    areas = [v * w * h / tot for v in vals]
    out = []

    def peor(fila, lado):
        s = sum(fila)
        return max(max(lado * lado * a / (s * s), s * s / (lado * lado * a)) for a in fila)

    i = 0
    while i < len(areas):
        lado = min(w, h)
        fila = [areas[i]]
        j = i + 1
        while j < len(areas) and peor(fila + [areas[j]], lado) <= peor(fila, lado):
            fila.append(areas[j])
            j += 1
        s = sum(fila)
        if w >= h:
            rw, yy = s / h, y
            for a in fila:
                out.append((x, yy, rw, a / rw))
                yy += a / rw
            x, w = x + rw, w - rw
        else:
            rh, xx = s / w, x
            for a in fila:
                out.append((xx, y, a / rh, rh))
                xx += a / rh
            y, h = y + rh, h - rh
        i = j
    return out


def brillo_rel(hexc):
    r, g, b = (int(hexc[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# ---------------------------------------------------------------------------------------------------------------------
# Datos del informe (CSV sintéticos) y fórmulas de las medidas DAX, periodo MENSUAL «hasta ayer»
# ---------------------------------------------------------------------------------------------------------------------
MEDIANOCHE, CIELO, VIOLETA, ACERO, ROSA, SALVIA = "#1B2A41", "#4F9DDE", "#7B61C9", "#2F6FB5", "#C26B8E", "#A3B18A"
PLOMO, NIQUEL, ZINC, PLATA = "#3A4352", "#B4BAC4", "#C5CBD6", "#E6E9EE"
VERDE, AMBAR, ROJO = "#2E7D32", "#F28C28", "#C62828"
ROJO_CLARO, VERDE_CLARO, TEXTO_CLARO = "#FFAB91", "#A5D6A7", "#C8D3E3"
COLORES_TEMA = [MEDIANOCHE, CIELO, VIOLETA, ACERO, SALVIA, ROSA, PLOMO, NIQUEL, "#8D949F", "#95C4EB", "#B0A0DF", ZINC]
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
CAT_NO_DISP = ["Mantención programada", "Mantención no programada", "Daño operacional", "Neumáticos",
               "Cambio programado de neumáticos"]
CAT_NO_EFECTIVO = ["Demora programada", "Demora no programada", "Reserva"]
COMPONENTES = [("Viaje vacío", "traveling_time"), ("Espera en carguío", "waiting_time"), ("Aculatamiento", "spotting_time"),
               ("Carguío", "loading_time"), ("Viaje cargado", "hauling_time"), ("Cola en descarga", "queued_time"),
               ("Descarga", "tipping_time"), ("Retroceso", "backing_time")]
TIPOS_UEBD = [("Demora programada", "Horas Demora Programada"), ("Demora no programada", "Horas Demora No Programada"),
              ("Reserva", "Horas Reserva"), ("PO espera", "Horas PO Espera"), ("PO cola", "Horas PO Cola")]


def leer(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


class Oee:
    """Cifras del informe en el periodo MENSUAL (1 de mayo a ayer); mismas fórmulas que Medidas RD.tmdl."""

    def __init__(self):
        g = DATOS / "oee"
        marca = leer(g / "Dim_Actualizacion.csv")[0]["Marca"]
        self.hoy = date.fromisoformat(marca[:10])
        self.f = self.hoy - timedelta(days=1)           # [Último día]: ayer
        self.i = date(self.f.year, self.f.month, 1)     # [Inicio mes]
        en = lambda s: self.i <= date.fromisoformat(s[:10]) <= self.f  # noqa: E731
        self.dias = [self.i + timedelta(days=k) for k in range((self.f - self.i).days + 1)]
        cols = {"hn": "Horas Nominales", "hd": "Horas Disponibles", "he": "Horas Efectivas", "mov": "Movimiento Total"}
        cols.update({"t_" + n: c for n, c in TIPOS_UEBD})
        self.tot = defaultdict(float)
        self.dia = defaultdict(lambda: defaultdict(float))
        self.eq = defaultdict(lambda: defaultdict(float))
        for r in leer(g / "Fact_HorasEquipo.csv"):
            if not en(r["Fecha"]):
                continue
            d = date.fromisoformat(r["Fecha"])
            for k, c in cols.items():
                v = float(r[c])
                self.tot[k] += v
                self.dia[d][k] += v
                self.eq[r["Equipo"]][k] += v
        # Plan mensual (Planes_Mina), día a día
        items = {"hn": "Horas Nominales CAEX", "hd": "Horas Disponibles CAEX", "he": "Horas Efectivas CAEX", "t": "Total Toneladas CAEX"}
        inv = {v: k for k, v in items.items()}
        self.ptot = defaultdict(float)
        self.pdia = defaultdict(lambda: defaultdict(float))
        for r in leer(g / "Planes_Mina.csv"):
            if r["plan_type"] == "Mensual" and r["property_name"] in inv and en(r["start_date"]):
                d = date.fromisoformat(r["start_date"])
                self.ptot[inv[r["property_name"]]] += float(r["value"])
                self.pdia[d][inv[r["property_name"]]] += float(r["value"])
        # Horas por código
        self.cod = defaultdict(float)
        self.cod_cat = {}
        for r in leer(g / "Horas_Codigo_CAEX.csv"):
            if en(r["Fecha"]):
                self.cod[r["Codigo"]] += float(r["Horas"])
                self.cod_cat[r["Codigo"]] = r["Categoria"]
        # Ciclos
        self.ciclo = defaultdict(float)
        self.ciclo_n = 0
        pay = defaultdict(list)
        for r in leer(g / "Fact_Ciclos.csv"):
            if not en(r["time"]):
                continue
            self.ciclo_n += 1
            for _, c in COMPONENTES:
                self.ciclo[c] += float(r[c])
            p = float(r["payload"])
            if 200 < p < 330:
                pay[r["TruckName"]].append(p)
        self.fc = {k: sum(v) / len(v) for k, v in pay.items()}
        fcp = [float(r["Plan"]) for r in leer(g / "Plan_FactorCarga.csv") if en(r["Fecha"])]
        self.fc_plan = sum(fcp) / len(fcp)
        # Palancas (cascada que cierra exactamente)
        t, p = self.tot, self.ptot
        self.df, self.ue, self.rr = t["hd"] / t["hn"], t["he"] / t["hd"], t["mov"] / t["he"]
        self.dfp, self.uep, self.rrp = p["hd"] / p["hn"], p["he"] / p["hd"], p["t"] / p["he"]
        self.plan_t, self.real_t = p["t"], t["mov"]
        hnp, hnr = p["hn"], t["hn"]
        self.d_df = hnp * (self.df - self.dfp) * self.uep * self.rrp
        self.d_ue = hnp * self.df * (self.ue - self.uep) * self.rrp
        self.d_rr = hnp * self.df * self.ue * (self.rr - self.rrp)
        self.d_hn = (hnr - hnp) * self.df * self.ue * self.rr
        self.control = self.plan_t + self.d_df + self.d_ue + self.d_rr + self.d_hn - self.real_t
        self.oee = self.df * self.ue * self.rr / self.rrp
        self.oee_p = self.dfp * self.uep
        self.var = self.real_t / self.plan_t - 1
        self.tol = 0.001 * self.plan_t

    # series por día
    def s_dia(self, k):
        d = self.dia
        if k == "df":
            return [d[x]["hd"] / d[x]["hn"] for x in self.dias], [self.pdia[x]["hd"] / self.pdia[x]["hn"] for x in self.dias]
        if k == "uebd":
            return [d[x]["he"] / d[x]["hd"] for x in self.dias], [self.pdia[x]["he"] / self.pdia[x]["hd"] for x in self.dias]
        if k == "rend":
            return [d[x]["mov"] / d[x]["he"] for x in self.dias], [self.pdia[x]["t"] / self.pdia[x]["he"] for x in self.dias]
        return [d[x]["hn"] / 24 for x in self.dias], [self.pdia[x]["hn"] / 24 for x in self.dias]

    def texto_periodo(self):
        i, f = self.i, self.f
        return f"{DIAS[i.weekday()]} {i:%d} a {DIAS[f.weekday()]} {f:%d-%m} · contra el plan mensual"


def semaforo(r, p):
    if p is None or p == 0:
        return CIELO
    return VERDE if r >= 0.999 * p else AMBAR if r >= 0.95 * p else ROJO


# ---------------------------------------------------------------------------------------------------------------------
# Piezas de las páginas del informe
# ---------------------------------------------------------------------------------------------------------------------
def selector(tx, x, y, w, h, marco, elegido=2):
    """Segmentador «Periodo»: tres mosaicos (JUE-DOM, SEMANAL, MENSUAL); el elegido va oscuro."""
    c = tx.c
    nombres = ["JUE-DOM", "SEMANAL", "MENSUAL"]
    aw = w / 3
    for k, n in enumerate(nombres):
        xx = x + k * aw
        sel = k == elegido
        if marco:
            c.caja(xx, y, aw, h, fill=MEDIANOCHE if sel else "#FFFFFF", borde=MEDIANOCHE, ancho=1)
        else:
            c.caja(xx + 1, y, aw - 2, h, fill=MEDIANOCHE if sel else "#FFFFFF", borde="#FFFFFF" if sel else None, ancho=1)
        tx.etiqueta(xx, y, aw, h, n, 9, "#FFFFFF" if sel else MEDIANOCHE, "n", align="c", wrap=False, pad=(0, 0, 0, 0))


def cabecera_detalle(c, tx, o, titulo, etiqueta, real_txt, plan_txt, plan_color):
    c.caja(0, 0, 1280, 96, fill=MEDIANOCHE)
    c.pegar(LOGO_BLANCO, 0, 8, w=125)
    pegar_fit(c, ICONO, 126, 6, 56, 44)
    # botón «← Volver al OEE»
    c.caja(16, 60, 120, 28, borde="#FFFFFF", r=14)
    tx.etiqueta(16, 60, 120, 28, "← Volver al OEE", 10, "#FFFFFF", "b", align="l", wrap=False, pad=(10, 4, 0, 0))
    tx.etiqueta(196, 8, 520, 24, "Tablero de control", 13, "#FFFFFF", pad=(4, 4, 0, 0), valign="t", wrap=False)
    tx.etiqueta(196, 32, 520, 32, titulo, 18, "#FFFFFF", "b", pad=(4, 4, 0, 0), valign="t", wrap=False)
    selector(tx, 720, 10, 330, 32, marco=False)
    tx.etiqueta(700, 48, 370, 20, o.texto_periodo(), 9, "#FFFFFF", align="c", wrap=False, pad=(0, 0, 0, 0))
    tx.etiqueta(1074, 4, 196, 44, real_txt, 24, "#FFFFFF", "s", align="c", wrap=False, pad=(0, 0, 0, 0))
    tx.etiqueta(1074, 48, 196, 20, etiqueta, 10, "#FFFFFF", align="c", wrap=False, pad=(0, 0, 0, 0))
    tx.etiqueta(1074, 70, 196, 20, plan_txt, 9, plan_color, "s", align="c", wrap=False, pad=(0, 0, 0, 0))


def tarjeta(c, tx, x, y, w, h, titulo, subtitulo=None):
    """Contenedor de un visual: fondo blanco, borde gris, título en negrita y, opcional, «● Plan»."""
    c.caja(x, y, w, h, fill="#FFFFFF", borde=ZINC, r=6)
    tx.etiqueta(x + 4, y + 4, w - 8, 24, titulo, 11, MEDIANOCHE, "b", wrap=False, pad=(6, 4, 0, 0))
    if subtitulo:
        tx.etiqueta(x + 4, y + 26, w - 8, 18, subtitulo, 9, MEDIANOCHE, wrap=False, pad=(6, 4, 0, 0))


def combo(c, tx, x, y, w, h, titulo, real, plan, colores, fmt_v, o, rotulos=None, marcas=None):
    """Columnas por día (color de semáforo) + línea del plan con marcadores."""
    tarjeta(c, tx, x, y, w, h, titulo, "● Plan")
    n = len(real)
    ticks = nice_ticks(max(max(real), max(plan)) * 1.02, 5)
    top_v = ticks[-1]
    izq, der, arriba, abajo = x + 12 + max(tx.w(fmt_v(t), 12) for t in ticks) + 8, x + w - 14, y + 54, y + h - 62
    for t in ticks:
        yy = abajo - (abajo - arriba) * t / top_v
        c.linea([(izq, yy), (der, yy)], PLATA, 1)
        tx.linea(izq - 6, yy, fmt_v(t), 12, PLOMO, "n", "r")
    slot = (der - izq) / n
    bw = slot * 0.64
    for k in range(n):
        bx = izq + k * slot + (slot - bw) / 2
        bh = (abajo - arriba) * real[k] / top_v
        c.caja(bx, abajo - bh, bw, bh, fill=colores[k])
    pts = [(izq + (k + 0.5) * slot, abajo - (abajo - arriba) * plan[k] / top_v) for k in range(n)]
    c.linea(pts, MEDIANOCHE, 2)
    for px_, py_ in pts:
        c.elipse(px_, py_, 3, fill=MEDIANOCHE)
    for k in range(0, n, 2):  # etiquetas de datos (en las columnas pares: así no se pisan)
        bh = (abajo - arriba) * real[k] / top_v
        cx = izq + (k + 0.5) * slot
        s = fmt_v(real[k])
        ww = tx.w(s, 12)
        c.caja(cx - ww / 2 - 2, abajo - bh - 17, ww + 4, 15, fill=(255, 255, 255, 215))
        tx.linea(cx, abajo - bh - 9.5, s, 12, PLOMO, "n", "c")
    c.linea([(izq, abajo), (der, abajo)], ZINC, 1)
    for k in range(n):
        d = o.dias[k]
        tx.rotado(izq + (k + 0.5) * slot, abajo + 5, f"{DIAS[d.weekday()]} {d:%d-%m}", 12, PLOMO)


def barras_h(c, tx, x, y, w, h, titulo, cats, vals, colores, fmt_v, vmax=None, ticks_n=5, cada=2):
    """Barras horizontales (primera categoría arriba) con etiquetas de categoría y de dato en filas alternas."""
    tarjeta(c, tx, x, y, w, h, titulo)
    n = len(cats)
    ticks = nice_ticks(vmax if vmax else max(vals) * 1.02, ticks_n)
    top_v = ticks[-1]
    izq = x + 14 + max(tx.w(s, 12) for s in cats) + 8
    der, arriba, abajo = x + w - 56, y + 36, y + h - 38
    for t in ticks:
        xx = izq + (der - izq) * t / top_v
        c.linea([(xx, arriba), (xx, abajo)], PLATA, 1)
        tx.linea(xx, abajo + 12, fmt_v(t), 12, PLOMO, "n", "c")
    slot = (abajo - arriba) / n
    bh = slot * 0.72
    for k in range(n):
        by = arriba + k * slot + (slot - bh) / 2
        bw_ = (der - izq) * vals[k] / top_v
        c.caja(izq, by, bw_, bh, fill=colores[k])
        if k % cada == 0:
            tx.linea(izq - 6, by + bh / 2, cats[k], 12, PLOMO, "n", "r")
            tx.linea(izq + bw_ + 4, by + bh / 2, fmt_v(vals[k]), 12, PLOMO, "n", "l")
    c.linea([(izq, arriba), (izq, abajo)], ZINC, 1)


def tabla(c, tx, x, y, w, h, titulo, cab, filas, anchos, alin, fila_h=22, colores_col=None, resto_pie=16):
    """Tabla: cabecera medianoche con texto blanco en negrita, filas con línea horizontal gris; recorta lo que no cabe."""
    tarjeta(c, tx, x, y, w, h, titulo)
    ix, iy, iw = x + 8, y + 34, w - 16
    k = iw / sum(anchos)
    anchos = [a * k for a in anchos]
    c.caja(ix, iy, iw, fila_h + 1, fill=MEDIANOCHE)
    xx = ix
    for j, t in enumerate(cab):
        tx.etiqueta(xx, iy, anchos[j], fila_h + 1, t, 8, "#FFFFFF", "b", align="c", wrap=False, pad=(4, 4, 0, 0))
        xx += anchos[j]
    yy = iy + fila_h + 1
    limite = y + h - resto_pie
    for fila in filas:
        if yy + fila_h > limite:
            break
        xx = ix
        for j, t in enumerate(fila):
            col = MEDIANOCHE if not colores_col or colores_col[j] is None else colores_col[j]
            tx.etiqueta(xx, yy, anchos[j], fila_h, t, 9, col, "n", align=alin[j], wrap=False, pad=(6, 6, 0, 0))
            xx += anchos[j]
        c.linea([(ix, yy + fila_h), (ix + iw, yy + fila_h)], PLATA, 1)
        yy += fila_h + 1


def treemap(c, tx, x, y, w, h, titulo, items):
    """items: [(nombre, valor)] de mayor a menor; colores del tema en ese orden."""
    tarjeta(c, tx, x, y, w, h, titulo)
    ix, iy, iw, ih = x + 8, y + 34, w - 16, h - 34 - 22
    rects = squarify([v for _, v in items], ix, iy, iw, ih)
    for k, ((nom, v), (rx, ry, rw, rh)) in enumerate(zip(items, rects)):
        col = COLORES_TEMA[k % len(COLORES_TEMA)]
        c.caja(rx + 1, ry + 1, rw - 2, rh - 2, fill=col)
        txt = "#FFFFFF" if brillo_rel(col) < 150 else MEDIANOCHE
        lineas = tx.envolver(nom, 12, "n", rw - 14)
        for i, ln in enumerate(lineas[:3]):
            tx.linea(rx + 6, ry + 14 + i * 15, ln, 12, txt, "n")
        tx.linea(rx + 6, ry + 14 + len(lineas[:3]) * 15, fm(v, 1), 12, txt, "b")


# ---------------------------------------------------------------------------------------------------------------------
# Páginas del informe
# ---------------------------------------------------------------------------------------------------------------------
def nuevo_informe():
    c = Lienzo(1280, 720, "#FFFFFF")
    c.color_leyenda = "#8D949F"
    return c, Tx(c)


def pagina_oee(o):
    c, tx = nuevo_informe()
    tx.etiqueta(16, 4, 520, 40, "Equipos Mina", 22, MEDIANOCHE, "b", valign="t", wrap=False, pad=(4, 4, 2, 0))
    tx.etiqueta(16, 42, 520, 30, "Transporte", 15, PLOMO, valign="t", wrap=False, pad=(4, 4, 0, 0))
    selector(tx, 852, 10, 412, 34, marco=True)
    tx.etiqueta(700, 50, 564, 22, o.texto_periodo(), 10, MEDIANOCHE, "s", align="c", wrap=False, pad=(0, 0, 0, 0))
    tx.etiqueta(16, 80, 400, 26, "OEE Transporte", 12, MEDIANOCHE, "b", valign="t", wrap=False, pad=(4, 4, 0, 0))

    ch_x, ch_y, ch_w, ch_h = 16, 120, 1248, 296
    plot_l, plot_r = 89, 63
    banda = (ch_w - plot_l - plot_r) / 6
    cent = [round(ch_x + plot_l + (k + 0.5) * banda) for k in range(6)]
    # Corchete de la variación total
    a, b = cent[0], cent[-1]
    c.caja(a, 104, b - a, 2, fill=PLOMO)
    c.caja(a, 104, 2, 16, fill=PLOMO)
    c.caja(b - 2, 104, 2, 16, fill=PLOMO)
    rojo_var = o.var < -0.001
    tx.etiqueta((a + b) // 2 - 80, 88, 160, 34, ("+" if o.var > 0 else "-") + fm(abs(o.var) * 100, 2) + "%", 18, ROJO if rojo_var else MEDIANOCHE, "s",
                align="c", wrap=False, pad=(0, 0, 0, 0), fill="#FFFFFF")

    # Cascada (columnas apiladas: base invisible + total / pérdida / ganancia), eje desde 0
    niveles = [o.plan_t]
    for d in (o.d_df, o.d_ue, o.d_rr, o.d_hn):
        niveles.append(niveles[-1] + d)
    ticks = nice_ticks(o.plan_t * 1.02, 7)
    top_v = ticks[-1]
    arriba, abajo = ch_y + 10, ch_y + ch_h - 46
    sc = (abajo - arriba) / top_v
    c.linea([(ch_x + plot_l, abajo), (ch_x + ch_w - plot_r, abajo)], ZINC, 1)
    bw = 141
    pasos = ["Movimiento Total - Plan", "Pérdida CAEX Disponibilidad", "Pérdida CAEX UEBD", "Pérdida CAEX Rendimiento Efectivo",
             "Pérdida CAEX Horas Nominales", "Movimiento Total - Real"]
    deltas = [None, o.d_df, o.d_ue, o.d_rr, o.d_hn, None]
    for k in range(6):
        bx = cent[k] - bw / 2
        if k in (0, 5):
            v = o.plan_t if k == 0 else o.real_t
            c.caja(bx, abajo - v * sc, bw, v * sc, fill=CIELO)
        else:
            lo, hi = sorted((niveles[k - 1], niveles[k]))
            alto = max((hi - lo) * sc, 3)
            c.caja(bx, abajo - hi * sc, bw, alto, fill=ROJO if deltas[k] < 0 else VERDE)
        for i, ln in enumerate(tx.envolver(pasos[k], 12, "n", banda - 14)):
            tx.linea(cent[k], abajo + 12 + i * 15, ln, 12, PLOMO, "n", "c")
    # Cifra de cada barra y botón «Ver detalle ›» bajo las cuatro palancas
    yv = ch_y + ch_h + 2
    tx.etiqueta(cent[0] - 95, yv, 190, 22, fm(o.plan_t) + " t", 10, CIELO, "s", align="c", wrap=False, pad=(0, 0, 0, 0))
    tx.etiqueta(cent[5] - 95, yv, 190, 22, fm(o.real_t) + " t", 10, CIELO, "s", align="c", wrap=False, pad=(0, 0, 0, 0))
    for i, d in enumerate(deltas[1:5], start=1):
        col = PLOMO if abs(d) <= o.tol else ROJO if d < 0 else VERDE
        tx.etiqueta(cent[i] - 95, yv, 190, 22, sgn(d) + " t", 10, col, "s", align="c", wrap=False, pad=(0, 0, 0, 0))
        boton(tx, cent[i] - 66, 444, 132, 26, "Ver detalle  ›", 10, "#FFFFFF", ROJO if d < -o.tol else MEDIANOCHE, "s", r=13)

    # Tabla «Datos Transporte»
    tx.etiqueta(16, 480, 300, 22, "Datos Transporte", 11, MEDIANOCHE, "b", valign="t", wrap=False, pad=(4, 4, 0, 0))
    filas = [
        ("Producción", fm(o.plan_t), fm(o.real_t), o.var, None),
        ("Disponibilidad", pct(o.dfp), pct(o.df), o.df / o.dfp - 1, o.d_df),
        ("UEBD", pct(o.uep), pct(o.ue), o.ue / o.uep - 1, o.d_ue),
        ("Rendimiento", fm(o.rrp), fm(o.rr), o.rr / o.rrp - 1, o.d_rr),
        ("Horas nominales", fm(o.ptot["hn"]), fm(o.tot["hn"]), o.tot["hn"] / o.ptot["hn"] - 1, o.d_hn),
        ("OEE", pct(o.oee_p), pct(o.oee), o.oee / o.oee_p - 1, None),
    ]
    anchos = [272, 224, 224, 192, 304]
    k = 1248 / sum(anchos)
    anchos = [a * k for a in anchos]
    x0, y0, fh = 16, 504, 27
    c.caja(x0, y0, 1248, fh, fill=CIELO)
    xx = x0
    for j, t in enumerate(["Medición", "Plan CAEX", "Real CAEX", "Variación", "Pérdida/Ganancia CAEX (t)"]):
        tx.etiqueta(xx, y0, anchos[j], fh, t, 9, "#FFFFFF", "b", align="c", wrap=False, pad=(6, 6, 0, 0))
        xx += anchos[j]
    for i, (nom, p, r, v, d) in enumerate(filas):
        yy = y0 + fh * (i + 1)
        c.linea([(x0, yy + fh), (x0 + 1248, yy + fh)], PLATA, 1)
        vtxt = ("+" if v > 0 else "-") + fm(abs(v) * 100, 2) + "%"
        cv = PLOMO if abs(v) <= 0.001 else ROJO if v < 0 else VERDE
        celdas = [(nom, "l", MEDIANOCHE), (p, "r", MEDIANOCHE), (r, "r", MEDIANOCHE), (vtxt, "r", cv)]
        if d is not None:
            cd = PLOMO if abs(d) <= o.tol else ROJO if d < 0 else VERDE
            celdas.append((sgn(d), "r", cd))
        else:
            celdas.append(("", "r", MEDIANOCHE))
        xx = x0
        for j, (t, al, col) in enumerate(celdas):
            tx.etiqueta(xx, yy, anchos[j], fh, t, 10, col, "n", align=al, wrap=False, pad=(10, 10, 0, 0))
            xx += anchos[j]
    return guardar(c, "oee_transporte.png")


def kpis(o):
    """Texto del KPI de cada palanca: (real, plan en el encabezado, color, pérdida en toneladas)."""
    def plan_txt(plan, dif, t):
        col = ROJO_CLARO if t < -o.tol else VERDE_CLARO
        return plan + " · " + dif + " · " + sgn(t) + " t", col
    pp = lambda r, p: ("+" if r - p > 0 else "-") + fm(abs(r - p) * 100, 1) + " pp"  # noqa: E731
    d = {}
    d["df"] = (pct(o.df), *plan_txt("Plan " + pct(o.dfp), pp(o.df, o.dfp), o.d_df))
    d["uebd"] = (pct(o.ue), *plan_txt("Plan " + pct(o.uep), pp(o.ue, o.uep), o.d_ue))
    d["rend"] = (fm(o.rr) + " t/h", *plan_txt("Plan " + fm(o.rrp) + " t/h", sgn(o.rr - o.rrp) + " t/h", o.d_rr))
    d["hn"] = (fm(o.tot["hn"]) + " h", *plan_txt("Plan " + fm(o.ptot["hn"]) + " h", sgn(o.tot["hn"] - o.ptot["hn"]) + " h", o.d_hn))
    return d


IZQ, DER, AW = 16, 648, 616
FILA1, FILA2, H1, H2 = 106, 404, 290, 308


def por_equipo(o, clave, ascendente=True):
    ids = sorted(o.eq)
    vals = {e: clave(o.eq[e]) for e in ids if o.eq[e]["hn"] >= 12}
    orden = sorted(vals, key=lambda e: (vals[e], e), reverse=not ascendente)
    return orden, [vals[e] for e in orden]


def pagina_df(o):
    c, tx = nuevo_informe()
    k = kpis(o)["df"]
    cabecera_detalle(c, tx, o, "DISPONIBILIDAD CAEX", "Disponibilidad física CAEX", k[0], k[1], k[2])
    real, plan = o.s_dia("df")
    combo(c, tx, IZQ, FILA1, AW, H1, "Disponibilidad por día", real, plan, [semaforo(r, p) for r, p in zip(real, plan)],
          lambda v: pct(v, 1), o)
    cats, vals = por_equipo(o, lambda e: e["hd"] / e["hn"])
    barras_h(c, tx, IZQ, FILA2, AW, H2, "Disponibilidad por CAEX", cats, vals, [semaforo(v, o.dfp) for v in vals],
             lambda v: pct(v, 1), vmax=1.0)
    tot = sorted(((cod, h) for cod, h in o.cod.items() if o.cod_cat[cod] in CAT_NO_DISP), key=lambda kv: -kv[1])
    tabla(c, tx, DER, FILA1, AW, H1, "Horas no disponibles por código", ["Código", "Categoría", "Horas", "% del nominal"],
          [(cd, o.cod_cat[cd], fm(h, 1), pct(h / o.tot["hn"], 1)) for cd, h in tot], [255, 185, 66, 84], ["l", "l", "r", "r"])
    treemap(c, tx, DER, FILA2, AW, H2, "Horas no disponibles por código (mapa)", tot)
    return guardar(c, "disponibilidad.png")


def pagina_uebd(o):
    c, tx = nuevo_informe()
    k = kpis(o)["uebd"]
    cabecera_detalle(c, tx, o, "UTILIZACIÓN EFECTIVA (UEBD) CAEX", "UEBD CAEX", k[0], k[1], k[2])
    real, plan = o.s_dia("uebd")
    combo(c, tx, IZQ, FILA1, AW, H1, "UEBD por día", real, plan, [semaforo(r, p) for r, p in zip(real, plan)],
          lambda v: pct(v, 1), o)
    cats, vals = por_equipo(o, lambda e: e["he"] / e["hd"])
    barras_h(c, tx, IZQ, FILA2, AW, H2, "UEBD por CAEX", cats, vals, [semaforo(v, o.uep) for v in vals],
             lambda v: pct(v, 1), vmax=1.0)
    tot = sorted(((cd, h) for cd, h in o.cod.items() if o.cod_cat[cd] in CAT_NO_EFECTIVO), key=lambda kv: -kv[1])
    tabla(c, tx, DER, FILA1, AW, H1, "Horas de demora y reserva por código", ["Código", "Categoría", "Horas", "% del disponible"],
          [(cd, o.cod_cat[cd], fm(h, 1), pct(h / o.tot["hd"], 1)) for cd, h in tot], [290, 110, 76, 114], ["l", "l", "r", "r"])
    tipos = sorted(((n, o.tot["t_" + n]) for n, _ in TIPOS_UEBD), key=lambda kv: -kv[1])
    barras_h(c, tx, DER, FILA2, AW, H2, "Horas disponibles no efectivas por tipo", [n for n, _ in tipos], [v for _, v in tipos],
             [ROSA] * len(tipos), lambda v: fm(v), cada=1)
    return guardar(c, "uebd_caex.png")


def pagina_rend(o):
    c, tx = nuevo_informe()
    k = kpis(o)["rend"]
    cabecera_detalle(c, tx, o, "RENDIMIENTO EFECTIVO CAEX", "Rendimiento efectivo (t/h)", k[0], k[1], k[2])
    real, plan = o.s_dia("rend")
    combo(c, tx, IZQ, FILA1, AW, H1, "Rendimiento efectivo por día (t/h)", real, plan,
          [semaforo(r, p) for r, p in zip(real, plan)], lambda v: fm(v), o)
    cats, vals = por_equipo(o, lambda e: e["mov"] / e["he"])
    barras_h(c, tx, IZQ, FILA2, AW, H2, "Rendimiento efectivo por CAEX (t/h)", cats, vals, [semaforo(v, o.rrp) for v in vals],
             lambda v: fm(v))
    ids = sorted((e for e in o.eq if o.eq[e]["hn"] >= 12 and e in o.fc), key=lambda e: (o.fc[e], e))
    barras_h(c, tx, DER, FILA1, AW, H1, "Factor de carga por CAEX (t por carga)", ids, [o.fc[e] for e in ids],
             [semaforo(o.fc[e], o.fc_plan) for e in ids], lambda v: fm(v, 1))
    comp = sorted(((n, o.ciclo[col] / o.ciclo_n / 60) for n, col in COMPONENTES), key=lambda kv: -kv[1])
    barras_h(c, tx, DER, FILA2, AW, H2, "Tiempo de ciclo por componente (min por ciclo)", [n for n, _ in comp],
             [v for _, v in comp], [CIELO] * len(comp), lambda v: fm(v, 1), cada=1)
    return guardar(c, "rendimiento_efectivo.png")


def pagina_hn(o):
    c, tx = nuevo_informe()
    k = kpis(o)["hn"]
    cabecera_detalle(c, tx, o, "HORAS NOMINALES CAEX", "Horas nominales de la flota", k[0], k[1], k[2])
    real, plan = o.s_dia("hn")
    combo(c, tx, IZQ, FILA1, AW, H1, "CAEX en flota por día (horas nominales / 24)", real, plan,
          [semaforo(r, p) for r, p in zip(real, plan)], lambda v: fm(v, 1), o)
    cats, vals = por_equipo(o, lambda e: e["hn"])
    barras_h(c, tx, IZQ, FILA2, AW, H2, "Horas nominales por CAEX", cats, vals, [CIELO] * len(vals), lambda v: fm(v))
    ids, _ = por_equipo(o, lambda e: e["hn"])
    filas = [(e, fm(o.eq[e]["hn"] / 24, 1), fm(o.eq[e]["hn"]), fm(o.eq[e]["hd"]), fm(o.eq[e]["he"])) for e in ids]
    tabla(c, tx, DER, FILA1, AW, H1 + 8 + H2, "Horas por CAEX en el periodo",
          ["CAEX", "Días en flota", "Horas nominales", "Horas disponibles", "Horas efectivas"], filas,
          [120, 110, 130, 120, 110], ["l", "r", "r", "r", "r"], fila_h=21, resto_pie=24)
    return guardar(c, "horas_nominales.png")


PAGINAS = {"oee_transporte": pagina_oee, "disponibilidad": pagina_df, "uebd_caex": pagina_uebd,
           "rendimiento_efectivo": pagina_rend, "horas_nominales": pagina_hn}


def main(args):
    SALIDA.mkdir(parents=True, exist_ok=True)
    todo = dict(PAGINAS)
    todo.update(APP)
    pedidas = args or list(todo)
    o = None
    for nombre in pedidas:
        f = todo[nombre]
        if nombre in PAGINAS:
            o = o or Oee()
            f(o)
        else:
            f()


# ---------------------------------------------------------------------------------------------------------------------
# App «RD Terreno» (lienzo 1024 × 640: las notas de gen_visor.py y gen_editor.py dimensionan todo «a 1024 px»)
# Colores de App_Formulas.fx: colPrimario, colPrimarioClaro, colFondo, colTexto, colVerde, colAmbar, colRojo
# ---------------------------------------------------------------------------------------------------------------------
PRIM, PRIM_CLARO, FONDO, TEXTO = "#1B2A41", "#DFE5EE", "#F5F6F8", "#212529"
APP_VERDE, APP_AMBAR, APP_ROJO, APP_AZUL, GRIS = "#2E7D32", "#ED6C02", "#C62828", "#4F9DDE", "#5A6268"
BLANCO = "#FFFFFF"
BLANCO_14, BLANCO_15 = (255, 255, 255, 36), (255, 255, 255, 38)
CLARO_HDR = "#C8D3E3"
W_APP, H_APP = 1024, 640
HOY = date(2025, 6, 2)  # lunes de reunión: el día siguiente a la última marca de datos (Dim_Actualizacion)


class Reunion:
    """Datos de la app para la reunión del lunes 2 de junio: compromisos abiertos, preparación guardada y tiempos."""

    def __init__(self):
        a = DATOS / "app"
        self.clave = HOY.isoformat()
        self.fila = next(r for r in leer(a / "RD_Preparacion.csv") if r["Clave"] == self.clave)
        self.prep = json.loads(self.fila["Json"])
        self.abiertos = [r for r in leer(a / "RD_Compromisos.csv") if r["Abierto"] == "Sí"]
        est = {e["id"]: e for e in self.prep.get("est", [])}
        self.rev = []
        for r in self.abiertos:
            est0 = "Atrasado" if r["Estado"] == "Bloqueado" else r["Estado"]
            e = est.get(int(r["ID"]), {})
            self.rev.append({"titulo": r["Titulo"], "resp": r["ResponsableNombre"], "fecha": date.fromisoformat(r["FechaLimite"]),
                             "estado": e.get("estado") or est0, "com": e.get("com", ""), "url": e.get("url", "")})
        self.nuevos = [{"titulo": n["t"], "resp": n["r"], "fecha": date.fromisoformat(n["f"]), "estado": "En progreso",
                        "com": "", "url": ""} for n in self.prep.get("nue", [])]
        self.avisos = sorted(self.prep["avi"], key=lambda a: a["o"])
        self.ind = self.prep["ind"]
        self.part = [r for r in leer(a / "RD_Participantes.csv") if r["Activo"].strip().lower() in ("sí", "si") and r["Correo"].strip()]
        ses = leer(a / "RD_Sesiones.csv")[-1]
        self.tiempos = {t["Bloque"]: t["Seg"] for t in json.loads(ses["TiemposBloques"])}
        self.autor = self.fila["Autor"]
        self.actualizado = self.fila["Actualizado"]            # «aaaa-mm-dd hh:mm»
        self.guardado = f"{self.actualizado[8:10]}-{self.actualizado[5:7]} {self.actualizado[11:16]}"
        # Bloques de la agenda (tblBloques de App_Formulas.fx)
        self.bloques = [(1, "Seguridad", 5), (2, "Compromisos", 10), (3, "Indicadores", 20), (4, "Cierre", 5)]
        self.minutos = sum(m for _, _, m in self.bloques)

    def estado_de(self, e):
        return e if e in ("Cumplido", "Atrasado") else "En progreso"


def nuevo_app():
    c = Lienzo(W_APP, H_APP, FONDO)
    c.color_leyenda = "#82898E"
    return c, Tx(c)


def mmss(s):
    return f"{int(s // 60)}:{int(s % 60):02d}"


def logos_app(c, x_logo, w_logo, x_icono):
    pegar_fit(c, LOGO_BLANCO, x_logo, 8, w_logo, 56)
    pegar_fit(c, ICONO, x_icono, 14, 44, 44)


def cabecera_reunion(c, tx, r, modo):
    """Cabecera de 72 px del visor (modo 'visor') y del editor (modo 'editor')."""
    c.caja(0, 0, W_APP, 72, fill=PRIM)
    logos_app(c, 12, 120, 138)
    if modo == "visor":
        tx.etiqueta(190, 6, 234, 44, "RD Minera Demo · " + f"{HOY:%d-%m}", 13, BLANCO, "b", wrap=False)
        tx.etiqueta(190, 46, 242, 20, "Preparación guardada " + r.guardado, 11, CLARO_HDR)
        s1 = sum(r.tiempos.get(k, 0) for k in (0, 1)) + r.seg_actual
        boton(tx, 432, 13, 190, 46, f"{mmss(s1)} / {r.minutos}:00", 18, BLANCO, BLANCO_14, "b", r=23)
        quedan = 600 - r.seg_actual
        boton(tx, 630, 13, 224, 46, "Compromisos: quedan " + mmss(quedan), 12, BLANCO, BLANCO_14, "s", r=23)
        boton(tx, 862, 12, 150, 48, "Finalizar", 14, BLANCO, APP_AMBAR, "b", r=8)
    else:
        tx.etiqueta(190, 8, 310, 36, "RD Minera Demo · " + f"{DIAS[HOY.weekday()]} {HOY:%d-%m}", 15, BLANCO, "b", wrap=False)
        tx.etiqueta(190, 44, 300, 22, "✔ Guardado " + r.guardado, 12, "#A5D6A7", "s", wrap=False)
        tx.etiqueta(506, 4, 172, 64, "Modo editor: lo que prepares se muestra en la reunión (visor).", 11, CLARO_HDR,
                    pad=(5, 5, 2, 2))
        boton(tx, 706, 12, 150, 48, "Guardar", 14, BLANCO, APP_AMBAR, "b", r=8)
        boton(tx, 864, 12, 148, 48, "← Inicio", 14, BLANCO, BLANCO_15, "b", r=8, borde=BLANCO)


def galeria(c, x, y, w, h, dibujar):
    """Galería: se dibuja en un lienzo propio de su tamaño (lo que se sale de la galería queda recortado)."""
    cap = Lienzo(int(w), int(h), BLANCO)
    dibujar(cap, Tx(cap))
    c.im.paste(cap.im, (round(x * c.ss), round(y * c.ss)))


def icono_cancelar(c, cx, cy, r=13, color="#969696"):
    c.elipse(cx, cy, r, borde=color, ancho=2)
    k = r * 0.42
    c.linea([(cx - k, cy - k), (cx + k, cy + k)], color, 2)
    c.linea([(cx - k, cy + k), (cx + k, cy - k)], color, 2)


def pantalla_visor():
    r = Reunion()
    r.seg_actual = round(r.tiempos[2] * 0.35)      # a mitad del bloque Compromisos
    c, tx = nuevo_app()
    cabecera_reunion(c, tx, r, "visor")
    # Barra izquierda: bloques de la reunión con su tiempo, «Siguiente» y «Salir sin cerrar»
    bloques = [(0, "Agenda", 0)] + r.bloques
    visitados = {0, 1}
    for i, (n, nombre, minutos) in enumerate(bloques):
        by = 88 + 6 + i * 64
        actual = n == 2
        fill = PRIM if actual else PRIM_CLARO if n in visitados else BLANCO
        txt = BLANCO if actual else PRIM
        boton(tx, 10, by, 260, 52, nombre if n == 0 else f"{n}. {nombre}", 13, txt, fill, "s", r=8, borde=PRIM, align="l", padl=12)
        usados = r.tiempos[n] if n in visitados else (r.seg_actual if actual else 0)
        pasado = minutos > 0 and usados > minutos * 60
        if minutos == 0:
            t = mmss(usados)
        elif usados == 0 and not actual:
            t = f"{minutos}'"
        else:
            t = f"{mmss(usados)}/{minutos}'"
        pf = APP_ROJO if pasado else BLANCO if actual else PRIM_CLARO
        boton(tx, 10 + 166, by + 13, 88, 26, t, 11, BLANCO if pasado else PRIM, pf, "b", r=13)
    boton(tx, 10, 424, 260, 56, "Siguiente ▶", 16, BLANCO, PRIM, "b", r=8)
    boton(tx, 10, 490, 260, 44, "← Salir sin cerrar", 14, PRIM, BLANCO, "n", r=8, borde=PRIM)

    # Bloque «Compromisos» (conB2Compromisos: X 284, Y 88, 728 × 536)
    cx, cy, cw, ch = 284, 88, W_APP - 296, H_APP - 104
    c.caja(cx, cy, cw, ch, fill=BLANCO, r=12)
    tx.etiqueta(cx + 20, cy + 10, cw - 40, 44, "Compromisos de la semana", 26, TEXTO, "b", wrap=False)
    todos = r.rev + r.nuevos
    n_atr = sum(1 for f in todos if f["estado"] == "Atrasado")
    n_cum = sum(1 for f in todos if f["estado"] == "Cumplido")
    n_pro = len(todos) - n_atr - n_cum
    n_nue = len(r.nuevos)
    pl = lambda n, s, p: f"{n} {s if n == 1 else p}"  # noqa: E731
    resumen = (pl(len(todos), "abierto", "abiertos") + " · ✔ " + pl(n_cum, "cumplido", "cumplidos") + " · ⚠ " +
               pl(n_atr, "atrasado", "atrasados") + f" · {n_pro} en progreso" +
               (f" ({pl(n_nue, 'nuevo de esta semana', 'nuevos de esta semana')})" if n_nue else ""))
    tx.etiqueta(cx + 20, cy + 52, cw - 40, 44, resumen, 12, GRIS, valign="t", wrap=False)
    filtros = [(f"Todos ({len(todos)})", PRIM, True), (f"✔ Cumplido ({n_cum})", APP_VERDE, False),
               (f"En progreso ({n_pro})", PRIM, False), (f"⚠ Atrasado ({n_atr})", APP_AMBAR, False)]
    for k, (t, col, sel) in enumerate(filtros):
        boton(tx, cx + 20 + k * 158, cy + 98, 150, 34, t, 12, BLANCO if sel else col, col if sel else BLANCO, "n", r=17, borde=col)
    # Galería de revisión: 3 filas completas y la cuarta asomando (altura 358, filas de 112)
    gx, gy, gw, gh = cx + 12, cy + 166, cw - 24, ch - 178
    rw = min(180, max(116, gw * 0.18))
    ax = gw - 248 - rw                                   # X de «Responsable»
    c.caja(gx, cy + 140, gw, 24, fill=PRIM_CLARO)
    tx.etiqueta(gx + 12, cy + 140, gw - 248 - rw - 20, 24, "Compromiso", 11, PRIM, "b", wrap=False)
    tx.etiqueta(gx + ax, cy + 140, rw - 8, 24, "Responsable", 11, PRIM, "b", wrap=False)
    tx.etiqueta(gx + gw - 248, cy + 140, 96, 24, "Fecha límite", 11, PRIM, "b", wrap=False)
    tx.etiqueta(gx + gw - 152, cy + 140, 140, 24, "Estado", 11, PRIM, "b", align="c", wrap=False)
    orden = {"Cumplido": 1, "Atrasado": 3}
    filas = sorted(todos, key=lambda f: orden.get(f["estado"], 2) * 100000 + (f["fecha"] - date(2020, 1, 1)).days)

    def dibujar(cap, t2):
        tw = gw
        for i, f in enumerate(filas):
            y0 = i * 112
            if y0 > gh:
                break
            ancho_t = tw - 248 - rw - 20
            tam = 12 if len(f["titulo"]) > int((ancho_t - 10) / 8.7) * 2.7 else 14
            t2.etiqueta(12, y0 + 4, ancho_t, 78, f["titulo"], tam, TEXTO, "s", valign="t", pad=(5, 5, 2, 2))
            t2.etiqueta(ax, y0 + 4, rw - 8, 78, f["resp"], 13, TEXTO, valign="t", pad=(5, 5, 2, 2))
            vencido = f["fecha"] < HOY
            t2.etiqueta(tw - 248, y0 + 4, 88, 30, f"{f['fecha']:%d-%m}", 14, APP_ROJO if vencido else TEXTO, "s", valign="t",
                        wrap=False, pad=(5, 5, 2, 2))
            if vencido:
                t2.etiqueta(tw - 248, y0 + 34, 88, 24, "VENCIDO", 11, APP_ROJO, "b", valign="t", wrap=False, pad=(5, 5, 0, 0))
            if f["com"]:
                t2.etiqueta(12, y0 + 82, tw - 152 - 20, 26, "Evidencia: " + f["com"], 12, APP_VERDE, wrap=False)
            col = {"Cumplido": APP_VERDE, "Atrasado": APP_AMBAR}.get(f["estado"], PRIM)
            txt = {"Cumplido": "✔ Cumplido", "Atrasado": "⚠ Atrasado"}.get(f["estado"], "En progreso")
            boton(t2, tw - 152, y0 + 10, 140, 38, txt, 13, BLANCO, col, "b", r=19)
            cap.caja(0, y0 + 111, tw, 1, fill="#E6E6E6")
    galeria(c, gx, gy, gw, gh, dibujar)
    return guardar(c, "app_visor.png")


def tarjeta_cifra(c, tx, x, y, w, titulo, filas):
    c.caja(x, y, w, 116, fill="#F4F6FB")
    tx.etiqueta(x, y + 2, w, 38, titulo, 11, PRIM, "b", valign="t", pad=(8, 8, 2, 2))
    for k, (rot, valor) in enumerate(filas):
        yy = y + 42 + k * 36
        tx.etiqueta(x + 8, yy, w - 96, 30, rot, 11, GRIS, wrap=False)
        c.caja(x + w - 84, yy, 76, 30, fill=BLANCO, borde="#858585", ancho=2)
        tx.etiqueta(x + w - 84, yy, 76, 30, str(valor), 13, "#333333", wrap=False)


def pantalla_editor():
    r = Reunion()
    c, tx = nuevo_app()
    cabecera_reunion(c, tx, r, "editor")
    # Barra izquierda
    for i, nombre in enumerate(["Seguridad", "Compromisos"]):
        sel = i == 0
        boton(tx, 16, 88 + 6 + i * 80, 234, 68, f"{i + 1}. {nombre}", 15, BLANCO if sel else PRIM, PRIM if sel else BLANCO, "s", r=8,
              borde=PRIM, align="l", padl=16)
    boton(tx, 16, 88 + 166 + 12, 234, 64, "Siguiente ▶", 16, BLANCO, PRIM, "b", r=8)
    boton(tx, 16, 88 + 166 + 12 + 64 + 12, 234, 40, f"Convocados ({len(r.part)})", 14, PRIM, BLANCO, "n", r=8, borde=PRIM)
    # Bloque «Seguridad» (conB1Ed)
    cx, cy, cw, ch = 272, 88, W_APP - 296, H_APP - 104
    c.caja(cx, cy, cw, ch, fill=BLANCO, r=12)
    tx.etiqueta(cx + 24, cy + 14, cw - 48, 44, "Seguridad", 24, TEXTO, "b", wrap=False)
    tx.etiqueta(cx + 24, cy + 56, cw - 48, 30, "Cifras de la semana (a mano) y avisos con su nivel. Toca el nivel para cambiarlo.", 12, GRIS,
                valign="t", pad=(5, 5, 2, 2))
    tw = (cw - 48 - 24) / 3
    i = r.ind
    datos = [("Incidentes", [("Semana", i["inc"]), ("Anterior", i["inca"])]),
             ("Hipo Hazard", [("Semana", i["rep"]), ("Meta", i["repm"])]),
             ("Inspecciones", [("Hechas", i["ire"]), ("Plan", i["ipl"])])]
    for k, (tit, filas) in enumerate(datos):
        tarjeta_cifra(c, tx, cx + 24 + k * (tw + 12), cy + 92, tw, tit, filas)
    tx.etiqueta(cx + 24, cy + 216, 200, 28, "Avisos", 14, TEXTO, "b", wrap=False)
    c.caja(cx + 24, cy + 248, cw - 48, 40, fill=BLANCO, borde="#858585", ancho=2)
    tx.etiqueta(cx + 24, cy + 248, cw - 48, 40, "Ej.: tronadura en Fase 2 a las 13:00; evacuación desde las 12:30", 14, "#8C8C8C", wrap=False)
    niveles = [("✖ Crítico", APP_ROJO), ("⚠ Precaución", APP_AMBAR), ("✔ Recordar", APP_VERDE)]
    for k, (t, col) in enumerate(niveles):
        sel = k == 1                                      # varNivelEd parte en «Precaución»
        boton(tx, cx + 24 + k * 128, cy + 296, 120, 36, t, 12, BLANCO if sel else col, col if sel else BLANCO, "b", r=8, borde=col)
    boton(tx, cx + cw - 24 - 170, cy + 296, 170, 36, "+ Agregar aviso", 13, "#A6A6A6", "#F4F4F4", "b", r=8)  # sin texto: deshabilitado
    # Galería de avisos (filas de 52): 3 completas y la cuarta asomando
    gx, gy, gw, gh = cx + 24, cy + 344, cw - 48, ch - 356

    def dibujar(cap, t2):
        for n, a in enumerate(r.avisos):
            y0 = n * 52
            if y0 > gh:
                break
            col = {"Crítico": APP_ROJO, "Precaución": APP_AMBAR, "Recordar": APP_VERDE}.get(a["n"], PRIM)
            txt = {"Crítico": "✖ Crítico", "Precaución": "⚠ Precaución", "Recordar": "✔ Recordar"}.get(a["n"], "Aviso")
            boton(t2, 0, y0 + 10, 120, 32, txt, 11, BLANCO, col, "b", r=16)
            t2.etiqueta(132, y0, gw - 132 - 48, 52, a["x"], 13, TEXTO, pad=(5, 5, 2, 2))
            icono_cancelar(cap, gw - 24, y0 + 26)
            cap.caja(0, y0 + 51, gw, 1, fill="#E1E6E8")
    galeria(c, gx, gy, gw, gh, dibujar)
    return guardar(c, "app_editor.png")


def pantalla_inicio():
    r = Reunion()
    c, tx = nuevo_app()
    c.caja(0, 0, W_APP, 72, fill=PRIM)
    logos_app(c, 16, 154, 172)  # el YAML da 170 px al logo y pone el ícono en X = 172: aquí se achica para que no se pisen
    tx.etiqueta(210, 0, W_APP - 420, 72, "RD Minera Demo", 20, BLANCO, "b", align="c", wrap=False)
    tx.etiqueta(W_APP - 196, 0, 180, 72, "● En línea", 14, "#A5D6A7", "s", align="r", wrap=False)
    tx.etiqueta(24, 92, W_APP - 48, 56, "Reunión semanal de supervisores · lunes", 16, TEXTO, "s", wrap=False)
    # Reunión de hoy
    x1, y1, w1, h1 = 24, 172, W_APP * 0.58, H_APP - 196
    sombra(c, x1, y1, w1, h1)
    c.caja(x1, y1, w1, h1, fill=BLANCO, r=12)
    tx.etiqueta(x1 + 24, y1 + 20, w1 - 48, 48, "Reunión de hoy · " + f"{DIAS[HOY.weekday()]} {HOY:%d-%m-%Y}", 22, TEXTO, "b", wrap=False)
    tx.etiqueta(x1 + 24, y1 + 72, w1 - 48, 40, "Pendiente", 16, APP_AMBAR, "s", wrap=False)
    bw_ = (w1 - 64) / 2
    boton(tx, x1 + 24, y1 + 132, bw_, 110, "Preparar reunión (editor)", 18, PRIM, BLANCO, "b", r=12, borde=PRIM, bw=2, wrap=True)
    boton(tx, x1 + 24 + bw_ + 16, y1 + 132, bw_, 110, f"Presentar reunión (visor) · {r.minutos} min", 18, BLANCO, PRIM, "b", r=12,
          wrap=True)
    tx.etiqueta(x1 + 24, y1 + 250, w1 - 48, 64, f"Preparación de la reunión del {DIAS[HOY.weekday()]} {HOY:%d-%m}: guardada el "
                f"{r.guardado} por {r.autor}", 13, APP_VERDE, "s", valign="t")
    tx.etiqueta(x1 + 24, y1 + 320, w1 - 48, 48, " → ".join(f"{b} {m}'" for _, b, m in r.bloques), 13, GRIS)
    tx.etiqueta(x1 + 24, y1 + h1 - 72, w1 - 48, 60, "Funciona sin señal: lo que registres queda guardado en este equipo y se sube solo "
                "al volver la conexión.", 12, GRIS, valign="t")
    # Situación de los compromisos
    x2, w2 = x1 + w1 + 24, W_APP - w1 - 72
    sombra(c, x2, y1, w2, h1)
    c.caja(x2, y1, w2, h1, fill=BLANCO, r=12)
    vencidos = sum(1 for f in r.rev if f["fecha"] < HOY)
    tx.etiqueta(x2 + 20, y1 + 16, w2 - 40, 40, "Situación de los compromisos", 16, TEXTO, "b", wrap=False)
    tx.etiqueta(x2 + 20, y1 + 64, w2 - 40, 36, f"Compromisos abiertos: {len(r.rev)}", 14, TEXTO, wrap=False)
    tx.etiqueta(x2 + 20, y1 + 100, w2 - 40, 36, f"Compromisos vencidos: {vencidos}", 14, APP_ROJO if vencidos else TEXTO, wrap=False)
    tx.etiqueta(x2 + 20, y1 + 136, w2 - 40, 36, "Registros por sincronizar: 0", 14, TEXTO, wrap=False)
    tx.etiqueta(x2 + 20, y1 + 176, w2 - 40, 52, "Datos actualizados: " + f"{HOY:%d-%m} 08:10", 12, GRIS, valign="t")
    bw2 = (w2 - 52) / 2
    boton(tx, x2 + 20, y1 + h1 - 72, bw2, 52, "Actualizar datos", 13, PRIM, BLANCO, "n", r=0, borde=PRIM, bw=2)
    boton(tx, x2 + 32 + bw2, y1 + h1 - 72, bw2, 52, "Sincronizar (0)", 13, "#A6A6A6", "#F4F4F4", "n", r=0)  # deshabilitado: 0 pendientes
    return guardar(c, "app_inicio.png")


APP = {"app_inicio": pantalla_inicio, "app_editor": pantalla_editor, "app_visor": pantalla_visor}

if __name__ == "__main__":
    main(sys.argv[1:])
