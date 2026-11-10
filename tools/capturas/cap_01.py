# -*- coding: utf-8 -*-
"""Renders del diseño del informe «Operaciones» (proyecto 01-powerbi-tmdl-gestion-minera).

Genera capturas/mina.png y capturas/molienda.png (1920x1080, como las páginas del informe PBIR). NO son capturas de
Power BI Desktop: son renders dibujados con Pillow que reproducen cada tarjeta SVG del modelo (medidas DAX «Rd SVG ...»)
con cifras calculadas sobre los CSV sintéticos de datos_sinteticos/.

    python tools/capturas/cap_01.py            # desde cualquier carpeta
"""
import csv
import math
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from lib_render import Lienzo, fmt, LOGO_BLANCO, ICONO  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

PROYECTO = AQUI.parents[1] / "01-powerbi-tmdl-gestion-minera"
DATOS = PROYECTO / "datos_sinteticos"
SALIDA = PROYECTO / "capturas"
LEYENDA = "Render del diseño · datos sintéticos · Minera Demo"

# Día de reporte: un día cerrado dentro del periodo sintético (2025-03-03 + 90 días). Día de mina 08:00 -> 08:00;
# día de planta 07:00 -> 07:00 (ambos cerrados: el cierre oficial de planta ya está publicado).
FECHA = date(2025, 5, 23)

# ---- paleta del informe (valores literales de las medidas SVG y de los visuales PBIR) ----------------------------
PAGINA = "#1B2A41"
TARJETA = "#222931"
BORDE = "#343F4D"
SINOP = "#1B2127"
TITULO = "#9AA5B1"
TEXTO = "#E6E6E6"
BLANCO = "#FFFFFF"
ROTULO = "#7F8C99"
VERDE = "#2ECC71"
ROJO = "#E74C3C"
AMBAR = "#F1C40F"
AZUL = "#4F9DDE"
AZUL_CLARO = "#8EC3EE"
META_REL = "#3F464D"
META_BOR = "#4A545E"
SIN_DATO = "#5D6B7A"
REJILLA = "#2E3844"
ACERO = "#8FA3B8"


