# -*- coding: utf-8 -*-
"""Genera los CSV sintéticos del tablero de gestión del agua de «Minera Demo» (datos 100 % ficticios).

Salidas (en esta misma carpeta):
  catalogo_activos.csv    activos del sistema hídrico (pozos, estanques, tranques, estaciones, salas, áreas de consumo)
  catalogo_senales.csv    catálogo de señales TAG_AGUA_001... con su activo, medición, unidad y fuente
  fuentes.csv             grupos de origen de los datos
  config.csv              umbrales y parámetros editables (valores de ejemplo)
  lab_calidad.csv         resultados semanales de laboratorio (sólidos suspendidos) por punto
  mediciones_horarias.csv señales en formato largo (Tag, FechaHora, Valor), ventana horaria de los últimos 8 días
  balance_diario.csv      balance hídrico diario de 90 días (desde 2025-03-03) por concepto y área

Relaciones físicas que se cumplen por construcción:
  * captación = suma del caudal de los pozos de captación; agua fresca = captación - pérdida de conducción
  * agua total de proceso = agua fresca (reposición) + agua recuperada (pozos de recuperación + retorno del tranque)
  * consumo por área = (agua total - variación de almacenamiento) repartido entre las áreas, con un error de cierre < 1 %
  * el balance diario de los últimos 8 días es la suma exacta de las series horarias del CSV

Uso:
    python datos_sinteticos/generar_datos.py
El resultado es determinista (semilla fija en tools/sinteticos.py).
"""
import csv
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[1] / "tools"))
from sinteticos import rng  # noqa: E402

INICIO = date(2025, 3, 3)
N_DIAS = 90
H_TOTAL = N_DIAS * 24            # horas simuladas: 0 .. 2159
H_FIN = H_TOTAL - 1              # última marca: 2025-05-31 23:00
VENTANA_DIAS = 8                 # días con serie horaria en mediciones_horarias.csv
H_VENT = H_FIN - VENTANA_DIAS * 24
T0 = datetime(INICIO.year, INICIO.month, INICIO.day)
H_MES = (date(2025, 5, 1) - INICIO).days * 24   # primera hora del mes en curso (para volúmenes mensuales)


def marca(h):
    return T0 + timedelta(hours=h)


