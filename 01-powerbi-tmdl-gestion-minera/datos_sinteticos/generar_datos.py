# -*- coding: utf-8 -*-
"""Genera los CSV sintéticos (100 % ficticios, empresa «Minera Demo») que alimentan el modelo semántico.

Cada CSV tiene las columnas de la tabla del modelo que lo lee (ver `tools_proyecto/verificar_modelo.py`).
Todo sale de una semilla fija (tools/sinteticos.py): ejecutar dos veces da archivos idénticos.

Periodo: 90 días de mina desde 2025-03-03 (día de mina = 08:00 a 08:00). La «hora de actualización» simulada es
2025-05-31 14:30: el último día de mina y el último día de planta (07:00 a 07:00) están en curso. Las series del
historiador de proceso cubren solo los últimos 46 días, como la ventana de 45 días que muestran los segmentadores.

    python datos_sinteticos/generar_datos.py
"""
import csv
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ_REPO = AQUI.parents[1]
sys.path.insert(0, str(RAIZ_REPO / "tools"))
from sinteticos import (FLOTA_CAEX, FLOTA_CARGADORES, FLOTA_PALAS, chancado_tph, dias,  # noqa: E402
                        granulometria, horas_equipo, movimiento_mina_dia, rng, velocidad_caex)

INICIO = date(2025, 3, 3)
N_DIAS = 90
DIAS = dias(INICIO, N_DIAS)
ULTIMO_DIA = DIAS[-1]                        # 2025-05-31
AHORA = datetime(2025, 5, 31, 14, 30)        # hora simulada de la última actualización
HORAS_EN_CURSO = 6.5                         # horas de mina transcurridas del último día (08:00 a 14:30)
N_BLOQUES_EN_CURSO = 7                       # H1..H7 con datos en el último día
INICIO_HIST = datetime(2025, 4, 16, 0, 0)    # el historiador guarda 46 días

CARGADORES = ["CARG-01", "CARG-02", "PALA-01", "PALA-02", "PALA-03"]   # flota de carguío que muestra el informe
EQUIPOS_PLAN = {"CARG-01": "Cargador CARG-01", "CARG-02": "Cargador CARG-02",
                "PALA-01": "Pala PALA-01", "PALA-02": "Pala PALA-02", "PALA-03": "Pala PALA-03"}
# (tronadura, destino, participación de la extracción de mina)
COMBOS_MINA = [
    ("F01_B101", "CHA_PRIM", 0.13), ("F01_B101", "BOT_N01", 0.15), ("F01_B101", "DL_PAD01", 0.03),
    ("F02_B201", "CHA_PRIM", 0.12), ("F02_B201", "BOT_N01", 0.14), ("F02_B201", "DL_PAD01", 0.07),
    ("F03_B301", "CHA_PRIM", 0.09), ("F03_B301", "BOT_N01", 0.19), ("F03_B301", "STO_01", 0.08),
]
PART_REMANEJO = 0.06                          # parte del movimiento total que sale de stock hacia chancado
PESO_CARGADOR = {"CARG-01": 0.14, "CARG-02": 0.16, "PALA-01": 0.24, "PALA-02": 0.24, "PALA-03": 0.22}
PART_CHANCADO = {"CARG-01": 0.40, "CARG-02": 0.34, "PALA-01": 0.44, "PALA-02": 0.36, "PALA-03": 0.38}
OTRO_DESTINO = {"CARG-01": "BOT_N01", "CARG-02": "DL_PAD01", "PALA-01": "BOT_N01", "PALA-02": "DL_PAD01", "PALA-03": "BOT_N01"}

SALIDAS = []   # (nombre, filas)


def fmt(x, d=1):
    return f"{x:.{d}f}"


def escribir_csv(nombre, cabecera, filas):
    p = AQUI / nombre
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cabecera)
        w.writerows(filas)
    SALIDAS.append((nombre, len(filas), p.stat().st_size))


