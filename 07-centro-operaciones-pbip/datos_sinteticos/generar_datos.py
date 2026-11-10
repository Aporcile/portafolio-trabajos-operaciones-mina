# -*- coding: utf-8 -*-
"""Genera los CSV 100 % sintéticos del informe de sala de control (empresa ficticia Minera Demo).

Escribe en esta misma carpeta (datos_sinteticos/) un CSV por partición del modelo semántico:
  dim_equipo, dim_turno
  fact_horas_equipo, fact_horas_equipo_muro, fact_ciclos, fact_gps, fact_velocidad_caex_hora,
  fact_chancado, fact_chancado_origen_hora, fact_ley_alimentacion_hora
  plan_caex, plan_carguio, plan_perforadoras, plan_muro, plan_semanal_chancador

Periodo sintético: 90 días desde 2025-03-03 (planes y calendario). El detalle horario cubre solo los últimos
DIAS_DETALLE días y el detalle de ciclos los últimos DIAS_CICLOS, para que cada CSV pese menos de 2 MB. El último día
queda a medias (hasta la hora ULTIMA_HORA_ORDEN del día operacional) para mostrar un turno en curso.

Todo se deriva de una simulación única, así que las tablas son coherentes entre sí: el tonelaje por hora de los CAEX es
la suma de sus ciclos, lo que cargan las palas es lo que descargan los CAEX y el chancado sale de los mismos ciclos.

Reglas de negocio simuladas: turno A 08:00-19:59, turno B 20:00-07:59, día operacional 08:00 a 08:00; equipos con
sufijo «_M» pertenecen a la flota de Muro; CAEX-90 y los equipos de la flota «Equipo Testeo» quedan fuera de los KPI.

Uso:  python generar_datos.py        (semilla fija: cada ejecución reproduce los mismos archivos)
"""
import csv
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[1] / "tools"))
from sinteticos import FLOTA_CAEX, FLOTA_CARGADORES, FLOTA_PALAS, FLOTA_PERFORADORAS, personas, rng  # noqa: E402

INICIO = date(2025, 3, 3)
N_DIAS = 90
FIN = INICIO + timedelta(days=N_DIAS - 1)
DIAS = [INICIO + timedelta(days=k) for k in range(N_DIAS)]
DIAS_DETALLE = 7
DIAS_CICLOS = 3
ULTIMA_HORA_ORDEN = 17          # el último día llega hasta las 00:59 (hora 17 del día operacional)

# ---- flota ficticia ------------------------------------------------------------------------------------------
CAEX_MINA = list(FLOTA_CAEX)                                  # CAEX-01..26
CAEX_FUERA_KPI = ["CAEX-90", "CAEX-91"]                       # auxiliar y equipo de testeo (no entran a los hechos)
CAEX_MURO = ["CAEX-27_M", "CAEX-28_M", "CAEX-90_M"]
PALAS = list(FLOTA_PALAS)
PALA_MURO = ["PALA-05_M"]
CARGADORES = list(FLOTA_CARGADORES)
CARGADOR_MURO = ["CARG-03_M"]
PERFORADORAS = list(FLOTA_PERFORADORAS)
TIPO = {}
FLOTA = {}
for _n in CAEX_MINA + CAEX_FUERA_KPI + CAEX_MURO:
    TIPO[_n] = "Truck"
    FLOTA[_n] = "CAEX-A" if (_n[5:7].isdigit() and int(_n[5:7]) <= 14) else "CAEX-B"
FLOTA["CAEX-91"] = "Equipo Testeo"
for _n in PALAS + PALA_MURO:
    TIPO[_n] = "Shovel"
    FLOTA[_n] = "Pala Hidraulica" if _n in ("PALA-01", "PALA-02", "PALA-05_M") else "Pala Electrica"
for _n in CARGADORES + CARGADOR_MURO:
    TIPO[_n] = "Loader"
    FLOTA[_n] = "Cargador Frontal"
for _n in PERFORADORAS:
    TIPO[_n] = "Drill"
    FLOTA[_n] = "Perforadora Rotatoria"
PESO_CARGUIO = {**{p: 1.0 for p in PALAS}, **{c: 0.35 for c in CARGADORES}, "PALA-05_M": 1.0, "CARG-03_M": 0.4}

DUMPS = {  # nombre -> (id, tipo de ubicación)
    "CHANCADO": (1, "Crusher"), "BOTADERO_N": (2, "Dump"), "BOTADERO_S": (3, "Dump"),
    "STOCK_1": (4, "Stockpile"), "STOCK_2": (5, "Stockpile")}
ORIGENES = ["F01", "F02", "F03", "Stock_1", "Stock_2"]
PESO_ORIGEN = {"F01": 0.34, "F02": 0.26, "F03": 0.18, "Stock_1": 0.14, "Stock_2": 0.08}
CUT_ORIGEN = {"F01": 0.55, "F02": 0.48, "F03": 0.41, "Stock_1": 0.39, "Stock_2": 0.36}

# ---- centro de la mina sintética (punto arbitrario; en la hoja de mapa solo hay puntos inventados) ---------------
CENTRO_LAT, CENTRO_LON = 21.50, 25.90
GRADO_MS = 3_600_000            # milisegundos de arco por grado
PUNTOS_GPS = {                  # zona -> lista de (desfase de latitud, desfase de longitud) en grados
    "frente": [(0.008, -0.020), (0.004, -0.008), (-0.003, -0.024), (0.009, 0.004)],
    "chancado": [(-0.008, 0.026)],
    "botadero": [(0.012, 0.034), (-0.012, 0.010)],
    "taller": [(-0.010, -0.034)],
}

