# -*- coding: utf-8 -*-
"""Render del diseño de la pantalla «Operación Diaria» (07-centro-operaciones-pbip).

No es una captura de Power BI Desktop: es un render dibujado con Pillow a partir de los CSV sintéticos del proyecto
(`datos_sinteticos/`), con la disposición de la página PBIR (2740 x 1440 px) y los colores del tema oscuro.
El mapa es un plano esquemático abstracto del rajo (sin datos geográficos reales): solo se reutilizan los
desfases relativos de los puntos GPS sintéticos.

Uso:  python cap_07.py        (se puede ejecutar desde cualquier carpeta)
"""
import csv
import math
import random
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from lib_render import Lienzo, fmt, LOGO_BLANCO, ICONO  # noqa: E402

RAIZ = AQUI.parents[1]
PROY = RAIZ / "07-centro-operaciones-pbip"
DATOS = PROY / "datos_sinteticos"
SALIDA = PROY / "capturas" / "operacion_diaria.png"
LEYENDA = "Render del diseño · datos sintéticos · Minera Demo"

W, H = 2740, 1440

# ---- colores del tema «Minera Demo - Oscuro» y de docs/criterios_pantalla_sala_control.md ---------------------------
BG = "#0F1A2C"        # fondo de página
BANDA = "#1B2A41"     # tarjetas y bandas de título
TXT = "#E6ECF2"       # cifras y texto principal
ACENTO = "#8EC5F2"    # títulos y acentos
GRIS = "#8FA3B8"      # plan, referencias, ejes
VERDE = "#00C853"     # cumple el plan
ROJO = "#FF5C5C"      # no cumple
BORDE = "#2F6FB5"
REJILLA = "#2C3E5A"
ALT = "#16233A"
AZUL, VIOLETA, ACERO, ROSA, SALVIA = "#4F9DDE", "#7B61C9", "#2F6FB5", "#C26B8E", "#A3B18A"

PT = 96 / 72  # un punto de Power BI = 1,333 px


