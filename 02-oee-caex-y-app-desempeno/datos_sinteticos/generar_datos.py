# -*- coding: utf-8 -*-
"""Genera los datos 100 % sintéticos del proyecto (empresa ficticia «Minera Demo»).

Salida (CSV UTF-8, coma como separador, punto decimal, fechas ISO):
  datos_sinteticos/oee/  tablas del modelo semántico (pbip/): una carpeta que se indica en el parámetro RutaDatos
  datos_sinteticos/app/  tablas Excel de la app RD Terreno (mismas columnas que app/herramientas/crear_excel_demo.py)

Reproducible: toda cifra sale de una semilla fija (tools/sinteticos.py). Periodo: 90 días desde 2025-03-03.
Rangos: movimiento de la flota CAEX 150-260 kt/día, DF 82-94 %, UEBD 70-85 %, CAEX-01..26, turnos A (08-20) y B (20-08).

Uso:  python datos_sinteticos/generar_datos.py
"""
import csv
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[1] / "tools"))
from sinteticos import DOMINIO, FLOTA_CAEX, FLOTA_PALAS, GRUPOS, dias, personas, rng  # noqa: E402

SALIDA_OEE = AQUI / "oee"
SALIDA_APP = AQUI / "app"
MAX_BYTES = 2 * 1024 * 1024

INICIO = date(2025, 3, 3)           # lunes
NDIAS = 90
FECHAS = dias(INICIO, NDIAS)        # 2025-03-03 .. 2025-05-31
ULTIMO = FECHAS[-1]
MARCA = datetime(2025, 6, 1, 9, 30)  # «última actualización» del conjunto de datos
HOY_OPERACIONAL = MARCA.date() if MARCA.hour >= 8 else MARCA.date() - timedelta(days=1)

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre",
         "diciembre"]
MESES_CORTO = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Plan de la flota (valores inventados). Semanal: cambia por semana; mensual: por mes.
FLOTA_PLAN = 26
HORAS_NOMINALES_DIA = 24 * FLOTA_PLAN
PLAN_SEMANAL = {  # (disponibilidad, UEBD, rendimiento t/h); se elige por número de semana
    0: (0.880, 0.780, 480), 1: (0.870, 0.775, 475), 2: (0.885, 0.785, 485), 3: (0.880, 0.780, 480),
}
PLAN_MENSUAL = {3: (0.880, 0.780, 480), 4: (0.875, 0.780, 485), 5: (0.885, 0.785, 480)}
SEMANAS_FLOTA_25 = {3, 8}           # semanas con 25 CAEX en el plan
DIAS_SIN_PLAN_SEMANAL = {date(2025, 4, 9), date(2025, 4, 10)}
DIAS_SIN_PLAN_FACTOR = {date(2025, 4, 20) + timedelta(days=k) for k in range(5)}
PLAN_FACTOR_CARGA = 275.0           # t por carga (valor inventado)

# Códigos de horas (categoría, código). Las categorías son las que usan las medidas DAX.
MANT_PROG = [("Mantención programada", "Mantención preventiva"), ("Mantención programada", "Inspección programada"),
             ("Cambio programado de neumáticos", "Cambio de neumáticos programado")]
MANT_NO_PROG = [("Mantención no programada", "Falla de motor"), ("Mantención no programada", "Falla eléctrica"),
                ("Mantención no programada", "Sistema hidráulico"), ("Mantención no programada", "Frenos y suspensión"),
                ("Neumáticos", "Neumático dañado"), ("Daño operacional", "Daño por impacto")]
DEM_PROG = [("Demora programada", "Cambio de turno"), ("Demora programada", "Colación"),
            ("Demora programada", "Abastecimiento de combustible")]
DEM_NO_PROG = [("Demora no programada", "Espera de pala"), ("Demora no programada", "Tronadura"),
               ("Demora no programada", "Camino en mantención"), ("Demora no programada", "Condiciones climáticas"),
               ("Demora no programada", "Falta de frente")]
RESERVA = [("Reserva", "Reserva operacional"), ("Reserva", "Sin operador")]
CAT_MANT_PROG = {"Mantención programada", "Cambio programado de neumáticos"}