# =====================================================================================================================
#   DATOS (todo sale de datos_sinteticos/, con la misma lógica que las medidas DAX del modelo)
# =====================================================================================================================
def leer(nombre):
    with open(DATOS / nombre, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def ts(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def prefijo_tronadura(blast):
    return "STO" if blast[:3] in ("STO", "STK") else blast[:3]


class Mina:
    """Magnitudes de la página Mina para un día de mina cerrado (08:00 a 08:00)."""

    def __init__(self, d):
        self.d = d
        iso = d.isoformat()
        ini_mes = d.replace(day=1).isoformat()
        pm = leer("produccion_mina.csv")
        self.mov = self.ext = self.rem = 0.0
        self.dest = {"CHA": 0.0, "DL_": 0.0, "BOT": 0.0, "STO": 0.0}
        self.fase = {"F01": 0.0, "F02": 0.0, "F03": 0.0}
        self.mov_mes = 0.0
        for r in pm:
            t = float(r["material_tonnage"])
            if ini_mes <= r["time"] <= iso:
                self.mov_mes += t
            if r["time"] != iso:
                continue
            self.mov += t
            if prefijo_tronadura(r["blast"]) == "STO":
                self.rem += t
            else:
                self.ext += t
            k = r["dump"][:3]
            self.dest["STO" if k == "STK" else k] += t
            if r["blast"][:3] in self.fase:
                self.fase[r["blast"][:3]] += t
        planes = leer("planes_mina.csv")
        self.sem = {r["property_name"]: float(r["value"]) for r in planes if r["plan_type"] == "Semanal" and r["start_date"] == iso}
        self.men_dia = {r["start_date"]: float(r["value"]) for r in planes
                        if r["plan_type"] == "Mensual" and r["property_name"] == "Total Toneladas"}
        s = self.sem
        self.plan_mov = s["Total Toneladas SEM"]
        self.plan_ext = (s["Total Toneladas Chancado SEM"] + s["Total Toneladas Dump SEM"]
                         + s["Total Toneladas Esteril SEM"] + s["Total Toneladas Stock Sulfuro SEM"])
        self.plan_rem = s["Total Toneladas Chancador SEM"] - s["Total Toneladas Chancado SEM"]
        self.plan_dest = {"CHA": s["Total Toneladas Chancador SEM"], "DL_": s["Total Toneladas Dump SEM"],
                          "BOT": s["Total Toneladas Esteril SEM"], "STO": s["Total Toneladas Stock Sulfuro SEM"]}
        self.plan_fase = {r["Clave"]: float(r["Toneladas"]) for r in leer("planta_plan_fase.csv") if r["Fecha"] == iso}
        # plan mensual a la fecha: días previos del mes + el día de reporte completo (24 h transcurridas)
        previos = sum(v for k, v in self.men_dia.items() if ini_mes <= k < iso)
        self.plan_mes = previos + self.men_dia[iso]
        # horas CAEX
        hc = [r for r in leer("horas_caex.csv") if r["time"] == iso][0]
        self.hc = {k: float(hc[k]) for k in ("Nominal", "HD", "Efectivo")}
        # carguío: horas por equipo y turno, y toneladas cargadas del día
        hp = [r for r in leer("horas_palas_turno.csv") if r["time"] == iso]
        self.hp = {k: sum(float(r[k]) for r in hp) for k in ("Nominal", "MP", "MNP", "Efectivo")}
        self.mov_palas = sum(float(r["material_tonnage"]) for r in leer("produccion_palas_turno.csv") if r["time"] == iso)
        # alimentación a chancado por pala y hora de reloj (08..07)
        self.horas = []
        pal = {}
        for r in leer("produccion_palas_hora.csv"):
            if r["time"] != iso or r["dump"] != "CHANCADO":
                continue
            hop = int(r["hour"]) + 1 + (0 if r["shift"] == "A" else 12)
            pal.setdefault(hop, {})
            pal[hop][r["shovel"]] = pal[hop].get(r["shovel"], 0.0) + float(r["material_tonnage"])
        for hop in sorted(pal):
            self.horas.append(("%02d" % ((hop + 7) % 24), pal[hop]))

    # ---- cascadas plan semanal -> real (medidas Rd SVG Cascada CAEX / Carguío) --------------------------------------
    def cascada_caex(self):
        s, h = self.sem, self.hc
        nom_p, hd_p, ef_p = s["Horas Nominales CAEX SEM"], s["Horas Disponibles CAEX SEM"], s["Horas Efectivas CAEX SEM"]
        df_p, ue_p = hd_p / nom_p, ef_p / hd_p
        ren_p = self.plan_mov / ef_p
        df, ue = h["HD"] / h["Nominal"], h["Efectivo"] / h["HD"]
        ren = self.mov / h["Efectivo"]
        p0 = nom_p * df_p * ue_p * ren_p
        d1 = df * ue_p * ren_p * nom_p - df_p * ue_p * ren_p * nom_p
        d2 = df * ue * ren_p * nom_p - df * ue_p * ren_p * nom_p
        d3 = df * ue * ren * nom_p - df * ue * ren_p * nom_p
        d4 = df * ue * ren * h["Nominal"] - df * ue * ren * nom_p
        tabla = dict(real=(df, ue, ren, h["Nominal"], self.mov), plan=(df_p, ue_p, ren_p, nom_p, p0))
        return p0, (d1, d2, d3, d4), self.mov, tabla

    def cascada_carguio(self):
        s, h = self.sem, self.hp
        pal = ("Cargador CARG-01", "Cargador CARG-02", "Pala PALA-01", "Pala PALA-02", "Pala PALA-03")
        nom_p = sum(s["Horas Nominales %s SEM" % p] for p in pal)
        hd_p = sum(s["Horas Disponibles %s SEM" % p] for p in pal)
        ef_p = sum(s["Horas Efectivas %s SEM" % p] for p in pal)
        p0 = self.cascada_caex()[0]
        pd_, pu, pr = hd_p / nom_p, ef_p / hd_p, p0 / ef_p
        hd = h["Nominal"] - h["MNP"] - h["MP"]
        rd_, ru, rt = hd / h["Nominal"], h["Efectivo"] / hd, self.mov_palas / h["Efectivo"]
        d1 = rd_ * pu * pr * nom_p - pd_ * pu * pr * nom_p
        d2 = rd_ * ru * pr * nom_p - rd_ * pu * pr * nom_p
        d3 = rd_ * ru * rt * nom_p - rd_ * ru * pr * nom_p
        d4 = rd_ * ru * rt * h["Nominal"] - rd_ * ru * rt * nom_p
        tabla = dict(real=(rd_, ru, rt, h["Nominal"], self.mov_palas), plan=(pd_, pu, pr, nom_p, p0))
        return p0, (d1, d2, d3, d4), self.mov_palas, tabla


class Planta:
    """Magnitudes de la página Molienda para un día de planta cerrado (07:00 a 07:00)."""

    TAGS_EST = ["EST.CHANC.01", "EST.ALIM.01", "EST.ALIM.02", "EST.ALIM.03", "EST.ALIM.04", "EST.ALIM.05", "EST.ALIM.06",
                "EST.SAG.01", "EST.PEBBLES.01", "EST.PEBBLES.02", "EST.PEBBLES.03", "EST.BOLAS.01", "EST.BOLAS.02"]

    def __init__(self, d):
        self.d = d
        iso = d.isoformat()
        self.ini = datetime.combine(d, time(7, 0))
        self.fin = self.ini + timedelta(days=1)
        self.horas = 24.0
        K = {}
        for r in leer("hist_kpi.csv"):
            if r["numeric_value"] != "":
                K.setdefault(r["nombre_tag"], []).append((ts(r["timestamp"]), float(r["numeric_value"])))
        self.K = K
        ini, fin, eps = self.ini, self.fin, timedelta(seconds=9)
        un_h, c01 = timedelta(hours=1), timedelta(days=0.01)

        def ventana(tag, lo, hi):
            return [(t, v) for t, v in K[tag] if lo + eps < t <= hi + eps]

        def ultimo(tag, lo, hi):
            w = ventana(tag, lo, hi)
            return w[-1][1] if w else None

        def prom(vs):
            vs = list(vs)
            return sum(vs) / len(vs) if vs else None

        # estados on/off al cierre de la ventana (1 operando, 0 detenido, 2 sin señal)
        sen = {}
        for r in leer("hist_senales.csv"):
            if r["dim_variable.tipo_variable"] == "OnOff":
                sen.setdefault(r["dim_variable.name"], []).append((ts(r["timestamp"]), int(r["estado"])))
        est = []
        for tag in self.TAGS_EST:
            w = [(t, e) for t, e in sen.get(tag, []) if ini + eps < t <= fin + eps]
            if not w or fin - w[-1][0] > timedelta(hours=1, seconds=9):
                est.append(2)
            else:
                est.append(1 if w[-1][1] == 1 else 0)
        self.est = est
        # válvulas abiertas por batería al cierre
        self.valvulas = []
        cont = {}
        for r in leer("hist_senales.csv"):
            if r["dim_variable.tipo_variable"] == "Contador":
                cont.setdefault(r["dim_variable.name"], []).append((ts(r["timestamp"]), float(r["numeric_value"])))
        for n in range(1, 5):
            w = [(t, v) for t, v in cont.get("CIC.VALVULAS_ABIERTAS.%02d" % n, []) if ini + eps < t <= fin + eps]
            self.valvulas.append(int(w[-1][1]) if w else None)
        # planes semanales del día
        planes = {r["property_name"]: float(r["value"]) for r in leer("planes_mina.csv")
                  if r["plan_type"] == "Semanal" and r["start_date"] == iso}
        self.plan_chancado_dia = planes["Total Toneladas Chancador SEM"]
        # chancado: acumulado/proyectado del día (señal desfasada +1 h respecto de la ventana de planta)
        self.ton_chancado = ultimo("CHANC.ALIM.PROY_DIA", ini + un_h, fin + un_h - c01)
        # SAG: cierre oficial publicado (planta_cierre / planta_cierre_ejec)
        cierre = {r["Punto"]: float(r["Valor"]) for r in leer("planta_cierre.csv") if r["Fecha"] == iso}
        ejec = {r["Punto"]: float(r["Valor"]) for r in leer("planta_cierre_ejec.csv") if r["Fecha"] == iso}
        self.cierre_oficial = cierre.get("PLANTA.CIERRE.OFICIAL", 0) > 0
        t_sag = cierre.get("PLANTA.SAG.TON_DIA")
        h0 = ejec.get("PLANTA.SAG.HORAS_EF", 0)
        h_ef = h0 * 24 if (h0 > 0 and h0 <= 25 / 24 and t_sag and t_sag / h0 > 10000) else h0
        tph_c = t_sag / h_ef if t_sag and h_ef else None
        o = ejec.get("PLANTA.SAG.TPH_EF", 0)
        tph_ofi = o if (o > 0 and (tph_c is None or abs(o / tph_c - 1) <= 0.02)) else tph_c
        self.sag_ton = t_sag
        sq = prom(v for t, v in ventana("SAG.ALIM.TPH", ini, fin) if v > 100)
        self.sag_tph = tph_ofi if (self.cierre_oficial and tph_ofi and tph_ofi > 0) else sq
        self.sag_tph_plan = ultimo("PLAN.SAG.TPH_SEM", ini, fin - c01)
        self.sag_ton_plan = ultimo("PLAN.SAG.TON_DIA", ini, fin - c01)
        # mediciones del historiador
        self.spi = prom(v for t, v in ventana("SAG.DUREZA.SPI", ini, fin))
        self.spi_plan = next((float(r["Valor"]) for r in leer("planta_plan_spi.csv") if r["Fecha"] == iso), None)
        self.finos = None
        sag_t = dict(K["SAG.ALIM.TPH"])
        fi = [v for t, v in ventana("SAG.CORREA.FINOS_PCT", ini, fin) if sag_t.get(t, 0) > 1000]
        self.finos = prom(fi)
        op = {t for t, v in ventana("SAG.ALIM.TPH", ini, fin) if v > 100}
        self.pebble_tph = prom(v for t, v in ventana("PEBBLES.RETORNO.TPH", ini, fin) if t in op)
        self.pebble_plan = self.sag_tph_plan * 0.20 if self.sag_tph_plan else None
        self.pebble_serie = ventana("PEBBLES.RETORNO.TPH", ini, fin)
        self.pebble_ton = sum(max(v, 0) for t, v in self.pebble_serie) * 0.5
        self.p80 = prom(v for t, v in ventana("CICLONES.P80.UM", ini, fin))
        self.p80_serie = ventana("CICLONES.P80.UM", ini, fin)
        self.p80_plan = next((float(r["Valor"]) for r in leer("planta_plan_puntos.csv")
                              if r["Punto"] == "PLANTA.P80.PLAN" and r["Fecha"] == iso), None)
        self.nivel_serie = ventana("STOCK.NIVEL.PCT", ini, fin)
        self.nivel = self.nivel_serie[-1][1] if self.nivel_serie else None
        v0 = ultimo("STOCK.NIVEL.PCT", ini - timedelta(hours=12), ini)
        self.nivel_ini = v0
        self.tendencia = (self.nivel - v0) if (self.nivel is not None and v0 is not None) else None
        self.nivel_plan = 75
        # potencia de molinos y consumo específico del SAG
        pot = {}
        for r in leer("hist_potencia.csv"):
            pot.setdefault(r["nombre_tag"], []).append((ts(r["timestamp"]), float(r["numeric_value"])))
        self.bolas = [[(t, v) for t, v in pot["BOLAS.0%d.KW" % n] if ini + eps < t <= fin + eps] for n in (1, 2)]
        self.bolas_prom = [prom(v for t, v in s if v > 5000) for s in self.bolas]
        kw = [(t, v) for t, v in pot["SAG.MOTOR.KW"] if ini + eps < t <= fin + eps]
        num = den = 0.0
        for t, v in kw:
            tph = sag_t.get(t)
            if tph is not None and tph > 100 and v > 0:
                num += v
                den += tph
        self.kwh_t = num / den if den else None
        # DF y UE del día (promedio por área) y de los ciclones
        self.df, self.ue = {}, {}
        for r in leer("equipos_df_ue.csv"):
            if r["Fecha"] == iso:
                (self.df if r["Medicion"] == "DF" else self.ue)[r["Nombre"]] = float(r["Valor"])
        cic = {"DF": [], "UE": []}
        for r in leer("equipos_ciclones.csv"):
            if r["Fecha"] == iso:
                cic[r["Medicion"]].append(float(r["Valor"]))
        self.cic_df = prom(cic["DF"])
        self.cic_ue = prom(cic["UE"])


# =====================================================================================================================
#   DIBUJO: primitivas que imitan el SVG de las medidas (coordenadas del viewBox -> píxeles de la página)
# =====================================================================================================================
_RUTAS = {"r": ["segoeui.ttf", "arial.ttf"], "sb": ["seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"],
          "b": ["segoeuib.ttf", "arialbd.ttf"], "l": ["segoeuil.ttf", "segoeui.ttf"]}
_fuentes = {}


def fuente(px, w="r"):
    k = (max(1, int(round(px))), w)
    if k not in _fuentes:
        for nombre in _RUTAS[w]:
            try:
                _fuentes[k] = ImageFont.truetype(nombre, k[0])
                break
            except OSError:
                continue
        else:
            _fuentes[k] = ImageFont.load_default()
    return _fuentes[k]


def col(h, a=1.0):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(round(a * 255))


def n(v, dec=0):
    """Número con coma decimal y punto de miles (cultura es-ES del modelo), como FORMAT(x, "#,0.0")."""
    f = 10 ** dec
    v = math.copysign(math.floor(abs(v) * f + 0.5 + 1e-9) / f, v)  # redondeo comercial, como DAX
    return fmt(v, dec, ".")


def estado_color(e):
    return VERDE if e == 1 else (SIN_DATO if e == 2 else ROJO)


def estado_txt(e):
    return "OPERANDO" if e == 1 else ("SIN SEÑAL" if e == 2 else "DETENIDO")


def recortar_abajo(pts, y0):
    """Recorta un polígono dejando solo la parte con y >= y0 (equivale al clipPath del nivel del stockpile)."""
    out = []
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        ia, ib = a[1] >= y0, b[1] >= y0
        if ia:
            out.append(a)
        if ia != ib:
            t = (y0 - a[1]) / (b[1] - a[1])
            out.append((a[0] + t * (b[0] - a[0]), y0))
    return out


class Svg:
    """Dibuja con coordenadas de viewBox SVG: x_pagina = ox + k*x ; y_pagina = oy + k*(y + dy)."""

    def __init__(self, c, ox=0.0, oy=0.0, k=1.0, dy=0.0):
        self.c, self.ox, self.oy, self.k, self.dy, self.s = c, ox, oy, k, dy, c.ss

    def px(self, x, y):
        return (self.ox + self.k * x) * self.s, (self.oy + self.k * (y + self.dy)) * self.s

    def _w(self, sw):
        return max(1, int(round(sw * self.k * self.s)))

    def rect(self, x, y, w, h, fill=None, fo=1.0, stroke=None, sw=1.0, rx=0.0, so=1.0):
        d = self.c.d
        x0, y0 = self.px(x, y)
        x1, y1 = self.px(x + w, y + h)
        r = min(rx * self.k * self.s, (x1 - x0) / 2, (y1 - y0) / 2)
        if fill:
            d.rounded_rectangle([x0, y0, x1 - 1, y1 - 1], r, fill=col(fill, fo))
        if stroke:
            e = self._w(sw) / 2.0
            d.rounded_rectangle([x0 - e, y0 - e, x1 - 1 + e, y1 - 1 + e], r + e, outline=col(stroke, so), width=self._w(sw))

    def line(self, x1, y1, x2, y2, color, sw=1.0, dash=None, a=1.0):
        d = self.c.d
        if not dash:
            d.line([self.px(x1, y1), self.px(x2, y2)], fill=col(color, a), width=self._w(sw))
            return
        L = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        t, on = 0.0, True
        while t < L:
            seg = min(dash[0] if on else dash[1], L - t)
            if on:
                d.line([self.px(x1 + (x2 - x1) * t / L, y1 + (y2 - y1) * t / L),
                        self.px(x1 + (x2 - x1) * (t + seg) / L, y1 + (y2 - y1) * (t + seg) / L)],
                       fill=col(color, a), width=self._w(sw))
            t += seg
            on = not on

    def circle(self, cx, cy, r, fill):
        x0, y0 = self.px(cx - r, cy - r)
        x1, y1 = self.px(cx + r, cy + r)
        self.c.d.ellipse([x0, y0, x1, y1], fill=col(fill))

    def poly(self, pts, fill=None, fo=1.0, stroke=None, sw=1.0, so=1.0):
        P = [self.px(x, y) for x, y in pts]
        if fill:
            self.c.d.polygon(P, fill=col(fill, fo))
        if stroke:
            self.c.d.line(P + [P[0]], fill=col(stroke, so), width=self._w(sw), joint="curve")

    def polyline(self, pts, color, sw=1.0):
        self.c.d.line([self.px(x, y) for x, y in pts], fill=col(color), width=self._w(sw), joint="curve")

    def text(self, x, y, s, size, fill, w="r", anchor="start", sp=0.0, fo=1.0, halo=None, halo_w=3.0, halo_o=0.5):
        f = fuente(size * self.k * self.s, w)
        X, Y = self.px(x, y)
        s = str(s)
        extra = sp * self.k * self.s
        if extra:
            ancho = sum(f.getlength(ch) + extra for ch in s) - extra
            X -= {"start": 0, "middle": ancho / 2, "end": ancho}[anchor]
            for ch in s:
                self.c.d.text((X, Y), ch, font=f, fill=col(fill, fo), anchor="ls")
                X += f.getlength(ch) + extra
            return
        kw = {}
        if halo:
            kw = dict(stroke_width=max(1, int(round(halo_w / 2 * self.k * self.s))), stroke_fill=col(halo, halo_o))
        self.c.d.text((X, Y), s, font=f, fill=col(fill, fo), anchor={"start": "ls", "middle": "ms", "end": "rs"}[anchor], **kw)

    def runs(self, x, y, partes, anchor="start"):
        """Texto con tspans: partes = [(texto, tamaño, color, peso, dx)]."""
        fs = [fuente(p[1] * self.k * self.s, p[3]) for p in partes]
        ws = [p[4] * self.k * self.s + f.getlength(p[0]) for p, f in zip(partes, fs)]
        X, Y = self.px(x, y)
        X -= {"start": 0, "middle": sum(ws) / 2, "end": sum(ws)}[anchor]
        for p, f, w in zip(partes, fs, ws):
            self.c.d.text((X + p[4] * self.k * self.s, Y), p[0], font=f, fill=col(p[2]), anchor="ls")
            X += w

    def ancho(self, s, size, w="r"):
        return fuente(size * self.k * self.s, w).getlength(str(s)) / (self.k * self.s)


def texto_rot(c, x, y, s, size, color, w="r"):
    """Texto girado 90° (título del eje vertical), centrado en (x, y) de la página."""
    f = fuente(size * c.ss, w)
    tw, th = int(f.getlength(s)) + 8, int(size * c.ss * 1.7)
    im = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4, th // 2), s, font=f, fill=col(color), anchor="lm")
    im = im.rotate(90, expand=True)
    c.im.paste(im, (int(x * c.ss - im.width / 2), int(y * c.ss - im.height / 2)), im)


# =====================================================================================================================
#   DIBUJO: elementos comunes de página
# =====================================================================================================================
def contenedor(c, x, y, w, h, fill=TARJETA):
    c.caja(x, y, w, h, fill=fill, borde=BORDE, r=10)


def titulo_visual(S0, x, y, s):
    """Título del visual: 14 pt negrita #9AA5B1, alineado a la izquierda."""
    S0.text(x + 16, y + 31, s, 18.7, TITULO, "b")


def cabecera(c, S0, titulo, ventana, fecha):
    """Logo + título de la página + selector de día + leyenda de ventana + última actualización."""
    c.caja(24, 18, 1872, 78, fill=PAGINA, borde=AZUL, r=10)
    c.pegar(LOGO_BLANCO, 28, 24, w=239)  # en el informe el logo arranca en x=12; aquí se acomoda dentro del recuadro
    c.pegar(ICONO, 280, 19, w=76)
    S0.text(960, 71, titulo, 22.5, BLANCO, "b", "middle")
    # segmentador «Día Reporte» (lista desplegable de selección única)
    c.caja(1384, 24, 196, 40, fill=PAGINA, borde="#7F8C99", r=2)
    S0.text(1398, 50, fecha.strftime("%d-%m-%Y"), 17, BLANCO)
    S0.polyline([(1556, 41), (1563, 48), (1570, 41)], BLANCO, 1.6)
    S0.text(1482, 82, ventana, 13.3, BLANCO, "r", "middle")
    # Rd SVG Última Actualización (240x44) sobre el fondo de la página
    Su = Svg(c, 1615, 39)
    act = ts(leer("actualizacion.csv")[0]["Actualizado"])
    Su.text(120, 15, "ÚLTIMA ACTUALIZACIÓN", 12, TITULO, "b", "middle", sp=0.5)
    Su.text(120, 38, act.strftime("%d-%m-%Y · %H:%M"), 20, BLANCO, "b", "middle")


# =====================================================================================================================
#   PÁGINA MINA
# =====================================================================================================================
def bullet_grande(S, real, plan, tam_num, tam_uni, proy=None, curso=False):
    """Tarjeta bullet 326x118 (Rd SVG Movimiento / Ampliacion / Remanejo / Tarjeta Destino)."""
    proy = real if proy is None else proy
    hay = plan is not None and plan > 0
    tope = max(plan or 0, proy, real, 1)
    esc = 322.0 / tope
    w_plan = int(round((plan or 0) * esc)) if plan else 0
    w_real, w_proy = int(round(real * esc)), int(round(proy * esc))
    color = AZUL if not hay else (VERDE if proy >= plan else ROJO)
    num = n(real / 1000, 1)
    S.runs(2, 48, [(num, tam_num, BLANCO, "sb", 0), ("mil", tam_uni, TITULO, "r", 10)])
    if w_plan > 0:
        S.rect(2, 57, w_plan, 16, META_REL, stroke=META_BOR, sw=1, rx=4)
    if w_proy > w_real:
        S.rect(w_real + 2, 61, w_proy - w_real, 8, color, fo=0.55, rx=4)
    if w_real > 0:
        S.rect(2, 57, w_real, 16, color, rx=4)
    if w_plan > 0:
        S.line(w_plan + 2, 53, w_plan + 2, 77, TEXTO, 2)
    S.text(2, 94, "Real día", 15, ROTULO)
    S.text(2, 114, num + " mil", 18, TEXTO, "sb")
    S.text(163, 94, "Proy. día", 15, ROTULO, anchor="middle")
    S.text(163, 114, (n(proy / 1000, 1) + " mil") if curso else "—", 18, AZUL_CLARO if curso else SIN_DATO, "sb", "middle")
    S.text(324, 94, "Plan día", 15, ROTULO, anchor="end")
    S.text(324, 114, (n(plan / 1000, 1) + " mil") if hay else "Sin plan", 18, TEXTO, "sb", "end")


def tarjeta_acumulado(S, real, plan, ini, fin):
    """Rd SVG Plan Movimiento: acumulado del mes contra el plan mensual a la fecha."""
    rat = real / plan if plan else None
    c = SIN_DATO if rat is None else (VERDE if rat >= 1 else (AMBAR if rat >= 0.9 else ROJO))
    dec = 0 if max(real, plan) >= 1e6 else 1
    S.circle(8, 29, 6, c)
    S.text(22, 34, "Acumulado", 15, ROTULO)
    S.text(22, 51, "%s al %s" % (ini.strftime("%d-%m"), fin.strftime("%d-%m")), 12, ROTULO)
    S.runs(324, 50, [(n(real / 1000, dec), 46, BLANCO, "sb", 0), ("mil", 28, TITULO, "r", 10)], "end")
    S.line(2, 66, 324, 66, "#2E3844", 1)
    S.text(22, 93, "Plan mensual", 15, ROTULO)
    S.text(22, 110, "a la fecha", 12, ROTULO)
    S.runs(324, 109, [(n(plan / 1000, dec), 46, BLANCO, "sb", 0), ("mil", 28, TITULO, "r", 10)], "end")


def bullet_fase(S, real, proy, plan, tope, part):
    """Rd SVG Bullet Fase (290x26)."""
    esc = 226.0 / max(tope, 1)
    hay = plan is not None and plan > 0
    color = AZUL if not hay else (VERDE if proy >= plan else ROJO)
    w_plan = int(round(plan * esc)) if hay else 0
    w_real, w_proy = int(round(real * esc)), int(round(proy * esc))
    if w_plan > 0:
        S.rect(2, 5, w_plan, 16, META_REL, stroke=META_BOR, sw=1, rx=4)
    if w_proy > w_real:
        S.rect(w_real + 2, 9, w_proy - w_real, 8, color, fo=0.55, rx=4)
    if w_real > 0:
        S.rect(2, 5, w_real, 16, color, rx=4)
    else:
        S.text(6, 19, "Sin movimiento", 15, ROTULO)
    if w_plan > 0:
        S.line(w_plan + 2, 1, w_plan + 2, 25, TEXTO, 2)
    if real > 0:
        S.text(288, 19, "%d %%" % int(round(part * 100)), 15, TITULO, "sb", "end")


def cascada(S, p, ds, r, tabla):
    """Rd SVG Cascada CAEX / Carguío (512x454): plan semanal -> disponibilidad -> UEBD -> rendimiento -> horas -> real."""
    c = [p]
    for d in ds:
        c.append(c[-1] + d)
    hi = max(p, r, c[1], c[2], c[3], c[4], 0)
    lo = min(c[1], c[2], c[3], c[4], r, 0)
    rng = (hi - lo) or 1.0

    def Y(v):
        return int(round(324 - (v - lo) / rng * 278))

    def barra(x, a, b, color):
        ytop, ybot = Y(max(a, b)), Y(min(a, b))
        S.rect(x, ytop, 52, max(ybot - ytop, 2), color, rx=2)
        return ytop

    S.line(0, Y(0), 512, Y(0), "#343F4D", 1)
    xs = [17, 102, 187, 273, 358, 443]
    yt = barra(xs[0], max(p, 0), min(p, 0), ACERO)
    S.text(43, yt - 8, n(p / 1000) + "K", 15, BLANCO, "sb", "middle")
    for i, d in enumerate(ds):
        x = xs[i + 1]
        S.line(x - 33, Y(c[i]), x, Y(c[i]), SIN_DATO, 1, dash=(3, 3))
        colr = ROJO if d <= -500 else VERDE
        yt = barra(x, c[i], c[i + 1], colr)
        etq = "0K" if abs(d) < 500 else (("+" if d >= 0 else "−") + n(abs(d) / 1000) + "K")
        S.text(x + 26, yt - 8, etq, 15, colr, "sb", "middle")
    S.line(410, Y(c[4]), 443, Y(c[4]), SIN_DATO, 1, dash=(3, 3))
    yt = barra(xs[5], max(r, 0), min(r, 0), ACERO)
    S.text(469, yt - 8, n(r / 1000) + "K", 18, BLANCO, "b", "middle")
    for x, t in zip([43, 128, 213, 299, 384, 469], ["Plan sem.", "Disp.", "UEBD", "Rend.", "Hs nom.", "Real"]):
        S.text(x, 350, t, 14, TITULO, "r", "middle")
    # fragmento de tabla real / plan (Rd Frag Tabla CAEX / Carguío)
    S.line(0, 362, 512, 362, REJILLA, 1)
    S.line(0, 404, 512, 404, REJILLA, 1)
    S.text(43, 390, "Real", 14, TITULO, "sb", "middle")
    S.text(43, 430, "Plan", 14, TITULO, "sb", "middle")
    xv = [128, 213, 299, 384, 469]
    re_, pl_ = tabla["real"], tabla["plan"]
    fmts = [lambda v: n(v * 100, 1) + " %", lambda v: n(v * 100, 1) + " %", lambda v: n(v, 1), lambda v: n(v), lambda v: n(v)]
    fmts_p = [fmts[0], fmts[1], lambda v: n(v), fmts[3], fmts[4]]
    unid = ["", "", " t/h", " h", " t"]
    rnd = [3, 3, None, 0, 0]
    for i, x in enumerate(xv):
        a, b = re_[i], pl_[i]
        ra = round(a, 1) if i == 2 else round(a, rnd[i])
        rb = round(b, 0) if i == 2 else round(b, rnd[i])
        colr = VERDE if ra >= rb else (AMBAR if a >= 0.9 * b else ROJO)
        S.runs(x, 390, [(fmts[i](a), 17, colr, "sb", 0)] + ([(unid[i], 12, ROTULO, "r", 0)] if unid[i] else []), "middle")
        S.runs(x, 430, [(fmts_p[i](b), 16, TITULO, "sb", 0)] + ([(unid[i], 12, ROTULO, "r", 0)] if unid[i] else []), "middle")


COLORES_PALA = {"CARG-01": "#8FA3B8", "CARG-02": "#4F9DDE", "PALA-01": "#C26B8E", "PALA-02": "#B8C2CC", "PALA-03": "#A3B18A"}


def grafico_palas(c, S0, M, x, y, w, h):
    """Columnas apiladas por pala y hora de reloj (Rd Alim Hora): toneladas a chancado del día de mina."""
    titulo_visual(S0, x, y, "ALIMENTACIÓN POR PALA (HORA – HORA)")
    palas = ["CARG-01", "CARG-02", "PALA-01", "PALA-02", "PALA-03"]
    # leyenda arriba al centro
    tam = 16.0
    anchos = [S0.ancho(p, tam) + 22 for p in palas]
    lx = x + (w - (sum(anchos) + 14 * (len(palas) - 1))) / 2
    for p, a in zip(palas, anchos):
        S0.circle(lx + 5, y + 61, 5, COLORES_PALA[p])
        S0.text(lx + 17, y + 66, p, tam, TITULO)
        lx += a + 14
    izq, der, arr, aba = x + 84, x + w - 20, y + 96, y + h - 82
    totales = [sum(s.values()) for _, s in M.horas]
    tope = (int(max(totales) * 1.04 / 1000) + 1) * 1000
    paso = 1000
    for v in range(0, tope + 1, paso):
        yy = aba - (aba - arr) * v / tope
        S0.line(izq, yy, der, yy, REJILLA, 1)
        S0.text(izq - 10, yy + 5, "0" if v == 0 else "%d mil" % (v // 1000), 14.7, TITULO, "r", "end")
    texto_rot(c, x + 24, (arr + aba) / 2, "Toneladas a chancado (t)", 16, TITULO)
    paso_x = (der - izq) / len(M.horas)
    bw = paso_x * 0.88
    tot_xy = []
    for i, (hr, s) in enumerate(M.horas):
        bx = izq + i * paso_x + (paso_x - bw) / 2
        base = 0.0
        for p in palas:
            v = s.get(p, 0.0)
            if v <= 0:
                continue
            y1, y0 = aba - (aba - arr) * (base + v) / tope, aba - (aba - arr) * base / tope
            c.caja(bx, y1, bw, y0 - y1, fill=COLORES_PALA[p])
            base += v
        S0.text(bx + bw / 2, aba + 22, hr, 14.7, TITULO, "r", "middle")
        tot_xy.append((bx + bw / 2, aba - (aba - arr) * base / tope - 7, n(base / 1000, 1) + " mil"))
    # totales de columna (se omiten los que se pisarían, como hace Power BI)
    ult_der = -1e9
    for cx0, cy0, etq in tot_xy:
        ew = S0.ancho(etq, 13, "b")
        if cx0 - ew / 2 > ult_der + 6:
            S0.text(cx0, cy0, etq, 13, BLANCO, "b", "middle")
            ult_der = cx0 + ew / 2
    S0.text((izq + der) / 2, y + h - 18, "Hora (día mina 08:00 → 08:00)", 16, TITULO, "r", "middle")


def pagina_mina(M):
    c = Lienzo(1920, 1080, PAGINA, ss=2)
    S0 = Svg(c)
    d = M.d
    cabecera(c, S0, "PANEL DE OPERACIÓN MINA · MINERA DEMO",
             "%s 08:00 → %s 08:00 h" % (d.strftime("%d-%m"), (d + timedelta(days=1)).strftime("%d-%m")), d)
    # --- fila 1: movimiento, ampliación, remanejo, chancado, dump leach
    t1 = [(24, 112, 361, "MOVIMIENTO TOTAL · DÍA", M.mov, M.plan_mov, 52, 30),
          (401, 112, 361, "AMPLIACION", M.ext, M.plan_ext, 46, 28),
          (777, 112, 361, "REMANEJO", M.rem, M.plan_rem, 46, 28),
          (1154, 112, 363, "CHANCADO", M.dest["CHA"], M.plan_dest["CHA"], 46, 28),
          (1533, 112, 363, "DUMP LEACH", M.dest["DL_"], M.plan_dest["DL_"], 46, 28)]
    for x, y, w, t, real, plan, tn, tu in t1:
        contenedor(c, x, y, w, 190)
        titulo_visual(S0, x, y, t)
        bullet_grande(Svg(c, x + 14, y + 54), real, plan, tn, tu)
    # --- fila 2: acumulado mes, botadero, stock, indicadores por fase
    contenedor(c, 24, 318, 361, 190)
    titulo_visual(S0, 24, 318, "MOVIMIENTO ACUMULADO MES")
    tarjeta_acumulado(Svg(c, 38, 372), M.mov_mes, M.plan_mes, M.d.replace(day=1), M.d)
    for x, t, k in ((401, "BOTADERO", "BOT"), (777, "STOCK", "STO")):
        contenedor(c, x, 318, 361, 190)
        titulo_visual(S0, x, 318, t)
        bullet_grande(Svg(c, x + 14, 372), M.dest[k], M.plan_dest[k], 46, 28)
    # indicadores por fase
    fx, fy = 1154, 318
    contenedor(c, fx, fy, 742, 190)
    titulo_visual(S0, fx, fy, "INDICADORES POR FASE")
    cols = [(fx + 12, 90, "FASE", "l"), (fx + 102, 105, "REAL DÍA", "r"), (fx + 207, 105, "PROY. DÍA", "r"),
            (fx + 312, 105, "PLAN DÍA", "r"), (fx + 417, 300, "REAL / PROY. VS PLAN · % DEL MOV.", "l")]
    for x0, w0, t, al in cols:
        if al == "l":
            S0.text(x0 + 8, fy + 66, t, 12.5, ROTULO, "b")
        else:
            S0.text(x0 + w0 - 10, fy + 66, t, 12.5, ROTULO, "b", "end")
    tope = max(max(M.plan_fase[k], M.fase[k]) for k in M.fase)
    for i, k in enumerate(("F01", "F02", "F03")):
        ry = fy + 76 + i * 34
        S0.line(fx + 8, ry, fx + 734, ry, REJILLA, 1)
        S0.text(cols[0][0] + 8, ry + 23, "Fase %d" % (i + 1), 17.3, TEXTO)
        for (x0, w0, _, _), v in zip(cols[1:4], (M.fase[k], M.fase[k], M.plan_fase[k])):
            S0.text(x0 + w0 - 10, ry + 23, n(v), 17.3, TEXTO, "r", "end")
        bullet_fase(Svg(c, cols[4][0] + 4, ry + 4), M.fase[k], M.fase[k], M.plan_fase[k], tope, M.fase[k] / M.mov)
    # --- fila 3: cascadas CAEX y carguío, alimentación por pala
    for x, t, f in ((24, "FLOTA CAEX", M.cascada_caex), (589, "FLOTA CARGUÍO", M.cascada_carguio)):
        contenedor(c, x, 524, 549, 536)
        titulo_visual(S0, x, 524, t)
        p, ds, r, tabla = f()
        cascada(Svg(c, x + 18, 524 + 50), p, ds, r, tabla)
    contenedor(c, 1154, 524, 742, 536)
    grafico_palas(c, S0, M, 1154, 524, 742, 536)
    return c


# =====================================================================================================================
#   PÁGINA MOLIENDA
# =====================================================================================================================
def r0(v):
    """Redondeo comercial (como FORMAT(x, "0") de DAX)."""
    return int(math.floor(v + 0.5))


def sem_r(r):
    """Semáforo por razón real/plan: verde >= 100 %, ámbar >= 90 %, rojo bajo eso (blanco sin plan)."""
    return BLANCO if r is None else (VERDE if r >= 1 else (AMBAR if r >= 0.9 else ROJO))


def caja_sinop(S, y):
    S.rect(14, y, 228, 76, SINOP, stroke=BORDE, sw=1, rx=6)


def valor_plan(S, y, real, plan, unidad, color, dec=0):
    S.runs(128, y, [(n(real, dec), 27, color, "b", 0), (" / " + (n(plan, dec) if plan else "sin plan"), 21, ROTULO, "r", 0),
                    (" " + unidad, 15, ROTULO, "r", 0)], "middle")


def sinoptico_chancado(S, P):
    on = P.est[0]
    cico = estado_color(on)
    tph, plan = P.ton_chancado / 24, P.plan_chancado_dia / 24
    S.poly([(74, 40), (182, 40), (150, 150), (106, 150)], cico, 0.8, cico, 1.5)
    S.poly([(128, 52), (139, 138), (117, 138)], "#11161B", 0.35)
    caja_sinop(S, 188)
    valor_plan(S, 224, tph, plan, "TPH", sem_r(tph / plan))
    S.text(128, 250, estado_txt(on), 14, cico, "b", "middle", sp=0.5)


def sinoptico_stockpile(S, P):
    niv, plan = P.nivel, P.nivel_plan
    c = VERDE if r0(niv) >= plan else (AMBAR if r0(niv) >= 40 else ROJO)
    yl = 150 - 116 * min(max(niv, 0), 100) / 100
    yp = 150 - 116 * min(max(plan, 0), 100) / 100
    hw = (yp - 34) / 116 * 72
    tri = [(56, 150), (200, 150), (128, 34)]
    S.poly(tri, "#1F262E", 1.0, c, 1.5)
    S.poly(recortar_abajo(tri, yl), c, 0.8)
    S.line(128 - hw - 10, yp, 128 + hw + 10, yp, TEXTO, 1.5, dash=(4, 3))
    S.text(128 + hw + 14, yp + 4, "PLAN %d %%" % plan, 13, TEXTO, "b", sp=0.5)
    amar = c == AMBAR
    S.text(128, 119, "%d%%" % r0(niv), 22, "#11161B" if amar else BLANCO, "b", "middle",
           halo=None if amar else "#11161B", halo_w=3, halo_o=0.5)
    caja_sinop(S, 188)
    S.text(128, 206, "6 ALIMENTADORES", 13, ROTULO, "b", "middle", sp=0.5)
    for i in range(6):
        x0 = 23 + 36 * i
        cc = estado_color(P.est[1 + i])
        S.rect(x0, 213, 30, 44, SINOP, stroke=cc, sw=1.5, rx=4)
        S.text(x0 + 15, 231, "F%d" % (i + 1), 13, BLANCO, "b", "middle")
        S.circle(x0 + 15, 245, 5, cc)


def sinoptico_sag(S, P):
    on = P.est[7]
    cico = estado_color(on)
    S.rect(40, 46, 20, 32, cico, 0.55, cico, 1, 4)
    S.rect(196, 46, 20, 32, cico, 0.55, cico, 1, 4)
    S.rect(58, 28, 140, 68, cico, 0.8, cico, 1.5, 10)
    S.line(105, 30, 105, 94, "#11161B", 1, a=0.35)
    S.line(151, 30, 151, 94, "#11161B", 1, a=0.35)
    caja_sinop(S, 104)
    S.runs(128, 140, [(n(P.spi), 27, BLANCO, "b", 0), (" / " + n(P.spi_plan), 21, ROTULO, "r", 0), (" min", 15, ROTULO, "r", 0)], "middle")
    S.text(128, 166, "DUREZA SPI · PROM. DÍA", 14, TITULO, "b", "middle", sp=0.5)
    caja_sinop(S, 188)
    valor_plan(S, 224, P.sag_tph, P.sag_tph_plan, "TPH", sem_r(P.sag_tph / P.sag_tph_plan))
    S.text(128, 250, estado_txt(on), 14, cico, "b", "middle", sp=0.5)


def sinoptico_pebbles(S, P):
    for i in range(3):
        e = P.est[8 + i]
        cc = estado_color(e)
        y0 = 40 + 41 * i
        S.rect(14, y0, 228, 30, SINOP, stroke=BORDE, sw=1, rx=5)
        S.poly([(24, y0 + 6), (46, y0 + 6), (39, y0 + 24), (31, y0 + 24)], cc, 0.8, cc, 1)
        S.text(56, y0 + 20, "Chancador #%d" % (i + 1), 15, BLANCO, "b")
        S.text(232, y0 + 20, estado_txt(e), 13, cc, "b", "end", sp=0.5)
    caja_sinop(S, 188)
    valor_plan(S, 224, P.pebble_tph, P.pebble_plan, "TPH", sem_r(P.pebble_tph / P.pebble_plan))
    cc = P.pebble_tph / P.sag_tph
    S.text(128, 250, "CARGA CIRC. DÍA: " + n(cc * 100, 1) + "%", 14, TITULO, "b", "middle", sp=0.5)


def sinoptico_bolas(S, P):
    nm = sum(1 for e in P.est[11:13] if e == 1)
    nss = sum(1 for e in P.est[11:13] if e == 2)
    for i, nom in enumerate(("MB1", "MB2")):
        e = P.est[11 + i]
        cc = estado_color(e)
        y0 = 36 + 76 * i
        S.rect(26, y0 + 10, 12, 24, cc, 0.55, cc, 1, 3)
        S.rect(218, y0 + 10, 12, 24, cc, 0.55, cc, 1, 3)
        S.rect(38, y0, 180, 44, cc, 0.8, cc, 1.5, 7)
        S.text(128, y0 + 19, "MOLINO DE BOLAS #%d" % (i + 1), 14, "#11161B", "b", "middle")
        S.text(128, y0 + 36, "Disp. día: " + n(P.df[nom], 1) + " %", 14, "#11161B", "sb", "middle", fo=0.8)
        S.text(128, y0 + 61, estado_txt(e), 14, cc, "b", "middle", sp=0.5)
    caja_sinop(S, 188)
    S.text(128, 226, "%d / 2 OPERANDO" % nm, 27 if nss == 0 else 19, BLANCO, "b", "middle")
    S.text(128, 251, "UE día:  #1 %s %%  ·  #2 %s %%" % (n(P.ue["MB1"], 1), n(P.ue["MB2"], 1)), 13, TITULO, "b", "middle", sp=0.3)


def sinoptico_ciclones(S, P):
    m1, m2 = P.est[11], P.est[12]
    pos = [(40, 22, m1, 0), (152, 22, m1, 1), (40, 104, m2, 2), (152, 104, m2, 3)]
    for x0, y0, e, i in pos:
        cc = estado_color(e)
        S.rect(x0, y0, 64, 12, cc, 0.55, cc, 1, 3)
        S.poly([(x0, y0 + 12), (x0 + 64, y0 + 12), (x0 + 43, y0 + 50), (x0 + 21, y0 + 50)], cc, 0.8, cc, 1.5)
        S.rect(x0 + 25, y0 + 50, 14, 6, cc, 0.55, cc, 1, 1)
        v = P.valvulas[i]
        S.text(x0 + 32, y0 + 39, "–" if v is None else str(v), 20, "#11161B", "b", "middle")
        S.text(x0 + 32, y0 + 70, "B%d" % (i + 1), 13, TITULO, "b", "middle", sp=0.4)
    r = P.p80 / P.p80_plan
    creal = VERDE if r <= 1 else (AMBAR if r <= 1.05 else ROJO)
    nb = 2 * (m1 == 1) + 2 * (m2 == 1)
    nss = (m1 == 2) + (m2 == 2)
    caja_sinop(S, 188)
    S.text(128, 206, "P80 PROM. DÍA / PLAN", 13, ROTULO, "b", "middle", sp=0.5)
    S.runs(128, 234, [(n(P.p80), 27, creal, "b", 0), (" / " + n(P.p80_plan), 21, ROTULO, "r", 0), (" µm", 15, ROTULO, "r", 0)], "middle")
    cn = VERDE if nb == 4 else (AMBAR if nb > 0 else (SIN_DATO if nss > 0 else ROJO))
    S.text(128, 255, "%d / 4 BATERÍAS OPERANDO" % nb, 14, cn, "b", "middle", sp=0.5)


def estado_equipo(act, ss, df, ut):
    aten = (df is not None and df < 85) or (ut is not None and ut < 85)
    if not act:
        return ("SIN SEÑAL", SIN_DATO) if ss else ("DETENIDO", ROJO)
    return ("ATENCIÓN", AMBAR) if aten else ("OPERANDO", VERDE)


def caja_t(S, y, h):
    S.rect(1, y, 264, h, SINOP, stroke=BORDE, sw=1, rx=6)


def bloque_dfue(S, df, ut, est):
    """DF y UE del día con barras de 160 px + estado del equipo (parte baja de cada tarjeta de planta)."""
    caja_t(S, 278, 140)
    for y0, lbl, v in ((314, "DF", df), (348, "UE", ut)):
        cc = SIN_DATO if v is None else (VERDE if v >= 85 else (AMBAR if v >= 70 else ROJO))
        S.text(14, y0, lbl, 13, TITULO, "b")
        S.text(80, y0, "s/d" if v is None else "%d%%" % r0(v), 14, cc, "b", "end")
        S.rect(92, y0 - 10, 160, 11, "#2A333D", rx=5)
        if v is not None:
            S.rect(92, y0 - 10, 160 * min(max(v, 0), 100) / 100, 11, cc, rx=5)
    S.line(14, 372, 252, 372, REJILLA, 1)
    S.text(133, 400, est[0], 14, est[1], "b", "middle", sp=0.4)


def etiqueta(S, x, y, s, tam=14, color=ROTULO, anchor="start"):
    S.text(x, y, s, tam, color, "b", anchor, sp=0.4)


def serie_xy(P, serie, y_de_v, ancho=238):
    """Puntos (x, y) de una serie sobre la ventana 07:00 -> 07:00, redondeados como en el SVG."""
    tot = (P.fin - P.ini).total_seconds()
    return [(r0(14 + ancho * (t - P.ini).total_seconds() / tot), r0(y_de_v(v))) for t, v in serie]


def traza(S, pts, base_y, color=AZUL_CLARO, sw=1.6, area=True, punto=True):
    if area:
        S.poly([(pts[0][0], base_y)] + pts + [(pts[-1][0], base_y)], color, 0.10)
    S.polyline(pts, color, sw)
    if punto:
        S.circle(pts[-1][0], pts[-1][1], 2.8, color)


def tarjeta_chancado(S, P):
    on = P.est[0]
    df, ut = P.df["Chancado Primario"], P.ue["Chancado Primario"]
    acum, plan = P.ton_chancado, P.plan_chancado_dia
    dvp = acum / plan - 1
    S.rect(1, 1, 264, 124, SINOP, stroke=BORDE, sw=1, rx=6)
    etiqueta(S, 14, 30, "TON DÍA · CIERRE")
    S.text(14, 96, n(acum) + " t", 46, sem_r(acum / plan), "b")
    S.rect(1, 139, 264, 125, SINOP, stroke=BORDE, sw=1, rx=6)
    etiqueta(S, 14, 168, "PLAN DÍA")
    S.runs(14, 228, [(n(plan) + " t", 34, TEXTO, "b", 0), (" (%s%s%%)" % ("+" if dvp >= 0 else "", n(dvp * 100, 1)), 20, TITULO, "r", 0)])
    bloque_dfue(S, df, ut, estado_equipo(on == 1, on == 2, df, ut))


def tarjeta_stockpile(S, P):
    niv, tend, plan = P.nivel, P.tendencia, P.nivel_plan
    cH = VERDE if r0(niv) >= plan else (AMBAR if r0(niv) >= 40 else ROJO)
    df, ut = P.df["Feeders"], P.ue["Feeders"]
    feeders = P.est[1:7]
    est = estado_equipo(any(e == 1 for e in feeders), any(e == 2 for e in feeders), df, ut)
    S.rect(1, 1, 264, 110, SINOP, stroke=BORDE, sw=1, rx=6)
    etiqueta(S, 14, 28, "VARIACIÓN EN EL DÍA")
    d = -1 if tend <= -2 else (1 if tend >= 2 else 0)
    if d == 1:
        S.poly([(14, 72), (25, 52), (36, 72)], cH)
    elif d == -1:
        S.poly([(14, 52), (25, 72), (36, 52)], cH)
    else:
        S.rect(14, 59, 22, 6, cH, rx=2)
    S.runs(44, 78, [(n(abs(tend), 1), 40, cH, "b", 0), (" pts", 20, ROTULO, "r", 0)])
    S.text(14, 100, "de %s %% a %s %% (07:00 → 07:00)" % (n(P.nivel_ini, 1), n(niv, 1)), 14, TITULO)
    S.rect(1, 124, 264, 140, SINOP, stroke=BORDE, sw=1, rx=6)
    etiqueta(S, 14, 144, "NIVEL DEL DÍA", 13)
    vals = [v for _, v in P.nivel_serie]
    S.text(133, 224, "mín %d · máx %d %%" % (r0(min(vals)), r0(max(vals))), 12, TITULO, "r", "middle")
    S.line(14, 212, 252, 212, "#3A4654", 1)
    yp = r0(212 - 62 * min(max(plan, 0), 100) / 100)
    S.line(14, yp, 252, yp, TITULO, 1, dash=(4, 3))
    S.text(252, yp - 4, "plan %d %%" % plan, 12, TITULO, "r", "end")
    traza(S, serie_xy(P, P.nivel_serie, lambda v: 212 - 62 * min(max(v, 0), 100) / 100), 212)
    S.text(14, 224, "07:00", 12, ROTULO)
    S.text(252, 224, "07:00", 12, ROTULO, "r", "end")
    S.line(14, 232, 252, 232, REJILLA, 1)
    etiqueta(S, 14, 253, "FINOS SAG · PROM. DÍA", 13)
    S.text(252, 254, "%d %%" % r0(P.finos), 18, TEXTO, "sb", "end")
    bloque_dfue(S, df, ut, est)


def tarjeta_sag(S, P):
    on = P.est[7]
    df, ut = P.df["Molienda"], P.ue["Molienda"]
    proc, plan = P.sag_ton, P.sag_ton_plan
    dv = proc / plan - 1
    cT = VERDE if dv >= 0 else (AMBAR if dv >= -0.1 else ROJO)
    S.rect(1, 1, 264, 110, SINOP, stroke=BORDE, sw=1, rx=6)
    etiqueta(S, 14, 28, "TON PROCESADAS EN EL DÍA")
    S.text(14, 88, n(proc) + " t", 46, cT, "b")
    S.rect(1, 124, 264, 74, SINOP, stroke=BORDE, sw=1, rx=6)
    etiqueta(S, 14, 147, "PLAN DÍA · PLAN MES")
    S.runs(14, 184, [(n(plan) + " t", 30, TEXTO, "b", 0), (" (%s%s%%)" % ("+" if dv >= 0 else "", n(dv * 100, 1)), 18, TITULO, "r", 0)])
    S.rect(1, 210, 264, 54, SINOP, stroke=BORDE, sw=1, rx=6)
    etiqueta(S, 14, 230, "ENERGÍA SAG · DÍA", 13)
    S.text(14, 252, n(P.kwh_t, 2) + " kWh/t", 17, TEXTO, "sb")
    bloque_dfue(S, df, ut, estado_equipo(on == 1, on == 2, df, ut))


def tarjeta_pebbles(S, P):
    est3 = P.est[8:11]
    df, ut = P.df["Circuitos Pebbles"], P.ue["Circuitos Pebbles"]
    est = estado_equipo(any(e == 1 for e in est3), any(e == 2 for e in est3), df, ut)
    plan = P.pebble_plan
    rH = P.pebble_ton / (plan * P.horas)
    vs = [max(v, 0) for _, v in P.pebble_serie]
    top = math.ceil((max(max(vs), plan) * 1.1 + 1) / 50) * 50
    S.rect(1, 1, 264, 110, SINOP, stroke=BORDE, sw=1, rx=6)
    etiqueta(S, 14, 28, "TON PEBBLES EN EL DÍA")
    S.text(14, 88, n(P.pebble_ton) + " t", 46, sem_r(rH), "b")
    S.rect(1, 124, 264, 140, SINOP, stroke=BORDE, sw=1, rx=6)
    etiqueta(S, 14, 151, "PEBBLES DEL DÍA", 13)
    S.line(14, 228, 252, 228, "#3A4654", 1)
    yp = r0(228 - 66 * plan / top)
    S.line(14, yp, 252, yp, TITULO, 1, dash=(4, 3))
    S.text(252, 151, "plan %s t/h" % n(plan), 12, TITULO, "r", "end")
    traza(S, serie_xy(P, P.pebble_serie, lambda v: 228 - 66 * max(v, 0) / top), 228)
    S.text(14, 248, "07:00", 12, ROTULO)
    S.text(133, 248, "prom %s · máx %s t/h" % (n(sum(vs) / len(vs)), n(max(vs))), 12, TITULO, "r", "middle")
    S.text(252, 248, "07:00", 12, ROTULO, "r", "end")
    bloque_dfue(S, df, ut, est)


def tarjeta_bolas(S, P):
    est2 = P.est[11:13]
    df, ut = P.df["Molienda Secundaria"], P.ue["Molienda Secundaria"]
    est = estado_equipo(any(e == 1 for e in est2), any(e == 2 for e in est2), df, ut)
    S.rect(1, 1, 264, 110, SINOP, stroke=BORDE, sw=1, rx=6)
    S.text(14, 28, "POTENCIA PROM. OPERANDO", 14, ROTULO, "b", sp=0.4)
    S.line(133, 42, 133, 100, REJILLA, 1)
    for i, x0 in enumerate((14, 146)):
        S.text(x0, 56, "MOLINO #%d" % (i + 1), 12, ROTULO, "b", sp=0.3)
        cc = estado_color(est2[i])
        S.runs(x0, 94, [(n(P.bolas_prom[i] / 1000, 1), 32, cc, "b", 0), (" MW", 18, ROTULO, "r", 0)])
    S.rect(1, 124, 264, 140, SINOP, stroke=BORDE, sw=1, rx=6)
    etiqueta(S, 14, 151, "POTENCIA DEL DÍA", 13)
    S.line(176, 147, 188, 147, AZUL_CLARO, 2)
    S.text(192, 151, "#1", 12, TITULO)
    S.line(218, 147, 230, 147, TEXTO, 2)
    S.text(234, 151, "#2", 12, TITULO)
    S.line(14, 228, 252, 228, "#3A4654", 1)
    mx = max(max(v for _, v in s) for s in P.bolas)
    top = max(math.ceil((mx + 500) / 5000) * 5000, 5000)
    f = lambda v: 228 - 66 * max(v, 0) / top
    p1, p2 = serie_xy(P, P.bolas[0], f), serie_xy(P, P.bolas[1], f)
    S.polyline(p2, TEXTO, 1.4)
    S.polyline(p1, AZUL_CLARO, 1.6)
    S.circle(p2[-1][0], p2[-1][1], 2.6, TEXTO)
    S.circle(p1[-1][0], p1[-1][1], 2.8, AZUL_CLARO)
    S.text(14, 248, "07:00", 12, ROTULO)
    S.text(133, 248, "escala 0 – %d MW" % (top // 1000), 12, TITULO, "r", "middle")
    S.text(252, 248, "07:00", 12, ROTULO, "r", "end")
    bloque_dfue(S, df, ut, est)


def tarjeta_ciclones(S, P):
    m1, m2 = P.est[11], P.est[12]
    nb = 2 * (m1 == 1) + 2 * (m2 == 1)
    nss = (m1 == 2) + (m2 == 2)
    df, ut = P.cic_df, P.cic_ue
    est = estado_equipo(nb > 0, nss > 0, df, ut)
    vals = [v for _, v in P.p80_serie]
    mn, mx, plan = min(vals), max(vals), P.p80_plan
    lo = math.floor((min(mn, plan) - 5) / 10) * 10
    hi = math.ceil((max(mx, plan) + 5) / 10) * 10
    S.rect(1, 1, 264, 263, SINOP, stroke=BORDE, sw=1, rx=6)
    etiqueta(S, 14, 28, "P80 DEL DÍA")
    S.line(14, 226, 252, 226, "#3A4654", 1)
    S.text(14, 54, "%d µm" % hi, 12, ROTULO)
    S.text(14, 220, "%d" % lo, 12, ROTULO)
    f = lambda v: 226 - 166 * (v - lo) / (hi - lo)
    yp = r0(f(plan))
    S.line(14, yp, 252, yp, TITULO, 1, dash=(4, 3))
    S.text(252, 28, "plan %d µm" % r0(plan), 12, TITULO, "r", "end")
    traza(S, serie_xy(P, P.p80_serie, f), 226)
    S.text(14, 248, "07:00", 12, ROTULO)
    S.text(133, 248, "mín %d · máx %d µm" % (r0(mn), r0(mx)), 12, TITULO, "r", "middle")
    S.text(252, 248, "07:00", 12, ROTULO, "r", "end")
    bloque_dfue(S, df, ut, est)


def pagina_molienda(P):
    c = Lienzo(1920, 1080, PAGINA, ss=2)
    S0 = Svg(c)
    d = P.d
    cabecera(c, S0, "PANEL DE OPERACIÓN PLANTA · CIRCUITO DE MOLIENDA · MINERA DEMO",
             "%s 07:00 → %s 07:00 h" % (d.strftime("%d-%m"), (d + timedelta(days=1)).strftime("%d-%m")), d)
    contenedor(c, 24, 112, 1872, 440)
    etapas = [("1. CHANCADO", sinoptico_chancado, tarjeta_chancado), ("2. STOCKPILE", sinoptico_stockpile, tarjeta_stockpile),
              ("3. MOLIENDA SAG", sinoptico_sag, tarjeta_sag), ("4. PEBBLES", sinoptico_pebbles, tarjeta_pebbles),
              ("5. BOLAS (SECUNDARIA)", sinoptico_bolas, tarjeta_bolas), ("6. CICLONES", sinoptico_ciclones, tarjeta_ciclones)]
    xs_s = [31, 346, 661, 975, 1290, 1605]
    xs_t = [24, 339, 653, 968, 1283, 1597]
    for (t, f_sin, f_tar), xs, xt in zip(etapas, xs_s, xs_t):
        S0.text(xs + 142, 159, t, 21.3, BLANCO, "b", "middle")
        contenedor(c, xs, 178, 284, 352, SINOP)
        f_sin(Svg(c, xs + 3.75, 178 + 24.8, 276.5 / 256, -12), P)
        contenedor(c, xt, 568, 299, 488)
        f_tar(Svg(c, xt + 9.85, 568 + 23.5, 279.3 / 266), P)
    return c


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)
    pagina_mina(Mina(FECHA)).guardar(SALIDA / "mina.png", LEYENDA)
    pagina_molienda(Planta(FECHA)).guardar(SALIDA / "molienda.png", LEYENDA)
    for nombre in ("mina.png", "molienda.png"):
        print("OK %s  %d KB" % (nombre, (SALIDA / nombre).stat().st_size // 1024))


if __name__ == "__main__":
    main()