def bloque_a_turno_hora(k):
    """Bloque H1..H24 (k = 0..23) -> (turno, hora dentro del turno 0..11)."""
    return ("A", k) if k < 12 else ("B", k - 12)


def n_bloques(d):
    return 24 if d != ULTIMO_DIA else N_BLOQUES_EN_CURSO


def peso_bloque(k, r):
    """Peso relativo del bloque horario: ciclo suave, caída en el cambio de turno y ruido."""
    import math
    base = 1 + 0.06 * math.sin(2 * math.pi * (k - 6) / 24) + r.gauss(0, 0.05)
    return base * (0.85 if k in (0, 12) else 1.0)


# ------------------------------------------------------------------------------------------------ mina
def generar_mina():
    r = rng("mina")
    total_dia = {d: movimiento_mina_dia(r)["total_kt"] * 1000 for d in DIAS}      # t/día
    descargas, cargas, turno_dias = [], [], {}
    bloques_dia = {}
    for d in DIAS:
        pesos = [peso_bloque(k, r) for k in range(24)]
        s = sum(pesos)
        bloques_dia[d] = [p * 24 / s for p in pesos]
    for d in DIAS:
        for k in range(n_bloques(d)):
            f = bloques_dia[d][k] / 24
            if d == ULTIMO_DIA and k == N_BLOQUES_EN_CURSO - 1:
                f *= 0.5                    # el último bloque viene a medias
            turno, hora = bloque_a_turno_hora(k)
            t_bloque = total_dia[d] * f
            for blast, dump, w in COMBOS_MINA:
                v = t_bloque * (1 - PART_REMANEJO) * w * r.gauss(1, 0.10)
                descargas.append((d.isoformat(), turno, hora, r.choice(FLOTA_CAEX), blast, dump, fmt(v)))
            v = t_bloque * PART_REMANEJO * r.gauss(1, 0.10)
            descargas.append((d.isoformat(), turno, hora, r.choice(FLOTA_CAEX), "STO_P01", "CHA_PRIM", fmt(v)))
            # cargas: ligeramente adelantadas respecto de las descargas
            t_carga = t_bloque * r.uniform(1.00, 1.03)
            for c in CARGADORES:
                tc = t_carga * PESO_CARGADOR[c] * r.gauss(1, 0.06)
                share = PART_CHANCADO[c] * r.gauss(1, 0.05)
                cargas.append((d.isoformat(), turno, hora, c, "CHANCADO", fmt(tc * share)))
                cargas.append((d.isoformat(), turno, hora, c, OTRO_DESTINO[c], fmt(tc * (1 - share))))
            turno_dias.setdefault((d, turno), set()).add(hora)
    escribir_csv("produccion_mina.csv", ["time", "shift", "hour", "truck", "blast", "dump", "material_tonnage"], descargas)
    escribir_csv("produccion_palas_hora.csv", ["time", "shift", "hour", "shovel", "dump", "material_tonnage"], cargas)
    # por turno (suma de cargas)
    por_turno = {}
    for d_, t_, h_, _, _, v in cargas:
        por_turno[(d_, t_)] = por_turno.get((d_, t_), 0.0) + float(v)
    escribir_csv("produccion_palas_turno.csv", ["time", "shift", "material_tonnage"],
                 [(d_, t_, fmt(v)) for (d_, t_), v in sorted(por_turno.items())])
    escribir_csv("calendario_turno.csv", ["time", "shift"],
                 [(d.isoformat(), t) for (d, t) in sorted(turno_dias)])
    escribir_csv("calendario_turno_hora.csv", ["time", "shift", "hour"],
                 [(d.isoformat(), t, h) for (d, t), hs in sorted(turno_dias.items()) for h in sorted(hs)])
    return total_dia