def escribir(ruta, columnas, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columnas)
        w.writerows(filas)
    if ruta.stat().st_size >= MAX_BYTES:
        raise SystemExit(f"{ruta.name} pesa {ruta.stat().st_size} bytes: supera el límite de 2 MB")
    print(f"  {ruta.relative_to(AQUI)}: {ruta.stat().st_size // 1024} KB")


def clip(x, lo, hi):
    return max(lo, min(hi, x))


def repartir(r, total, opciones, maximo):
    """Reparte `total` horas entre 1..maximo códigos de `opciones`; la suma es exacta a 2 decimales."""
    if total < 0.01:
        return []
    elegidas = r.sample(opciones, min(len(opciones), r.randint(1, maximo)))
    pesos = [r.uniform(0.3, 1.0) for _ in elegidas]
    s = sum(pesos)
    horas = [round(total * p / s, 2) for p in pesos]
    horas[-1] = round(total - sum(horas[:-1]), 2)
    return [(cat, cod, h) for (cat, cod), h in zip(elegidas, horas) if h > 0]


# ---------------------------------------------------------------------------------------------------------------------
# Modelo semántico (OEE de transporte)
# ---------------------------------------------------------------------------------------------------------------------

def dimensiones():
    equipos = [(e, "Truck", "CAEX", 1, 0) for e in FLOTA_CAEX] + [(e, "Shovel", "Pala", 1, 1) for e in FLOTA_PALAS]
    escribir(SALIDA_OEE / "Dim_Equipo.csv", ["Equipo", "TipoEquipo", "Flota", "Activo_KPI", "Es Carguio"], equipos)
    escribir(SALIDA_OEE / "Dim_Turno.csv", ["Turno", "Nombre", "HoraInicio", "HoraFin"],
             [("A", "Turno A (08:00-20:00)", "1899-12-30 08:00:00", "1899-12-30 20:00:00"),
              ("B", "Turno B (20:00-08:00)", "1899-12-30 20:00:00", "1899-12-30 08:00:00")])
    escribir(SALIDA_OEE / "Dim_Actualizacion.csv", ["Marca", "Hora_Texto"],
             [(MARCA.strftime("%Y-%m-%d %H:%M:%S"), MARCA.strftime("%H:%M"))])
    filas = []
    for d in FECHAS + [FECHAS[-1] + timedelta(days=1)]:
        lunes = d - timedelta(days=d.weekday())
        filas.append((
            d.isoformat(), d.year, d.month, MESES[d.month - 1], f"{d.year}-{d.month:02d}", d.isocalendar()[1],
            d.weekday() + 1, DIAS_SEMANA[d.weekday()], lunes.isoformat(),
            f"Sem {lunes.day:02d}-{MESES_CORTO[lunes.month - 1]}", f"{MESES_CORTO[d.month - 1]} {d.year}",
            "TRUE" if d == HOY_OPERACIONAL else "FALSE",
            "HOY" if d == HOY_OPERACIONAL else f"{DIAS_SEMANA[d.weekday()]} {d.day:02d} de {MESES[d.month - 1]} de {d.year}"))
    escribir(SALIDA_OEE / "Dim_Tiempo.csv",
             ["Fecha", "Anio", "Mes", "NombreMes", "AnioMes", "Semana", "DiaSemana", "NombreDia", "Semana_Inicio",
              "Etiqueta_Semana", "Etiqueta_Mes", "Es_Hoy_Operacional", "Dia_Etiqueta"], filas)