ESCENARIO = "esc_f"                              # nombre de la secuencia aleatoria (cambia todo el detalle horario)
PATRON_FUERA_SERVICIO = [1, 0, 2, 1, 1, 0, 2]   # camiones que pasan el día entero fuera de servicio
PATRON_PALA_FUERA = [0, 0, 1, 0, 0, 1, 0]        # 1 = una pala fuera de servicio ese día
PATRON_PERF_FUERA = [0, 1, 0, 0, 1, 0, 0]        # 1 = una perforadora fuera de servicio ese día

CARPETA_SALIDA = AQUI


def fmt(x, nd=3):
    if isinstance(x, float):
        s = f"{x:.{nd}f}".rstrip("0").rstrip(".")
        return s if s not in ("", "-0") else "0"
    return x


def escribir(nombre, columnas, filas):
    ruta = CARPETA_SALIDA / f"{nombre}.csv"
    n = 0
    with open(ruta, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(columnas)
        for f in filas:
            w.writerow([fmt(f.get(c, "")) for c in columnas])
            n += 1
    kb = ruta.stat().st_size / 1024
    print(f"  {nombre}.csv: {n} filas, {kb:,.0f} KB")
    if kb >= 2000:
        raise SystemExit(f"{nombre}.csv supera 2 MB")


def d_iso(d):
    return d.isoformat()


def dt_iso(t):
    return t.strftime("%Y-%m-%d %H:%M:%S")


def inicio_hora(d, orden):
    """Instante de inicio de la hora `orden` (1..24) del día operacional d (08:00 = orden 1)."""
    return datetime(d.year, d.month, d.day) + timedelta(hours=7 + orden)


def turno_orden(orden):
    return "A" if orden <= 12 else "B"


def hora_indice(orden):
    return (orden - 1) % 12


def ultimo_orden(d):
    return ULTIMA_HORA_ORDEN if d == FIN else 24


def pesos_elegir(r, opciones, pesos):
    return r.choices(opciones, weights=pesos, k=1)[0]


# ---- simulación de estados horarios --------------------------------------------------------------------------
def estados_equipo(r, tipo, orden_max, k_po, fuera_servicio=False):
    """Estados de las 24 horas de un equipo. Cada hora nominal dura 1,0 h:
    nominal = operativa + demora no programada + demora programada + reserva + mantención programada + no programada."""
    caido = [None] * 24                              # None | 'mp' | 'mnp'
    if fuera_servicio:
        caido = ["mnp" if r.random() < 0.7 else "mp"] * 24
    else:
        if r.random() < 0.12:                        # mantención programada: un bloque de 4 a 8 horas
            ini = r.randrange(0, 24)
            for k in range(r.randint(4, 8)):
                if ini + k < 24:
                    caido[ini + k] = "mp"
        i = 0
        while i < 24:                                # fallas: episodios cortos de 1 a 3 horas
            if caido[i] is None and r.random() < 0.035:
                largo = r.randint(1, 3)
                for k in range(largo):
                    if i + k < 24 and caido[i + k] is None:
                        caido[i + k] = "mnp"
                i += largo
            else:
                i += 1
    horas = []
    for o in range(1, orden_max + 1):
        h = dict(oper=0.0, efec=0.0, esp=0.0, cola=0.0, dnp=0.0, dp=0.0, res=0.0, mp=0.0, mnp=0.0)
        c = caido[o - 1]
        if c:
            h["mp" if c == "mp" else "mnp"] = 1.0
        else:
            cambio = o in (1, 13)
            h["dp"] = r.uniform(0.02, 0.06) + (r.uniform(0.07, 0.13) if cambio else 0.0)
            if tipo == "Truck":
                h["dnp"], h["res"] = r.uniform(0, 0.05), r.uniform(0, 0.05)
                po = r.uniform(0.05, 0.17) * k_po
                h["esp"] = po * r.uniform(0.45, 0.65)
                h["cola"] = po - h["esp"]
            elif tipo in ("Shovel", "Loader"):
                h["dnp"], h["res"] = r.uniform(0, 0.05), r.uniform(0, 0.05)
                h["esp"] = r.uniform(0.05, 0.16) * k_po
            else:
                h["dnp"], h["res"] = r.uniform(0.04, 0.12), r.uniform(0, 0.10)
            h["oper"] = 1.0 - h["dp"] - h["dnp"] - h["res"]
            h["efec"] = max(0.0, h["oper"] - h["esp"] - h["cola"])
        horas.append(h)
    return horas


# ---- simulación de ciclos ---------------------------------------------------------------------------------------
def simular():
    """Simula los días de detalle y devuelve las estructuras para escribir todas las tablas."""
    r = rng(ESCENARIO)              # estados, asignación y destinos
    rg = rng("gps")                 # lecturas GPS y velocidad
    rc = rng("ciclos")              # detalle de cada ciclo y calidad del mineral
    personas_op = personas(40, "operadores")
    dias_det = DIAS[-DIAS_DETALLE:]
    res = dict(horas=[], horas_muro=[], ciclos=[], gps=[], vel=[], chanc=[], chanc_hora=[], ley=[])
    id_ciclo = 100000
    for k_dia, d in enumerate(dias_det):
        omax = ultimo_orden(d)
        k_po = r.uniform(0.8, 1.35)
        f_prod = r.gauss(1.0, 0.04)
        # estados: Mina
        n_fuera = PATRON_FUERA_SERVICIO[k_dia % len(PATRON_FUERA_SERVICIO)]
        camiones_fuera = set(r.sample(CAEX_MINA, n_fuera))
        palas_fuera = set(r.sample(PALAS, 1)) if PATRON_PALA_FUERA[k_dia % 7] else set()
        perf_fuera = set(r.sample(PERFORADORAS, 1)) if PATRON_PERF_FUERA[k_dia % 7] else set()
        est = {}
        for eq in CAEX_MINA:
            est[eq] = estados_equipo(r, "Truck", omax, k_po, eq in camiones_fuera)
        for eq in PALAS + CARGADORES:
            est[eq] = estados_equipo(r, TIPO[eq], omax, k_po, eq in palas_fuera)
        for eq in PERFORADORAS:
            est[eq] = estados_equipo(r, "Drill", omax, k_po, eq in perf_fuera)
        for o in range(1, omax + 1):               # siempre debe haber una pala operando
            if not any(est[c][o - 1]["oper"] > 0 for c in PALAS + CARGADORES):
                est["PALA-01"][o - 1] = dict(oper=0.9, efec=0.8, esp=0.1, cola=0.0, dnp=0.0, dp=0.05, res=0.05,
                                             mp=0.0, mnp=0.0)
        # estados: Muro (la pala siempre asignada; camiones y cargador solo algunos días)
        asignados = [c for c in ("CAEX-27_M", "CAEX-28_M")] + (["CAEX-90_M"] if r.random() < 0.5 else [])
        est_m = {}
        est_m["PALA-05_M"] = estados_equipo(r, "Shovel", omax, k_po)
        if r.random() < 0.55:
            est_m["CARG-03_M"] = estados_equipo(r, "Loader", omax, k_po)
        for eq in asignados:
            est_m[eq] = estados_equipo(r, "Truck", omax, k_po)
        for o in range(1, omax + 1):               # sin equipo de carguío operando, los camiones quedan en reserva
            if not any(est_m[c][o - 1]["oper"] > 0 for c in ("PALA-05_M", "CARG-03_M") if c in est_m):
                for eq in asignados:
                    est_m[eq][o - 1] = dict(oper=0.0, efec=0.0, esp=0.0, cola=0.0, dnp=0.0, dp=0.0, res=1.0,
                                            mp=0.0, mnp=0.0)

        # ciclos de los camiones de Mina
        ciclos = []
        for eq in CAEX_MINA:
            for o in range(1, omax + 1):
                h = est[eq][o - 1]
                if h["efec"] <= 0:
                    continue
                lam = h["efec"] * 1.58 * f_prod
                n = int(lam) + (1 if r.random() < lam - int(lam) else 0)
                for _ in range(n):
                    ciclos.append(dict(eq=eq, o=o, t=inicio_hora(d, o) + timedelta(seconds=r.randrange(0, 3600)),
                                       payload=min(370.0, max(290.0, r.gauss(332, 10)))))
        ciclos.sort(key=lambda c: c["t"])
        por_hora = defaultdict(list)
        for c in ciclos:
            por_hora[c["o"]].append(c)

        # pesos de origen por turno del día
        pesos_turno = {}
        for t in ("A", "B"):
            w = {k: PESO_ORIGEN[k] * r.uniform(0.7, 1.3) for k in ORIGENES}
            s = sum(w.values())
            pesos_turno[t] = {k: v / s for k, v in w.items()}

        for o in range(1, omax + 1):
            lista = por_hora[o]
            cuota = int(min(len(lista), max(10, min(14, round(r.gauss(12.0, 1.1))))))
            idx_chanc = set(r.sample(range(len(lista)), cuota)) if lista else set()
            t_ab = turno_orden(o)
            carguio_ok = [c for c in PALAS + CARGADORES if est[c][o - 1]["oper"] > 0]
            for i, c in enumerate(lista):
                shovel = pesos_elegir(r, carguio_ok, [PESO_CARGUIO[x] for x in carguio_ok])
                c["shovel"] = shovel
                if i in idx_chanc:
                    org = pesos_elegir(r, ORIGENES, [pesos_turno[t_ab][k] for k in ORIGENES])
                    c["origen"] = org
                    c["dump"] = "CHANCADO"
                    c["blast"] = nombre_blast(d, org, r)
                    c["cut"] = cut_de(c["blast"], org, r)
                    c["grado"] = "Alta" if c["cut"] >= 0.50 else ("Media" if c["cut"] >= 0.38 else "Baja")
                    c["material"] = "Mineral"
                elif r.random() < 0.92:
                    org = r.choice(["F04", "F05"])
                    c["origen"] = org
                    c["dump"] = r.choice(["BOTADERO_N", "BOTADERO_S"])
                    c["blast"] = nombre_blast(d, org, r)
                    c["cut"] = 0.0
                    c["grado"] = "Esteril"
                    c["material"] = "Esteril"
                else:
                    org = r.choice(["F01", "F02", "F03"])
                    c["origen"] = org
                    c["dump"] = r.choice(["STOCK_1", "STOCK_2"])
                    c["blast"] = nombre_blast(d, org, r)
                    c["cut"] = cut_de(c["blast"], org, r)
                    c["grado"] = "Baja"
                    c["material"] = "Mineral"
                c["remanejo"] = c["blast"].startswith("STOCK")

        # ---- tablas por hora de Mina -------------------------------------------------------------------------
        ton_eq = defaultdict(float)        # (eq, o) -> t
        ext_eq = defaultdict(float)
        rem_eq = defaultdict(float)
        for c in ciclos:
            ton_eq[(c["eq"], c["o"])] += c["payload"]
            (rem_eq if c["remanejo"] else ext_eq)[(c["eq"], c["o"])] += c["payload"]
        ton_pala = defaultdict(float)
        for c in ciclos:
            ton_pala[(c["shovel"], c["o"])] += c["payload"]
        todos = CAEX_MINA + PALAS + CARGADORES + PERFORADORAS
        for eq in todos:
            tipo = TIPO[eq]
            for o in range(1, omax + 1):
                h = est[eq][o - 1]
                if tipo == "Truck":
                    ton, ex, rm, met = ton_eq[(eq, o)], ext_eq[(eq, o)], rem_eq[(eq, o)], 0.0
                elif tipo in ("Shovel", "Loader"):
                    ton, ex, rm, met = ton_pala[(eq, o)], 0.0, 0.0, 0.0
                else:
                    ton, ex, rm = 0.0, 0.0, 0.0
                    met = h["efec"] * max(0.0, r.gauss(32, 3))
                res["horas"].append(fila_hora_equipo(d, o, eq, tipo, h, ton, ex, rm, met))

        # ---- tablas por hora de Muro -------------------------------------------------------------------------
        ton_m = defaultdict(float)
        ext_m = defaultdict(float)
        rem_m = defaultdict(float)
        carg_m = {}
        for eq in asignados:
            for o in range(1, omax + 1):
                h = est_m[eq][o - 1]
                if h["efec"] <= 0:
                    continue
                lam = h["efec"] * 1.35 * f_prod
                n = int(lam) + (1 if r.random() < lam - int(lam) else 0)
                tot = sum(min(370.0, max(290.0, r.gauss(332, 10))) for _ in range(n))
                ton_m[(eq, o)] = tot
                rm = tot * (r.uniform(0.0, 0.10) if r.random() < 0.3 else 0.0)
                rem_m[(eq, o)] = rm
                ext_m[(eq, o)] = tot - rm
        for o in range(1, omax + 1):
            total_o = sum(ton_m[(e, o)] for e in asignados)
            activos = [c for c in ("PALA-05_M", "CARG-03_M") if c in est_m and est_m[c][o - 1]["oper"] > 0]
            if activos:
                pesos = [PESO_CARGUIO[c] for c in activos]
                for c, p in zip(activos, pesos):
                    carg_m[(c, o)] = total_o * p / sum(pesos)
        for eq, estados in est_m.items():
            tipo = TIPO[eq]
            for o in range(1, omax + 1):
                h = estados[o - 1]
                if tipo == "Truck":
                    ton, ex, rm = ton_m[(eq, o)], ext_m[(eq, o)], rem_m[(eq, o)]
                else:
                    ton, ex, rm = carg_m.get((eq, o), 0.0), 0.0, 0.0
                res["horas_muro"].append(fila_hora_muro(d, o, eq, tipo, h, ton, ex, rm))

        # ---- GPS y velocidad ---------------------------------------------------------------------------------
        sesgo_vel = rg.gauss(0, 0.8)
        for eq in CAEX_MINA:
            for o in range(1, omax + 1):
                h = est[eq][o - 1]
                if h["oper"] <= 0:
                    continue
                lect = int(max(40, rg.gauss(165, 15)) * h["oper"])
                mov = int(lect * rg.uniform(0.45, 0.62))
                prom = min(29.5, max(15.5, rg.gauss(21.5 + sesgo_vel, 2.2)))
                suma = round(mov * prom, 1)
                res["vel"].append(dict(Fecha=d_iso(d), Turno=turno_orden(o), Orden_Hora_Dia=o, Equipo=eq, Lecturas=lect,
                                       Suma_Velocidad=suma, Lecturas_Movimiento=mov, Suma_Velocidad_Movimiento=suma))
                for _ in range(int(rg.expovariate(1 / 1.1) + 0.5)):      # lecturas de baja velocidad (0-5 km/h)
                    zona = rg.choices(["frente", "chancado", "botadero", "taller"], weights=[0.45, 0.25, 0.2, 0.1])[0]
                    dlat, dlon = rg.choice(PUNTOS_GPS[zona])
                    lat = CENTRO_LAT + dlat + rg.gauss(0, 0.0018)
                    lon = CENTRO_LON + dlon + rg.gauss(0, 0.0018)
                    t = inicio_hora(d, o) + timedelta(seconds=rg.randrange(0, 3600))
                    v = 0.0 if rg.random() < 0.4 else round(rg.uniform(0.2, 5.0), 1)
                    res["gps"].append(dict(Fecha=d_iso(d), Turno=turno_orden(o), Orden_Hora_Dia=o, Equipo=eq,
                                           FechaHora=dt_iso(t), Latitud=round(lat * GRADO_MS),
                                           Longitud=round(lon * GRADO_MS), **{"Velocidad km/h": v}))

        # ---- chancado: de los ciclos con destino CHANCADO --------------------------------------------------------
        cargas = [c for c in ciclos if c["dump"] == "CHANCADO"]
        agrup = defaultdict(lambda: dict(ton=0.0, viajes=0, cut_x_ton=0.0))
        for c in cargas:
            t = turno_orden(c["o"])
            clave = (t, c["shovel"], c["eq"], c["grado"], c["blast"])
            g = agrup[clave]
            g["ton"] += c["payload"]
            g["viajes"] += 1
            g["cut_x_ton"] += c["cut"] * c["payload"]
        for (t, shovel, eq, grado, blast), g in sorted(agrup.items()):
            cut = g["cut_x_ton"] / g["ton"]
            q = calidad(rc, cut)
            res["chanc"].append(dict(Fecha=d_iso(d), Turno=t, Equipo_Carguio=shovel, CAEX=eq, Ley=grado, Origen=blast,
                                     Destino="CHANCADO", Material="Mineral", Tonelaje=round(g["ton"], 1),
                                     Viajes=g["viajes"], CuT=round(cut, 4), **q))
        por_ho = defaultdict(float)
        ley_h = defaultdict(lambda: [0.0, 0.0])
        for c in cargas:
            hora_reloj = c["t"].hour
            turno_hora = turno_orden(c["o"])
            if r.random() < 0.005:                 # registro cuyo turno no coincide con la hora: queda sin hora de turno
                turno_hora = "B" if turno_hora == "A" else "A"
            clave = (turno_hora, hora_reloj, origen_corto(c["blast"]))
            por_ho[clave] += c["payload"]
            k = (turno_orden(c["o"]), c["blast"], c["o"])
            ley_h[k][0] += c["payload"]
            ley_h[k][1] += c["payload"] * c["cut"]
        for (t, hora, org), ton in sorted(por_ho.items(), key=lambda x: (x[0][1], x[0][0], x[0][2])):
            if t == "A":
                ht = hora - 7
            elif hora >= 20:
                ht = hora - 19
            else:
                ht = hora + 5
            res["chanc_hora"].append(dict(Fecha=d_iso(d), Hora=hora, Hora_Orden=(hora + 16) % 24,
                                          HoraTurno=ht if 1 <= ht <= 12 else "", Turno=t, Origen=org,
                                          Tonelaje=round(ton, 1)))
        for (t, blast, o), (ton, cxt) in sorted(ley_h.items(), key=lambda x: (x[0][2], x[0][1])):
            res["ley"].append(dict(Fecha=d_iso(d), Turno=t, Blast=blast, Orden_Hora_Dia=o, Tonelaje=round(ton, 1),
                                   Ley_x_Ton=round(cxt, 2)))

        # ---- ciclos completos (solo los últimos días) ----------------------------------------------------------
        if d >= DIAS[-DIAS_CICLOS]:
            for c in ciclos:
                id_ciclo += 1
                res["ciclos"].append(fila_ciclo(rc, d, c, id_ciclo, personas_op))
    res["ciclos"].sort(key=lambda f: f["time"])
    return res


def nombre_blast(d, origen, r):
    if origen.startswith("Stock"):
        return "STOCK_" + origen[-1]
    k = r.choice([0, 1])
    fase = int(origen[1:])
    banco = 10 + fase * 3 + ((d.toordinal() // 2) % 4)
    return f"{origen}-B{banco:02d}-{(d.toordinal() // 2 * 7 + k * 13 + fase * 31) % 300 + 100}"


def origen_corto(blast):
    return "Stock_" + blast[-1] if blast.startswith("STOCK") else blast[:3]


def cut_de(blast, origen, r):
    base = CUT_ORIGEN[origen] if origen in CUT_ORIGEN else 0.30
    desfase = rng("blast:" + blast).gauss(0, 0.04)
    return min(0.9, max(0.15, base + desfase + r.gauss(0, 0.025)))


def calidad(r, cut):
    """Columnas de calidad (texto, como las entrega la fuente): solo CuT se usa en el modelo."""
    return {"Cusc": f"{cut * r.uniform(0.10, 0.16):.4f}", "Cuas": f"{cut * r.uniform(0.04, 0.08):.4f}",
            "CuS": f"{cut * r.uniform(0.84, 0.92):.4f}", "Cuins": f"{cut * r.uniform(0.02, 0.05):.4f}",
            "Mo": f"{r.uniform(0.004, 0.02):.4f}", "rec_cu_1": f"{r.uniform(78, 90):.1f}",
            "rec_cu_2": f"{r.uniform(80, 92):.1f}", "zona_1": f"{r.uniform(0.2, 0.6):.3f}",
            "zona_2": f"{r.uniform(0.01, 0.04):.3f}", "dens": f"{r.uniform(2.55, 2.72):.2f}",
            "cucns": f"{cut * r.uniform(0.01, 0.03):.4f}"}


def fila_hora_equipo(d, o, eq, tipo, h, ton, ex, rm, met):
    disp = h["oper"] + h["dnp"] + h["dp"] + h["res"]
    po = h["esp"] + h["cola"]
    rend = 0.0
    if h["efec"] > 0:
        rend = met / h["efec"] if tipo == "Drill" else ton / h["efec"]
    return {"Fecha": d_iso(d), "Turno": turno_orden(o), "Hora": hora_indice(o), "Tipo Equipo": tipo, "Equipo": eq,
            "Flota": FLOTA[eq], "Horas Nominales": 1.0, "Horas Operativas": h["oper"], "Horas Efectivas": h["efec"],
            "Horas PO Espera": h["esp"], "Horas PO Cola": h["cola"], "Horas PO Totales": po,
            "Horas Demora No Programada": h["dnp"], "Horas Demora Programada": h["dp"], "Horas Reserva": h["res"],
            "Horas Disponibles": disp, "Horas Mantencion Programada": h["mp"],
            "Horas Mantencion No Programada": h["mnp"], "Tonelaje": ton, "Material Extraido": ex,
            "Material Remanejo": rm, "Movimiento Total": ex + rm, "Metros Perforados": met,
            "Disponibilidad": disp * 100, "Utilizacion": (h["oper"] / disp * 100) if disp > 0 else 0.0,
            "UE": (h["efec"] / disp * 100) if disp > 0 else 0.0, "OEE_Horas": h["efec"] * 100, "Rendimiento": rend}


def fila_hora_muro(d, o, eq, tipo, h, ton, ex, rm):
    disp = h["oper"] + h["dnp"] + h["dp"] + h["res"]
    return {"Fecha": d_iso(d), "Turno": turno_orden(o), "Hora": hora_indice(o), "Equipo": eq,
            "Horas Operativas": h["oper"], "Tipo Equipo": tipo, "Flota": FLOTA[eq], "Horas Nominales": 1.0,
            "Horas Efectivas": h["efec"], "Horas Disponibles": disp, "Horas PO Totales": h["esp"] + h["cola"],
            "Horas Demora No Programada": h["dnp"], "Horas Demora Programada": h["dp"], "Horas Reserva": h["res"],
            "Horas Mantencion Programada": h["mp"], "Horas Mantencion No Programada": h["mnp"], "Tonelaje": ton,
            "Material Extraido": ex, "Material Remanejo": rm, "Movimiento Total": ex + rm}


def fila_ciclo(r, d, c, id_ciclo, personas_op):
    t_empty = c["t"]
    trav, espera = int(r.gauss(620, 70)), int(abs(r.gauss(95, 60)))
    spot, carga = int(r.uniform(18, 45)), int(r.gauss(205, 25))
    haul, cola = int(r.gauss(880, 90)), int(abs(r.gauss(60, 45)))
    back, tip = int(r.uniform(15, 40)), int(r.uniform(35, 70))
    t_full = t_empty - timedelta(seconds=haul + cola + back + tip)
    t_spotted = t_full - timedelta(seconds=carga)
    t_spotting = t_spotted - timedelta(seconds=spot)
    t_arrive = t_spotting - timedelta(seconds=espera)
    t_depart = t_arrive - timedelta(seconds=trav)
    turno = "A" if 8 <= t_empty.hour < 20 else "B"
    crew_n = ((d.toordinal() + (0 if turno == "A" else 1)) % 4) + 1
    eq_n = int(c["eq"][5:7])
    pala = c["shovel"]
    pala_n = (PALAS + CARGADORES).index(pala) + 1
    dump_id, dump_tipo = DUMPS[c["dump"]]
    v_vacio, v_carga = r.uniform(22, 30), r.uniform(15, 24)
    d_vacio, d_carga = int(trav * v_vacio / 3.6), int(haul * v_carga / 3.6)
    po_car, po_des = espera / 60, cola / 60
    op_t, op_p = personas_op[(eq_n * 3 + crew_n) % 30], personas_op[30 + (pala_n + crew_n) % 10]
    fase = int(c["origen"][1:]) if c["origen"].startswith("F") else 0
    return {
        "DiaOperativo": d_iso(d) + " 00:00:00", "id_registro_ciclo": id_ciclo, "time": dt_iso(t_empty), "shift_id": 1 if turno == "A" else 2,
        "shift": turno, "crew_id": crew_n, "crew": f"G{crew_n}", "truck_id": 100 + eq_n, "TruckName": c["eq"],
        "TruckFleet": FLOTA[c["eq"]], "shovel_id": 200 + pala_n, "ShovelName": pala, "ShovelFleet": FLOTA[pala],
        "grade_id": {"Alta": 1, "Media": 2, "Baja": 3, "Esteril": 4}[c["grado"]], "GradeName": c["grado"],
        "material_id": 1 if c["material"] == "Mineral" else 2, "MaterialName": c["material"], "dump_id": dump_id,
        "Dump_LocationType": dump_tipo, "DumpName": c["dump"], "blast_id": 5000 + fase * 10 + (id_ciclo % 7),
        "Blast_LocationType": "Stockpile" if c["blast"].startswith("STOCK") else "Blast", "BlastName": c["blast"],
        "latitude": 0, "longitude": 0, "elevation": 0, "northing": round(12000 + r.uniform(-1500, 1500), 1),
        "easting": round(22000 + r.uniform(-1500, 1500), 1), "l_elevation": round(2100 + r.uniform(-120, 60), 1),
        "by_dispatcher": "true" if r.random() < 0.85 else "false", "assignment_reason_id": 1,
        "asignacion_motivo_tipo": "Despacho", "assigned_shovel_id": 200 + pala_n,
        "asignacion_pala_tipo": "Pala" if pala.startswith("PALA") else "Cargador", "truck_operator_id": 300 + eq_n,
        "TruckOpName": op_t["nombre"], "TruckOpPayNumber": 100000 + op_t["id"], "shovel_operator_id": 400 + pala_n,
        "ShohvelOpName": op_p["nombre"], "ShovelOpPayNumber": 100000 + op_p["id"], "time_depart": dt_iso(t_depart),
        "time_arrive": dt_iso(t_arrive), "time_spotting": dt_iso(t_spotting), "time_spotted": dt_iso(t_spotted),
        "expected_time": int((trav + espera + spot + carga + haul + cola + back + tip) * 0.93),
        "distance": d_vacio + d_carga, "efh": int(d_carga * 1.8), "lift_down": r.randint(0, 40), "lift_up": r.randint(0, 120),
        "lift_distance_down": r.randint(0, 900), "lift_distance_up": r.randint(0, 2200), "start_location_id": 600 + pala_n,
        "end_location_id": 700 + dump_id, "has_payload": "true", "activity_id": 1, "time_full": dt_iso(t_full),
        "time_empty": dt_iso(t_empty), "load_count": 1, "cycle_count": 1, "material_tonnage": round(c["payload"], 1),
        "payload": round(c["payload"] * r.uniform(0.98, 1.02), 1), "payload_count": 1, "distance_empty": d_vacio,
        "distance_loaded": d_carga, "inactive_time": 0, "traveling_time": trav, "waiting_time": espera,
        "spotting_time": spot, "loading_time": carga, "hauling_time": haul, "queued_time": cola, "backing_time": back,
        "tipping_time": tip, "traveling_efh": int(d_vacio * 1.1), "hauling_efh": int(d_carga * 1.8),
        "swing_times": ";".join(str(r.randint(10, 14)) for _ in range(3)),
        "swing_angles": ";".join(str(r.randint(80, 110)) for _ in range(3)), "loading_seconds": carga,
        "spotting_seconds": spot, "waiting_seconds": int(abs(r.gauss(70, 50))), "extraload": 0,
        "login_dispatcher": f"persona.demo{(id_ciclo % 6) + 41:02d}", "PO_CAEX_CARGA_MIN": round(po_car, 2),
        "PO_CAEX_DESCARGA_MIN": round(po_des, 2), "PO_TOTAL_CAEX_MIN": round(po_car + po_des, 2),
        "PO_CARGUIO_ESPERANDO_CAEX_MIN": 0.0}


# ---- planes y dimensiones --------------------------------------------------------------------------------------
def semana(d):
    return d - timedelta(days=d.weekday())


def planes():
    r = rng("planes")
    plan_caex, plan_carguio, plan_perf, plan_muro, plan_chanc = [], [], [], [], []
    ruido = {}
    for d in DIAS:
        w = semana(d)
        if w not in ruido:
            ruido[w] = {k: r.gauss(0, 0.025) for k in ("mov", "chanc", "ley", "df", "rend")}
        n = ruido[w]
        nominales = len(CAEX_MINA) * 24.0
        disp = nominales * (0.90 + n["df"])
        efec = disp * 0.775
        plan_caex.append(dict(Fecha=d_iso(d), **{"Horas Disponibles Plan": disp, "Horas Efectivas Plan": efec,
                                                 "Horas Nominales Plan": nominales,
                                                 "Horas Operativas Plan": disp * 0.89,
                                                 "Toneladas Plan": efec * 510 * (1 + n["mov"])}))
        for eq in PALAS + CARGADORES:
            nom = 24.0
            dsp = nom * 0.91
            ef = dsp * 0.78
            rend = 2750 if eq.startswith("PALA") else 980
            plan_carguio.append({"Fecha": d_iso(d), "Equipo": eq, "Horas Disponibles Plan": dsp,
                                 "Horas Efectivas Plan": ef, "Horas Operativas Plan": dsp * 0.88,
                                 "Toneladas Plan": ef * rend * (1 + n["mov"]), "Horas Nominales Plan": nom})
        for eq in PERFORADORAS:
            dsp = 24.0 * 0.88
            ef = dsp * 0.82
            plan_perf.append({"Fecha": d_iso(d), "Equipo": eq, "Horas Disponibles Plan": dsp, "Horas Efectivas Plan": ef,
                              "Horas Nominales Plan": 24.0, "Horas Operativas Plan": dsp * 0.9,
                              "Metros Plan": ef * 33 * (1 + n["rend"])})
        for tag, base in (("PLAN_MURO_CAEX_DISP", 0.87), ("PLAN_MURO_CAEX_UEBD", 0.76), ("PLAN_MURO_CAEX_REND", 430),
                          ("PLAN_MURO_PALA_DISP", 0.88), ("PLAN_MURO_PALA_UEBD", 0.79), ("PLAN_MURO_PALA_REND", 900)):
            plan_muro.append({"Tag": tag, "Fecha": d_iso(d), "Valor": base * (1 + n["df"] * (0.3 if base < 2 else 1))})
        plan_chanc.append({"Fecha": d_iso(d), "Plan_Semanal_Chancado": 96000 * (1 + n["chanc"]),
                           "Plan_Ley_CuT": 0.45 * (1 + n["ley"])})
    return plan_caex, plan_carguio, plan_perf, plan_muro, plan_chanc


def dim_equipo():
    filas = []
    for eq in sorted(TIPO, key=lambda e: (["Truck", "Shovel", "Loader", "Drill"].index(TIPO[e]), e)):
        n = eq.replace(" ", "").upper()
        activo = 0 if ("_M" in n or n.startswith("CAEX-90") or "TESTEO" in (eq + " " + FLOTA[eq]).upper()) else 1
        filas.append(dict(Equipo=eq, TipoEquipo=TIPO[eq], Flota=FLOTA[eq], Activo_KPI=activo))
    return filas


def main():
    print("Generando CSV sintéticos en", CARPETA_SALIDA)
    res = simular()
    cols = {
        "fact_horas_equipo": ["Fecha", "Turno", "Hora", "Tipo Equipo", "Equipo", "Flota", "Horas Nominales",
                              "Horas Operativas", "Horas Efectivas", "Horas PO Espera", "Horas PO Cola",
                              "Horas PO Totales", "Horas Demora No Programada", "Horas Demora Programada",
                              "Horas Reserva", "Horas Disponibles", "Horas Mantencion Programada",
                              "Horas Mantencion No Programada", "Tonelaje", "Material Extraido", "Material Remanejo",
                              "Movimiento Total", "Metros Perforados", "Disponibilidad", "Utilizacion", "UE",
                              "OEE_Horas", "Rendimiento"],
        "fact_horas_equipo_muro": ["Fecha", "Turno", "Hora", "Equipo", "Horas Operativas", "Tipo Equipo", "Flota",
                                   "Horas Nominales", "Horas Efectivas", "Horas Disponibles", "Horas PO Totales",
                                   "Horas Demora No Programada", "Horas Demora Programada", "Horas Reserva",
                                   "Horas Mantencion Programada", "Horas Mantencion No Programada", "Tonelaje",
                                   "Material Extraido", "Material Remanejo", "Movimiento Total"],
        "fact_gps": ["Fecha", "Turno", "Orden_Hora_Dia", "Equipo", "FechaHora", "Latitud", "Longitud", "Velocidad km/h"],
        "fact_velocidad_caex_hora": ["Fecha", "Turno", "Orden_Hora_Dia", "Equipo", "Lecturas", "Suma_Velocidad",
                                     "Lecturas_Movimiento", "Suma_Velocidad_Movimiento"],
        "fact_chancado": ["Fecha", "Turno", "Equipo_Carguio", "CAEX", "Ley", "Origen", "Destino", "Material", "Tonelaje",
                          "Viajes", "CuT", "Cusc", "Cuas", "CuS", "Cuins", "Mo", "rec_cu_1", "rec_cu_2", "zona_1",
                          "zona_2", "dens", "cucns"],
        "fact_chancado_origen_hora": ["Fecha", "Hora", "Hora_Orden", "HoraTurno", "Turno", "Origen", "Tonelaje"],
        "fact_ley_alimentacion_hora": ["Fecha", "Turno", "Blast", "Orden_Hora_Dia", "Tonelaje", "Ley_x_Ton"],
    }
    escribir("dim_equipo", ["Equipo", "TipoEquipo", "Flota", "Activo_KPI"], dim_equipo())
    escribir("dim_turno", ["Turno", "Nombre", "HoraInicio", "HoraFin"],
             [dict(Turno="A", Nombre="Turno A", HoraInicio="08:00:00", HoraFin="19:59:59"),
              dict(Turno="B", Nombre="Turno B", HoraInicio="20:00:00", HoraFin="07:59:59")])
    for nombre, columnas in cols.items():
        clave = {"fact_horas_equipo": "horas", "fact_horas_equipo_muro": "horas_muro", "fact_gps": "gps",
                 "fact_velocidad_caex_hora": "vel", "fact_chancado": "chanc", "fact_chancado_origen_hora": "chanc_hora",
                 "fact_ley_alimentacion_hora": "ley"}[nombre]
        escribir(nombre, columnas, res[clave])
    ciclos = res["ciclos"]
    escribir("fact_ciclos", list(ciclos[0].keys()), ciclos)
    pc, pcg, pp, pm, pch = planes()
    escribir("plan_caex", ["Fecha", "Horas Disponibles Plan", "Horas Efectivas Plan", "Horas Nominales Plan",
                           "Horas Operativas Plan", "Toneladas Plan"], pc)
    escribir("plan_carguio", ["Fecha", "Equipo", "Horas Disponibles Plan", "Horas Efectivas Plan", "Horas Operativas Plan",
                              "Toneladas Plan", "Horas Nominales Plan"], pcg)
    escribir("plan_perforadoras", ["Fecha", "Equipo", "Horas Disponibles Plan", "Horas Efectivas Plan",
                                   "Horas Nominales Plan", "Horas Operativas Plan", "Metros Plan"], pp)
    escribir("plan_muro", ["Tag", "Fecha", "Valor"], pm)
    escribir("plan_semanal_chancador", ["Fecha", "Plan_Semanal_Chancado", "Plan_Ley_CuT"], pch)
    resumen(res)


def resumen(res):
    """Resumen por día para revisar los rangos (movimiento 150-260 kt, DF 82-94 %, UEBD 70-85 %, chancado 3.2-4.8 kt/h)."""
    por_dia = defaultdict(lambda: defaultdict(float))
    for f in res["horas"]:
        a = por_dia[f["Fecha"]]
        if f["Tipo Equipo"] == "Truck":
            a["mov"] += f["Movimiento Total"]
            a["nom"] += f["Horas Nominales"]
            a["disp"] += f["Horas Disponibles"]
            a["efec"] += f["Horas Efectivas"]
    chanc = defaultdict(float)
    for f in res["chanc_hora"]:
        chanc[f["Fecha"]] += f["Tonelaje"]
    print("  día          mov kt   DF %  UEBD %  chancado kt")
    for dia in sorted(por_dia):
        a = por_dia[dia]
        print(f"  {dia}  {a['mov'] / 1000:7.1f}  {a['disp'] / a['nom'] * 100:5.1f}  {a['efec'] / a['disp'] * 100:5.1f}"
              f"  {chanc[dia] / 1000:8.1f}")


if __name__ == "__main__":
    main()