def horas_flota():
    """Horas de equipos: CAEX por día y carguío por turno. El día en curso solo trae las horas transcurridas."""
    r = rng("horas")
    caex, palas = [], []
    for d in DIAS:
        h_dia = 24.0 if d != ULTIMO_DIA else HORAS_EN_CURSO
        e = horas_equipo(r, "CAEX")
        nominal = 26 * h_dia
        hd = nominal * e["df_pct"] / 100
        efectivo = hd * e["uebd_pct"] / 100
        caex.append((d.isoformat(), fmt(nominal, 2), fmt(hd, 2), fmt(efectivo, 2)))
        for turno in ("A", "B"):
            if d == ULTIMO_DIA and turno == "B":
                continue
            h_turno = 12.0 if d != ULTIMO_DIA else HORAS_EN_CURSO
            for eq in CARGADORES:
                e = horas_equipo(r, "PALA")
                indisp = h_turno * (1 - e["df_pct"] / 100)
                mp, mnp = indisp * 0.4, indisp * 0.6
                hd_ = h_turno - mp - mnp
                efec = hd_ * e["uebd_pct"] / 100
                palas.append((d.isoformat(), turno, eq, fmt(h_turno, 2), fmt(mp, 2), fmt(mnp, 2), fmt(efec, 2)))
    escribir_csv("horas_caex.csv", ["time", "Nominal", "HD", "Efectivo"], caex)
    escribir_csv("horas_palas_turno.csv", ["time", "Shift", "equipment", "Nominal", "MP", "MNP", "Efectivo"], palas)


def generar_planes(total_dia):
    """Planes mensual y semanal por día. Formato único del bloque CAEX (horas nominales = 26 x 24)."""
    r = rng("planes")
    media = sum(total_dia.values()) / len(total_dia)
    filas = []
    base_mes, base_sem = {}, {}
    d = date(2025, 3, 1)
    while d <= ULTIMO_DIA:
        mes = (d.year, d.month)
        sem = d.isocalendar()[:2]
        base_mes.setdefault(mes, media * r.uniform(0.97, 1.03))
        base_sem.setdefault(sem, media * r.uniform(0.95, 1.05))
        for plan, base, sufijo in (("Mensual", base_mes[mes], ""), ("Semanal", base_sem[sem], " SEM")):
            total = base * r.uniform(0.98, 1.02) if plan == "Semanal" else base
            mina = total * (1 - PART_REMANEJO)
            cha = mina * sum(w for _, dp, w in COMBOS_MINA if dp == "CHA_PRIM")
            dl = mina * sum(w for _, dp, w in COMBOS_MINA if dp == "DL_PAD01")
            bot = mina * sum(w for _, dp, w in COMBOS_MINA if dp == "BOT_N01")
            sto = mina * sum(w for _, dp, w in COMBOS_MINA if dp == "STO_01")
            props = {
                "Total Toneladas" + sufijo: cha + dl + bot + sto + total * PART_REMANEJO,
                "Total Toneladas Chancado" + sufijo: cha,
                "Total Toneladas Chancador" + sufijo: cha + total * PART_REMANEJO,
                "Total Toneladas Dump" + sufijo: dl,
                "Total Toneladas Esteril" + sufijo: bot,
                "Total Toneladas Stock Sulfuro" + sufijo: sto,
            }
            if plan == "Semanal":
                nominal, disp, efec = 26 * 24.0, 26 * 24.0 * 0.90, 26 * 24.0 * 0.90 * 0.78
                props["Total Toneladas CAEX SEM"] = props["Total Toneladas SEM"]
                props["Horas Nominales CAEX SEM"] = nominal
                props["Horas Disponibles CAEX SEM"] = disp
                props["Horas Efectivas CAEX SEM"] = efec
                props["Horas Operativas CAEX SEM"] = efec
                for eq, nombre in EQUIPOS_PLAN.items():
                    props[f"Horas Nominales {nombre} SEM"] = 24.0
                    props[f"Horas Disponibles {nombre} SEM"] = 24.0 * 0.88
                    props[f"Horas Efectivas {nombre} SEM"] = 24.0 * 0.88 * 0.78
            for k, v in props.items():
                filas.append((d.isoformat(), k, fmt(v, 2), plan))
        d += timedelta(days=1)
    escribir_csv("planes_mina.csv", ["start_date", "property_name", "value", "plan_type"], filas)
    return media