def fmt(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# --------------------------------------------------------------------------------------------
# Catálogo de activos y señales
# --------------------------------------------------------------------------------------------
ACTIVOS = []
SENALES = []

F_CAP = "Pozos de captación (área C1)"
F_REC_N = "Recuperación Norte (área R1)"
F_REC_S = "Recuperación Sur (área R2)"
F_EST = "Estanques (áreas R1 / R2)"
F_MON = "Estaciones de monitoreo (área M1)"
F_TRQ = "Tranques y pozas (áreas T1 / T2)"
F_ENE = "Energía y comunicaciones (UPS, baterías, enlaces)"
F_REP = "Reporte externo (portales A y B)"
F_BAL = "Balance y consumo por área (área B1)"

FUENTES = [
    ("Historiador de proceso", "Historiador", "Servidor", 1, "Origen común de todas las señales"),
    (F_REC_N, "Recuperación Norte", "Area", 2, ""),
    (F_REC_S, "Recuperación Sur", "Area", 3, ""),
    (F_EST, "Estanques", "Area", 4, ""),
    (F_CAP, "Captación", "Area", 5, ""),
    (F_MON, "Estaciones de monitoreo", "Area", 6, ""),
    (F_TRQ, "Tranques y pozas", "Area", 7, ""),
    (F_ENE, "Energía y comunicaciones", "Area", 8, ""),
    (F_REP, "Reporte externo", "Area", 9, ""),
    (F_BAL, "Balance y consumo", "Area", 10, ""),
    ("Meteorología (sin señales)", "Meteorología", "Sin tag", 11, "Sin señales en el historiador (pendiente)"),
    ("Evaporación estimada (sin señales)", "Evaporación", "Sin tag", 12, "Sin señales en el historiador (pendiente)"),
]


def activo(aid, nombre, tipo, grupo, circuito, sector, pagina, estacion, confianza="Alta", nota="", asociado="", hi=None, hh=None):
    ACTIVOS.append({
        "ActivoID": aid, "Activo": nombre, "Tipo": tipo, "Grupo": grupo, "Circuito": circuito, "Sector": sector,
        "Pagina": pagina, "Orden": len(ACTIVOS) + 1, "Confianza": confianza, "Nota": nota, "Estacion": estacion,
        "CircuitoAsociado": asociado, "HI": "" if hi is None else hi, "HH": "" if hh is None else hh,
    })


def senal(aid, medicion, unidad, descripcion, familia, modulo, fuente, perfil, principal="Si", origen="Sensor",
          confianza="Alta", **p):
    SENALES.append({
        "Tag": f"TAG_AGUA_{len(SENALES) + 1:03d}", "Descripcion": descripcion, "Modulo": modulo, "Familia": familia,
        "Medicion": medicion, "Unidad": unidad, "ActivoID": aid, "Fuente": fuente, "Origen": origen,
        "Principal": principal, "Confianza": confianza, "_perfil": perfil, "_p": p,
    })


# ---- Captación (agua fresca): 10 pozos en dos campos --------------------------------------
BASE_CAP = [46, 41, 33, 39, 36, 42, 38, 31, 44, 30]                      # m3/h
FACTOR_CUPO = [1.22, 0.93, 1.18, 1.25, 1.12, 1.20, 1.04, 1.30, 1.15, 1.21]  # cupo mensual / volumen esperado
CAP_TOTALIZADOR = {4, 5, 9}   # pozos sin caudal instantáneo: se calcula con la diferencia del totalizador
NIVEL_POZO = [58, 61, 49, 55, 72, 64, 53, 69, 47, 60]                    # m (nivel dinámico)

for i in range(1, 11):
    campo = "Campo Norte" if i <= 5 else "Campo Sur"
    activo(f"CAP-{i:02d}", f"CAP-{i:02d}", "Pozo agua fresca", campo, "No aplica", campo, "Agua fresca",
           f"Estación Captación {'Norte' if i <= 5 else 'Sur'}",
           confianza="Media" if i == 9 else "Alta", nota="Sin caudal instantáneo: se calcula con el totalizador" if i in CAP_TOTALIZADOR else "")
activo("CAP-TOTAL", "Campo de pozos de captación (total)", "Campo de pozos", "Agua fresca", "No aplica", "", "Agua fresca", "Captación (total)")
activo("CAP-ENLACE", "Enlace satelital Campo Sur", "Comunicacion", "Campo Sur", "No aplica", "Campo Sur", "Agua fresca", "Enlace Campo Sur")
for i in range(1, 9):
    activo(f"PZ-{i:02d}", f"PZ-{i:02d}", "Piezometro", "Acuífero", "No aplica", "Acuífero", "Agua fresca", f"Piezómetro PZ-{i:02d}")

# ---- Recuperación (agua recuperada / recirculada) -----------------------------------------
BASE_REC = [38, 44, 36, 41, 33, 40, 35, 42]
for i in range(1, 9):
    c = "Circuito Norte" if i <= 5 else "Circuito Sur"
    est = "Recuperación Norte A" if i <= 3 else ("Recuperación Norte B" if i <= 5 else "Recuperación Sur")
    activo(f"REC-{i:02d}", f"REC-{i:02d}", "Pozo recuperacion", c, c, "Tranque Demo", "Recuperación", est)
for i in range(1, 4):
    activo(f"BR-{i:02d}", f"Bomba BR-{i:02d} Circuito Sur", "Bomba recuperacion", "Circuito Sur", "Circuito Sur", "Tranque Demo",
           "Recuperación", "Recuperación Sur", confianza="Media", nota="Relación bomba-pozo por validar")
activo("QR-01", "Retorno Tranque Demo 1", "Caudal recuperacion", "Circuito Norte", "Circuito Norte", "Tranque Demo", "Recuperación", "Retorno Tranque Demo")
activo("QR-02", "Retorno Tranque Demo 2", "Caudal recuperacion", "Circuito Sur", "Circuito Sur", "Tranque Demo", "Recuperación", "Retorno Tranque Demo")
activo("AFO-01", "Aforador Circuito Norte 1", "Aforador", "Circuito Norte", "Circuito Norte", "Tranque Demo", "Recuperación", "Aforadores Norte", nota="Caudal en L/s")
activo("AFO-02", "Aforador Circuito Norte 2", "Aforador", "Circuito Norte", "Circuito Norte", "Tranque Demo", "Recuperación", "Aforadores Norte", nota="Caudal en L/s")
activo("AFO-03", "Aforador Circuito Sur 1", "Aforador", "Circuito Sur", "Circuito Sur", "Tranque Demo", "Recuperación", "Aforadores Sur", nota="Caudal en L/s")
activo("CC-N", "Canal colector Circuito Norte", "Canal colector", "Circuito Norte", "Circuito Norte", "Tranque Demo", "Recuperación", "Canal Norte")
activo("CC-S", "Canal colector Circuito Sur", "Canal colector", "Circuito Sur", "Circuito Sur", "Tranque Demo", "Recuperación", "Canal Sur")
activo("REC-TOTAL", "Agua recuperada (total)", "Recirculacion", "Agua recuperada", "No aplica", "", "Agua fresca", "")

# ---- Estanques y tranques -------------------------------------------------------------------
activo("EST-01", "Estanque Norte 1", "Estanque", "Circuito Norte", "Circuito Norte", "Tranque Demo", "Estanques", "Estanques Norte")
activo("EST-02", "Estanque Norte 2", "Estanque", "Circuito Norte", "Circuito Norte", "Tranque Demo", "Estanques", "Estanques Norte")
activo("EST-03", "Estanque Norte 3", "Estanque", "Circuito Norte", "Circuito Norte", "Tranque Demo", "Estanques", "Estanques Norte")
activo("EST-04", "Estanque Sur 1", "Estanque", "Circuito Sur", "Circuito Sur", "Tranque Demo", "Estanques", "Estanque Sur")
TRANQUES = [
    ("TRQ-DEMO", "Tranque Demo", "Tranque Demo", 90, 95),
    ("TRQ-EMER", "Poza de emergencia", "Planta", 50, 80),
    ("TRQ-P1", "Poza de proceso 1", "Planta", 85, 95),
    ("TRQ-P2", "Poza de proceso 2", "Planta", 85, 95),
    ("TRQ-REF", "Poza de refino", "Planta", 80, 90),
    ("TRQ-CLA", "Poza clarificada", "Planta", 85, 95),
    ("TRQ-CONT", "Poza de contingencia", "Mina", 50, 80),
    ("TRQ-REB", "Poza de rebose", "Tranque Demo", 70, 90),
]
for aid, nom, grp, hi, hh in TRANQUES:
    activo(aid, nom, "Tranque", grp, "No aplica", grp, "Tranques", f"Instrumentación {nom}", hi=hi, hh=hh,
           nota="Límites HI/HH de ejemplo")

# ---- Monitoreo, calidad, energía, reporte, consumo -----------------------------------------
ASOC = ["Circuito Norte"] * 5 + ["Circuito Sur"] * 4 + ["Por asignar"] * 3
for i in range(1, 13):
    c = "Circuito Norte" if i <= 5 else ("Circuito Sur" if i <= 9 else "No aplica")
    est = "Estación Monitoreo Sur" if i in (7, 8) else f"EM MON-{i:02d}"
    activo(f"MON-{i:02d}", f"MON-{i:02d}", "Pozo monitoreo", c if c != "No aplica" else "Por asignar", c, "Aguas abajo", "Aguas abajo",
           est, confianza="Media" if ASOC[i - 1] == "Por asignar" else "Alta",
           nota="Circuito asociado por validar" if ASOC[i - 1] == "Por asignar" else "", asociado=ASOC[i - 1])
UBIC_EC = ["Captación Demo", "Salida Tranque Demo", "Entrada a planta", "Aguas abajo 1", "Aguas abajo 2", "Canal colector"]
for i in range(1, 7):
    activo(f"EC-{i:02d}", f"EC-{i:02d}", "Estacion calidad", UBIC_EC[i - 1], "No aplica", UBIC_EC[i - 1], "Calidad", f"EM EC-{i:02d}")
activo("LAB-01", "Punto de laboratorio 1", "Punto laboratorio", "Laboratorio", "No aplica", "", "Calidad", "Laboratorio", nota="Solo sólidos suspendidos de laboratorio")
GRUPO_SALA = ["Captación"] * 4 + ["Recuperación"] * 4 + ["Planta"] * 4
for i in range(1, 13):
    activo(f"SE-{i:02d}", f"Sala eléctrica {i:02d}", "Sala electrica", GRUPO_SALA[i - 1], "No aplica", "UPS", "Energía y reporte",
           f"Sala SE-{i:02d}", nota="Código de la UPS: +8 sin alimentación, +4 falla, +2 bypass, +1 batería")
activo("REP-A", "Envío de datos al portal A", "Reporte externo", "Portal A", "No aplica", "Reporte", "Energía y reporte", "Reporte externo",
       confianza="Media", nota="Horas desde el último mensaje por pozo")
activo("REP-B", "Envío de datos al portal B", "Reporte externo", "Portal B", "No aplica", "Reporte", "Energía y reporte", "Reporte externo",
       confianza="Media", nota="Errores de envío en 12 h por registrador")
AREAS_CONSUMO = [("CON-01", "Chancado", 0.07), ("CON-02", "Molienda y clasificación", 0.29), ("CON-03", "Flotación", 0.41),
                 ("CON-04", "Mina (riego y control de polvo)", 0.15), ("CON-05", "Servicios generales", 0.08)]
for aid, nom, _ in AREAS_CONSUMO:
    activo(aid, nom, "Area consumo", "Planta" if aid in ("CON-01", "CON-02", "CON-03") else ("Mina" if aid == "CON-04" else "Servicios"),
           "No aplica", "", "Balance", "", nota="Consumo horario por área")

# Señales: captación
for i in range(1, 11):
    aid = f"CAP-{i:02d}"
    if i in CAP_TOTALIZADOR:
        senal(aid, "Totalizador", "m³", f"Totalizador del pozo {aid}", "Totalizador pozo", "Captación", F_CAP, "tot", i=i)
    else:
        senal(aid, "Caudal", "m³/h", f"Caudal instantáneo del pozo {aid}", "Caudal por pozo", "Captación", F_CAP, "q_cap", i=i)
    senal(aid, "Nivel pozo", "m", f"Nivel dinámico del pozo {aid}", "Nivel en pozo", "Captación", F_CAP, "nivel_pozo", i=i)
    senal(aid, "Cupo mes", "m³/mes", f"Cupo mensual de ejemplo del pozo {aid}", "Cupo de extracción", "Captación", F_CAP, "cupo", i=i)
    senal(aid, "Volumen mes", "m³", f"Volumen acumulado del mes del pozo {aid}", "Volumen mensual", "Captación", F_CAP, "vol_mes", origen="Calculada", i=i)
senal("CAP-TOTAL", "Caudal total", "m³/h", "Caudal total captado por el campo de pozos", "Total campo de pozos", "Captación", F_CAP, "q_total", origen="Calculada")
senal("CAP-TOTAL", "Pozos sin comunicacion", "n°", "Pozos de captación con falla de comunicación según el sistema de control", "Estado comunicación", "Energía", F_ENE, "const", v=0)
senal("CAP-ENLACE", "Falla comunicacion", "0/1", "Falla del enlace satelital del Campo Sur", "Enlace satelital", "Energía", F_ENE, "const", v=0)
senal("CAP-ENLACE", "Estado enlace", "0/1", "Estado del enlace satelital del Campo Sur (1 = operativo)", "Enlace satelital", "Energía", F_ENE, "const", v=1)
PROF_PZ = [62, 71, 84, 58, 90, 77, 66, 69]
DRIFT_PZ = [0.02, -0.05, 0.71, 0.03, 0.12, -0.02, 0.04, 0.08]   # m en 7 días (positivo = baja el nivel)
for i in range(1, 9):
    senal(f"PZ-{i:02d}", "Profundidad", "m", f"Profundidad al agua del piezómetro PZ-{i:02d}", "Acuífero profundidad", "Captación", F_MON, "prof",
          base=PROF_PZ[i - 1], drift=DRIFT_PZ[i - 1])
# Señales: recuperación
for i in range(1, 9):
    aid = f"REC-{i:02d}"
    fu = F_REC_N if i <= 5 else F_REC_S
    senal(aid, "RUN", "on/off", f"Estado en marcha del pozo {aid}", "Estado bomba", "Recuperación", fu, "run", i=i)
    senal(aid, "Caudal", "m³/h", f"Caudal del pozo de recuperación {aid}", "Caudal por pozo", "Recuperación", fu, "q_rec", i=i)
    senal(aid, "Corriente", "A", f"Corriente de la bomba del pozo {aid}", "Corriente bomba", "Recuperación", fu, "corr", i=i)
    senal(aid, "Horas detenido", "h", f"Horas detenido del pozo {aid} (cálculo del historiador)", "Detención", "Recuperación", fu, "horas_det", origen="Calculada", i=i)
for i in range(1, 4):
    senal(f"BR-{i:02d}", "RUN", "on/off", f"Estado en marcha de la bomba BR-{i:02d}", "Estado bomba", "Recuperación", F_REC_S, "run_br", i=i)
    senal(f"BR-{i:02d}", "Corriente", "A", f"Corriente de la bomba BR-{i:02d}", "Corriente bomba", "Recuperación", F_REC_S, "corr_br", i=i)
senal("QR-01", "Caudal", "m³/h", "Caudal de retorno desde el Tranque Demo (línea 1)", "Caudal recuperación", "Balance", F_BAL, "q_ret", i=1)
senal("QR-02", "Caudal", "m³/h", "Caudal de retorno desde el Tranque Demo (línea 2)", "Caudal recuperación", "Balance", F_BAL, "q_ret", i=2)
for k, aid in enumerate(["AFO-01", "AFO-02", "AFO-03", "CC-N", "CC-S"]):
    fu = F_REC_S if aid.endswith("3") or aid == "CC-S" else F_REC_N
    senal(aid, "Caudal aforador", "L/s", f"Caudal medido en {aid}", "Aforo", "Recuperación", fu, "aforo", k=k)
senal("REC-TOTAL", "Caudal recuperada total", "m³/h", "Caudal total de agua recuperada y recirculada", "Total agua recuperada", "Balance", F_BAL, "r_total", origen="Calculada")
# Señales: estanques
EST_LIM = {"EST-01": (80, 90), "EST-02": (80, 90), "EST-03": (75, 90)}
for k, aid in enumerate(["EST-01", "EST-02", "EST-03", "EST-04"]):
    fu = F_EST
    senal(aid, "Nivel estanque", "%", f"Nivel del estanque {aid}", "Nivel estanque", "Estanques", fu, "nivel_est", k=k, act=aid)
    if aid in EST_LIM:
        senal(aid, "Limite HI", "%", f"Límite HI del estanque {aid}", "Límites de nivel", "Estanques", fu, "const", v=EST_LIM[aid][0], origen="Calculada")
        senal(aid, "Limite HH", "%", f"Límite HH del estanque {aid}", "Límites de nivel", "Estanques", fu, "const", v=EST_LIM[aid][1], origen="Calculada")
senal("EST-02", "Nivel estanque", "%", "Nivel redundante del estanque EST-02", "Nivel estanque", "Estanques", F_EST, "nivel_est", principal="No", k=1, act="EST-02", redundante=True)
for k, aid in enumerate(["EST-01", "EST-01", "EST-02", "EST-03", "EST-03", "EST-04"]):
    senal(aid, "RUN", "on/off", f"Estado de la bomba {chr(65 + (k % 2))} del estanque {aid}", "Estado bomba", "Estanques", F_EST, "run_est", k=k)
# Señales: tranques
for k, (aid, nom, _, hi, hh) in enumerate(TRANQUES):
    senal(aid, "Nivel tranque", "%", f"Nivel de {nom.lower()}", "Nivel tranque", "Tranques", F_TRQ, "nivel_trq", k=k, act=aid)
    if aid in ("TRQ-DEMO", "TRQ-EMER", "TRQ-P2", "TRQ-REF", "TRQ-CLA"):
        senal(aid, "Alarma alto nivel", "0/1", f"Alarma de nivel alto de {nom.lower()}", "Alarma nivel", "Tranques", F_TRQ, "alarma_trq", k=k, act=aid)
senal("TRQ-EMER", "Detector fuga", "0/1", "Detector de fuga de la poza de emergencia", "Detector de fuga", "Tranques", F_TRQ, "const", v=0)
senal("TRQ-DEMO", "Detector fuga", "0/1", "Detector de fuga del Tranque Demo", "Detector de fuga", "Tranques", F_TRQ, "const", v=0)
senal("TRQ-EMER", "RUN", "on/off", "Bomba A de la poza de emergencia en marcha", "Estado bomba", "Tranques", F_TRQ, "const", v=0)
senal("TRQ-EMER", "Modo auto", "0/1", "Bomba B de la poza de emergencia en automático", "Estado bomba", "Tranques", F_TRQ, "const", v=1)
senal("TRQ-DEMO", "pH tranque", "pH", "pH del Tranque Demo", "Calidad en tranque", "Tranques", F_TRQ, "ph", principal="No", base=7.9, k=11)
senal("TRQ-P1", "pH tranque", "pH", "pH de la poza de proceso 1", "Calidad en tranque", "Tranques", F_TRQ, "ph", principal="No", base=8.1, k=12)
# Señales: monitoreo
PROF_MON = [14.2, 21.5, 18.9, 25.3, 30.1, 16.8, 22.4, 19.6, 27.0, 12.9, 33.5, 24.1]
DRIFT_MON = [0.02, -0.6, 0.0, -0.04, -0.25, 0.01, 0.03, -0.02, 0.0, 0.05, -0.03, 0.01]   # m en 7 días (negativo = sube el agua)
for i in range(1, 13):
    aid = f"MON-{i:02d}"
    senal(aid, "Profundidad", "m", f"Profundidad al nivel freático del pozo {aid}", "Acuífero nivel freático", "Monitoreo", F_MON, "prof",
          base=PROF_MON[i - 1], drift=DRIFT_MON[i - 1], act=aid)
    senal(aid, "Bateria", "V", f"Batería de la estación del pozo {aid}", "Batería estación", "Energía", F_ENE, "bat", v=11.2 if i == 4 else 12.6, act=aid, k=i)
# Señales: calidad
for i in range(1, 7):
    aid = f"EC-{i:02d}"
    senal(aid, "pH", "pH", f"pH en línea de la estación {aid}", "Calidad en línea", "Calidad", F_MON, "ph", base=7.3 + 0.1 * (i % 3), k=i, act=aid)
    senal(aid, "CE", "µS/cm", f"Conductividad en línea de la estación {aid}", "Calidad en línea", "Calidad", F_MON, "ce", base=820 + 130 * i, k=i, act=aid)
    senal(aid, "Turbidez", "NTU", f"Turbidez en línea de la estación {aid}", "Calidad en línea", "Calidad", F_MON, "turb", base=6 + 2 * i, k=i, act=aid)
# Señales: energía (UPS) y reporte
UPS = [0, 0, 1, 0, 0, 0, 8, 0, 4, 0, 0, 0]
for i in range(1, 13):
    senal(f"SE-{i:02d}", "UPS estado", "código", f"Estado de la UPS de la sala eléctrica {i:02d}", "Estado UPS", "Energía", F_ENE, "const", origen="Calculada", v=UPS[i - 1])
ENVIO_A = [0.4, 5.2, 0.6, 0.3, 0.8, 0.5, 31.0, 0.7, 0.2, 0.9]
for i in range(1, 11):
    senal("REP-A", "Horas sin envio A", "h", f"Horas sin envio A · CAP-{i:02d}", "Envío reporte A", "Energía", F_REP, "envio_a", origen="Calculada",
          confianza="Media", v=ENVIO_A[i - 1], k=i)
ERR_B = [0, 1, 6, 0, 2, 0, 7, 1]
for i in range(1, 9):
    senal("REP-B", "Errores envio B 12 h", "n°", f"Errores envio B 12 h · LOG-{i:02d}", "Envío reporte B", "Energía", F_REP, "err_b", origen="Calculada",
          confianza="Media", v=ERR_B[i - 1], k=i)
for k, (aid, nom, _) in enumerate(AREAS_CONSUMO):
    senal(aid, "Consumo", "m³/h", f"Consumo horario de agua en {nom.lower()}", "Consumo por área", "Balance", F_BAL, "consumo", k=k)

# --------------------------------------------------------------------------------------------
# Simulación física (todas las horas del periodo)
# --------------------------------------------------------------------------------------------


def sub(h):
    return h % 24


def intervalos_parada(nombre, base_h, r):
    """Paradas cortas aleatorias en el historial (no en las últimas 30 h)."""
    out = []
    for _ in range(r.randint(0, 2)):
        ini = r.randint(80, H_FIN - 40)
        out.append((ini, ini + r.randint(2, 9)))
    return out


ESC_PARADA = {   # escenarios de parada que siguen abiertos al final del periodo
    "REC-03": H_FIN - 13,
    "REC-05": H_FIN - 51,
    "REC-06": H_FIN - 5, "REC-07": H_FIN - 5, "REC-08": H_FIN - 5,
    "BR-01": H_FIN - 5, "BR-02": H_FIN - 5, "BR-03": H_FIN - 5,
}
CORTE_DATOS = {"MON-07": 9, "MON-08": 9}       # horas finales sin dato (falla de comunicación)

Q = {}
for i in range(1, 11):
    r = rng(f"cap{i}")
    fase = r.uniform(0, 6.28)
    arr = []
    for h in range(H_TOTAL):
        v = BASE_CAP[i - 1] * (1 + 0.05 * math.sin(2 * math.pi * (sub(h) - 14) / 24)) * (1 + 0.07 * math.sin(2 * math.pi * h / 264 + fase)) * (1 + r.gauss(0, 0.02))
        arr.append(round(max(v, 0.0), 3))
    Q[f"CAP-{i:02d}"] = arr

PARADA = {}
for i in range(1, 9):
    aid = f"REC-{i:02d}"
    r = rng(f"rec{i}")
    mask = [1] * H_TOTAL
    for a, b in intervalos_parada(aid, 0, r):
        for h in range(a, b + 1):
            mask[h] = 0
    if aid in ESC_PARADA:
        for h in range(ESC_PARADA[aid], H_TOTAL):
            mask[h] = 0
    PARADA[aid] = mask
    fase = r.uniform(0, 6.28)
    Q[aid] = [round(BASE_REC[i - 1] * (1 + 0.04 * math.sin(2 * math.pi * h / 200 + fase)) * (1 + r.gauss(0, 0.02)) * mask[h], 3) for h in range(H_TOTAL)]
for i in range(1, 4):
    aid = f"BR-{i:02d}"
    mask = [1] * H_TOTAL
    for h in range(ESC_PARADA[aid], H_TOTAL):
        mask[h] = 0
    PARADA[aid] = mask
for i in (1, 2):
    r = rng(f"ret{i}")
    base = 455 if i == 1 else 430
    fase = r.uniform(0, 6.28)
    Q[f"QR-0{i}"] = [round(base * (1 + 0.03 * math.sin(2 * math.pi * h / 310 + fase)) * (1 + r.gauss(0, 0.015)), 3) for h in range(H_TOTAL)]

Q_TOT_CAP = [round(sum(Q[f"CAP-{i:02d}"][h] for i in range(1, 11)), 3) for h in range(H_TOTAL)]
R_TOT = [round(sum(Q[f"REC-{i:02d}"][h] for i in range(1, 9)) + Q["QR-01"][h] + Q["QR-02"][h], 3) for h in range(H_TOTAL)]

# pérdida de conducción por día, agua fresca horaria
rp = rng("perdida")
PERDIDA_DIA = [rp.uniform(0.022, 0.038) for _ in range(N_DIAS)]
F_HORA = [round(Q_TOT_CAP[h] * (1 - PERDIDA_DIA[h // 24]), 3) for h in range(H_TOTAL)]
T_HORA = [F_HORA[h] + R_TOT[h] for h in range(H_TOTAL)]

# variación de almacenamiento y consumo por área
rb = rng("balance")
DS_DIA = [rb.gauss(0, 0.006) for _ in range(N_DIAS)]    # fracción del agua total del día
BIAS_DIA = [rb.gauss(0, 0.004) for _ in range(N_DIAS)]
CONSUMO = {aid: [] for aid, _, _ in AREAS_CONSUMO}
DS_M3 = []
for d in range(N_DIAS):
    t_dia = sum(T_HORA[24 * d:24 * d + 24])
    DS_M3.append(round(DS_DIA[d] * t_dia, 1))
for h in range(H_TOTAL):
    d = h // 24
    t_dia = sum(T_HORA[24 * d:24 * d + 24])
    ds_h = DS_M3[d] / 24
    total = (T_HORA[h] - ds_h) * (1 + BIAS_DIA[d])
    rr = rng(f"consumo{h}")
    pesos = []
    for aid, _, share in AREAS_CONSUMO:
        diurno = 1 + (0.18 if aid == "CON-04" and 8 <= sub(h) < 19 else 0)
        pesos.append(share * diurno * (1 + rr.gauss(0, 0.02)))
    s = sum(pesos)
    for (aid, _, _), w in zip(AREAS_CONSUMO, pesos):
        CONSUMO[aid].append(round(total * w / s, 3))

# --------------------------------------------------------------------------------------------
# Series de cada señal (ventana horaria)
# --------------------------------------------------------------------------------------------
IDX = list(range(H_VENT, H_FIN + 1))


def suavizado(r, n, amp):
    """Ruido lento de media cero (caminata acotada)."""
    x, out = 0.0, []
    for _ in range(n):
        x = 0.92 * x + r.gauss(0, amp)
        out.append(x)
    return out


def serie(s):
    perfil, p = s["_perfil"], s["_p"]
    tag = s["Tag"]
    r = rng(f"serie:{tag}")
    if perfil == "q_cap":
        return [Q[f"CAP-{p['i']:02d}"][h] for h in IDX]
    if perfil == "tot":
        q = Q[f"CAP-{p['i']:02d}"]
        off = 1_800_000 + 90_000 * p["i"]
        acum, tot = 0.0, []
        for h in range(H_TOTAL):
            acum += q[h]
            tot.append(round(off + acum, 3))
        return [tot[h] for h in IDX]
    if perfil == "nivel_pozo":
        q = Q[f"CAP-{p['i']:02d}"]
        base = NIVEL_POZO[p["i"] - 1]
        lento = suavizado(r, H_TOTAL, 0.03)
        return [round(base + lento[h] - 0.02 * (q[h] - BASE_CAP[p["i"] - 1]) + r.gauss(0, 0.01), 3) for h in IDX]
    if perfil == "cupo":
        return [round(FACTOR_CUPO[p["i"] - 1] * BASE_CAP[p["i"] - 1] * 744, 0)] * len(IDX)
    if perfil == "vol_mes":
        q = Q[f"CAP-{p['i']:02d}"]
        acum, vol = 0.0, {}
        for h in range(H_MES, H_TOTAL):
            acum += q[h]
            vol[h] = round(acum, 3)
        return [vol[h] for h in IDX]
    if perfil == "q_total":
        return [Q_TOT_CAP[h] for h in IDX]
    if perfil == "r_total":
        return [R_TOT[h] for h in IDX]
    if perfil == "q_rec":
        return [Q[f"REC-{p['i']:02d}"][h] for h in IDX]
    if perfil == "q_ret":
        return [Q[f"QR-0{p['i']}"][h] for h in IDX]
    if perfil in ("run", "run_br"):
        aid = f"REC-{p['i']:02d}" if perfil == "run" else f"BR-{p['i']:02d}"
        return [PARADA[aid][h] for h in IDX]
    if perfil in ("corr", "corr_br"):
        aid = f"REC-{p['i']:02d}" if perfil == "corr" else f"BR-{p['i']:02d}"
        amp = 31 + 2.1 * p["i"]
        return [round(PARADA[aid][h] * (amp + r.gauss(0, 0.35)), 3) for h in IDX]
    if perfil == "horas_det":
        aid = f"REC-{p['i']:02d}"
        m = PARADA[aid]
        out, cont = [], 0
        for h in range(H_TOTAL):
            cont = 0 if m[h] else cont + 1
            out.append(float(cont) if cont else 0.0)
        return [out[h] for h in IDX]
    if perfil == "aforo":
        base = [14.0, 9.5, 7.2, 3.1, 2.4][p["k"]]
        return [round(base * (1 + 0.04 * math.sin(h / 17 + p["k"])) + r.gauss(0, 0.05), 3) for h in IDX]
    if perfil == "nivel_est":
        k, aid = p["k"], p["act"]
        base = [72.0, 41.3, 38.0, 27.0][k]
        lento = suavizado(r, H_TOTAL, 0.18)
        out = []
        for h in IDX:
            v = base + lento[h] + 1.5 * math.sin(h / 9 + k)
            if aid == "EST-01" and h > H_FIN - 72:
                v += (h - (H_FIN - 72)) * (84.6 - 72.0) / 72
            if aid == "EST-02":
                v = 41.3 + (r.gauss(0, 0.15) if h <= H_FIN - 60 else 0.0)
            out.append(round(v, 3))
        if p.get("redundante"):
            out = [round(v + 0.4, 3) for v in out]
        return out
    if perfil == "run_est":
        k = p["k"]
        return [int((h // (6 + 2 * k) + k) % 3 != 0) for h in IDX]
    if perfil in ("nivel_trq", "alarma_trq"):
        k, aid = p["k"], p["act"]
        base = [74.0, 12.0, 58.0, 79.0, 61.0, 66.0, 9.0, 31.0][k]
        r2 = rng(f"nivel_trq:{aid}")
        lento = suavizado(r2, H_TOTAL, 0.12)
        niv = []
        for h in IDX:
            v = base + lento[h] + 0.8 * math.sin(h / 23 + k)
            if aid == "TRQ-P2" and h > H_FIN - 72:
                v += (h - (H_FIN - 72)) * (91.2 - 79.0) / 72
            niv.append(round(v, 3))
        if perfil == "alarma_trq":
            return [1 if v >= 88 else 0 for v in niv]
        return niv
    if perfil == "prof":
        base, drift = p["base"], p["drift"]
        lento = suavizado(r, H_TOTAL, 0.004)
        return [round(base + drift * (h - H_FIN) / 168 + lento[h] + r.gauss(0, 0.004), 3) for h in IDX]
    if perfil == "bat":
        return [round(p["v"] + 0.15 * math.sin((h + p["k"]) / 11) + r.gauss(0, 0.02), 3) for h in IDX]
    if perfil == "ph":
        aid = p.get("act", "")
        out = []
        for h in IDX:
            v = p["base"] + 0.08 * math.sin(h / 13 + p["k"]) + r.gauss(0, 0.02)
            if aid == "EC-04" and h > H_FIN - 20:
                v = 6.1 + r.gauss(0, 0.03)
            out.append(round(v, 3))
        return out
    if perfil == "ce":
        return [round(p["base"] * (1 + 0.03 * math.sin(h / 19 + p["k"])) + r.gauss(0, 3), 3) for h in IDX]
    if perfil == "turb":
        out = []
        for h in IDX:
            v = p["base"] * (1 + 0.15 * math.sin(h / 15 + p["k"])) + r.gauss(0, 0.3)
            if p.get("act") == "EC-04" and h > H_FIN - 20:
                v = 62 + r.gauss(0, 1.0)
            out.append(round(max(v, 0.1), 3))
        return out
    if perfil == "consumo":
        return [CONSUMO[AREAS_CONSUMO[p["k"]][0]][h] for h in IDX]
    if perfil == "envio_a":
        # horas desde el último mensaje: diente de sierra si el pozo envía; rampa creciente si tiene atraso
        base = p["v"]
        if base < 3:
            return [round(0.2 + ((h + p["k"]) % 5) * 0.1, 3) for h in IDX]
        return [round(max(base - (H_FIN - h), 0.1), 3) for h in IDX]
    if perfil == "err_b":
        return [p["v"]] * len(IDX)
    if perfil == "const":
        return [p["v"]] * len(IDX)
    raise ValueError(perfil)


def escribir_csv(nombre, cab, filas):
    with open(AQUI / nombre, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cab)
        w.writerows(filas)


def main():
    # catálogos
    escribir_csv("catalogo_activos.csv",
                 ["ActivoID", "Activo", "Tipo", "Grupo", "Circuito", "Sector", "Pagina", "Orden", "Confianza", "Nota", "Estacion",
                  "CircuitoAsociado", "HI", "HH"],
                 [[a[c] for c in ["ActivoID", "Activo", "Tipo", "Grupo", "Circuito", "Sector", "Pagina", "Orden", "Confianza", "Nota",
                                  "Estacion", "CircuitoAsociado", "HI", "HH"]] for a in ACTIVOS])
    cab_s = ["Tag", "Descripcion", "Modulo", "Familia", "Medicion", "Unidad", "ActivoID", "Fuente", "Origen", "Principal", "Confianza"]
    escribir_csv("catalogo_senales.csv", cab_s, [[s[c] for c in cab_s] for s in SENALES])
    escribir_csv("fuentes.csv", ["Fuente", "FuenteCorta", "Tipo", "Orden", "Nota"], FUENTES)
    escribir_csv("config.csv", ["Parametro", "Valor", "Unidad", "Nota"], [
        ["Horas sin dato", 2, "h", "Sin muestra nueva en este plazo = Sin dato"],
        ["Caudal minimo bombeo (L/s)", 0.14, "L/s", "Bajo este caudal el pozo se considera detenido (valor de ejemplo)"],
        ["Cupo captacion (L/s)", 120, "L/s", "Cupo de captación de ejemplo del campo de pozos"],
        ["Meta recuperacion Norte (L/s)", 60, "L/s", "Meta de ejemplo del Circuito Norte"],
        ["Meta recuperacion Sur (L/s)", 35, "L/s", "Meta de ejemplo del Circuito Sur"],
        ["pH minimo", 6.5, "pH", "Banda aceptable de ejemplo"],
        ["pH maximo", 8.5, "pH", "Banda aceptable de ejemplo"],
        ["Turbidez maxima (NTU)", 50, "NTU", "Límite de ejemplo"],
        ["HI por defecto (%)", 80, "%", "Se usa si el estanque no tiene señal de límite HI"],
        ["HH por defecto (%)", 90, "%", "Se usa si el estanque no tiene señal de límite HH"],
        ["Descenso piezometro fuerte (m)", 0.5, "m en 7 días", "Límite de ejemplo"],
        ["Descenso piezometro leve (m)", 0.1, "m en 7 días", "Límite de ejemplo"],
        ["Horas para congelado", 48, "h", "Una señal analógica que no cambia nada en este plazo se marca Congelada"],
        ["Horas datos atrasados", 3, "h", "Si la última muestra es más antigua, el encabezado avisa que la actualización está detenida"],
        ["Ascenso freatico alerta (m)", 0.5, "m en 7 días", "Pozos de monitoreo: subida fuerte del nivel freático (límite de ejemplo)"],
        ["Ascenso freatico aviso (m)", 0.2, "m en 7 días", "Pozos de monitoreo: el nivel freático sube (límite de ejemplo)"],
        ["Bateria baja 12 V (V)", 11.8, "V", "Estaciones con batería de 12 V"],
        ["Bateria baja 3,6 V (V)", 3.3, "V", "Registradores con batería de 3,6 V"],
        ["Horas sin envio A", 3, "h", "El portal A recibe un mensaje por hora; sobre este plazo el envío está atrasado"],
        ["Errores envio B 12 h", 5, "n°", "Errores de envío en 12 h desde los que se alerta (ejemplo)"],
        ["Minutos simultaneidad corte", 30, "min", "Si todas las bombas de una estación se detienen dentro de este margen se avisa posible corte de energía"],
    ])
    # laboratorio: sólidos suspendidos semanales
    filas_lab, rl = [], rng("lab")
    puntos = [("EC-01", 38), ("EC-03", 47), ("EC-05", 41), ("LAB-01", 52)]
    for punto, base in puntos:
        for k in range(14):
            f = INICIO + timedelta(days=7 * k)
            v = base + 6 * math.sin(k / 2.3) + rl.gauss(0, 2.0) + (22 if punto == "LAB-01" and k == 13 else 0)
            filas_lab.append([f.isoformat(), punto, punto, fmt(v), 70, 90])
    escribir_csv("lab_calidad.csv", ["Fecha", "Punto", "ActivoID", "SST", "LimiteAviso", "LimiteAlerta"], filas_lab)

    # mediciones horarias
    filas, series = [], {}
    for s in SENALES:
        vals = serie(s)
        cut = CORTE_DATOS.get(s["ActivoID"], 0)
        corte_h = H_FIN - cut if cut else None
        series[s["Tag"]] = vals
        for h, v in zip(IDX, vals):
            if corte_h is not None and h > corte_h:
                continue
            filas.append([s["Tag"], marca(h).strftime("%Y-%m-%d %H:%M"), fmt(v)])
    escribir_csv("mediciones_horarias.csv", ["Tag", "FechaHora", "Valor"], filas)

    # balance diario (90 días)
    filas_b = []
    for d in range(N_DIAS):
        f = (INICIO + timedelta(days=d)).isoformat()
        hs = range(24 * d, 24 * d + 24)
        cap_n = sum(sum(Q[f"CAP-{i:02d}"][h] for i in range(1, 6)) for h in hs)
        cap_s = sum(sum(Q[f"CAP-{i:02d}"][h] for i in range(6, 11)) for h in hs)
        fresca = sum(F_HORA[h] for h in hs)
        rec_p = sum(sum(Q[f"REC-{i:02d}"][h] for i in range(1, 9)) for h in hs)
        rec_t = sum(Q["QR-01"][h] + Q["QR-02"][h] for h in hs)
        filas_b += [[f, "Captación", "Campo Norte", fmt(round(cap_n, 1))], [f, "Captación", "Campo Sur", fmt(round(cap_s, 1))]]
        filas_b.append([f, "Pérdida de conducción", "Conducción", fmt(round(cap_n + cap_s - fresca, 1))])
        filas_b.append([f, "Agua fresca", "Reposición", fmt(round(fresca, 1))])
        filas_b += [[f, "Agua recuperada", "Pozos de recuperación", fmt(round(rec_p, 1))], [f, "Agua recuperada", "Retorno Tranque Demo", fmt(round(rec_t, 1))]]
        for aid, nom, _ in AREAS_CONSUMO:
            filas_b.append([f, "Consumo", nom, fmt(round(sum(CONSUMO[aid][h] for h in hs), 1))])
        filas_b.append([f, "Variación de almacenamiento", "Tranque Demo", fmt(DS_M3[d])])
    escribir_csv("balance_diario.csv", ["Fecha", "Concepto", "Area", "Volumen_m3"], filas_b)

    # autoverificación de coherencia
    n_ok = 0
    for d in range(N_DIAS - VENTANA_DIAS, N_DIAS):
        hs = range(24 * d, 24 * d + 24)
        cons = sum(sum(CONSUMO[a][h] for h in hs) for a, _, _ in AREAS_CONSUMO)
        total = sum(T_HORA[h] for h in hs)
        assert abs(cons - (total - DS_M3[d]) * (1 + BIAS_DIA[d])) < 5.0, "balance diario incoherente"
        n_ok += 1
    t_tot = sum(T_HORA)
    r_tot = sum(R_TOT)
    print(f"Activos: {len(ACTIVOS)} | señales: {len(SENALES)} | filas horarias: {len(filas)} | filas de balance: {len(filas_b)}")
    print(f"Recirculación media: {100 * r_tot / t_tot:.1f} % | agua total media: {t_tot / N_DIAS:,.0f} m3/día | días verificados: {n_ok}")


if __name__ == "__main__":
    main()