def planes():
    semana = lambda d: ((d - INICIO).days // 7)  # noqa: E731
    semanal, mensual, factor = [], [], []
    for d in FECHAS:
        df, ue, rend = PLAN_SEMANAL[semana(d) % 4]
        flota = 25 if semana(d) in SEMANAS_FLOTA_25 else FLOTA_PLAN
        hn = 24 * flota
        hd, he = hn * df, hn * df * ue
        if d not in DIAS_SIN_PLAN_SEMANAL:
            semanal.append((d.isoformat(), round(hd, 1), round(he, 1), round(hn, 1), round(he * rend, 0)))
        df, ue, rend = PLAN_MENSUAL[d.month]
        hn, hd = HORAS_NOMINALES_DIA, HORAS_NOMINALES_DIA * df
        he = hd * ue
        for item, v in (("Horas Nominales CAEX", hn), ("Horas Disponibles CAEX", hd), ("Horas Efectivas CAEX", he),
                        ("Total Toneladas CAEX", he * rend)):
            mensual.append((d.isoformat(), item, round(v, 1), "Mensual"))
        if d not in DIAS_SIN_PLAN_FACTOR:
            factor.append((d.isoformat(), PLAN_FACTOR_CARGA))
    escribir(SALIDA_OEE / "Plan_CAEX.csv",
             ["Fecha", "Horas Disponibles Plan", "Horas Efectivas Plan", "Horas Nominales Plan", "Toneladas Plan"], semanal)
    escribir(SALIDA_OEE / "Planes_Mina.csv", ["start_date", "property_name", "value", "plan_type"], mensual)
    escribir(SALIDA_OEE / "Plan_FactorCarga.csv", ["Fecha", "Plan"], factor)


def operacion():
    """Horas por equipo y turno, códigos de horas y ciclos de acarreo de los CAEX."""
    r = rng("flota")
    fuera = {}
    for eq in r.sample(FLOTA_CAEX, 7):
        ini = r.randrange(0, NDIAS - 9)
        fuera[eq] = {FECHAS[ini + k] for k in range(r.randint(2, 9))}
    base = {eq: dict(df=r.uniform(0.85, 0.93), ue=r.uniform(0.725, 0.815), rend=r.uniform(450, 510)) for eq in FLOTA_CAEX}
    operadores = [p["nombre"] for p in personas(30, "operadores")]
    palas_de = {eq: FLOTA_PALAS[i % 4] for i, eq in enumerate(FLOTA_CAEX)}

    r = rng("horas")
    rc = rng("ciclos")
    horas, codigos, ciclos = [], [], []
    ventana_codigos = FECHAS[-45]
    mov_dia = {}
    for i_dia, d in enumerate(FECHAS):
        for turno in ("A", "B"):
            for eq in FLOTA_CAEX:
                if d in fuera.get(eq, ()):
                    continue
                b = base[eq]
                df = clip(r.gauss(b["df"], 0.04), 0.5, 0.99)
                if r.random() < 0.06:
                    df = r.uniform(0.35, 0.7)  # falla mayor en el turno
                ue = clip(r.gauss(b["ue"], 0.035), 0.55, 0.9)
                nominal = 12.0
                no_disp = nominal * (1 - df)
                mant_prog = no_disp * clip(r.gauss(0.55, 0.15), 0.1, 0.9)
                items = repartir(r, mant_prog, MANT_PROG, 2) + repartir(r, no_disp - mant_prog, MANT_NO_PROG, 2)
                h_mp = round(sum(h for c, _, h in items if c in CAT_MANT_PROG), 2)
                h_mn = round(sum(h for c, _, h in items if c not in CAT_MANT_PROG), 2)
                hd = round(nominal - h_mp - h_mn, 2)
                no_efectivo = hd * (1 - ue)
                w = [r.uniform(0.7, 1.3) * x for x in (0.30, 0.18, 0.22, 0.18, 0.12)]
                sw = sum(w)
                dp, dn, rs, pe, pc = (round(no_efectivo * x / sw, 2) for x in w)
                it_ef = (repartir(r, dp, DEM_PROG, 2) + repartir(r, dn, DEM_NO_PROG, 3) + repartir(r, rs, RESERVA, 2))
                dp = round(sum(h for c, _, h in it_ef if c == "Demora programada"), 2)
                dn = round(sum(h for c, _, h in it_ef if c == "Demora no programada"), 2)
                rs = round(sum(h for c, _, h in it_ef if c == "Reserva"), 2)
                he = round(hd - dp - dn - rs - pe - pc, 2)
                rend = r.gauss(b["rend"] * (0.985 if turno == "B" else 1.0), 22)
                mov = round(he * rend, 0)
                extraido = round(mov * r.uniform(0.90, 0.96), 0)
                horas.append((d.isoformat(), turno, "Truck", eq, "CAEX", nominal, he, round(pe, 2), round(pc, 2),
                              round(pe + pc, 2), dn, dp, rs, hd, h_mp, h_mn, mov, extraido, mov - extraido))
                mov_dia[d] = mov_dia.get(d, 0) + mov
                if d >= ventana_codigos:
                    codigos += [(d.isoformat(), turno, eq, c, cod, h) for c, cod, h in items + it_ef]
                crew = GRUPOS[((i_dia // 2) + (0 if turno == "A" else 2)) % 4]
                operador = operadores[(FLOTA_CAEX.index(eq) * 3 + i_dia // 3 + (0 if turno == "A" else 11)) % 30]
                for _ in range(2):
                    carga = rc.gauss(272, 12)
                    if rc.random() < 0.03:
                        carga = rc.uniform(40, 190)    # carga parcial
                    elif rc.random() < 0.005:
                        carga = rc.uniform(335, 360)   # lectura anómala
                    destino = rc.choices(["Crusher", "Dump", "Stockpile"], [0.6, 0.3, 0.1])[0]
                    ciclos.append((d.isoformat(), turno, crew, eq,
                                   palas_de[eq] if rc.random() > 0.15 else rc.choice(FLOTA_PALAS), destino, operador,
                                   round(carga, 1), int(rc.gauss(330, 40)), int(abs(rc.gauss(60, 30))),
                                   int(clip(rc.gauss(35, 10), 10, 80)), int(clip(rc.gauss(170, 30), 80, 300)),
                                   int(rc.gauss(520, 60)), int(abs(rc.gauss(45, 25))), int(clip(rc.gauss(25, 8), 8, 60)),
                                   int(clip(rc.gauss(40, 10), 15, 90))))
    # El movimiento diario de la flota debe quedar en el rango pedido (150-260 kt)
    for d, m in mov_dia.items():
        if not 150_000 <= m <= 260_000:
            raise SystemExit(f"Movimiento fuera de rango el {d}: {m:,.0f} t")
    escribir(SALIDA_OEE / "Fact_HorasEquipo.csv",
             ["Fecha", "Turno", "Tipo Equipo", "Equipo", "Flota", "Horas Nominales", "Horas Efectivas", "Horas PO Espera",
              "Horas PO Cola", "Horas PO Totales", "Horas Demora No Programada", "Horas Demora Programada", "Horas Reserva",
              "Horas Disponibles", "Horas Mantencion Programada", "Horas Mantencion No Programada", "Movimiento Total",
              "Material Extraido", "Material Remanejo"], horas)
    escribir(SALIDA_OEE / "Horas_Codigo_CAEX.csv", ["Fecha", "Turno", "Equipo", "Categoria", "Codigo", "Horas"], codigos)
    escribir(SALIDA_OEE / "Fact_Ciclos.csv",
             ["time", "shift", "crew", "TruckName", "ShovelName", "Dump_LocationType", "TruckOpName", "payload",
              "traveling_time", "waiting_time", "spotting_time", "loading_time", "hauling_time", "queued_time",
              "backing_time", "tipping_time"], ciclos)
    return horas, mov_dia


# ---------------------------------------------------------------------------------------------------------------------
# App RD Terreno (tablas Excel)
# ---------------------------------------------------------------------------------------------------------------------

TITULOS = [
    "Revisar la asignación de CAEX a la pala PALA-02 en el turno B", "Actualizar el estándar de cambio de turno en terreno",
    "Reforzar el control de velocidad en la rampa de la fase 3", "Ajustar el plan de mantención de neumáticos de la flota",
    "Programar la limpieza del camino en el sector de descarga", "Confirmar la disponibilidad de repuestos críticos de frenos",
    "Medir tiempos de espera en carguío durante tres turnos", "Coordinar la tronadura con la ventana de cambio de turno",
    "Validar la calibración de las balanzas de payload", "Capacitar a operadores en aculatamiento seguro",
    "Levantar las causas de colas en la descarga del chancador", "Revisar el programa de lubricación de la flota",
    "Definir el criterio de reserva operacional por turno", "Verificar la señalética de los accesos a la fase 2",
    "Implementar un checklist de inicio de turno en CAEX", "Evaluar rutas alternativas durante la mantención del camino",
    "Actualizar el plan de abastecimiento de combustible", "Analizar las demoras no programadas por clima",
    "Consolidar el reporte de incidentes de la semana", "Cerrar los hallazgos de la inspección de seguridad del taller",
    "Revisar el factor de carga de la flota en la fase 1", "Ajustar el ciclo de acarreo hacia el stockpile",
    "Reducir la espera de camiones en la pala PALA-03", "Documentar el procedimiento de reserva de equipos",
    "Coordinar el relevo de operadores en la colación", "Priorizar la mantención de los CAEX con más horas caídas",
    "Revisar el mantenimiento del camino de acarreo", "Alinear el plan semanal con el programa de tronaduras",
    "Medir la disponibilidad física por flota y turno", "Definir las metas de UEBD por turno para el próximo mes",
]
COMENTARIOS = ["Avance según lo planificado.", "Pendiente de repuestos.", "Se coordinó con mantención.", "Falta confirmar fecha.",
               "Listo, queda registrada la evidencia.", "Se revisa de nuevo la próxima semana.", "Sin novedades.", ""]
AVISOS = [("Crítico", "Material suelto en la rampa de la fase 3: reducir la velocidad y avisar al despacho."),
          ("Precaución", "Viento fuerte en la tarde: asegurar tapas y señales móviles."),
          ("Precaución", "Visibilidad reducida por polvo en el camino de acarreo."),
          ("Recordar", "Uso de cinturón de seguridad en todos los CAEX."),
          ("Recordar", "Distancia de seguridad en la cola de descarga."),
          ("Crítico", "Tronadura programada en la fase 2: respetar el radio de exclusión.")]
METEO = ["Viento moderado en la tarde, sin precipitaciones.", "Nubosidad parcial, temperatura baja en el turno B.",
         "Viento fuerte desde la tarde, posible polvo en el camino.", "Despejado, sin restricciones."]
ACTIVIDADES = ["Acarreo normal con tres palas operando.", "Mantención programada de dos CAEX y una pala.",
               "Preparación de la fase 3 y apertura de rampa nueva.", "Operación con la pala PALA-04 en reserva."]
TRONADURAS = ["Una tronadura en la fase 2 el miércoles.", "Dos tronaduras: fase 1 y fase 3.", "Sin tronaduras esta semana."]
POSICIONAMIENTO = ["Palas en las fases 1, 2 y 3.", "Pala de reserva en la fase 4.", "Cambio de pala en la fase 2."]
RIESGOS = ["Cruce de camiones y vehículos livianos en el acceso norte.", "Caída de rocas en el talud de la fase 3.",
           "Condición de piso blando por la humedad."]


def _hora(d, h, m):
    return datetime(d.year, d.month, d.day, h, m)


def app(horas, mov_dia):
    r = rng("app")
    gente = personas(24, "participantes")
    areas = ["Mina", "Chancado", "Molienda", "Mantención", "Planificación"]
    cargos = {"Mina": "Supervisor de Mina", "Chancado": "Supervisor de Chancado", "Molienda": "Supervisor de Molienda",
              "Mantención": "Supervisor de Mantención", "Planificación": "Planificador"}
    participantes = []
    for i, p in enumerate(gente):
        area = "" if i == 23 else areas[i % 5]
        participantes.append((p["nombre"], p["correo"], cargos.get(area, p["cargo"]), "No" if i in (20, 22) else "Sí", area))
    escribir(SALIDA_APP / "RD_Participantes.csv", ["Nombre", "Correo", "Cargo", "Activo", "Area"], participantes)
    activos = [p for p in participantes if p[3] == "Sí"]
    lider = gente[0]

    lunes = [INICIO + timedelta(days=7 * k) for k in range(13)]       # 03-03 .. 05-26
    proxima = lunes[-1] + timedelta(days=7)                           # reunión por preparar (editor)
    compromisos, revisiones, sesiones, asistencia, destacados, plan_sem, preparaciones = [], [], [], [], [], [], []
    abiertos = []        # compromisos vigentes (dict)
    siguiente_id = 1
    for k, d in enumerate(lunes):
        # Revisión de los compromisos abiertos
        cierre_txt = _hora(d, 9, 5 + k % 10).strftime("%Y-%m-%d %H:%M")
        for c in list(abiertos):
            vencido = date.fromisoformat(c["FechaLimite"]) < d
            estado = r.choices(["Cumplido", "En progreso", "Atrasado"], [0.55, 0.30, 0.15])[0]
            if vencido and estado == "En progreso":
                estado = "Atrasado"
            comentario = r.choice(COMENTARIOS) if estado != "Cumplido" else r.choice(COMENTARIOS[4:5] + COMENTARIOS[:2])
            revisiones.append((cierre_txt, c["ID"], c["Titulo"], c["Estado"], estado, comentario, "Supervisores",
                               f"ses-{d:%Y%m%d}", f"REV-{d:%Y%m%d}-{c['ID']}"))
            c["Estado"], c["Comentario"] = estado, comentario
            if estado == "Cumplido":
                c["Abierto"], c["FechaCierre"] = "No", cierre_txt
                if r.random() < 0.3:
                    c["EvidenciaUrl"] = f"https://{DOMINIO}/rd/evidencias/Prep_{d:%Y-%m-%d}_C{c['ID']}_083015.jpg"
                abiertos.remove(c)
        # Compromisos nuevos de la reunión
        for _ in range(r.randint(3, 4)):
            resp = r.choice(activos)
            c = {"ID": siguiente_id, "Titulo": TITULOS[(siguiente_id * 7) % len(TITULOS)], "ResponsableNombre": resp[0],
                 "FechaLimite": (d + timedelta(days=r.choice([7, 14, 14, 21]))).isoformat(), "Estado": "En progreso",
                 "Abierto": "Sí", "FechaCreacion": d.isoformat(), "FechaCierre": "", "Comentario": "", "EvidenciaUrl": "",
                 "Grupo": "Supervisores", "Prioridad": r.choice(["Alta", "Media", "Media", "Baja"]), "Origen": "Reunión",
                 "ResponsableEmail": resp[1], "SesionIdLocal": f"ses-{d:%Y%m%d}", "IdLocal": f"cmp-{siguiente_id:04d}"}
            siguiente_id += 1
            compromisos.append(c)
            abiertos.append(c)
        # Sesión y asistencia
        presentes = [p for p in activos if r.random() > 0.12]
        ausentes = [p[0] for p in activos if p not in presentes]
        dur = round(r.uniform(36, 47), 1)
        t_bloques = [{"Bloque": b, "Seg": int(m * 60 * r.uniform(0.8, 1.2))} for b, m in ((0, 1), (1, 5), (2, 10), (3, 20), (4, 5))]
        sesiones.append((d.isoformat(), "Reunión semanal RD", "Supervisores", "Mina", "Cerrada",
                         _hora(d, 8, 30).strftime("%Y-%m-%d %H:%M"),
                         (_hora(d, 8, 30) + timedelta(minutes=dur)).strftime("%Y-%m-%d %H:%M"), dur, max(0, round(dur - 40, 1)),
                         len(presentes), 0, 0, 0, 0, 0, AVISOS[k % len(AVISOS)][1], json.dumps(t_bloques, separators=(",", ":")),
                         sum(1 for c in compromisos if c["FechaCreacion"] == d.isoformat()), 0, lider["nombre"],
                         lider["correo"], "", "", "", f"ses-{d:%Y%m%d}"))
        json_asis = [{"Nombre": p[0], "Correo": p[1], "Area": p[4] or "Sin área", "Tipo": "Convocado", "Presente": p in presentes}
                     for p in activos]
        asistencia.append((d.isoformat(), f"ses-{d:%Y%m%d}", len(activos), len(presentes), 0, ", ".join(ausentes),
                           json.dumps(json_asis, ensure_ascii=False, separators=(",", ":")), lider["correo"]))
        for o, tipo in enumerate(("Highlight", "Lowlight", "Tema")):
            if k % 3 == o or k % 4 == 0:
                destacados.append((d.isoformat(), tipo, o + 1, ["Disponibilidad sobre el plan en el turno A.",
                                   "Demoras de cambio de turno sobre lo esperado.",
                                   "Definir el criterio de reserva operacional."][o], "Supervisores", f"ses-{d:%Y%m%d}",
                                   f"dst-{d:%Y%m%d}-{o + 1}"))
        plan_sem.append((d.isoformat(), "Supervisores", METEO[k % 4], ACTIVIDADES[k % 4], TRONADURAS[k % 3],
                         POSICIONAMIENTO[k % 3], RIESGOS[k % 3]))
    plan_sem.append((proxima.isoformat(), "Supervisores", METEO[1], ACTIVIDADES[2], TRONADURAS[0], POSICIONAMIENTO[1], RIESGOS[1]))

    # Preparación (editor): una fila por reunión; la última es la reunión por presentar
    for clave, vigentes in ((lunes[-2], None), (lunes[-1], None), (proxima, abiertos)):
        avisos = [{"id": f"avi-{i}", "n": n, "x": x, "o": i} for i, (n, x) in enumerate(AVISOS[:4], start=1)]
        est = [{"id": c["ID"], "estado": c["Estado"], "rev": True, "com": c["Comentario"], "url": c["EvidenciaUrl"]}
               for c in (vigentes or [])]
        nue = [{"id": "nue-1", "t": TITULOS[3], "r": activos[2][0], "f": (clave + timedelta(days=14)).isoformat()}]
        prep = {"seg": "\n".join(f"{n}: {x}" for n, x in AVISOS[:4]), "avi": avisos,
                "ind": {"inc": 0, "inca": 1, "rep": 6, "repm": 5, "ire": 18, "ipl": 20}, "cor": lider["correo"], "est": est,
                "des": [], "nue": nue}
        preparaciones.append((clave.isoformat(), json.dumps(prep, ensure_ascii=False, separators=(",", ":")),
                              _hora(clave - timedelta(days=1), 16, 40).strftime("%Y-%m-%d %H:%M"), lider["nombre"]))

    cols = ["ID", "Titulo", "ResponsableNombre", "FechaLimite", "Estado", "Abierto", "FechaCreacion", "FechaCierre", "Comentario",
            "EvidenciaUrl", "Grupo", "Prioridad", "Origen", "ResponsableEmail", "SesionIdLocal", "IdLocal"]
    escribir(SALIDA_APP / "RD_Compromisos.csv", cols, [[c[k] for k in cols] for c in compromisos])
    escribir(SALIDA_APP / "RD_RevisionCompromisos.csv",
             ["FechaRevision", "CompromisoId", "Compromiso", "EstadoAnterior", "EstadoNuevo", "Comentario", "Grupo",
              "SesionIdLocal", "Clave"], revisiones)
    escribir(SALIDA_APP / "RD_Sesiones.csv",
             ["Fecha", "Titulo", "Grupo", "Area", "Estado", "HoraInicio", "HoraTermino", "MinutosDuracion", "MinutosExceso",
              "Asistentes", "Animo1", "Animo2", "Animo3", "Animo4", "Animo5", "TemaSeguridad", "TiemposBloques",
              "CompromisosNuevos", "IdeasPresentadas", "LiderNombre", "LiderEmail", "Motivo", "Observaciones", "RutaActa",
              "IdLocal"], sesiones)
    escribir(SALIDA_APP / "RD_Destacados.csv",
             ["FechaReunion", "Tipo", "Orden", "Texto", "Grupo", "SesionIdLocal", "IdLocal"], destacados)
    escribir(SALIDA_APP / "RD_PlanSemanal.csv",
             ["SemanaInicio", "Grupo", "Meteorologia", "Actividades", "Tronaduras", "Posicionamiento", "Riesgos"], plan_sem)
    escribir(SALIDA_APP / "RD_Preparacion.csv", ["Clave", "Json", "Actualizado", "Autor"], preparaciones)
    escribir(SALIDA_APP / "RD_Asistencia.csv",
             ["Fecha", "SesionIdLocal", "Convocados", "Presentes", "Invitados", "Ausentes", "Json", "LiderEmail"], asistencia)
    kpi_semanal(lunes[-4:], horas, mov_dia)


def kpi_semanal(lunes, horas, mov_dia):
    """Catálogo de 13 indicadores (JSON por semana). Los de CAEX salen de las horas generadas; el resto, de rangos inventados."""
    r = rng("kpi")
    por_dia = {}
    for f in horas:
        d = f[0]
        a = por_dia.setdefault(d, [0.0, 0.0, 0.0, 0.0])
        a[0] += f[5]   # nominales
        a[1] += f[13]  # disponibles
        a[2] += f[6]   # efectivas
        a[3] += f[16]  # movimiento

    def agg(ini, fin):
        t = [0.0] * 4
        for k in range((fin - ini).days + 1):
            for i, v in enumerate(por_dia.get((ini + timedelta(days=k)).isoformat(), [0] * 4)):
                t[i] += v
        hn, hd, he, mov = t
        return hd / hn, he / hd, mov / he, mov

    catalogo = [(1, "Mina", "Extracción total mina", "t"), (2, "CAEX", "DF", "%"), (3, "CAEX", "UEBD", "%"),
                (4, "CAEX", "Rendimiento", "t/h"), (5, "CAEX", "Velocidad prom.", "km/h"),
                (6, "CAEX", "Factor de carga", "t/carga"), (7, "Pala", "DF", "%"), (8, "Pala", "UEBD", "%"),
                (9, "Pala", "Rendimiento", "t/h"), (10, "Perforación", "DF", "%"), (11, "Perforación", "UEBD", "%"),
                (12, "Perforación", "Rendimiento", "m/h"), (13, "Perforación", "Metros perforados", "m")]
    filas = []
    for ini in lunes:
        fin = min(ini + timedelta(days=6), ULTIMO)
        ini_jd = ini - timedelta(days=4)                 # jueves a domingo de la semana anterior
        ini_mes = date(fin.year, fin.month, 1)
        ventanas = {"": (ini, fin), "JD": (ini_jd, ini_jd + timedelta(days=3)), "Mes": (ini_mes, fin), "SemAnt": (ini - timedelta(days=7), ini - timedelta(days=1))}
        reales = {k: agg(*v) for k, v in ventanas.items()}
        indicadores = []
        for orden, area, ind, unidad in catalogo:
            fila = {"Orden": orden, "Area": area, "Indicador": ind, "Unidad": unidad}
            for sufijo, (a, b) in ventanas.items():
                df, ue, rend, mov = reales[sufijo]
                dias_v = (b - a).days + 1
                if orden == 1:
                    real, plan = mov, 205_000 * dias_v
                elif orden == 2:
                    real, plan = df, 0.88
                elif orden == 3:
                    real, plan = ue, 0.78
                elif orden == 4:
                    real, plan = rend, 480
                elif orden == 5:
                    real, plan = round(r.uniform(15, 30), 1), None
                elif orden == 6:
                    real, plan = round(r.gauss(272, 5), 1), PLAN_FACTOR_CARGA
                elif orden in (7, 10):
                    real, plan = round(r.uniform(0.82, 0.94), 3), 0.88
                elif orden in (8, 11):
                    real, plan = round(r.uniform(0.70, 0.85), 3), 0.78
                elif orden == 9:
                    real, plan = round(r.uniform(3200, 4800), 0), 4000
                elif orden == 12:
                    real, plan = round(r.uniform(28, 36), 1), 32
                else:
                    real, plan = round(r.uniform(9000, 13000) * dias_v / 7, 0), 11000 * dias_v / 7
                clave = {"": "", "JD": "JD", "Mes": "Mes", "SemAnt": "SemAnt"}[sufijo]
                if clave == "SemAnt":
                    fila["RealSemAnt"] = round(real, 4)
                    continue
                fila["Real" + clave] = round(real, 4)
                fila["Plan" + clave] = None if plan is None else round(plan, 4)
                fila["Cumpl" + clave] = None if not plan else round(real / plan, 4)
            indicadores.append(fila)
        filas.append((ini.isoformat(), "KPI semanal", "Semanal", json.dumps(indicadores, ensure_ascii=False, separators=(",", ":"))))
    escribir(SALIDA_APP / "RD_KPI.csv", ["Periodo", "Titulo", "Grupo", "Json"], filas)


def main():
    print("Datos del modelo semántico (oee/):")
    dimensiones()
    planes()
    horas, mov_dia = operacion()
    print("Datos de la app (app/):")
    app(horas, mov_dia)
    totales = [mov_dia[d] for d in FECHAS]
    print(f"Movimiento diario de la flota: mínimo {min(totales) / 1000:,.0f} kt, máximo {max(totales) / 1000:,.0f} kt")
    print("Listo.")


if __name__ == "__main__":
    main()