# ------------------------------------------------------------------------------------------------ planta
def dia_planta(t):
    """Día de planta (07:00 a 07:00) al que pertenece una muestra; la muestra de las 07:00 cierra el día anterior."""
    return (t - timedelta(hours=7, seconds=1)).date()


def dia_mina(t):
    return (t - timedelta(hours=8, seconds=1)).date()


def generar_historiador():
    r = rng("historiador")
    slots = []
    t = INICIO_HIST
    while t <= AHORA:
        slots.append(t)
        t += timedelta(minutes=30)
    # paradas del SAG: pocas, de 1,5 a 3 h, nunca en las últimas 12 horas
    media_sag, paradas = {}, set()
    for t in slots:
        media_sag.setdefault(dia_planta(t), r.uniform(3500, 4100))
    for d in list(media_sag):
        if r.random() < 0.06:
            ini = datetime(d.year, d.month, d.day, 8) + timedelta(minutes=30 * r.randint(0, 30))
            for j in range(r.randint(3, 6)):
                paradas.add(ini + timedelta(minutes=30 * j))
    sag, chan, stock, finos, spi, peb, p80 = {}, {}, {}, {}, {}, {}, {}
    nivel = 60.0
    spi_v = 78.0
    for t in slots:
        reciente = t > AHORA - timedelta(hours=12)
        sag[t] = 0.0 if (t in paradas and not reciente) else max(0.0, r.gauss(media_sag[dia_planta(t)], 110))
        chan[t] = chancado_tph(r, t.hour)
        nivel = min(92.0, max(25.0, nivel + 0.05 * (60 - nivel) + r.gauss(0, 0.8)))
        stock[t] = nivel
        fino = granulometria(r)["Fina (<12 mm)"]
        finos[t] = fino if sag[t] > 1000 else r.uniform(92, 99)
        spi_v = min(95.0, max(60.0, spi_v + r.gauss(0, 0.6)))
        spi[t] = spi_v
        peb[t] = sag[t] * r.uniform(0.18, 0.23) if sag[t] > 0 else 0.0
        p80[t] = r.gauss(205, 9)
    # acumulado diario del SAG (se reinicia en la muestra siguiente a las 07:00) y proyección del día de mina
    acum, proy = {}, {}
    acc, pd_prev = 0.0, None
    suma_m, n_m, md_prev = 0.0, 0, None
    for t in slots:
        pd = dia_planta(t)
        if pd != pd_prev:
            acc, pd_prev = 0.0, pd
        acc += sag[t] * 0.5
        acum[t] = acc
        md = dia_mina(t)
        if md != md_prev:
            suma_m, n_m, md_prev = 0.0, 0, md
        suma_m += chan[t]
        n_m += 1
        proy[t] = (suma_m / n_m) * 24
    # planes de planta (cambian en la muestra de cierre de las 07:00)
    plan_dia, plan_tph = {}, {}
    for t in slots:
        d = (t - timedelta(hours=7)).date()
        if d not in plan_dia:
            sem = d.isocalendar()[:2]
            plan_tph.setdefault(sem, r.uniform(3750, 3950))
            plan_dia[d] = plan_tph[sem] * 24 * r.uniform(0.97, 1.0)
    series = {
        "CHANC.ALIM.TPH": chan, "CHANC.ALIM.PROY_DIA": proy, "STOCK.NIVEL.PCT": stock, "SAG.ALIM.TPH": sag,
        "SAG.ALIM.ACUM_DIA": acum,
        "PLAN.SAG.TON_DIA": {t: plan_dia[(t - timedelta(hours=7)).date()] for t in slots},
        "PLAN.SAG.TPH_SEM": {t: plan_tph[(t - timedelta(hours=7)).date().isocalendar()[:2]] for t in slots},
        "SAG.CORREA.FINOS_PCT": finos, "SAG.DUREZA.SPI": spi, "PEBBLES.RETORNO.TPH": peb, "CICLONES.P80.UM": p80,
    }
    filas = []
    for i, (tag, serie) in enumerate(series.items(), 1):
        for t in slots:
            filas.append((f"KPI-{i:02d}", t.strftime("%Y-%m-%d %H:%M:%S"), fmt(serie[t]), tag))
    escribir_csv("hist_kpi.csv", ["item_id", "timestamp", "numeric_value", "nombre_tag"], filas)

    # potencia de molinos (kW), misma rejilla de 30 min
    kw = []
    for t in slots:
        kw.append(("SAG.MOTOR.KW", t.strftime("%Y-%m-%d %H:%M:%S"), fmt(r.gauss(15500, 500) if sag[t] > 100 else 0.0)))
        kw.append(("BOLAS.01.KW", t.strftime("%Y-%m-%d %H:%M:%S"), fmt(r.gauss(10200, 350))))
        kw.append(("BOLAS.02.KW", t.strftime("%Y-%m-%d %H:%M:%S"), fmt(r.gauss(9900, 350))))
    escribir_csv("hist_potencia.csv", ["nombre_tag", "timestamp", "numeric_value"], kw)

    # señales on/off y contadores (cada hora en punto)
    horas = [t for t in slots if t.minute == 0]
    onoff = ["EST.CHANC.01"] + [f"EST.ALIM.{i:02d}" for i in range(1, 7)] + ["EST.SAG.01"] + \
            [f"EST.PEBBLES.{i:02d}" for i in range(1, 4)] + [f"EST.BOLAS.{i:02d}" for i in range(1, 3)]
    contadores = [f"CIC.VALVULAS_ABIERTAS.{i:02d}" for i in range(1, 5)]
    filas = []
    for n, nombre in enumerate(onoff + contadores, 1):
        sid = f"SIG-{n:02d}"
        es_cont = nombre in contadores
        valv = r.randint(3, 8)
        for t in horas:
            if nombre == "EST.ALIM.06" and t > datetime(2025, 5, 31, 12, 0):
                continue                                        # sin señal: la última muestra tiene más de 1 h
            if es_cont:
                if r.random() < 0.08:
                    valv = min(10, max(2, valv + r.choice((-1, 1))))
                filas.append((sid, t.strftime("%Y-%m-%d %H:%M:%S"), valv, 1 if valv > 0 else 0, nombre, "Contador"))
                continue
            on = 0 if r.random() < 0.015 else 1
            if nombre == "EST.SAG.01":
                on = 0 if sag[t] <= 100 else 1
            if nombre == "EST.PEBBLES.03" and t >= datetime(2025, 5, 31, 10, 0):
                on = 0                                          # un equipo detenido en la vista en línea
            filas.append((sid, t.strftime("%Y-%m-%d %H:%M:%S"), on, on, nombre, "OnOff"))
    escribir_csv("hist_senales.csv", ["item_id", "timestamp", "numeric_value", "estado", "dim_variable.name", "dim_variable.tipo_variable"], filas)
    return sag, acum, slots, plan_tph