# =============================================================================================================
#  Datos
# =============================================================================================================
def rd(nombre):
    with open(DATOS / f"{nombre}.csv", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def suma(filas, col):
    return sum(float(r[col]) for r in filas)


def razon(a, b):
    return a / b if b else 0.0


def orden_hora(turno, hora_en_turno):
    """Posición 1-24 en el día operacional: A = 1-12 (08:00-19:59), B = 13-24 (20:00-07:59)."""
    return hora_en_turno + (1 if turno == "A" else 13)


def calcular():
    d = {}
    horas = rd("fact_horas_equipo")
    dia = max(r["Fecha"] for r in horas)
    d["dia"] = dia
    H_ = [r for r in horas if r["Fecha"] == dia]
    camion = [r for r in H_ if r["Tipo Equipo"] == "Truck"]
    pala = [r for r in H_ if r["Tipo Equipo"] == "Shovel"]
    perf = [r for r in H_ if r["Tipo Equipo"] == "Drill"]
    carg = [r for r in H_ if r["Tipo Equipo"] in ("Shovel", "Loader")]

    def mets(rows, col_ton):
        nom, disp, efe = suma(rows, "Horas Nominales"), suma(rows, "Horas Disponibles"), suma(rows, "Horas Efectivas")
        return razon(disp, nom), razon(efe, disp), razon(suma(rows, col_ton), efe)

    # ---- planes -------------------------------------------------------------------------------------------
    pc = [r for r in rd("plan_caex") if r["Fecha"] == dia][0]
    plan_caex = (razon(float(pc["Horas Disponibles Plan"]), float(pc["Horas Nominales Plan"])),
                 razon(float(pc["Horas Efectivas Plan"]), float(pc["Horas Disponibles Plan"])),
                 razon(float(pc["Toneladas Plan"]), float(pc["Horas Efectivas Plan"])))
    plan_mov_dia = float(pc["Toneladas Plan"])
    pcg = {r["Equipo"]: r for r in rd("plan_carguio") if r["Fecha"] == dia}

    def plan_de(filas, col_ton):
        nom = sum(float(r["Horas Nominales Plan"]) for r in filas)
        disp = sum(float(r["Horas Disponibles Plan"]) for r in filas)
        efe = sum(float(r["Horas Efectivas Plan"]) for r in filas)
        return razon(disp, nom), razon(efe, disp), razon(sum(float(r[col_ton]) for r in filas), efe)

    plan_pala = plan_de([r for e, r in pcg.items() if e.startswith("P")], "Toneladas Plan")
    plan_perf_filas = {r["Equipo"]: r for r in rd("plan_perforadoras") if r["Fecha"] == dia}
    plan_perf = plan_de(list(plan_perf_filas.values()), "Metros Plan")
    pm = {r["Tag"]: float(r["Valor"]) for r in rd("plan_muro") if r["Fecha"] == dia}
    plan_chanc = [r for r in rd("plan_semanal_chancador") if r["Fecha"] == dia][0]

    # ---- resumen de flota Mina: (real, plan) por métrica -----------------------------------------------------
    d["flota_mina"] = {
        "CAEX": (mets(camion, "Movimiento Total"), plan_caex),
        "PALA": (mets(pala, "Tonelaje"), plan_pala),
        "PERFO": (mets(perf, "Metros Perforados"), plan_perf),
    }
    # ---- perforadoras y carguío por equipo ---------------------------------------------------------------------
    d["perf_equipos"] = []
    for eq in sorted({r["Equipo"] for r in perf}):
        real = mets([r for r in perf if r["Equipo"] == eq], "Metros Perforados")
        d["perf_equipos"].append((eq, real, plan_de([plan_perf_filas[eq]], "Metros Plan")))
    d["carg_equipos"] = []
    for eq in sorted({r["Equipo"] for r in carg}):
        real = mets([r for r in carg if r["Equipo"] == eq], "Tonelaje")
        d["carg_equipos"].append((eq, real, plan_de([pcg[eq]], "Toneladas Plan")))

    # ---- tarjetas ---------------------------------------------------------------------------------------------
    mov_acum = suma(camion, "Movimiento Total")
    extraido = suma(camion, "Material Extraido")
    por_hora = defaultdict(float)
    ext_h, rem_h = defaultdict(float), defaultdict(float)
    for r in camion:
        o = orden_hora(r["Turno"], int(r["Hora"]))
        por_hora[o] += float(r["Movimiento Total"])
        ext_h[o] += float(r["Material Extraido"])
        rem_h[o] += float(r["Material Remanejo"])
    horas_con_datos = sum(1 for v in por_hora.values() if v > 0)
    d["tonelaje_dia"] = suma(camion, "Tonelaje")
    d["plan_mov_dia"] = plan_mov_dia
    d["proy_mov"] = razon(mov_acum, horas_con_datos) * 24
    d["proy_amp"] = razon(extraido, horas_con_datos) * 24
    d["horas_con_datos"] = horas_con_datos
    d["ext_h"], d["rem_h"] = ext_h, rem_h

    chanc = [r for r in rd("fact_chancado") if r["Fecha"] == dia]
    d["chancado"] = suma(chanc, "Tonelaje")
    d["plan_chancado"] = float(plan_chanc["Plan_Semanal_Chancado"])
    d["ley"] = razon(sum(float(r["CuT"]) * float(r["Tonelaje"]) for r in chanc), suma(chanc, "Tonelaje"))
    d["plan_ley"] = float(plan_chanc["Plan_Ley_CuT"])

    dim = rd("dim_equipo")

    def total_kpi(tipo):
        return len({r["Equipo"] for r in dim if r["TipoEquipo"] == tipo and r["Activo_KPI"] == "1"})

    def operando(rows, tipo):
        return len({r["Equipo"] for r in rows if r["Tipo Equipo"] == tipo and float(r["Horas Operativas"]) > 0})

    muro = [r for r in rd("fact_horas_equipo_muro") if r["Fecha"] == dia]
    d["en_uso"] = {
        "CAEX": f"{operando(H_, 'Truck')} / {len({r['Equipo'] for r in camion})}",
        "PALA": f"{operando(H_, 'Shovel')} / {total_kpi('Shovel')}",
        "CARGUÍO": f"{operando(H_, 'Loader')} / {total_kpi('Loader')}",
        "PERFO": f"{operando(H_, 'Drill')} / {total_kpi('Drill')}",
    }
    flota_m = lambda tipo: len({r["Equipo"] for r in dim if r["TipoEquipo"] == tipo and "_M" in r["Equipo"]})  # noqa: E731
    d["en_uso_muro"] = {
        "CAEX": f"{operando(muro, 'Truck')} / {flota_m('Truck')}",
        "PALA": f"{operando(muro, 'Shovel')} / {flota_m('Shovel')}",
        "CARGUÍO": f"{operando(muro, 'Loader')} / {flota_m('Loader')}",
    }

    # ---- velocidad de los CAEX por turno (solo lecturas en movimiento) -------------------------------------------
    vel = [r for r in rd("fact_velocidad_caex_hora") if r["Fecha"] == dia]
    d["vel"] = {}
    for t in ("A", "B"):
        f = [r for r in vel if r["Turno"] == t]
        d["vel"][t] = razon(suma(f, "Suma_Velocidad_Movimiento"), suma(f, "Lecturas_Movimiento")) if f else None

    # ---- Muro ----------------------------------------------------------------------------------------------------
    m_cam = [r for r in muro if r["Tipo Equipo"] == "Truck"]
    m_pal = [r for r in muro if r["Tipo Equipo"] == "Shovel"]
    d["flota_muro"] = {
        "CAEX": (mets(m_cam, "Movimiento Total"),
                 (pm["PLAN_MURO_CAEX_DISP"], pm["PLAN_MURO_CAEX_UEBD"], pm["PLAN_MURO_CAEX_REND"])),
        "PALA": (mets(m_pal, "Tonelaje"),
                 (pm["PLAN_MURO_PALA_DISP"], pm["PLAN_MURO_PALA_UEBD"], pm["PLAN_MURO_PALA_REND"])),
    }
    d["carg_muro"] = []
    for eq in sorted({r["Equipo"] for r in muro if r["Tipo Equipo"] in ("Shovel", "Loader")}):
        real = mets([r for r in muro if r["Equipo"] == eq], "Tonelaje")
        plan = (pm["PLAN_MURO_PALA_DISP"], pm["PLAN_MURO_PALA_UEBD"], pm["PLAN_MURO_PALA_REND"]) \
            if eq == "PALA-05_M" else None
        d["carg_muro"].append((eq, real, plan))
    mur_h = defaultdict(float)
    for r in muro:
        mur_h[orden_hora(r["Turno"], int(r["Hora"]))] += float(r["Movimiento Total"])
    d["muro_h"] = mur_h

    # ---- chancado por origen y hora --------------------------------------------------------------------------------
    co = [r for r in rd("fact_chancado_origen_hora") if r["Fecha"] == dia]
    d["chanc_origen"] = defaultdict(lambda: defaultdict(float))   # (turno, hora_turno) -> origen -> t
    for r in co:
        d["chanc_origen"][(r["Turno"], int(r["HoraTurno"]))][r["Origen"]] += float(r["Tonelaje"])

    # ---- ley de alimentación por fase (blast) y hora ------------------------------------------------------------------
    ley = [r for r in rd("fact_ley_alimentacion_hora") if r["Fecha"] == dia]
    acum = defaultdict(lambda: [0.0, 0.0])
    tot = defaultdict(lambda: [0.0, 0.0])
    for r in ley:
        o = int(r["Orden_Hora_Dia"])
        acum[(r["Blast"], o)][0] += float(r["Ley_x_Ton"])
        acum[(r["Blast"], o)][1] += float(r["Tonelaje"])
        tot[o][0] += float(r["Ley_x_Ton"])
        tot[o][1] += float(r["Tonelaje"])
    d["ley_blast"] = sorted({r["Blast"] for r in ley}, reverse=True)
    d["ley_celda"] = {k: razon(v[0], v[1]) for k, v in acum.items() if v[1]}
    d["ley_pond"] = {k: razon(v[0], v[1]) for k, v in tot.items() if v[1]}

    # ---- ciclos de acarreo por pala o cargador ----------------------------------------------------------------------
    ciclos = [r for r in rd("fact_ciclos") if r["DiaOperativo"].startswith(dia)]
    por_pala = defaultdict(list)
    for r in ciclos:
        por_pala[r["ShovelName"]].append(r)

    def minutos(r):
        return sum(float(r[k]) for k in ("traveling_time", "waiting_time", "loading_time", "hauling_time",
                                         "queued_time", "tipping_time")) / 60

    pt = lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M:%S")  # noqa: E731
    d["ciclos"] = []
    for eq, rows in por_pala.items():
        prom = sum(minutos(r) for r in rows) / len(rows)
        ult = max(pt(r["time_empty"]) for r in rows)
        ultima_h = [r for r in rows if pt(r["time_empty"]) > ult - timedelta(hours=1)]
        prom_u = sum(minutos(r) for r in ultima_h) / len(ultima_h)
        destino = max(rows, key=lambda r: r["time"])["DumpName"]
        d["ciclos"].append((eq, destino, prom, prom_u - prom))
    d["ciclos"].sort(key=lambda t: -t[3])

    # ---- GPS: baja velocidad en la última hora con datos ---------------------------------------------------------------
    gps = [r for r in rd("fact_gps") if r["Fecha"] == dia]
    ult_h = max(int(r["Orden_Hora_Dia"]) for r in gps)
    d["gps_hora"] = ult_h
    d["gps"] = [(r["Equipo"], float(r["Longitud"]) / 3.6e6, float(r["Latitud"]) / 3.6e6, float(r["Velocidad km/h"]))
                for r in gps if int(r["Orden_Hora_Dia"]) == ult_h]
    return d


# =============================================================================================================
#  Utilidades de dibujo
# =============================================================================================================
_FUENTES = {"r": "segoeui.ttf", "b": "segoeuib.ttf", "sb": "seguisb.ttf"}
_cache = {}


def fuente(px, tipo="r"):
    k = (round(px, 1), tipo)
    if k not in _cache:
        try:
            _cache[k] = ImageFont.truetype(_FUENTES[tipo], round(px))
        except OSError:
            _cache[k] = ImageFont.truetype("DejaVuSans-Bold.ttf" if tipo != "r" else "DejaVuSans.ttf", round(px))
    return _cache[k]


def T(c, x, y, s, pt, color, tipo="r", a="la"):
    """Texto con tamaño en puntos de Power BI (1 pt = 1,333 px)."""
    c.d.text((x * c.ss, y * c.ss), str(s), font=fuente(pt * PT * c.ss, tipo), fill=color, anchor=a)


def tw(c, s, pt, tipo="r"):
    return c.d.textlength(str(s), font=fuente(pt * PT * c.ss, tipo)) / c.ss


def pct(v):
    return fmt(v * 100, 1) + " %"


def kt(v):
    return fmt(v / 1000, 1) + " kt"


def marco(c, x, y, w, h, titulo=None, tit_h=36, pt=14):
    """Visual con borde de 3 px (radio 8) y banda de título."""
    c.caja(x, y, w, h, fill=BG, borde=BORDE, r=8, ancho=3)
    if titulo:
        c.caja(x + 3, y + 3, w - 6, tit_h - 3, fill=BANDA, r=6)
        c.caja(x + 3, y + 3 + (tit_h - 3) // 2, w - 6, (tit_h - 3) // 2, fill=BANDA)
        T(c, x + w / 2, y + 3 + (tit_h - 3) / 2, titulo, pt, ACENTO, "b", "mm")


def semaforo(real, plan):
    return VERDE if real >= plan else ROJO


def fmt_met(i, v, plan=False):
    """0 = DF, 1 = UEBD (porcentaje) y 2 = rendimiento (#,0.0 real; #,0 plan)."""
    if i < 2:
        return pct(v)
    return fmt(v, 0 if plan else 1, ".")


# =============================================================================================================
#  Cabecera y tarjetas
# =============================================================================================================
def cabecera(c, d):
    c.caja(0, 0, W, 61, fill=BANDA)
    c.pegar(LOGO_BLANCO, 0, 7, w=216)
    c.pegar(ICONO, 239, 5, h=50)
    T(c, 1382, 31, "CENTRO DE OPERACIONES DEMO", 20, "#FFFFFF", "b", "mm")
    T(c, 330, 31, "Render del diseño · datos sintéticos", 13, GRIS, "r", "lm")
    # recuadro «ÚLTIMA ACTUALIZACIÓN» (SVG de 240 x 44 escalado a 1,273) con la fecha porque el dato sintético es antiguo
    ref = datetime.strptime(d["dia"], "%Y-%m-%d") + timedelta(days=1, hours=1, minutes=10)
    c.caja(2060, 0, 332, 56, fill=BG, borde=BORDE, r=6, ancho=2)
    T(c, 2226, 17, "ÚLTIMA ACTUALIZACIÓN", 9, ACENTO, "b", "mm")
    T(c, 2226, 40, ref.strftime("%d-%m-%Y") + " · " + ref.strftime("%H:%M"), 15, "#FFFFFF", "b", "mm")
    # segmentador de día (lista desplegable en «Dia actual»)
    c.caja(2405, 0, 301, 56, fill=BANDA, borde=BORDE, r=8, ancho=2)
    T(c, 2427, 28, "Dia actual", 14, TXT, "r", "lm")
    c.linea([(2668, 24), (2677, 33), (2686, 24)], ACENTO, 3)


def tarjeta_plan(c, x, y, w, titulo, real, plan, color, fmt_v):
    """Tarjeta de 93 px: título en banda y debajo el real (semáforo) junto al plan (gris pizarra)."""
    c.caja(x, y, w, 93, fill=BG, borde=BORDE, r=8, ancho=3)
    c.caja(x + 4, y + 4, w - 8, 33, fill=BANDA, r=6)
    T(c, x + w / 2, y + 20.5, titulo, 14, ACENTO, "b", "mm")
    cy = y + 66
    a, b = fmt_v(real), (fmt_v(plan) if plan is not None else "")
    if plan is None:
        T(c, x + w / 2, cy, a, 22, color, "b", "mm")
        return
    sep = 26
    wa, wb = tw(c, a, 22, "b"), tw(c, b, 22, "b")
    total = wa + wb + sep
    x0 = x + (w - total) / 2
    T(c, x0, cy, a, 22, color, "b", "lm")
    T(c, x0 + wa + sep / 2, cy, "/", 18, GRIS, "r", "mm")
    T(c, x0 + wa + sep, cy, b, 22, GRIS, "b", "lm")


def tarjeta_una(c, x, y, w, titulo, texto, color=TXT):
    c.caja(x, y, w, 93, fill=BG, borde=BORDE, r=8, ancho=3)
    c.caja(x + 4, y + 4, w - 8, 33, fill=BANDA, r=6)
    T(c, x + w / 2, y + 20.5, titulo, 14, ACENTO, "b", "mm")
    T(c, x + w / 2, y + 66, texto, 22, color, "b", "mm")


def tarjetas(c, d):
    y = 60
    ton, plan = d["tonelaje_dia"], d["plan_mov_dia"]
    tarjeta_plan(c, 0, y, 672, "MOV. TOTAL DIA / PLAN (kt)", ton, plan, semaforo(ton, plan), lambda v: fmt(v / 1000, 1) + " kt")
    tarjeta_una(c, 676, y, 436, "PROYECCIÓN MOV TOTAL MINA (kt)", fmt(d["proy_mov"] / 1000, 1) + " kt")
    tarjeta_una(c, 1116, y, 436, "PROYECCIÓN AMPLIACION (kt)", fmt(d["proy_amp"] / 1000, 1) + " kt")
    tarjeta_plan(c, 1556, y, 507, "LEY DE ALIMENTACIÓN MINA / PLAN", d["ley"], d["plan_ley"], semaforo(d["ley"], d["plan_ley"]),
                 lambda v: fmt(v, 2) + "%")
    ch, pch = d["chancado"], d["plan_chancado"]
    tarjeta_plan(c, 2068, y, 672, "TONELAJE CHANCADO / PLAN (kt)", ch, pch, semaforo(ch, pch), lambda v: fmt(v / 1000, 1) + " kt")


def equipos_en_uso(c, d):
    y = 155
    for x, w, tit in ((0, 561, "EQUIPOS EN USO MINA"), (564, 394, "EQUIPOS EN USO MURO")):
        c.caja(x, y, w, 36, fill=BANDA, borde=BORDE, r=6, ancho=2)
        T(c, x + w / 2, y + 18, tit, 14, ACENTO, "b", "mm")

    def mini(x, w, tit, val):
        c.caja(x, y + 39, w, 117, fill=BG, borde=BORDE, r=8, ancho=3)
        c.caja(x + 3, y + 42, w - 6, 33, fill=BANDA, r=6)
        T(c, x + w / 2, y + 58.5, tit, 12, ACENTO, "b", "mm")
        T(c, x + w / 2, y + 39 + 76, val, 15, TXT, "b", "mm")

    for (x, w, k) in ((0, 156, "CAEX"), (160, 127, "PALA"), (291, 129, "CARGUÍO"), (423, 137, "PERFO")):
        mini(x, w, k, d["en_uso"][k])
    for (x, w, k) in ((564, 130, "CAEX"), (698, 123, "PALA"), (824, 133, "CARGUÍO")):
        mini(x, w, k, d["en_uso_muro"][k])

    # velocidad promedio de los CAEX por turno
    x, w = 962, 235
    c.caja(x, y, w, 156, fill=BG, borde=BORDE, r=8, ancho=3)
    c.caja(x + 3, y + 3, w - 6, 50, fill=BANDA, r=6)
    T(c, x + w / 2, y + 20, "VELOCIDAD PROM. CAEX", 12, ACENTO, "b", "mm")
    T(c, x + w / 2, y + 40, "TURNO KM/H", 12, ACENTO, "b", "mm")
    for i, t in enumerate(("A", "B")):
        cx = x + w * (0.27 + 0.46 * i)
        T(c, cx, y + 86, t, 13, ACENTO, "r", "mm")
        v = d["vel"][t]
        T(c, cx, y + 118, fmt(v, 1) if v is not None else "–", 15, TXT, "b", "mm")


# =============================================================================================================
#  Matrices y tablas
# =============================================================================================================
def matriz(c, x, y, w, h, titulo, grupos, filas, rh_w, rh_max=46):
    """grupos: [(nombre, [subcolumnas...])]; filas: [(etiqueta, [(texto, color)...])]."""
    marco(c, x, y, w, h, titulo)
    top = y + 36
    hh = 28
    subcols = [(g, s) for g, ss in grupos for s in ss]
    n = len(subcols)
    cw = (w - 6 - rh_w) / n
    x0 = x + 3 + rh_w
    # encabezados de dos niveles
    c.caja(x + 3, top, w - 6, hh * 2, fill=BANDA)
    xi = x0
    for g, ss in grupos:
        gw = cw * len(ss)
        T(c, xi + gw / 2, top + hh / 2, g, 12, ACENTO, "b", "mm")
        for j, s in enumerate(ss):
            T(c, xi + cw * (j + 0.5), top + hh * 1.5, s, 12, ACENTO, "b", "mm")
        xi += gw
    avail = h - 36 - hh * 2 - 3
    rh = min(rh_max, avail / max(1, len(filas)))
    for i, (et, celdas) in enumerate(filas):
        ry = top + hh * 2 + i * rh
        c.caja(x + 3, ry, w - 6, rh, fill=(BG if i % 2 == 0 else ALT))
        T(c, x + 14, ry + rh / 2, et, 13, TXT, "b", "lm")
        for j, (txt, col) in enumerate(celdas):
            T(c, x0 + cw * (j + 0.5), ry + rh / 2, txt, 14, col, "b", "mm")
    # rejilla
    yb = top + hh * 2 + len(filas) * rh
    for i in range(len(filas) + 1):
        c.linea([(x + 3, top + hh * 2 + i * rh), (x + w - 3, top + hh * 2 + i * rh)], REJILLA, 1)
    c.linea([(x0, top), (x0, yb)], REJILLA, 1)
    xi = x0
    for g, ss in grupos:
        gw = cw * len(ss)
        c.linea([(xi, top), (xi, yb)], BORDE if xi > x0 else REJILLA, 1.5 if xi > x0 else 1)
        for j in range(1, len(ss)):
            c.linea([(xi + cw * j, top + hh), (xi + cw * j, yb)], REJILLA, 1)
        c.linea([(xi, top + hh), (xi + gw, top + hh)], REJILLA, 1)
        xi += gw
    c.linea([(x + 3, yb), (x + w - 3, yb)], REJILLA, 1)


def celdas_pares(real, plan, plan_gris=GRIS):
    """Filas Real / Plan para cada métrica: devuelve [(texto, color)] en orden real, plan."""
    out = []
    for i in range(3):
        out.append((fmt_met(i, real[i]), semaforo(real[i], plan[i]) if plan else TXT))
        out.append((fmt_met(i, plan[i], True) if plan else "", plan_gris))
    return out


def resumen_flota(c, d, x, y, w, h, titulo, claves, clave_d):
    metricas = ["DF", "UEBD", "Rendimiento"]
    grupos = [(k, ["Real", "Plan"]) for k in claves]
    filas = []
    for i, m in enumerate(metricas):
        celdas = []
        for k in claves:
            real, plan = d[clave_d][k]
            celdas += [(fmt_met(i, real[i]), semaforo(real[i], plan[i])), (fmt_met(i, plan[i], True), GRIS)]
        filas.append((m, celdas))
    matriz(c, x, y, w, h, titulo, grupos, filas, 150 if w > 1000 else 132)


def matriz_equipos(c, x, y, w, h, titulo, equipos, rend="Rendimiento", rh_w=130, rh_max=46):
    grupos = [("DF", ["Real", "Plan"]), ("UEBD", ["Real", "Plan"]), (rend, ["Real", "Plan"])]
    filas = []
    for eq, real, plan in equipos:
        celdas = []
        for i in range(3):
            if plan:
                celdas += [(fmt_met(i, real[i]), semaforo(real[i], plan[i])), (fmt_met(i, plan[i], True), GRIS)]
            else:
                celdas += [(fmt_met(i, real[i]), TXT), ("", GRIS)]
        filas.append((eq, celdas))
    matriz(c, x, y, w, h, titulo, grupos, filas, rh_w, rh_max)


def tabla_ciclos(c, d, x, y, w, h):
    marco(c, x, y, w, h, "TIEMPO CICLO")
    top = y + 36
    hh = 32
    anchos = [0.15, 0.36, 0.22, 0.27]
    cols = ["Equipo", "Destino Actual", "Promedio Min", "Desviacion Minutos"]
    xs = [x + 3]
    for a in anchos:
        xs.append(xs[-1] + (w - 6) * a)
    c.caja(x + 3, top, w - 6, hh, fill=BANDA)
    for i, t in enumerate(cols):
        if i < 2:
            T(c, xs[i] + 12, top + hh / 2, t, 11, ACENTO, "b", "lm")
        else:
            T(c, xs[i + 1] - 14, top + hh / 2, t, 11, ACENTO, "b", "rm")
    filas = d["ciclos"]
    rh = min(40, (h - 36 - hh - 3) / max(1, len(filas)))
    for i, (eq, dest, prom, desv) in enumerate(filas):
        ry = top + hh + i * rh
        c.caja(x + 3, ry, w - 6, rh, fill=(BG if i % 2 == 0 else ALT))
        T(c, xs[0] + 12, ry + rh / 2, eq, 14, TXT, "b", "lm")
        T(c, xs[1] + 12, ry + rh / 2, dest, 14, TXT, "b", "lm")
        T(c, xs[3] - 14, ry + rh / 2, fmt(prom, 1), 14, TXT, "b", "rm")
        T(c, xs[4] - 14, ry + rh / 2, fmt(desv, 1), 14, TXT, "b", "rm")
    yb = top + hh + len(filas) * rh
    for i in range(len(filas) + 1):
        c.linea([(x + 3, top + hh + i * rh), (x + w - 3, top + hh + i * rh)], REJILLA, 1)
    for xv in xs[1:-1]:
        c.linea([(xv, top), (xv, yb)], REJILLA, 1)


def tabla_ley(c, d, x, y, w, h):
    marco(c, x, y, w, h, "LEY DE ALIMENTACION POR FASE")
    top = y + 36
    hh = 24
    rh_w = 150
    n = 25                                   # A 1-12, hueco, B 1-12
    cw = (w - 6 - rh_w) / n
    x0 = x + 3 + rh_w
    c.caja(x + 3, top, w - 6, hh * 2, fill=BANDA)
    for j in range(n):
        if j == 12:
            continue
        hora = j + 1 if j < 12 else j - 12
        T(c, x0 + cw * (j + 0.5), top + hh * 1.5, str(hora), 11, ACENTO, "b", "mm")
    T(c, x0 + cw * 6, top + hh / 2, "A", 11, ACENTO, "b", "mm")
    T(c, x0 + cw * 19, top + hh / 2, "B", 11, ACENTO, "b", "mm")
    filas = [("Ponderado", None)] + [(b, b) for b in d["ley_blast"]]
    avail = h - 36 - hh * 2 - 3
    rh = min(28, avail / len(filas))
    for i, (et, blast) in enumerate(filas):
        ry = top + hh * 2 + i * rh
        c.caja(x + 3, ry, w - 6, rh, fill=(BANDA if i == 0 else (BG if i % 2 else ALT)))
        T(c, x + 12, ry + rh / 2, et, 12, ACENTO if i == 0 else TXT, "b", "lm")
        for j in range(n):
            if j == 12:
                continue
            o = j + 1 if j < 12 else j
            v = d["ley_pond"].get(o) if blast is None else d["ley_celda"].get((blast, o))
            if v is not None:
                T(c, x0 + cw * (j + 0.5), ry + rh / 2, fmt(v, 2), 11.7, ACENTO if i == 0 else TXT, "b", "mm")
    yb = top + hh * 2 + len(filas) * rh
    for i in range(len(filas) + 1):
        c.linea([(x + 3, top + hh * 2 + i * rh), (x + w - 3, top + hh * 2 + i * rh)], REJILLA, 1)
    for j in range(n + 1):
        if j in (13,):
            continue
        xv = x0 + cw * j
        c.linea([(xv, top + (hh if j not in (0, 12, 13, 25) else 0)), (xv, yb)], REJILLA, 1)
    c.linea([(x0, top), (x0, yb)], REJILLA, 1)


# =============================================================================================================
#  Gráficos de columnas por hora (A 1-12 | hueco | B 1-12)
# =============================================================================================================
def grafico_horas(c, x, y, w, h, titulo, series, valores, colores, inicio_vacio=0, etiqueta_pt=12,
                  fmt_tot=lambda v: fmt(v, 0, "."), unidad=None):
    """valores[s][(turno, i)] -> número. Columnas apiladas con el total encima."""
    marco(c, x, y, w, h, titulo)
    # leyenda superior centrada
    ly = y + 36 + 19
    sw = [tw(c, s, 13, "b") + 28 for s in series]
    lx = x + (w - (sum(sw) + 26 * (len(series) - 1))) / 2
    for s, col, ancho in zip(series, colores, sw):
        c.caja(lx, ly - 6, 12, 12, fill=col, r=2)
        T(c, lx + 20, ly, s, 13, TXT, "b", "lm")
        lx += ancho + 26
    slots = [None] * inicio_vacio + [("A", i) for i in range(1, 13)] + [None] + [("B", i) for i in range(1, 13)]
    n = len(slots)
    px0, px1 = x + 16, x + w - 16
    pt_top, pt_bot = y + 36 + 40, y + h - 50
    band = (px1 - px0) / n
    totales = [sum(v.get(s, 0) for v in valores) if s else 0 for s in slots]
    mx = max(totales) * 1.12
    for k in range(1, 4):
        yy = pt_bot - (pt_bot - pt_top) * k / 3.4
        c.linea([(px0, yy), (px1, yy)], REJILLA, 1)
    c.linea([(px0, pt_bot), (px1, pt_bot)], GRIS, 1.5)
    bw = band * 0.68
    for k, s in enumerate(slots):
        if s is None:
            continue
        cx = px0 + band * (k + 0.5)
        base = pt_bot
        tot = 0
        for v, col in zip(valores, colores):
            val = v.get(s, 0)
            if val <= 0:
                continue
            hh = (pt_bot - pt_top) * val / mx
            c.caja(cx - bw / 2, base - hh, bw, hh, fill=col)
            base -= hh
            tot += val
        if tot > 0:
            T(c, cx, base - 4, fmt_tot(tot), etiqueta_pt, TXT, "b", "ms")
    # eje X: hora dentro del turno (cada 2 h) y turno debajo
    for k, s in enumerate(slots):
        if s and s[1] % 2 == 0:
            T(c, px0 + band * (k + 0.5), pt_bot + 14, str(s[1]), 12, TXT, "b", "mm")
    for tur, k0 in (("A", inicio_vacio), ("B", inicio_vacio + 13)):
        cx = px0 + band * (k0 + 6)
        T(c, cx, pt_bot + 36, tur, 12, TXT, "b", "mm")
        c.linea([(px0 + band * k0 + 2, pt_bot + 26), (px0 + band * (k0 + 12) - 2, pt_bot + 26)], REJILLA, 1)
    if unidad:
        T(c, x + w - 18, y + 36 + 19, unidad, 12, GRIS, "b", "rm")


def grafico_muro(c, x, y, w, h, d):
    marco(c, x, y, w, h, "MOVIMIENTO TONELAJE POR HORA MURO")
    ly = y + 36 + 19
    ancho = tw(c, "Material Muro", 13, "b") + 28
    lx = x + (w - ancho) / 2
    c.caja(lx, ly - 6, 12, 12, fill=TXT, r=2)
    T(c, lx + 20, ly, "Material Muro", 13, TXT, "b", "lm")
    T(c, x + w - 18, ly, "kt", 12, GRIS, "b", "rm")
    slots = [("A", i) for i in range(1, 13)] + [None] + [("B", i) for i in range(1, 13)]
    n = len(slots)
    px0, px1 = x + 16, x + w - 16
    pt_top, pt_bot = y + 36 + 44, y + h - 50
    band = (px1 - px0) / n
    val = lambda s: d["muro_h"].get(orden_hora(s[0], s[1] - 1), 0) if s else 0  # noqa: E731
    mx = max(val(s) for s in slots) * 1.14
    for k in range(1, 4):
        yy = pt_bot - (pt_bot - pt_top) * k / 3.4
        c.linea([(px0, yy), (px1, yy)], REJILLA, 1)
    c.linea([(px0, pt_bot), (px1, pt_bot)], GRIS, 1.5)
    bw = band * 0.68
    for k, s in enumerate(slots):
        if s is None:
            continue
        v = val(s)
        cx = px0 + band * (k + 0.5)
        if v > 0:
            hh = (pt_bot - pt_top) * v / mx
            c.caja(cx - bw / 2, pt_bot - hh, bw, hh, fill=TXT)
            T(c, cx, pt_bot - hh - 4, fmt(v / 1000, 2), 11.5, TXT, "b", "ms")
        if s[1] % 2 == 0:
            T(c, cx, pt_bot + 14, str(s[1]), 12, TXT, "b", "mm")
    for tur, k0 in (("A", 0), ("B", 13)):
        T(c, px0 + band * (k0 + 6), pt_bot + 36, tur, 12, TXT, "b", "mm")
        c.linea([(px0 + band * k0 + 2, pt_bot + 26), (px0 + band * (k0 + 12) - 2, pt_bot + 26)], REJILLA, 1)


# =============================================================================================================
#  Mapa: plano esquemático abstracto del rajo (curvas de nivel, rampas y puntos de equipos)
# =============================================================================================================
def _suave(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def mapa(c, d, x, y, w, h):
    marco(c, x, y, w, h, "CAEX EN BAJA VELOCIDAD")
    rx, ry, rw, rh = x + 3, y + 36, w - 6, h - 36 - 3          # área del plano
    ss = c.ss
    k = 9200.0                                                 # px por grado (escala del plano abstracto)
    lon0, lat0 = 25.90, 21.50                                   # centro arbitrario del dato sintético
    cx, cy = rw / 2, rh / 2 + 10

    def a_px(lon, lat):
        return cx + (lon - lon0) * k, cy - (lat - lat0) * k

    # elementos del plano a partir de los desfases sintéticos
    frentes = [(-0.020, 0.008), (-0.008, 0.004), (-0.024, -0.003), (0.004, 0.009)]
    chanc = a_px(lon0 + 0.026, lat0 - 0.008)
    bot_n = a_px(lon0 + 0.034, lat0 + 0.012)
    bot_s = a_px(lon0 + 0.010, lat0 - 0.012)
    taller = a_px(lon0 - 0.034, lat0 - 0.010)
    pit = a_px(lon0 - 0.0135, lat0 + 0.0045)

    # campo de elevación a media resolución
    res = 2.0
    nx, ny = int(rw * res), int(rh * res)
    gx, gy = np.meshgrid(np.linspace(0, rw, nx), np.linspace(0, rh, ny))
    z = 80 + 0.020 * (gx - cx) - 0.012 * (gy - cy)
    z += 3.4 * np.sin(gx / 71.0 + 1.3) * np.cos(gy / 53.0 - 0.4) + 2.2 * np.sin(gx / 29.0 + gy / 41.0)
    dx, dy = gx - pit[0], gy - pit[1]
    ang = np.arctan2(dy, dx)
    a_ax, b_ax = 210.0, 96.0
    rho = np.sqrt((dx / a_ax) ** 2 + (dy / b_ax) ** 2)
    rho = rho / (1 + 0.10 * np.sin(3 * ang + 0.7) + 0.06 * np.sin(5 * ang + 2.1) + 0.04 * np.sin(2 * ang - 1.0))
    for (mx_, my_, amp, rr) in ((bot_n[0], bot_n[1], 22, 62), (bot_s[0], bot_s[1], 19, 55), (chanc[0] + 40, chanc[1] + 18, 8, 46)):
        z += amp * np.exp(-(((gx - mx_) / rr) ** 2 + ((gy - my_) / (rr * 0.78)) ** 2))
    z_terreno = z.copy()
    z = z - 62.0 * np.clip(1 - rho, 0, 1) ** 0.9 - 4 * _suave((1.12 - rho) / 0.12) * (rho < 1.12)

    # fondo coloreado por elevación (muy tenue)
    zn = (z - z.min()) / (z.max() - z.min())
    lo, hi = np.array([10, 20, 36]), np.array([24, 44, 70])
    img = (lo + (hi - lo) * zn[..., None]).astype(np.uint8)
    base = Image.fromarray(img, "RGB").resize((int(rw * ss), int(rh * ss)), Image.BICUBIC)
    c.im.paste(base, (int(rx * ss), int(ry * ss)))

    # retícula tenue
    for gxl in range(0, int(rw) + 1, 100):
        c.linea([(rx + gxl, ry), (rx + gxl, ry + rh)], "#142238", 1)
    for gyl in range(0, int(rh) + 1, 100):
        c.linea([(rx, ry + gyl), (rx + rw, ry + gyl)], "#142238", 1)

    # curvas de nivel (contourpy viene con matplotlib)
    from contourpy import contour_generator
    xs_, ys_ = gx[0], gy[:, 0]
    # terreno fuera del rajo: curvas cada 3,4 m, con una más marcada cada 5
    gen = contour_generator(xs_, ys_, np.ma.masked_where(rho < 1.04, z_terreno))
    paso = 3.4
    niv = np.arange(math.floor(float(z_terreno.min()) / paso) * paso, float(z_terreno.max()), paso)
    for lv in niv:
        indice = (round(lv / paso) % 5 == 0)
        for seg in gen.lines(lv):
            pts = [(rx + px, ry + py) for px, py in seg]
            if len(pts) > 1:
                c.linea(pts, "#2E5C8C" if indice else "#1E3A5C", 1.6 if indice else 1.0)
    # rajo: anillos de banco (más juntos donde el talud es más empinado) y borde superior
    gen_r = contour_generator(xs_, ys_, rho)
    for k_, lv in enumerate(np.arange(0.10, 1.0, 0.075)):
        mezcla = lv
        col = "#%02x%02x%02x" % (int(63 + 40 * (1 - mezcla)), int(120 + 60 * (1 - mezcla)), int(176 + 50 * (1 - mezcla)))
        for seg in gen_r.lines(float(lv)):
            c.linea([(rx + px, ry + py) for px, py in seg], col, 1.3)
    for seg in gen_r.lines(1.0):
        c.linea([(rx + px, ry + py) for px, py in seg], ACENTO, 2.4)

    # rampa en espiral dentro del rajo y caminos de acarreo
    def cuerpo(t_ang, r):
        s = 1 + 0.10 * math.sin(3 * t_ang + 0.7) + 0.06 * math.sin(5 * t_ang + 2.1) + 0.04 * math.sin(2 * t_ang - 1.0)
        return pit[0] + r * a_ax * s * math.cos(t_ang), pit[1] + r * b_ax * s * math.sin(t_ang)

    esp = []
    for i in range(0, 260):
        f = i / 259
        r = 0.97 - 0.80 * f
        esp.append(cuerpo(-0.4 + f * 2 * math.pi * 2.15, r))
    c.linea([(rx + px, ry + py) for px, py in esp], "#9FB1C9", 2.6)
    c.linea([(rx + px, ry + py) for px, py in esp], "#3A5878", 0.8)

    def bezier(p0, p1, p2, n=40):
        return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                 (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in np.linspace(0, 1, n)]

    salida = cuerpo(0.35, 1.0)
    caminos = [
        bezier(salida, (salida[0] + 120, salida[1] + 70), chanc),
        bezier(salida, (salida[0] + 150, salida[1] - 20), bot_n),
        bezier(cuerpo(1.1, 1.0), (pit[0] + 60, pit[1] + 150), bot_s),
        bezier(cuerpo(2.7, 1.0), (pit[0] - 240, pit[1] + 80), taller),
    ]
    for cam in caminos:
        pts = [(rx + px, ry + py) for px, py in cam]
        c.linea(pts, "#52708F", 5)
        c.linea(pts, "#9FB1C9", 1.4)

    # destinos
    def pildora(x_, y_, txt, pt, color, a="mm"):
        """Texto con fondo oscuro translúcido para que se lea sobre las curvas de nivel."""
        ancho_t = tw(c, txt, pt, "b")
        x0_ = x_ - ancho_t / 2 if a == "mm" else (x_ if a == "lm" else x_ - ancho_t)
        c.caja(x0_ - 4, y_ - 9, ancho_t + 8, 18, fill=(15, 26, 44, 215), r=4)
        T(c, x_, y_, txt, pt, color, "b", a)

    for (pxx, pyy, nombre, dxl, dyl, anc) in ((chanc[0], chanc[1], "CHANCADO", 30, 0, "lm"),
                                               (bot_n[0], bot_n[1], "BOTADERO_N", 0, 30, "mm"),
                                               (bot_s[0], bot_s[1], "BOTADERO_S", 30, 0, "lm")):
        c.poligono([(rx + pxx - 20, ry + pyy + 11), (rx + pxx + 20, ry + pyy + 11), (rx + pxx + 13, ry + pyy - 11),
                    (rx + pxx - 13, ry + pyy - 11)], fill="#2C4666", borde="#9FB1C9")
        pildora(rx + pxx + dxl, ry + pyy + dyl, nombre, 10, TXT, anc)
    c.caja(rx + taller[0] - 10, ry + taller[1] - 8, 20, 16, fill="#2C4666", borde="#9FB1C9", r=2)

    # CAEX en baja velocidad (última hora con datos): burbujas rojas
    pts = [(eq, *a_px(lon, lat)) for eq, lon, lat, _v in d["gps"]]
    for _eq, px_, py_ in pts:
        c.elipse(rx + px_, ry + py_, 7, fill=ROJO, borde="#FFFFFF", ancho=2)

    # palas (cuadrados azules) en los frentes, con la etiqueta a la izquierda
    ocupado = []
    for i, (dlon, dlat) in enumerate(frentes):
        px_, py_ = a_px(lon0 + dlon, lat0 + dlat)
        c.caja(rx + px_ - 8, ry + py_ - 8, 16, 16, fill=AZUL, borde="#FFFFFF", r=2, ancho=2)
        nom = f"PALA-0{i + 1}"
        pildora(rx + px_ - 14, ry + py_, nom, 10, "#BFE0FA", "rm")
        ocupado.append((rx + px_ - 14 - tw(c, nom, 10, "b") - 4, ry + py_ - 12, tw(c, nom, 10, "b") + 30, 24))
    etiquetadas = 0
    random.seed(7)
    orden = sorted(pts, key=lambda t: (t[1], t[2]))
    for eq, px_, py_ in orden:
        if etiquetadas >= 9:
            break
        tx = rx + px_ + 11
        ty = ry + py_
        rect = (tx - 2, ty - 8, tw(c, eq, 9.5, "b") + 6, 16)
        solapa = any(not (rect[0] + rect[2] < o[0] or o[0] + o[2] < rect[0] or rect[1] + rect[3] < o[1] or o[1] + o[3] < rect[1])
                     for o in ocupado)
        cerca = any(abs((rx + qx) - (rx + px_)) < 120 and abs((ry + qy) - (ry + py_)) < 24 and (qx, qy) != (px_, py_)
                    and (rx + qx) > tx - 14 for _e, qx, qy in pts)
        if solapa or cerca or tx + rect[2] > rx + rw - 6 or ty < ry + 20 or ty > ry + rh - 12:
            continue
        pildora(tx, ty, eq, 9.5, TXT, "lm")
        ocupado.append(rect)
        etiquetadas += 1

    # leyenda superpuesta (arriba al centro) y brújula
    lw = 330
    c.caja(rx + rw / 2 - lw / 2, ry + 8, lw, 34, fill=(15, 26, 44, 225), borde="#2C4666", r=8)
    T(c, rx + rw / 2 - lw / 2 + 16, ry + 25, "km/h", 13, ACENTO, "b", "lm")
    c.elipse(rx + rw / 2 - 52, ry + 25, 7, fill=ROJO, borde="#FFFFFF", ancho=2)
    T(c, rx + rw / 2 - 38, ry + 25, "Bajo (0-5)", 13, TXT, "b", "lm")
    c.caja(rx + rw / 2 + 72, ry + 18, 14, 14, fill=AZUL, borde="#FFFFFF", r=2, ancho=2)
    T(c, rx + rw / 2 + 92, ry + 25, "PALA", 13, TXT, "b", "lm")
    nx0, ny0 = rx + rw - 34, ry + rh - 40
    c.poligono([(nx0, ny0 - 16), (nx0 - 8, ny0 + 8), (nx0 + 8, ny0 + 8)], fill="#9FB1C9")
    T(c, nx0, ny0 + 18, "N", 11, "#9FB1C9", "b", "mm")


# =============================================================================================================
#  Página completa
# =============================================================================================================
def dibujar():
    d = calcular()
    c = Lienzo(W, H, BG, ss=2)
    cabecera(c, d)
    tarjetas(c, d)
    equipos_en_uso(c, d)

    # centro-derecha: mapa y tiempos de ciclo
    mapa(c, d, 1201, 155, 877, 338)
    tabla_ciclos(c, d, 2081, 155, 659, 338)

    # alimentación a chancado por origen y hora
    origenes = ["F01", "F02", "F03", "Stock_1", "Stock_2"]
    col_orig = [ROSA, VIOLETA, SALVIA, AZUL, ACERO]
    vals = [{k: v.get(o, 0) for k, v in d["chanc_origen"].items()} for o in origenes]
    vals = [{(t, i): val for (t, i), val in v.items()} for v in vals]
    grafico_horas(c, 1201, 497, 1539, 291, "ALIMENTACIÓN A CHANCADO POR ORIGEN", origenes, vals, col_orig, inicio_vacio=3,
                  unidad="t/h")

    tabla_ley(c, d, 1201, 791, 1539, 300)
    grafico_muro(c, 1201, 1094, 890, 346, d)
    resumen_flota(c, d, 2094, 1094, 646, 197, "RESUMEN FLOTA MURO", ["CAEX", "PALA"], "flota_muro")
    matriz_equipos(c, 2094, 1294, 646, 146, "CARGUÍO MURO", d["carg_muro"], rh_w=132, rh_max=34)

    # columna izquierda
    ext = {("A" if o <= 12 else "B", o if o <= 12 else o - 12): v for o, v in d["ext_h"].items()}
    rem = {("A" if o <= 12 else "B", o if o <= 12 else o - 12): v for o, v in d["rem_h"].items()}
    grafico_horas(c, 0, 315, 1197, 348, "MOVIMIENTO TONELAJE POR HORA MINA", ["Material Extraido", "Material Remanejo"],
                  [ext, rem], [TXT, VIOLETA], fmt_tot=lambda v: fmt(v / 1000, 1), unidad="kt")
    resumen_flota(c, d, 0, 665, 1197, 210, "RESUMEN FLOTA MINA", ["CAEX", "PALA", "PERFO"], "flota_mina")
    matriz_equipos(c, 0, 878, 1197, 239, "PERFORADORAS", d["perf_equipos"], rend="Rendimiento m/h", rh_w=150)
    matriz_equipos(c, 0, 1119, 1197, 321, "EQUIPO CARGUÍO MINA", d["carg_equipos"], rh_w=150)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    c.guardar(SALIDA, LEYENDA)
    return d


def reducir_si_pesa(max_kb=600):
    """Cuantización de paleta (256 colores, sin dither) si el PNG supera el peso ideal; el diseño es de colores planos."""
    kb = SALIDA.stat().st_size / 1024
    if kb <= max_kb:
        return kb
    im = Image.open(SALIDA).convert("RGB")
    q = im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q.save(SALIDA, "PNG", optimize=True)
    return SALIDA.stat().st_size / 1024


if __name__ == "__main__":
    datos = dibujar()
    kb = reducir_si_pesa()
    print(f"{SALIDA}  {Image.open(SALIDA).size}  {kb:,.0f} KB")
    print("dia:", datos["dia"], "| mov", round(datos["tonelaje_dia"]), "plan", round(datos["plan_mov_dia"]),
          "| chancado", round(datos["chancado"]), "plan", round(datos["plan_chancado"]), "| ley", round(datos["ley"], 3))
