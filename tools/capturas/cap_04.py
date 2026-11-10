# -*- coding: utf-8 -*-
"""Render 04-despacho-tiempo-real: panel técnico oscuro de 1600x900 con lo que SÍ existe en el proyecto.

Este proyecto no tiene interfaz (servidor, simulador y frontend son hoja de ruta), así que la imagen NO dibuja un
tablero: muestra
  (a) la salida real de `python -m unittest discover -s tests -t . -v` (se ejecuta al generar la imagen),
  (b) un resumen de docs/snapshot_ejemplo.json y dos gráficos con los CSV sintéticos del turno del snapshot,
  (c) la cadena de la arquitectura implementada y, en gris, la hoja de ruta.

Uso (desde cualquier carpeta):  python tools/capturas/cap_04.py
"""
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from PIL import ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib_render import Lienzo, PAL, LOGO_BLANCO, RAIZ, fmt  # noqa: E402

PROY = RAIZ / "04-despacho-tiempo-real"
SALIDA = PROY / "capturas" / "nucleo_y_tests.png"
W, H = 1600, 900

# colores propios del panel (derivados de la paleta de Minera Demo)
T_FONDO = "#0A1424"      # terminal
T_TEXTO = "#C8D3E3"
T_DIM = "#6F82A0"
T_OK = PAL["verde"]
T_MOD = PAL["azul"]
T_CLS = "#B7A5F0"
GRIS = "#7C8DA6"
VIOLETA_CLARO = "#A18CE8"


# ---------------------------------------------------------------------------------------------------------------
# Fuente monoespaciada (la librería solo trae la proporcional)
# ---------------------------------------------------------------------------------------------------------------
_mono_cache = {}


def _mono(px, bold=False):
    clave = (round(px * 2), bold)
    if clave not in _mono_cache:
        nombres = ["consolab.ttf", "courbd.ttf", "DejaVuSansMono-Bold.ttf"] if bold else \
                  ["consola.ttf", "cour.ttf", "DejaVuSansMono.ttf"]
        for n in nombres:
            try:
                _mono_cache[clave] = ImageFont.truetype(n, round(px))
                break
            except OSError:
                continue
        else:
            _mono_cache[clave] = ImageFont.load_default()
    return _mono_cache[clave]


def mono(c, x, y, txt, tam, color, bold=False, ancla="lm"):
    c.d.text((x * c.ss, y * c.ss), str(txt), font=_mono(tam * c.ss, bold), fill=color, anchor=ancla)


def ancho_mono(c, txt, tam, bold=False):
    return c.d.textlength(str(txt), font=_mono(tam * c.ss, bold)) / c.ss