def generar_cierres(sag, slots):
    """Cierres diarios publicados al día siguiente, plan de planta, DF y UE diarios."""
    r = rng("cierres")
    por_dia = {}
    for t in slots:
        pd = dia_planta(t)
        v = por_dia.setdefault(pd, [0.0, 0])
        v[0] += sag[t] * 0.5
        if sag[t] > 100:
            v[1] += 1
    ult_cerrado = dia_planta(AHORA) - timedelta(days=1)          # 2025-05-30: su cierre aún no se publica
    cierre, ejec = [], []
    for d in sorted(por_dia):
        if d < INICIO_HIST.date() + timedelta(days=1) or d >= ult_cerrado:
            continue
        ton, n = por_dia[d]
        horas = 0.5 * n
        if horas <= 0:
            continue
        cierre.append(("PLANTA.CIERRE.OFICIAL", d.isoformat(), fmt(ton * r.uniform(0.0050, 0.0058))))
        cierre.append(("PLANTA.SAG.TON_DIA", d.isoformat(), fmt(ton)))
        ejec.append(("PLANTA.SAG.HORAS_EF", d.isoformat(), fmt(horas, 2)))
        ejec.append(("PLANTA.SAG.TPH_EF", d.isoformat(), fmt(ton / horas)))
    escribir_csv("planta_cierre.csv", ["Punto", "Fecha", "Valor"], cierre)
    escribir_csv("planta_cierre_ejec.csv", ["Punto", "Fecha", "Valor"], ejec)
    escribir_csv("planta_plan_spi.csv", ["Fecha", "Valor"], [(d.isoformat(), fmt(r.uniform(72, 80))) for d in DIAS])
    escribir_csv("planta_plan_puntos.csv", ["Punto", "Fecha", "Valor"],
                 [("PLANTA.P80.PLAN", d.isoformat(), fmt(r.uniform(195, 205))) for d in DIAS])
    # plan por fase: reparte el plan de movimiento del día
    filas = []
    for d in DIAS:
        total = r.uniform(190000, 215000)
        for clave, w in (("F01", 0.31), ("F02", 0.33), ("F03", 0.36)):
            filas.append((d.isoformat(), clave, fmt(total * w * r.uniform(0.97, 1.03), 0)))
    escribir_csv("planta_plan_fase.csv", ["Fecha", "Clave", "Toneladas"], filas)
    # DF y UE diarios por área (se publican al día siguiente: el día en curso no existe)
    areas = ["Chancado Primario", "Feeders", "Molienda", "Circuitos Pebbles", "MB1", "MB2", "Molienda Secundaria"]
    filas = []
    for d in DIAS[:-1]:
        for a in areas:
            filas.append((d.isoformat(), a, "DF", fmt(r.uniform(82, 94))))
            filas.append((d.isoformat(), a, "UE", fmt(r.uniform(70, 85))))
    escribir_csv("equipos_df_ue.csv", ["Fecha", "Nombre", "Medicion", "Valor"], filas)
    filas = []
    for d in DIAS[:-1]:
        for _ in range(4):                                      # 4 baterías de hidrociclones
            filas.append((d.isoformat(), "DF", fmt(r.uniform(82, 94))))
            filas.append((d.isoformat(), "UE", fmt(r.uniform(70, 85))))
    escribir_csv("equipos_ciclones.csv", ["Fecha", "Medicion", "Valor"], filas)


