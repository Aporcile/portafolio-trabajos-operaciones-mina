# -*- coding: utf-8 -*-
"""Generador de datos sintéticos del dashboard de despacho (100 % ficticios, empresa Minera Demo).

Todo sale de la semilla fija de tools/sinteticos.py: dos ejecuciones producen archivos idénticos.

Periodo: 90 días desde 2025-03-03. El "ahora" del snapshot es el último día del periodo (15:03:10);
las series históricas contienen solo horas completas. El detalle por equipo (ciclos y velocidad) cubre
los últimos 7 días; las series agregadas (chancado, granulometría, gaviota) cubren los 90.

Salidas (CSV y JSON):
  datos_sinteticos/equipos.csv                  catálogo (contrato `equipos`)
  datos_sinteticos/gps.csv                      últimas posiciones (contrato `gps`) en el instante del snapshot
  datos_sinteticos/ciclos_hora_pala_camion.csv  ciclos por hora, carguío y camión
  datos_sinteticos/velocidad_caex_hora.csv      velocidad media (15-30 km/h) por hora y camión
  datos_sinteticos/chancado_hora.csv            alimentación a chancado en t/h (3.200-4.800) y plan
  datos_sinteticos/granulometria_hora.csv       granulometría en 3 fracciones (~60/20/20)
  datos_sinteticos/plan_gaviota_hora.csv        plan vs real por hora (curva gaviota)
  docs/snapshot_ejemplo.json                    snapshot completo del instante AHORA

Uso:
  python datos_sinteticos/generar_datos.py [--salida DIR] [--docs DIR]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
RAIZ_REPO = RAIZ_PROYECTO.parent
sys.path.insert(0, str(RAIZ_REPO / "tools"))
sys.path.insert(0, str(RAIZ_PROYECTO / "backend"))

import sinteticos as sin  # noqa: E402
from despacho import config, tiempo  # noqa: E402

INICIO = date(2025, 3, 3)
DIAS = 90
DIAS_DETALLE = 7
AHORA = datetime(2025, 5, 31, 15, 3, 10)   # instante del snapshot (hora local)
# Detención sintética de un equipo de carguío: desde el minuto indicado de la hora `orden` del último día.
EVENTO = {"equipo": "PALA-03", "orden": 7, "minutos": 10}
# Ruta lenta sintética: los ciclos de ese carguío se alargan desde la hora `orden` del último día.
CONGESTION = {"pala": "PALA-02", "orden": 5, "factor": 1.25}

FLOTAS = {"Truck": "CAEX 220 t", "Shovel": "Pala hidráulica", "Loader": "Cargador frontal",
          "Drill": "Perforadora rotatoria"}
TIPO_CORTO = {"Truck": "caex", "Shovel": "pala", "Loader": "cargador", "Drill": "perforadora"}
Z90 = 1.2816  # cuantil 90 de la normal estándar
SESGO_MEZCLA = {"Fase 1": 0.88, "Fase 2": 1.15}   # desvío sintético de la mezcla real respecto del plan


# ---------------------------------------------------------------------------
# Utilidades de tiempo (hora operacional: orden 1 = 08:00 ... 24 = 07:00 del día siguiente)
# ---------------------------------------------------------------------------
def inicio_hora(d: date, orden: int) -> datetime:
    return datetime(d.year, d.month, d.day, 8) + timedelta(hours=orden - 1)


def completa(d: date, orden: int) -> bool:
    return inicio_hora(d, orden) + timedelta(hours=1) <= AHORA


def info_hora(orden: int) -> tuple[str, int, int]:
    """(turno, hora_turno 1..12, hora de reloj 0..23) de una hora operacional."""
    turno = "A" if orden <= 12 else "B"
    return turno, (orden if orden <= 12 else orden - 12), (8 + orden - 1) % 24


# ---------------------------------------------------------------------------
# Simulación
# ---------------------------------------------------------------------------
@dataclass
class Datos:
    camiones: list[str]
    cargas: list[str]
    rutas: dict
    destinos: dict
    base_min: dict
    pesos: list[float]
    fracciones: list[float]
    plan_mov_dia_kt: float
    plan_chancado_dia_kt: float
    real_kt: dict = field(default_factory=dict)       # fecha -> [24] kt por hora operacional
    tph: dict = field(default_factory=dict)           # fecha -> [24] alimentación a chancado (t/h)
    gran: dict = field(default_factory=dict)          # fecha -> [24] {fraccion: %}
    ciclos: list = field(default_factory=list)        # filas de ciclos (toneladas ya escaladas)
    velocidad: list = field(default_factory=list)     # una fila por camión-hora disponible
    uebd_camion: dict = field(default_factory=dict)   # (fecha, camion) -> fracción UEBD
    asignacion_final: dict = field(default_factory=dict)  # camión -> carguío en la última hora del último día


def _largo(puntos: list) -> float:
    return sum(math.dist(a, b) for a, b in zip(puntos, puntos[1:]))


def preparar(cfg) -> Datos:
    dash = cfg.dashboard
    pesos = list(cfg.plan_horario["turno_A"]["pesos"]) + list(cfg.plan_horario["turno_B"]["pesos"])
    rep = cfg.plan_horario["reparto_turnos"]
    fracciones = [rep["A"] * p for p in pesos[:12]] + [rep["B"] * p for p in pesos[12:]]
    excluidos = set(dash["equipos"]["excluidos"])
    rutas = {r["origen"]: r for r in cfg.mapa["rutas"]}
    return Datos(
        camiones=[c for c in sin.FLOTA_CAEX if c not in excluidos],
        cargas=sin.FLOTA_PALAS + sin.FLOTA_CARGADORES,
        rutas=rutas,
        destinos={d["nombre"]: d for d in cfg.mapa["destinos"]},
        base_min={k: round(20 + 30 * _largo(v["puntos"]), 1) for k, v in rutas.items()},
        pesos=pesos,
        fracciones=fracciones,
        plan_mov_dia_kt=dash["planes_por_defecto"]["movimiento_mina_kt_dia"],
        plan_chancado_dia_kt=dash["planes_por_defecto"]["chancado_kt_dia"],
    )


def _real_agregado(r, total_kt: float, pesos: list[float]) -> list[float]:
    """Perfil horario del día repartido según el perfil plan con ruido, sumando el total del día."""
    ruido = [p * r.uniform(0.88, 1.12) for p in pesos]
    s = sum(ruido)
    return [round(total_kt * x / s, 2) for x in ruido]


def _simular_detalle(d: date, datos: Datos, total_kt: float, es_ultimo: bool) -> list[float]:
    """Ciclos y velocidad por camión-hora de un día; devuelve los kt por hora (suman total_kt)."""
    r = sin.rng(f"ciclos:{d}")
    df, uebd = {}, {}
    for c in datos.camiones:
        h = sin.horas_equipo(r, "CAEX")
        df[c], uebd[c] = h["df_pct"] / 100, h["uebd_pct"] / 100
        datos.uebd_camion[(d, c)] = uebd[c]
    pesos_carga = [3 if x.startswith("PALA") else 2 for x in datos.cargas]
    asign = {t: {c: r.choices(datos.cargas, weights=pesos_carga)[0] for c in datos.camiones} for t in ("A", "B")}

    filas, filas_vel = [], []
    for orden in range(1, 25):
        turno, hora_turno, hora_reloj = info_hora(orden)
        fh = datos.pesos[orden - 1] * 12          # factor de utilización de la hora (cae en pausas)
        if es_ultimo and orden == EVENTO["orden"] + 1:  # el equipo detenido deja sus camiones a otros
            otros = [x for x in datos.cargas if x != EVENTO["equipo"]]
            for c in datos.camiones:
                if asign[turno][c] == EVENTO["equipo"]:
                    asign[turno][c] = r.choice(otros)
        for c in datos.camiones:
            if r.random() >= df[c]:
                continue                           # camión no disponible esta hora
            pala = asign[turno][c]
            factor = 1.0
            if es_ultimo and pala == EVENTO["equipo"] and orden == EVENTO["orden"]:
                factor = EVENTO["minutos"] / 60    # sigue operando solo hasta que se detiene
            ciclo_min = max(20.0, r.gauss(datos.base_min[pala], 2.0))
            if es_ultimo and pala == CONGESTION["pala"] and orden >= CONGESTION["orden"]:
                ciclo_min *= CONGESTION["factor"]
            n = int(60 * uebd[c] * fh * factor / ciclo_min + r.random())
            v_carg, v_vac = sin.velocidad_caex(r, True), sin.velocidad_caex(r, False)
            base = {"fecha": d.isoformat(), "hora_inicio": inicio_hora(d, orden).isoformat(),
                    "turno": turno, "hora_turno": hora_turno, "hora_reloj": hora_reloj, "orden": orden}
            filas_vel.append({**base, "camion": c, "velocidad_cargado_kmh": v_carg,
                              "velocidad_vacio_kmh": v_vac, "velocidad_media_kmh": round((v_carg + v_vac) / 2, 1)})
            if n > 0:
                filas.append({**base, "pala": pala, "camion": c, "destino": datos.rutas[pala]["destino"],
                              "ciclos": n, "tiempo_ciclo_min": round(ciclo_min, 1),
                              "toneladas": n * r.uniform(205, 235)})
        if es_ultimo and inicio_hora(d, orden) <= AHORA < inicio_hora(d, orden) + timedelta(hours=1):
            datos.asignacion_final = dict(asign[turno])   # asignación vigente en el instante del snapshot

    # Escala las toneladas para que el día sume exactamente el movimiento diario sintético.
    suma = sum(f["toneladas"] for f in filas)
    escala = total_kt * 1000 / suma
    por_hora = [0.0] * 24
    for f in filas:
        f["toneladas"] = round(f["toneladas"] * escala, 1)
        por_hora[f["orden"] - 1] += f["toneladas"] / 1000
    datos.ciclos.extend(filas)
    datos.velocidad.extend(filas_vel)
    return [round(x, 2) for x in por_hora]


def simular(cfg) -> Datos:
    datos = preparar(cfg)
    dias = sin.dias(INICIO, DIAS)
    primer_detalle = dias[-DIAS_DETALLE]
    for d in dias:
        total_kt = sin.movimiento_mina_dia(sin.rng(f"movimiento:{d}"))["total_kt"]
        if d >= primer_detalle:
            datos.real_kt[d] = _simular_detalle(d, datos, total_kt, es_ultimo=(d == dias[-1]))
        else:
            datos.real_kt[d] = _real_agregado(sin.rng(f"perfil:{d}"), total_kt, datos.pesos)
        r = sin.rng(f"chancado:{d}")
        datos.tph[d] = [int(sin.chancado_tph(r, info_hora(o)[2])) for o in range(1, 25)]
        datos.gran[d] = [sin.granulometria(r) for _ in range(24)]
    return datos


# ---------------------------------------------------------------------------
# Posiciones (GPS y mapa)
# ---------------------------------------------------------------------------
def _punto_en_ruta(puntos: list, t: float) -> tuple[float, float]:
    """Punto a la fracción t (0..1) del largo de una polilínea."""
    objetivo, recorrido = t * _largo(puntos), 0.0
    for a, b in zip(puntos, puntos[1:]):
        tramo = math.dist(a, b)
        if recorrido + tramo >= objetivo and tramo > 0:
            u = (objetivo - recorrido) / tramo
            return a[0] + u * (b[0] - a[0]), a[1] + u * (b[1] - a[1])
        recorrido += tramo
    return tuple(puntos[-1])


def _xy_a_geo(cal: dict, x: float, y: float) -> tuple[float, float]:
    lat = cal["lat_max"] - y * (cal["lat_max"] - cal["lat_min"])
    lon = cal["lon_min"] + x * (cal["lon_max"] - cal["lon_min"])
    return lat, lon


def posiciones(cfg, datos: Datos) -> list[dict]:
    """Última posición de cada equipo disponible en el instante AHORA (camiones sobre su ruta)."""
    r = sin.rng("posiciones")
    cal = cfg.mapa["calibracion"]
    mas = cal["milisegundos_arco_por_grado"]
    frentes = {f["nombre"]: f for f in cfg.mapa["frentes"]}
    disponibles = {f["camion"] for f in datos.velocidad
                   if f["fecha"] == AHORA.date().isoformat() and f["orden"] == 8}
    salida = []

    def agregar(nombre, tipo_equipo, x, y, vel, cargado=False, pala=None):
        lat, lon = _xy_a_geo(cal, x, y)
        salida.append({"equipo": nombre, "tipo_equipo": tipo_equipo, "tipo": TIPO_CORTO[tipo_equipo],
                       "x": round(x, 3), "y": round(y, 3), "lat": round(lat, 5), "lon": round(lon, 5),
                       "latitud_mas": round(lat * mas), "longitud_mas": round(lon * mas),
                       "velocidad_kmh": vel, "cargado": cargado, "pala": pala,
                       "segundos_atras": r.randint(2, 25)})

    for c in datos.camiones:
        if c not in disponibles:
            continue
        pala = datos.asignacion_final[c]
        puntos = datos.rutas[pala]["puntos"]
        if r.random() < 0.12:                       # cargando en el frente
            x, y = frentes[pala]["x"], frentes[pala]["y"]
            agregar(c, "Truck", x, y, 0.0, False, pala)
        else:
            cargado = r.random() < 0.5
            x, y = _punto_en_ruta(puntos, r.uniform(0.08, 0.95))
            agregar(c, "Truck", x, y, sin.velocidad_caex(r, cargado), cargado, pala)
    for nombre in datos.cargas:
        f = frentes[nombre]
        tipo = "Shovel" if nombre.startswith("PALA") else "Loader"
        agregar(nombre, tipo, f["x"], f["y"], 0.0)
    for nombre in sin.FLOTA_PERFORADORAS:
        agregar(nombre, "Drill", r.uniform(0.10, 0.50), r.uniform(0.15, 0.85), 0.0)
    return salida


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------
def proyectar(real: float, plan_dia: float, plan_acum: float, orden: int, frac: float,
              ritmo_reciente: float, proy: dict) -> dict:
    """Cierre probable del día: real + horas restantes × ritmo esperado (mezcla de ritmo reciente y plan)."""
    horas_rest = 24 - (orden - 1 + frac)
    ritmo_plan = (plan_dia - plan_acum) / horas_rest
    ritmo = proy["peso_reciente"] * ritmo_reciente + (1 - proy["peso_reciente"]) * ritmo_plan
    p50 = real + horas_rest * ritmo
    cv = min(max(proy["cv_maximo"] * horas_rest / 24, proy["cv_minimo"]), proy["cv_maximo"])
    sigma = max(cv * (p50 - real), 1e-6)
    prob = 1 - 0.5 * (1 + math.erf((plan_dia - p50) / (sigma * math.sqrt(2))))
    return {"cierre_p50_kt": round(p50, 1), "cierre_p10_kt": round(p50 - Z90 * sigma, 1),
            "cierre_p90_kt": round(p50 + Z90 * sigma, 1), "prob_cumplir": round(prob, 2)}


def _iso(naive: datetime) -> str:
    return tiempo.iso(tiempo.a_local(naive))


def construir_snapshot(cfg, datos: Datos, pos: list[dict]) -> dict:
    dash = cfg.dashboard
    ahora = tiempo.a_local(AHORA)
    t = tiempo.turno_de(ahora)
    dia = t.fecha_operacional
    desplaz = 0 if t.turno == "A" else 12
    orden_act = desplaz + t.hora_turno
    frac = (ahora - tiempo.a_local(inicio_hora(dia, orden_act))).total_seconds() / 3600
    iso_dia = dia.isoformat()
    proy = dash["proyeccion"]

    def acum(valores):     # acumulado del día operacional hasta AHORA (hora actual proporcional)
        return sum(v if o < orden_act else v * frac for o, v in enumerate(valores, 1) if o <= orden_act)

    # ---- movimiento mina -------------------------------------------------
    real = datos.real_kt[dia]
    plan_h = [round(datos.plan_mov_dia_kt * f, 2) for f in datos.fracciones]
    real_dia, plan_acum = acum(real), acum(plan_h)
    recientes = real[orden_act - 1 - proy["horas_recientes"]: orden_act - 1]
    mov = {"titulo": "Movimiento Mina", "unidad": "kt", "real_kt": round(real_dia, 1),
           "turno_kt": round(sum(v if o < orden_act else v * frac for o, v in enumerate(real, 1)
                                 if desplaz < o <= orden_act), 1),
           "plan_dia_kt": datos.plan_mov_dia_kt, "plan_a_la_hora_kt": round(plan_acum, 1),
           **proyectar(real_dia, datos.plan_mov_dia_kt, plan_acum, orden_act, frac,
                       sum(recientes) / len(recientes), proy)}
    mov["estado"] = sin.semaforo(mov["cierre_p50_kt"], datos.plan_mov_dia_kt)
    mov["fuente"] = "horas_equipo.MovimientoTotal (Truck) · plan_caex.ToneladasPlan"
    mov["estimado"] = ["cierre_p50_kt", "cierre_p10_kt", "cierre_p90_kt", "prob_cumplir"]

    # ---- chancado -------------------------------------------------------
    tph_kt = [x / 1000 for x in datos.tph[dia]]
    plan_ch_h = [round(datos.plan_chancado_dia_kt * f, 2) for f in datos.fracciones]
    ch_dia, ch_plan_acum = acum(tph_kt), acum(plan_ch_h)
    rec_ch = tph_kt[orden_act - 1 - proy["horas_recientes"]: orden_act - 1]
    chancado = {"titulo": "Chancado", "unidad": "kt", "real_kt": round(ch_dia, 1),
                "plan_dia_kt": datos.plan_chancado_dia_kt, "plan_a_la_hora_kt": round(ch_plan_acum, 1),
                "alimentacion_tph": datos.tph[dia][orden_act - 2],
                **proyectar(ch_dia, datos.plan_chancado_dia_kt, ch_plan_acum, orden_act, frac,
                            sum(rec_ch) / len(rec_ch), proy)}
    chancado["estado"] = sin.semaforo(chancado["cierre_p50_kt"], datos.plan_chancado_dia_kt)
    chancado["fuente"] = "chancado_hora.Tonelaje · plan_chancador.ToneladasPlan"
    chancado["estimado"] = ["cierre_p50_kt", "cierre_p10_kt", "cierre_p90_kt", "prob_cumplir"]

    # ---- velocidad CAEX (promedio en movimiento del turno vs mismas horas de los días previos) ----
    rango = range(desplaz + 1, orden_act)
    def vel_media(fecha_iso):
        v = [f["velocidad_media_kmh"] for f in datos.velocidad if f["fecha"] == fecha_iso and f["orden"] in rango]
        return sum(v) / len(v)
    previos = [(dia - timedelta(days=k)).isoformat() for k in range(1, DIAS_DETALLE)]
    vel, normal = vel_media(iso_dia), sum(vel_media(p) for p in previos) / len(previos)
    velocidad = {"titulo": "Velocidad CAEX", "unidad": "km/h", "mina_kmh": round(vel, 1), "normal_kmh": round(normal, 1),
                 "delta_kmh": round(vel - normal, 1), "estado": sin.semaforo(vel, normal),
                 "fuente": "velocidad_hora: SumaVelocidadMovimiento / LecturasMovimiento (turno actual) · normal = mismas horas de los 6 días previos",
                 "estimado": ["normal_kmh"]}

    # ---- equipos en uso (camiones disponibles en la hora vigente) -------------
    disp = {f["camion"] for f in datos.velocidad if f["fecha"] == iso_dia and f["orden"] == orden_act}
    cargas_uso = {datos.asignacion_final[c] for c in disp}
    en_uso = {"titulo": f"Equipos en uso · turno {t.turno}",
              "mina": {"caex": {"en_uso": len(disp), "total": len(datos.camiones)},
                       "pala": {"en_uso": len([c for c in cargas_uso if c.startswith("PALA") and c != EVENTO["equipo"]]),
                                "total": len(sin.FLOTA_PALAS)},
                       "cargador": {"en_uso": len([c for c in cargas_uso if c.startswith("CARG")]),
                                    "total": len(sin.FLOTA_CARGADORES)},
                       "perforadora": {"en_uso": 3, "total": len(sin.FLOTA_PERFORADORAS)}},
              "fuente": "horas_equipo: HorasOperativas > 0 en la hora vigente"}

    # ---- gaviota -------------------------------------------------------------
    def horas_turno(fecha, desp, hasta_orden=None):
        salida = []
        for ht in range(1, 13):
            o = desp + ht
            kt = datos.real_kt[fecha][o - 1]
            if hasta_orden is not None and o > hasta_orden:
                kt = None
            elif hasta_orden is not None and o == hasta_orden:
                kt = round(kt * frac, 2)
            salida.append({"hora_turno": ht, "hora_reloj": info_hora(o)[2], "kt": kt,
                           "completa": hasta_orden is None or o < hasta_orden})
        return salida
    actual = horas_turno(dia, desplaz, orden_act)
    acumulado, s = [], 0.0
    for h in actual:
        if h["kt"] is None:
            acumulado.append(None)
        else:
            s += h["kt"]
            acumulado.append(round(s, 1))
    anterior = dia - timedelta(days=1) if t.turno == "A" else dia
    ant = horas_turno(anterior, 12 if t.turno == "A" else 0)
    gaviota = {"titulo": "Gaviota", "turno_actual": {"etiqueta": t.etiqueta_corta, "total_kt": acumulado[t.hora_turno - 1], "horas": actual},
               "turno_anterior": {"etiqueta": f"T{'B' if t.turno == 'A' else 'A'} del {anterior.day}",
                                  "total_kt": round(sum(h["kt"] for h in ant), 1), "horas": ant},
               "plan_horas_kt": plan_h[desplaz: desplaz + 12], "acumulado_kt": acumulado,
               "fuente": "horas_equipo.MovimientoTotal por hora · plan = plan_dia × perfil horario (config/plan_horario.toml)"}

    # ---- ciclos por ruta (turno actual, horas completas) vs norma de los días previos --------
    def ciclos_ruta(fecha_iso):
        acc = {}
        for f in datos.ciclos:
            if f["fecha"] == fecha_iso and desplaz < f["orden"] < orden_act:
                a = acc.setdefault(f["pala"], {"n": 0, "min": 0.0, "t": 0.0})
                a["n"] += f["ciclos"]; a["min"] += f["ciclos"] * f["tiempo_ciclo_min"]; a["t"] += f["toneladas"]
        return acc
    hoy = ciclos_ruta(iso_dia)
    hist = {}
    for p in previos:
        for pala, a in ciclos_ruta(p).items():
            h = hist.setdefault(pala, {"n": 0, "min": 0.0})
            h["n"] += a["n"]; h["min"] += a["min"]
    rutas = []
    for pala, a in sorted(hoy.items(), key=lambda kv: -kv[1]["n"]):
        if a["n"] < dash["ciclos"]["minimo_ciclos_ruta"]:
            continue
        real_min = a["min"] / a["n"]
        norma = hist[pala]["min"] / hist[pala]["n"] if pala in hist else dash["ciclos"]["norma_por_defecto_min"]
        ton_medio = a["t"] / a["n"]
        rutas.append({"origen": pala, "destino": datos.rutas[pala]["destino"],
                      "tipo_destino": datos.destinos[datos.rutas[pala]["destino"]]["tipo"], "ciclos": a["n"],
                      "real_min": round(real_min, 1), "norma_min": round(norma, 1),
                      "desvio_min": round(real_min - norma, 1),
                      "kt_delta": round(-(real_min - norma) * a["n"] * ton_medio / real_min / 1000, 1) + 0.0})
    total_n = sum(x["ciclos"] for x in rutas)
    ciclos = {"titulo": f"Ciclo origen → destino {t.etiqueta_corta}",
              "rutas": rutas[: dash["ciclos"]["rutas_visibles"]],
              "total": {"ciclos": total_n,
                        "real_min": round(sum(x["real_min"] * x["ciclos"] for x in rutas) / total_n, 1),
                        "norma_min": round(sum(x["norma_min"] * x["ciclos"] for x in rutas) / total_n, 1)},
              "fuente": "ciclos: promedio del ciclo por ruta · norma = promedio de las mismas horas en los 6 días previos (estimado)",
              "estimado": ["norma_min", "kt_delta"]}
    ciclos["total"]["desvio_min"] = round(ciclos["total"]["real_min"] - ciclos["total"]["norma_min"], 1)

    # ---- flota (real del día vs plan por defecto) -----------------------------
    pd = dash["planes_por_defecto"]
    r = sin.rng("flota")
    df_c = [f for f in datos.velocidad if f["fecha"] == iso_dia and f["orden"] < orden_act]
    horas_disp = len(df_c)
    df_caex = 100 * horas_disp / (len(datos.camiones) * (orden_act - 1))
    uebd_caex = 100 * sum(datos.uebd_camion[(dia, c)] for c in datos.camiones) / len(datos.camiones)
    ton_dia = sum(f["toneladas"] for f in datos.ciclos if f["fecha"] == iso_dia and f["orden"] < orden_act)
    rend_caex = ton_dia / (horas_disp * uebd_caex / 100)
    h_palas = [sin.horas_equipo(r, "PALA") for _ in datos.cargas]
    h_perf = [sin.horas_equipo(r, "PERF") for _ in sin.FLOTA_PERFORADORAS]
    media = lambda xs: sum(xs) / len(xs)
    df_p, ue_p = media([h["df_pct"] for h in h_palas]), media([h["uebd_pct"] for h in h_palas])
    flota = {"titulo": "Flota · real del día vs plan", "filas": [
        {"flota": "CAEX", "df_pct": round(df_caex, 1), "df_plan_pct": pd["df_caex_pct"], "uebd_pct": round(uebd_caex, 1),
         "uebd_plan_pct": pd["uebd_caex_pct"], "rend": round(rend_caex), "rend_plan": pd["rend_caex_tph"], "rend_unidad": "t/h"},
        {"flota": "Carguío", "df_pct": round(df_p, 1), "df_plan_pct": pd["df_palas_pct"], "uebd_pct": round(ue_p, 1),
         "uebd_plan_pct": pd["uebd_palas_pct"], "rend": round(ton_dia / (len(datos.cargas) * (orden_act - 1) * df_p / 100 * ue_p / 100)),
         "rend_plan": pd["rend_palas_tph"], "rend_unidad": "t/h"},
        {"flota": "Perforación", "df_pct": round(media([h["df_pct"] for h in h_perf]), 1), "df_plan_pct": pd["df_perfo_pct"],
         "uebd_pct": round(media([h["uebd_pct"] for h in h_perf]), 1), "uebd_plan_pct": pd["uebd_perfo_pct"],
         "rend": round(r.uniform(16, 26), 1), "rend_plan": pd["rend_perfo_mph"], "rend_unidad": "m/h"}],
        "fuente": "horas_equipo (día operacional): DF = Disponibles/Nominales · UEBD = Efectivas/Disponibles · Rend = Tonelaje/Efectivas"}

    # ---- chancado: acumulado por hora, mezcla por origen y granulometría --------
    mezcla = dash["chancado"]["mezcla_plan"]
    rm = sin.rng(f"mezcla:{iso_dia}")
    horas_ch, acu_origen, acu = [], {k: 0.0 for k in mezcla}, 0.0
    for ht in range(1, t.hora_turno):
        o = desplaz + ht
        w = {k: v * SESGO_MEZCLA.get(k, 1.0) * rm.uniform(0.85, 1.15) for k, v in mezcla.items()}
        sw = sum(w.values())
        for k in w:
            acu_origen[k] += tph_kt[o - 1] * w[k] / sw
        acu += tph_kt[o - 1]
        horas_ch.append({"hora_turno": ht, "acumulado_kt": round(acu, 1),
                         "por_origen": {k: round(v, 1) for k, v in acu_origen.items()}})
    total_o = sum(acu_origen.values())
    origenes = [{"origen": k, "real_pct": round(100 * acu_origen[k] / total_o), "plan_pct": round(100 * mezcla[k])}
                for k in mezcla]
    ultimas = datos.gran[dia][orden_act - 4: orden_act - 1]
    gran = {k: round(media([g[k] for g in ultimas]), 1) for k in sin.FRACCIONES}
    chancado_det = {"titulo": f"Chancado {t.etiqueta_corta} acumulado", "acumulado_kt": round(acu, 1),
                    "plan_a_la_hora_kt": round(sum(plan_ch_h[desplaz: orden_act - 1]), 1),
                    "horas": horas_ch, "origenes": origenes,
                    "adherencia_pct": round(100 - 0.5 * sum(abs(o["real_pct"] - o["plan_pct"]) for o in origenes)),
                    "granulometria_pct": gran,
                    "fuente": "chancado_hora.Tonelaje acumulado por HoraTurno y Origen · granulometría: promedio de las últimas 3 horas",
                    "estimado": ["adherencia_pct", "granulometria_pct"]}

    # ---- equipos y mapa --------------------------------------------------------
    por_equipo = {p["equipo"]: p for p in pos}
    kt_equipo = {}
    for f in datos.ciclos:
        if f["fecha"] == iso_dia and desplaz < f["orden"] < orden_act:
            for k in (f["camion"], f["pala"]):
                kt_equipo[k] = kt_equipo.get(k, 0.0) + f["toneladas"] / 1000
    desde_evento = inicio_hora(dia, EVENTO["orden"]) + timedelta(minutes=EVENTO["minutos"])
    caidos = {EVENTO["equipo"]: ("DemoraOperacional", "Demora operacional", desde_evento)}
    sin_gps = next((c for c in datos.camiones if c not in disp), None)
    if sin_gps:
        caidos[sin_gps] = ("MantencionNoProgramada", "Mantención no programada", inicio_hora(dia, orden_act) - timedelta(hours=2, minutes=20))
    lista = []
    for nombre in dict.fromkeys([EVENTO["equipo"], "PALA-01", "CARG-01", datos.camiones[0], sin_gps]):
        if nombre is None:
            continue
        p = por_equipo.get(nombre)
        cat, motivo, desde = caidos.get(nombre, ("Operativo", None, inicio_hora(dia, orden_act) - timedelta(minutes=37)))
        tipo = "Truck" if nombre.startswith("CAEX") else ("Shovel" if nombre.startswith("PALA") else "Loader")
        lista.append({"equipo": nombre, "tipo": TIPO_CORTO[tipo], "tipo_equipo": tipo,
                      "estado": {"Operativo": "operativo", "DemoraOperacional": "demora",
                                 "MantencionNoProgramada": "mantencion"}[cat],
                      "categoria": cat, "motivo": motivo, "desde": _iso(desde),
                      "minutos_en_estado": int((AHORA - desde).total_seconds() // 60),
                      "kt_turno": round(kt_equipo.get(nombre, 0.0), 1),
                      "velocidad_kmh": p["velocidad_kmh"] if p else None,
                      "ultimo_gps": _iso(AHORA - timedelta(seconds=p["segundos_atras"])) if p and nombre != sin_gps else None})
    mapa_eq = []
    for p in pos:
        if p["tipo"] == "perforadora":
            continue
        mapa_eq.append({"equipo": p["equipo"], "tipo": p["tipo"], "x": p["x"], "y": p["y"], "lat": p["lat"], "lon": p["lon"],
                        "velocidad_kmh": p["velocidad_kmh"], "cargado": p["cargado"],
                        "estado": "demora" if p["equipo"] == EVENTO["equipo"] else "operativo",
                        "alerta_id": "al-0001" if p["equipo"] == EVENTO["equipo"] else None})
    frentes = [{"nombre": f["nombre"], "x": f["x"], "y": f["y"], "kt": round(kt_equipo.get(f["nombre"], 0.0), 1)}
               for f in cfg.mapa["frentes"]]
    vel_ruta = {}
    for p in pos:
        if p["tipo"] == "caex" and p["pala"]:
            vel_ruta.setdefault(p["pala"], []).append(p["velocidad_kmh"])
    mapa = {"equipos": mapa_eq, "frentes": frentes, "destinos": cfg.mapa["destinos"],
            "rutas": [{"id": f"{r['origen']}-{r['destino']}", "puntos": r["puntos"],
                       "velocidad_kmh": round(media(vel_ruta[r["origen"]]), 1) if r["origen"] in vel_ruta else None,
                       "estado": "normal"} for r in cfg.mapa["rutas"]],
            "calibracion": cfg.mapa["calibracion"],
            "nota": "coordenadas ficticias: no corresponden a ninguna faena real"}

    # ---- alerta sintética coherente con los datos -------------------------------
    ritmo_pala = sum(f["toneladas"] for f in datos.ciclos
                     if f["fecha"] == iso_dia and f["pala"] == EVENTO["equipo"] and f["orden"] < EVENTO["orden"]) / 1000 / (EVENTO["orden"] - 1)
    dur_min = int((AHORA - desde_evento).total_seconds() // 60)
    alertas = {"activas": [{
        "id": "al-0001", "regla": "equipo_detenido", "severidad": "critica", "estado": "activa",
        "clave": EVENTO["equipo"], "equipo": EVENTO["equipo"], "tipo_equipo": "Shovel",
        "titulo": f"{EVENTO['equipo']} detenida", "detalle": "Demora operacional",
        "desde": _iso(desde_evento), "duracion_min": dur_min, "duracion_texto": tiempo.duracion_texto(dur_min),
        "impacto_kt": -round(ritmo_pala * dur_min / 60, 1),
        "valor": dur_min, "umbral": 30, "unidad": "min",
        "accion": f"Evaluar el estado de {EVENTO['equipo']} y reasignar sus camiones mientras tanto.",
        "reconocida_en": None, "reconocida_por": None}],
        "resumen": {"criticas": 1, "altas": 0, "medias": 0, "informativas": 0, "total": 1}}

    # ---- encabezado --------------------------------------------------------------
    n_ciclos = sum(f["ciclos"] for f in datos.ciclos
                   if completa(date.fromisoformat(f["fecha"]), f["orden"])
                   and datetime.fromisoformat(f["hora_inicio"]) >= inicio_hora(dia, 1) - timedelta(hours=12))
    consultas = {
        "horas_equipo": {"ok": True, "filas": len(datos.camiones) * (orden_act - 1), "ms": 38},
        "ciclos": {"ok": True, "filas": n_ciclos, "ms": 52},
        "gps": {"ok": True, "filas": len(pos), "ms": 12},
        "chancado_hora": {"ok": True, "filas": 4 * orden_act, "ms": 21},
    }
    for c in consultas.values():
        c["actualizado"], c["error"] = _iso(AHORA - timedelta(seconds=5)), None
    ultimo = AHORA - timedelta(seconds=20)
    return {
        "version": 1, "generado": tiempo.iso(ahora), "modo": "demo", "estado_datos": "DEMO",
        "fuente": {"nombre": dash["general"]["fuente_nombre"], "ultimo_dato": _iso(ultimo),
                   "edad_s": int((AHORA - ultimo).total_seconds()),
                   "detalle": f"datos sintéticos · semilla {sin.SEMILLA}", "consultas": consultas},
        "turno": {"fecha_operacional": iso_dia, "fecha_texto": tiempo.fecha_texto(dia), "turno": t.turno,
                  "nombre": t.nombre, "etiqueta": t.etiqueta_corta, "inicio": tiempo.iso(t.inicio), "fin": tiempo.iso(t.fin),
                  "hora_turno": t.hora_turno, "horas_transcurridas": round(t.horas_transcurridas(ahora), 2),
                  "horas_restantes": round(t.horas_restantes(ahora), 2),
                  "fraccion_dia": round(tiempo.fraccion_dia_operacional(ahora), 3)},
        "reloj": {"iso": tiempo.iso(ahora), "texto_12h": tiempo.hora_texto_12h(ahora), "texto_24h": tiempo.hora_texto_24h(ahora)},
        "tarjetas": {"movimiento_mina": mov, "chancado": chancado, "velocidad_caex": velocidad, "equipos_en_uso": en_uso},
        "gaviota": gaviota, "ciclos": ciclos, "flota": flota, "chancado": chancado_det,
        "equipos": {"lista": lista,
                    "fuente": "estado_equipos si existe; si no, derivado de horas_equipo y gps. estado ∈ operativo | detenido | demora | mantencion | reserva | sin_dato"},
        "mapa": mapa, "alertas": alertas,
    }


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------
def a_json(obj, sangria: int = 0, ancho: int = 185) -> str:
    """JSON legible: lo que cabe en una línea se escribe en una línea."""
    plano = json.dumps(obj, ensure_ascii=False)
    pad = "  " * sangria
    if not isinstance(obj, (dict, list)) or len(plano) + len(pad) <= ancho:
        return plano
    if isinstance(obj, dict):
        cuerpo = [f"{pad}  {json.dumps(k, ensure_ascii=False)}: {a_json(v, sangria + 1, ancho)}" for k, v in obj.items()]
        return "{\n" + ",\n".join(cuerpo) + f"\n{pad}}}"
    cuerpo = [f"{pad}  {a_json(v, sangria + 1, ancho)}" for v in obj]
    return "[\n" + ",\n".join(cuerpo) + f"\n{pad}]"


def escribir_csv(ruta: Path, columnas: list[str], filas) -> int:
    n = 0
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columnas)
        for fila in filas:
            w.writerow([fila[c] for c in columnas])
            n += 1
    return n


def _filas_horarias(datos: Datos, columnas_extra):
    """Una fila por hora COMPLETA de cada día del periodo; `columnas_extra(d, orden)` aporta los valores."""
    for d, _ in sorted(datos.real_kt.items()):
        for orden in range(1, 25):
            if not completa(d, orden):
                continue
            turno, ht, hr = info_hora(orden)
            base = {"fecha": d.isoformat(), "hora_inicio": inicio_hora(d, orden).isoformat(),
                    "turno": turno, "hora_turno": ht, "hora_reloj": hr}
            for extra in columnas_extra(d, orden):
                yield {**base, **extra}


def generar(salida: Path, docs: Path) -> dict[str, int]:
    """Genera todos los archivos. Devuelve {nombre_archivo: filas}."""
    tiempo.configurar_zona("UTC")
    cfg = config.cargar_config(RAIZ_PROYECTO)
    datos = simular(cfg)
    pos = posiciones(cfg, datos)
    salida.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    cuenta: dict[str, int] = {}
    cab = ["fecha", "hora_inicio", "turno", "hora_turno", "hora_reloj"]
    excluidos = set(cfg.dashboard["equipos"]["excluidos"])

    equipos = [{"Equipo": n, "TipoEquipo": tipo, "Flota": FLOTAS[tipo], "ActivoKPI": 0 if n in excluidos else 1}
               for tipo, lista in (("Truck", sin.FLOTA_CAEX), ("Shovel", sin.FLOTA_PALAS),
                                   ("Loader", sin.FLOTA_CARGADORES), ("Drill", sin.FLOTA_PERFORADORAS)) for n in lista]
    cuenta["equipos.csv"] = escribir_csv(salida / "equipos.csv", ["Equipo", "TipoEquipo", "Flota", "ActivoKPI"], equipos)

    gps = [{"Equipo": p["equipo"], "TipoEquipo": p["tipo_equipo"], "FechaHora": (AHORA - timedelta(seconds=p["segundos_atras"])).isoformat(),
            "Latitud": p["latitud_mas"], "Longitud": p["longitud_mas"], "Velocidad": p["velocidad_kmh"]} for p in pos]
    cuenta["gps.csv"] = escribir_csv(salida / "gps.csv", ["Equipo", "TipoEquipo", "FechaHora", "Latitud", "Longitud", "Velocidad"], gps)

    hist = lambda f: (x for x in f if completa(date.fromisoformat(x["fecha"]), x["orden"]))
    cuenta["ciclos_hora_pala_camion.csv"] = escribir_csv(
        salida / "ciclos_hora_pala_camion.csv", cab + ["pala", "camion", "destino", "ciclos", "tiempo_ciclo_min", "toneladas"],
        hist(datos.ciclos))
    cuenta["velocidad_caex_hora.csv"] = escribir_csv(
        salida / "velocidad_caex_hora.csv",
        cab + ["camion", "velocidad_cargado_kmh", "velocidad_vacio_kmh", "velocidad_media_kmh"], hist(datos.velocidad))
    cuenta["chancado_hora.csv"] = escribir_csv(
        salida / "chancado_hora.csv", cab + ["alimentacion_tph", "plan_tph"],
        _filas_horarias(datos, lambda d, o: [{"alimentacion_tph": datos.tph[d][o - 1],
                                              "plan_tph": round(datos.plan_chancado_dia_kt * 1000 * datos.fracciones[o - 1])}]))
    cuenta["granulometria_hora.csv"] = escribir_csv(
        salida / "granulometria_hora.csv", cab + ["fraccion", "masa_pct"],
        _filas_horarias(datos, lambda d, o: [{"fraccion": k, "masa_pct": v} for k, v in datos.gran[d][o - 1].items()]))
    cuenta["plan_gaviota_hora.csv"] = escribir_csv(
        salida / "plan_gaviota_hora.csv", cab + ["plan_kt", "real_kt"],
        _filas_horarias(datos, lambda d, o: [{"plan_kt": round(datos.plan_mov_dia_kt * datos.fracciones[o - 1], 2),
                                              "real_kt": datos.real_kt[d][o - 1]}]))

    snapshot = construir_snapshot(cfg, datos, pos)
    (docs / "snapshot_ejemplo.json").write_text(a_json(snapshot) + "\n", encoding="utf-8", newline="\n")
    cuenta["snapshot_ejemplo.json"] = 1
    return cuenta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--salida", default=str(RAIZ_PROYECTO / "datos_sinteticos"), help="carpeta de los CSV")
    ap.add_argument("--docs", default=str(RAIZ_PROYECTO / "docs"), help="carpeta del snapshot de ejemplo")
    a = ap.parse_args()
    for nombre, filas in generar(Path(a.salida), Path(a.docs)).items():
        print(f"{nombre:34s} {filas:>7,} filas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