# ---------------------------------------------------------------------------------------------------------------
# (a) Ejecutar los tests de verdad y leer su salida
# ---------------------------------------------------------------------------------------------------------------
def correr_tests():
    env = dict(os.environ, PYTHONPATH="backend", PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"],
                       cwd=str(PROY), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    salida = r.stderr + r.stdout
    casos_test = []
    for m in re.finditer(r"^(test\w+) \(([\w.]+)\)(.*?) \.\.\. (\w+)\s*$", salida, re.M | re.S):
        nombre, ident, _, estado = m.groups()
        partes = ident.split(".")
        casos_test.append({"nombre": nombre, "modulo": partes[1], "clase": partes[2], "estado": estado})
    ran = re.search(r"^Ran (\d+) tests? in ([\d.]+)s\s*$", salida, re.M)
    final = re.search(r"^(OK|FAILED.*)\s*$", salida, re.M)
    if not (ran and final and r.returncode == 0 and final.group(1) == "OK" and len(casos_test) == int(ran.group(1))):
        sys.exit("Los tests no pasaron o la salida no se pudo leer; no se genera la imagen.\n" + salida[-1500:])
    return casos_test, ran.group(0).strip(), final.group(1)


def armar_lineas(casos_test):
    """Lista plana de líneas: ('mod', archivo, n, clase_unica|None) / ('cls', clase, n) / ('test', nombre, estado)."""
    items = []
    modulos = []
    for p in casos_test:
        if not modulos or modulos[-1][0] != p["modulo"]:
            modulos.append((p["modulo"], []))
        modulos[-1][1].append(p)
    for modulo, ps in modulos:
        clases = []
        for p in ps:
            if not clases or clases[-1][0] != p["clase"]:
                clases.append((p["clase"], []))
            clases[-1][1].append(p)
        unica = clases[0][0] if len(clases) == 1 else None
        items.append(("mod", f"tests/{modulo}.py", len(ps), unica))
        for clase, cps in clases:
            if unica is None:
                items.append(("cls", clase, len(cps)))
            for p in cps:
                items.append(("test", p["nombre"], p["estado"], clase))
    return items


def dividir_columnas(items):
    n = len(items)
    k = (n + 1) // 2
    while items[k - 1][0] != "test":          # no dejar un encabezado huérfano al pie de la columna 1
        k -= 1
    col1, col2 = items[:k], items[k:]
    if col2 and col2[0][0] == "test":         # la clase continúa en la columna 2: se repite su encabezado
        col2 = [("cont", col2[0][3])] + col2
    return col1, col2


def dibujar_terminal(c, x, y, w, h, casos_test, ran, final):
    c.caja(x, y, w, h, fill=T_FONDO, borde=PAL["borde"], r=10)
    # barra de título
    c.caja(x, y, w, 28, fill="#12213A", r=10)
    c.caja(x, y + 16, w, 12, fill="#12213A")
    for i, col in enumerate(("#F2655F", "#F5A524", "#3FCF8E")):
        c.elipse(x + 18 + i * 18, y + 14, 5, fill=col)
    mono(c, x + 92, y + 14, "unittest · salida real · agrupada por módulo y clase", 11.5, T_DIM)
    c.linea([(x, y + 28), (x + w, y + 28)], PAL["borde"], 1)

    cmd_y = y + 44
    mono(c, x + 18, cmd_y, "$", 12.5, T_OK, bold=True)
    mono(c, x + 34, cmd_y, "PYTHONPATH=backend python -m unittest discover -s tests -t . -v", 12.5, T_TEXTO)

    items = armar_lineas(casos_test)
    col1, col2 = dividir_columnas(items)
    lh, fs = 13.5, 12.5
    y0 = y + 62
    colw = (w - 32 - 16) / 2
    anchos = [x + 16, x + 16 + colw + 16]
    for cx, col in zip(anchos, (col1, col2)):
        for i, it in enumerate(col):
            ly = y0 + i * lh + lh / 2
            tipo = it[0]
            if tipo == "mod":
                _, archivo, n, unica = it
                if i > 0:                      # filete fino para separar módulos
                    c.linea([(cx, ly - lh / 2 + 0.5), (cx + colw, ly - lh / 2 + 0.5)], "#1B2F4B", 1)
                mono(c, cx, ly, archivo, fs, T_MOD, bold=True)
                if unica:
                    mono(c, cx + ancho_mono(c, archivo, fs, True) + 8, ly, f"· {unica}", fs, T_CLS)
                mono(c, cx + colw, ly, f"{n} tests", fs - 1, T_DIM, ancla="rm")
            elif tipo in ("cls", "cont"):
                nombre = it[1] + (" (cont.)" if tipo == "cont" else "")
                mono(c, cx + 4, ly, nombre, fs, T_CLS)
                if tipo == "cls":
                    mono(c, cx + 4 + ancho_mono(c, nombre, fs) + 6, ly, f"({it[2]})", fs - 1, T_DIM)
            else:
                _, nombre, estado, _cl = it
                sx = cx + 10
                mono(c, sx, ly, nombre, fs, T_TEXTO)
                ax = sx + ancho_mono(c, nombre, fs) + ancho_mono(c, " ", fs)
                mono(c, ax, ly, "...", fs, T_DIM)
                mono(c, ax + ancho_mono(c, "... ", fs), ly, estado, fs, T_OK if estado == "ok" else PAL["rojo"],
                     bold=True)
                assert ax + ancho_mono(c, "... ok", fs) <= cx + colw + 1, f"línea demasiado ancha: {nombre}"
    # cierre real de unittest
    yb = y0 + max(len(col1), len(col2)) * lh + 10
    mono(c, x + 18, yb, "-" * 70, fs, T_DIM)
    mono(c, x + 18, yb + 15, ran, fs, T_TEXTO)
    mono(c, x + 18, yb + 38, final, 14, T_OK, bold=True)
    return yb + 46


# ---------------------------------------------------------------------------------------------------------------
# (b) Snapshot de ejemplo: tarjetas y dos gráficos
# ---------------------------------------------------------------------------------------------------------------
def tarjeta(c, x, y, w, h, titulo, valor, unidad, subs, color):
    c.caja(x, y, w, h, fill=PAL["panel"], borde=PAL["borde"], r=8)
    c.caja(x, y + 10, 4, h - 20, fill=color, r=2)
    c.texto(x + 16, y + 10, titulo, 10, PAL["texto2"], bold=True)
    c.texto(x + 16, y + 46, valor, 24, PAL["texto"], bold=True, ancla="ls")
    c.texto(x + 16 + c.ancho_texto(valor, 24, True) + 5, y + 46, unidad, 12, PAL["texto2"], ancla="ls")
    for i, s in enumerate(subs):
        c.texto(x + 16, y + 52 + i * 14, s, 10.5, PAL["texto2"])


def panel_grafico(c, x, y, w, h, titulo, fuente, cifra):
    c.caja(x, y, w, h, fill=PAL["panel"], borde=PAL["borde"], r=8)
    c.texto(x + 16, y + 12, titulo, 13, PAL["texto"], bold=True)
    mono(c, x + 16, y + 40, fuente, 10, T_DIM)
    if cifra:
        c.texto(x + w - 16, y + 12, cifra, 13, PAL["azul"], bold=True, ancla="ra")


def barras_hora(c, x, y, w, h, valores, etiquetas, tope, pasos, plan=None, fmt_val=None, dec=0):
    """Columnas por hora con rejilla; plan = marcas horizontales (opcional)."""
    n = len(valores)
    for t in pasos:
        gy = y + h - h * t / tope
        c.linea([(x, gy), (x + w, gy)], "#25405F" if t else "#3A5578", 1)
        c.texto(x - 8, gy, fmt(t, 0), 10, PAL["texto2"], ancla="rm")
    slot = w / n
    bw = slot * 0.56
    for i, v in enumerate(valores):
        bx = x + i * slot + (slot - bw) / 2
        bh = h * v / tope
        c.caja(bx, y + h - bh, bw, bh, fill=PAL["azul"], r=3)
        cima = y + h - bh
        if plan:
            py = y + h - h * plan[i] / tope
            c.linea([(bx - 7, py), (bx + bw + 7, py)], VIOLETA_CLARO, 2.5)
            cima = min(cima, py)           # la cifra va sobre lo más alto (barra o marca de plan)
        c.texto(bx + bw / 2, cima - 6, (fmt_val or (lambda q: fmt(q, dec)))(v), 11, PAL["texto"], bold=True,
                ancla="ms")
        c.texto(bx + bw / 2, y + h + 8, etiquetas[i], 10.5, PAL["texto2"], ancla="ma")


def dibujar_snapshot(c, x, y, w, snap, ciclos_h, chanc_h):
    t, tj = snap["turno"], snap["tarjetas"]
    c.texto(x, y, "Snapshot de ejemplo", 15, PAL["texto"], bold=True)
    mono(c, x + 168, y + 9, "docs/snapshot_ejemplo.json", 11, T_DIM)
    # chip de estado de datos
    chip = f"estado de datos: {snap['estado_datos']}"
    cw = c.ancho_texto(chip, 10.5, True) + 18
    c.caja(x + w - cw, y - 1, cw, 20, fill="#2B2350", borde=PAL["violeta"], r=10)
    c.texto(x + w - cw / 2, y + 9, chip, 10.5, "#CFC3F5", bold=True, ancla="mm")
    # turno + avance
    sub = (f"{t['nombre']} · {t['fecha_texto']} · {t['inicio'][11:16]}–{t['fin'][11:16]} · "
           f"{fmt(t['horas_transcurridas'], 2)} h transcurridas · {fmt(t['horas_restantes'], 2)} h restantes")
    c.texto(x, y + 30, sub, 11.5, PAL["texto2"])
    c.caja(x, y + 52, w, 6, fill="#223552", r=3)
    c.caja(x, y + 52, w * t["horas_transcurridas"] / 12, 6, fill=PAL["azul"], r=3)

    # tarjetas 3 x 2
    mm, ch, vc, eq = tj["movimiento_mina"], tj["chancado"], tj["velocidad_caex"], tj["equipos_en_uso"]["mina"]
    ci, al = snap["ciclos"]["total"], snap["alertas"]["activas"][0]
    col_estado = {"verde": PAL["verde"], "ambar": PAL["ambar"], "rojo": PAL["rojo"]}
    cw3, chh, gap = (w - 20) / 3, 80, 10
    tarjetas = [
        ("MOVIMIENTO MINA", fmt(mm["real_kt"], 1), "kt",
         [f"plan a la hora {fmt(mm['plan_a_la_hora_kt'], 1)} kt",
          f"cierre P50 {fmt(mm['cierre_p50_kt'], 1)} kt (est.)"], col_estado[mm["estado"]]),
        ("CHANCADO", fmt(ch["real_kt"], 1), "kt",
         [f"alimentación {fmt(ch['alimentacion_tph'])} t/h",
          f"plan a la hora {fmt(ch['plan_a_la_hora_kt'], 1)} kt"], col_estado[ch["estado"]]),
        ("VELOCIDAD CAEX", fmt(vc["mina_kmh"], 1), "km/h",
         [f"normal {fmt(vc['normal_kmh'], 1)} km/h · Δ {fmt(vc['delta_kmh'], 1)}",
          "turno actual vs 6 días previos"], col_estado[vc["estado"]]),
        (f"EQUIPOS EN USO · TURNO {t['turno']}", f"{eq['caex']['en_uso']}/{eq['caex']['total']}", "CAEX",
         [f"Pala {eq['pala']['en_uso']}/{eq['pala']['total']} · Cargador {eq['cargador']['en_uso']}/{eq['cargador']['total']}",
          f"Perforadora {eq['perforadora']['en_uso']}/{eq['perforadora']['total']}"], PAL["azul"]),
        (f"CICLO ORIGEN → DESTINO {t['etiqueta']}", fmt(ci["ciclos"]), "ciclos",
         [f"real {fmt(ci['real_min'], 1)} min · norma {fmt(ci['norma_min'], 1)} min",
          f"desvío +{fmt(ci['desvio_min'], 1)} min (norma est.)"], PAL["azul"]),
        ("ALERTAS ACTIVAS", str(snap["alertas"]["resumen"]["total"]), "crítica",
         [al["titulo"], f"{al['detalle']} · {al['duracion_texto']}"], PAL["rojo"]),
    ]
    ty = y + 70
    for i, (tit, val, uni, subs, col) in enumerate(tarjetas):
        tarjeta(c, x + (i % 3) * (cw3 + gap), ty + (i // 3) * (chh + gap), cw3, chh, tit, val, uni, subs, col)

    # gráficos
    gy = ty + 2 * chh + gap + 12
    gh = 218
    hs = [f"{h:02d}:00" for h in ciclos_h["horas"]]
    fecha = snap["turno"]["fecha_operacional"]
    panel_grafico(c, x, gy, w, gh, f"Ciclos por hora · {t['etiqueta']}",
                  f"ciclos_hora_pala_camion.csv · {fecha} · turno {t['turno']}",
                  f"{fmt(sum(ciclos_h['vals']))} ciclos")
    barras_hora(c, x + 50, gy + 66, w - 50 - 16, gh - 66 - 34, ciclos_h["vals"], hs, 40, [0, 10, 20, 30, 40])

    gy2 = gy + gh + 10
    gh2 = 220
    panel_grafico(c, x, gy2, w, gh2, "Alimentación a chancado · t/h",
                  f"chancado_hora.csv · {fecha} · turno {t['turno']}", None)
    # leyenda
    lx = x + w - 16
    c.texto(lx, gy2 + 14, "plan", 11, PAL["texto2"], ancla="ra")
    c.linea([(lx - 44, gy2 + 22), (lx - 26, gy2 + 22)], VIOLETA_CLARO, 2.5)
    c.texto(lx - 62, gy2 + 14, "real", 11, PAL["texto2"], ancla="ra")
    c.caja(lx - 100, gy2 + 17, 10, 10, fill=PAL["azul"], r=2)
    barras_hora(c, x + 50, gy2 + 66, w - 50 - 16, gh2 - 66 - 34, chanc_h["real"], hs, 5000,
                [0, 1000, 2000, 3000, 4000, 5000], plan=chanc_h["plan"], fmt_val=lambda v: fmt(v))
    return gy2 + gh2


# ---------------------------------------------------------------------------------------------------------------
# (c) Cadena de arquitectura
# ---------------------------------------------------------------------------------------------------------------
def flecha(c, x1, x2, y, color, dash=False):
    if dash:
        xx = x1
        while xx < x2 - 6:
            c.linea([(xx, y), (min(xx + 4, x2 - 6), y)], color, 1.6)
            xx += 8
    else:
        c.linea([(x1, y), (x2 - 6, y)], color, 2)
    c.poligono([(x2, y), (x2 - 8, y - 5), (x2 - 8, y + 5)], fill=color)


def dibujar_cadena(c, x, y, w, h):
    titulo = "Arquitectura · cadena implementada y con tests"
    c.texto(x, y, titulo, 12, PAL["texto"], bold=True)
    mono(c, x + c.ancho_texto(titulo, 12, True) + 12, y + 7, "docs/ARQUITECTURA.md", 10.5, T_DIM)
    by, bh = y + 22, h - 22
    cajas = [
        ("1", "Despacho y planta", "fuente · SQL solo lectura", "sql/ · 8 consultas"),
        ("2", "Barrera de solo lectura SQL", "login de lectura + texto SQL", "datos/solo_lectura.py"),
        ("3", "Contratos de datos", "15 datasets · validación", "contratos.py"),
        ("4", "Núcleo de turnos", "turnos A/B · reloj inyectable", "tiempo.py"),
    ]
    bw, ar = 232, 36
    for i, (n, tit, sub, arch) in enumerate(cajas):
        bx = x + i * (bw + ar)
        c.caja(bx, by, bw, bh, fill=PAL["panel2"], borde=PAL["azul"], r=8, ancho=2)
        c.elipse(bx + 20, by + 20, 10, fill=PAL["azul"])
        c.texto(bx + 20, by + 20, n, 12, PAL["azul_noche"], bold=True, ancla="mm")
        c.texto(bx + 38, by + 11, tit, 13, PAL["texto"], bold=True)
        c.texto(bx + 38, by + 31, sub, 10.5, PAL["texto2"])
        mono(c, bx + 38, by + 53, arch, 10.5, "#8FB8E6")
        if i < len(cajas) - 1:
            flecha(c, bx + bw + 6, bx + bw + ar - 4, by + bh / 2, PAL["azul"])
    # hoja de ruta, en gris
    rx = x + 4 * bw + 3 * ar + 22
    rw = x + w - rx
    flecha(c, rx - 20, rx - 4, by + bh / 2, GRIS, dash=True)
    dash_y = by
    # borde punteado
    pts = [(rx, dash_y), (rx + rw, dash_y), (rx + rw, dash_y + bh), (rx, dash_y + bh), (rx, dash_y)]
    for (ax, ay), (bx2, by2) in zip(pts, pts[1:]):
        L = max(abs(bx2 - ax), abs(by2 - ay))
        k = 0
        while k < L:
            f0, f1 = k / L, min(k + 6, L) / L
            c.linea([(ax + (bx2 - ax) * f0, ay + (by2 - ay) * f0), (ax + (bx2 - ax) * f1, ay + (by2 - ay) * f1)],
                    GRIS, 1.4)
            k += 11
    c.texto(rx + 16, by + 10, "Hoja de ruta: servidor, simulador y frontend", 13, GRIS, bold=True)
    c.texto(rx + 16, by + 31, "Programador · Motor de KPI y alertas · Servidor HTTP + SSE · Simulador y frontend",
            10.5, GRIS)
    c.texto(rx + 16, by + 50, "Diseñado en docs/ · no implementado: este repositorio no incluye interfaz", 10.5, GRIS)


# ---------------------------------------------------------------------------------------------------------------
def main():
    casos_test, ran, final = correr_tests()
    snap = json.loads((PROY / "docs" / "snapshot_ejemplo.json").read_text(encoding="utf-8"))
    t = snap["turno"]

    # series del turno del snapshot, desde los CSV sintéticos
    ciclos = {}
    for r in csv.DictReader(open(PROY / "datos_sinteticos" / "ciclos_hora_pala_camion.csv", encoding="utf-8")):
        if r["fecha"] == t["fecha_operacional"] and r["turno"] == t["turno"]:
            h = int(r["hora_reloj"])
            ciclos[h] = ciclos.get(h, 0) + int(r["ciclos"])
    horas_c = sorted(ciclos, key=lambda h: (h - 8) % 24)   # el turno A parte a las 08:00
    ciclos_h = {"horas": horas_c, "vals": [ciclos[h] for h in horas_c]}
    assert sum(ciclos_h["vals"]) == snap["ciclos"]["total"]["ciclos"], "los ciclos del CSV no cuadran con el snapshot"

    chanc = {}
    for r in csv.DictReader(open(PROY / "datos_sinteticos" / "chancado_hora.csv", encoding="utf-8")):
        if r["fecha"] == t["fecha_operacional"] and r["turno"] == t["turno"]:
            chanc[int(r["hora_reloj"])] = (int(r["alimentacion_tph"]), int(r["plan_tph"]))
    horas_h = sorted(chanc, key=lambda h: (h - 8) % 24)
    chanc_h = {"real": [chanc[h][0] for h in horas_h], "plan": [chanc[h][1] for h in horas_h]}
    assert horas_h == horas_c
    assert chanc_h["real"][-1] == snap["tarjetas"]["chancado"]["alimentacion_tph"]

    c = Lienzo(W, H, PAL["fondo"])

    # cabecera
    c.caja(0, 0, W, 56, fill="#12223A")
    c.linea([(0, 56), (W, 56)], PAL["borde"], 1)
    c.pegar(LOGO_BLANCO, 24, 14, h=28)
    c.texto(150, 12, "Despacho Mina en Tiempo Real", 19, PAL["texto"], bold=True)
    c.texto(150, 35, "Núcleo y arquitectura · sin interfaz todavía: servidor, simulador y frontend son hoja de ruta",
            11.5, PAL["texto2"])
    n = len(casos_test)
    chips = [(f"{n} tests · OK", PAL["verde"], "#123B2F"), ("datos 100 % sintéticos", PAL["violeta"], "#2B2350")]
    cx = W - 24
    for txt, col, bg in chips:
        cw = c.ancho_texto(txt, 11.5, True) + 24
        cx -= cw
        c.caja(cx, 16, cw, 24, fill=bg, borde=col, r=12)
        c.texto(cx + cw / 2, 28, txt, 11.5, "#FFFFFF" if col != PAL["verde"] else "#8CF0C4", bold=True, ancla="mm")
        cx -= 10

    # (a) terminal  y  (b) snapshot
    TY, TH = 68, 700
    dibujar_terminal(c, 24, TY, 960, TH, casos_test, ran, final)
    dibujar_snapshot(c, 1008, TY, 568, snap, ciclos_h, chanc_h)

    # (c) cadena de arquitectura
    dibujar_cadena(c, 24, 782, 1552, 90)

    c.guardar(SALIDA, "Salida real del núcleo · datos sintéticos · Minera Demo")
    print(SALIDA, f"{SALIDA.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