def generar_actualizacion():
    t = AHORA.strftime("%Y-%m-%d %H:%M:%S")
    escribir_csv("actualizacion.csv", ["Actualizado"], [(t,)])
    escribir_csv("pulso.csv", ["Ahora"], [(t,)])


def generar_ciclos():
    """Extra (no lo lee el modelo): velocidades de CAEX por turno, para las consultas de ejemplo de sql/."""
    r = rng("ciclos")
    filas = []
    for d in DIAS:
        for turno in ("A", "B"):
            for cx in FLOTA_CAEX:
                filas.append((d.isoformat(), turno, cx, r.randint(18, 30), fmt(velocidad_caex(r, True)), fmt(velocidad_caex(r, False))))
    escribir_csv("ciclos_caex.csv", ["fecha", "turno", "equipo", "ciclos", "velocidad_cargado_kmh", "velocidad_vacio_kmh"], filas)


def main():
    total_dia = generar_mina()
    horas_flota()
    generar_planes(total_dia)
    sag, acum, slots, plan_tph = generar_historiador()
    generar_cierres(sag, slots)
    generar_actualizacion()
    generar_ciclos()
    print(f"{'archivo':32s} {'filas':>8s} {'KB':>8s}")
    exceso = False
    for nombre, n, tam in sorted(SALIDAS):
        print(f"{nombre:32s} {n:8d} {tam / 1024:8.1f}")
        exceso |= tam > 2 * 1024 * 1024
    if exceso:
        sys.exit("ERROR: algún CSV supera 2 MB")


if __name__ == "__main__":
    main()
