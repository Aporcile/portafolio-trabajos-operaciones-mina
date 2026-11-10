# -*- coding: utf-8 -*-
"""Genera el PBIP «OEE CAEX Demo»: el OEE de transporte (flota CAEX) y el detalle de cada barra de la cascada.

Salida (carpeta pbip/, junto a este generador):
  OEE CAEX Demo.pbip
  OEE CAEX Demo.SemanticModel/   modelo semántico en TMDL (tablas, relaciones, medidas DAX, parámetro RutaDatos)
  OEE CAEX Demo.Report/          informe en PBIR: página «OEE Transporte» y cuatro páginas de detalle

El modelo lee CSV sintéticos de datos_sinteticos/oee/ (ver parámetro RutaDatos en el README del proyecto).

Periodos (la reunión es los lunes; entre semana muestran lo que va, hasta ayer):
  - SEMANAL: de lunes a ayer; el lunes de la reunión, la semana completa. Contra el plan semanal (Plan_CAEX).
  - JUE-DOM: último jueves a domingo hasta ayer, contra el plan de esos días (el plan semanal viene día a día).
  - MENSUAL: del 1 del mes hasta ayer; el primer lunes del mes, el mes anterior completo. Contra el plan mensual
    (Planes_Mina), día a día.

Cascada: se cambia una palanca a la vez.
    Plan = HN plan × DF plan × UEBD plan × Rend plan (= toneladas plan)
    Pérdida DF   = HN plan × (DF real − DF plan) × UEBD plan × Rend plan
    Pérdida UEBD = HN plan × DF real × (UEBD real − UEBD plan) × Rend plan
    Pérdida Rend = HN plan × DF real × UEBD real × (Rend real − Rend plan)
    Pérdida HN   = (HN real − HN plan) × DF real × UEBD real × Rend real
    Real = Plan + las cuatro pérdidas (= movimiento real de los CAEX)
    OEE = DF × UEBD × (rendimiento real / rendimiento plan)

Uso:  python pbip/generador/gen_pbi_oee.py
Después, validar con:  python pbip/generador/validar_oee.py
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pbir_lib import (AMBAR, B, C, CF, CIELO, CIELO_60, CM, COLORES_TEMA, Dn, LOGO, LOGO_AREA, MEDIANOCHE, MF, MT,  # noqa: E402
                      PLATA, PLOMO, RECURSOS, ROJO, ROSA, S, TEMA_BASE, TEMA_PROPIO, VERDE, Pagina as PaginaBase,
                      caja, cat_filter, escribir, escribir_json, filtros_equipo, hid, medida_filter, medida_tmdl, proj, q,
                      qref, rango_txt, tabla_calculada, tag)

NOMBRE = "OEE CAEX Demo"
RAIZ = Path(__file__).resolve().parent.parent
MODELO = RAIZ / f"{NOMBRE}.SemanticModel"
INFORME = RAIZ / f"{NOMBRE}.Report"
SM = MODELO / "definition"
TDIR = SM / "tables"
DATOS = RAIZ.parent / "datos_sinteticos" / "oee"
# Marcador: Power Query necesita una ruta absoluta; se fija en Transformar datos › Administrar parámetros (ver README)
PARAMETRO_RUTA = "<CARPETA_DEL_REPO>" + "\\".join(["", "02-oee-caex-y-app-desempeno", "datos_sinteticos", "oee", ""])

# Colores sobre el encabezado oscuro (más claros que el semáforo, para que se lean)
ROJO_CLARO, VERDE_CLARO, TEXTO_CLARO = "#FFAB91", "#A5D6A7", "#C8D3E3"
TOTAL = CIELO  # barras de totales (plan y real) y encabezados de tabla; pérdidas en rojo y ganancias en verde

# Categorías de horas por código
CAT_NO_DISP = ["Mantención programada", "Mantención no programada", "Daño operacional", "Neumáticos",
               "Cambio programado de neumáticos"]
CAT_NO_EFECTIVO = ["Demora programada", "Demora no programada", "Reserva"]

PASOS = [(1, "Movimiento Total - Plan"), (2, "Pérdida CAEX Disponibilidad"), (3, "Pérdida CAEX UEBD"),
         (4, "Pérdida CAEX Rendimiento Efectivo"), (5, "Pérdida CAEX Horas Nominales"), (6, "Movimiento Total - Real")]
FILAS = [(1, "Producción"), (2, "Disponibilidad"), (3, "UEBD"), (4, "Rendimiento"), (5, "Horas nominales"), (6, "OEE")]
TIPOS_UEBD = [(1, "Demora programada", "Horas Demora Programada"), (2, "Demora no programada", "Horas Demora No Programada"),
              (3, "Reserva", "Horas Reserva"), (4, "PO espera", "Horas PO Espera"), (5, "PO cola", "Horas PO Cola")]
COMPONENTES = [(1, "Viaje vacío", "traveling_time"), (2, "Espera en carguío", "waiting_time"),
               (3, "Aculatamiento", "spotting_time"), (4, "Carguío", "loading_time"), (5, "Viaje cargado", "hauling_time"),
               (6, "Cola en descarga", "queued_time"), (7, "Descarga", "tipping_time"), (8, "Retroceso", "backing_time")]
# Palancas: clave, nombre, real, plan, formato, pérdida (t)
PALANCAS = [("df", "Disponibilidad", "[DF real]", "[DF plan]", "pct", "[Pérdida disponibilidad]"),
            ("uebd", "UEBD", "[UEBD real]", "[UEBD plan]", "pct", "[Pérdida UEBD]"),
            ("rend", "Rendimiento efectivo", "[Rendimiento real]", "[Rendimiento plan]", "tph", "[Pérdida rendimiento]"),
            ("hn", "Horas nominales", "[HN real]", "[HN plan]", "h", "[Pérdida horas nominales]")]
PAYLOAD_MIN, PAYLOAD_MAX = 200, 330  # t: promedio de cargas completas (ignora cargas parciales y lecturas anómalas)


# ---------------------------------------------------------------------------------------------------------------------
# MODELO (TMDL): tablas importadas desde CSV
# ---------------------------------------------------------------------------------------------------------------------
TIPO_M = {"text": "type text", "number": "type number", "int": "Int64.Type", "date": "type date",
          "datetime": "type datetime", "logical": "type logical"}
DTYPE = {"text": "string", "number": "double", "int": "int64", "date": "dateTime", "datetime": "dateTime", "logical": "boolean"}


def col(nombre, tipo, fmt=None, resumen=None, **o):
    """Columna importada. resumen: 'sum' (por omisión en números) o 'none'. Opciones: hidden, nullable, sort_by, desc, cat."""
    if resumen is None:
        resumen = "sum" if tipo in ("number", "int") else "none"
    return dict(nombre=nombre, tipo=tipo, fmt=fmt, resumen=resumen, **o)


T = "text"
HORAS = lambda n: col(n, "number")  # noqa: E731
TABLAS = [
    dict(nombre="Planes_Mina", desc="Plan mensual de la flota CAEX, una fila por día e ítem (Horas Nominales, Disponibles, Efectivas y "
                                    "Total Toneladas). Fuente: Planes_Mina.csv.",
         cols=[col("start_date", "date", "Short Date", resumen="none", anot={"UnderlyingDateTimeDataType": "Date"}),
               col("property_name", T), col("value", "number", anot={"PBI_FormatHint": '{"isGeneralNumber":true}'}),
               col("plan_type", T)]),
    dict(nombre="Plan_FactorCarga", desc="Plan diario del factor de carga de los CAEX (t por carga). Hay días sin plan. "
                                         "Fuente: Plan_FactorCarga.csv.",
         cols=[col("Fecha", "datetime", "dd-mm-yyyy"), col("Plan", "number", "#,0.0", resumen="none")]),
    dict(nombre="Horas_Codigo_CAEX", desc="Horas por código de los CAEX por día (inicio del turno) y turno. Las categorías de mantención "
                                          "explican la disponibilidad y las de demora y reserva, la UEBD. Fuente: Horas_Codigo_CAEX.csv.",
         cols=[col("Fecha", "datetime", "dd-mm-yyyy"), col("Turno", T), col("Equipo", T), col("Categoria", T), col("Codigo", T),
               col("Horas", "number", "#,0.0")]),
    dict(nombre="Fact_HorasEquipo", desc="Horas y movimiento de cada CAEX por día y turno (12 h nominales por turno). "
                                         "Fuente: Fact_HorasEquipo.csv.",
         cat="Uncategorized", anot_col="User",
         cols=[col("Fecha", "datetime", "General Number"), col("Turno", T), col("Tipo Equipo", T), col("Equipo", T), col("Flota", T)]
              + [HORAS(n) for n in ("Horas Nominales", "Horas Efectivas", "Horas PO Espera", "Horas PO Cola", "Horas PO Totales",
                                    "Horas Demora No Programada", "Horas Demora Programada", "Horas Reserva", "Horas Disponibles",
                                    "Horas Mantencion Programada", "Horas Mantencion No Programada", "Movimiento Total",
                                    "Material Extraido", "Material Remanejo")]),
    dict(nombre="Fact_Ciclos", desc="Ciclos de acarreo (muestra de dos por camión y turno). time es el día en que empieza el turno; "
                                    "los tiempos están en segundos. Fuente: Fact_Ciclos.csv.",
         cat="Uncategorized", anot_col="User",
         cols=[col("time", "datetime", "General Number"), col("shift", T), col("crew", T), col("TruckName", T), col("ShovelName", T),
               col("Dump_LocationType", T), col("TruckOpName", T), col("payload", "number")]
              + [col(c, "int", "0") for c in ("traveling_time", "waiting_time", "spotting_time", "loading_time", "hauling_time",
                                              "queued_time", "backing_time", "tipping_time")]),
    dict(nombre="Plan_CAEX", desc="Plan semanal de la flota CAEX, una fila por día. Los días sin fila no tienen plan. "
                                  "Fuente: Plan_CAEX.csv.",
         cat="Uncategorized", cols=[col("Fecha", "datetime", resumen="none"), HORAS("Horas Disponibles Plan"),
                                    HORAS("Horas Efectivas Plan"), HORAS("Horas Nominales Plan"), HORAS("Toneladas Plan")]),
    dict(nombre="Dim_Tiempo", desc="Calendario con el día operacional en curso (cambio de día a las 08:00). Fuente: Dim_Tiempo.csv.",
         cat="Uncategorized", anot_col="User", medidas_extra="Fecha_Operacional_Actual",
         cols=[col("Fecha", "datetime", "Long Date", nullable=False), col("Anio", "int", "0"), col("Mes", "int", "0"),
               col("NombreMes", T), col("AnioMes", T), col("Semana", "int", "0"), col("DiaSemana", "int", "0"), col("NombreDia", T),
               col("Semana_Inicio", "datetime", "General Number", resumen="none", hidden=True,
                   desc="Lunes de la semana calendario de esta fecha (fecha real, no número de semana): única y ordenable entre años."),
               col("Etiqueta_Semana", T, sort_by="Semana_Inicio",
                   desc="Etiqueta del eje X en vista semana: «Sem 14-abr» (lunes de esa semana)."),
               col("Etiqueta_Mes", T, sort_by="AnioMes", desc="Etiqueta del eje X en vista mes: «abr 2025»."),
               col("Es_Hoy_Operacional", "logical", '"TRUE";"TRUE";"FALSE"',
                   desc="VERDADERO para el día operacional en curso (cambio de día a las 08:00)."),
               col("Dia_Etiqueta", T, sort_by="Fecha",
                   desc="Texto del segmentador de fecha: «HOY» para el día operacional en curso y la fecha larga para los demás.")],
         calculadas=[("Dia RD", 'SUBSTITUTE(FORMAT(Dim_Tiempo[Fecha], "ddd dd-mm"), ".", "")', "Fecha")]),
    dict(nombre="Dim_Turno", desc="Turnos: A (08:00-20:00) y B (20:00-08:00). Fuente: Dim_Turno.csv.", cat="Uncategorized",
         anot_col="User",
         cols=[col("Turno", T, nullable=False), col("Nombre", T), col("HoraInicio", "datetime", "Long Time"),
               col("HoraFin", "datetime", "Long Time")]),
    dict(nombre="Dim_Equipo", desc="Equipos: 26 CAEX (Truck) y 4 palas (Shovel). Fuente: Dim_Equipo.csv.", cat="Uncategorized",
         anot_col="User",
         cols=[col("Equipo", T, nullable=False), col("TipoEquipo", T), col("Flota", T), col("Activo_KPI", "int", "0"),
               col("Es Carguio", "int", "0")]),
    dict(nombre="Dim_Actualizacion", desc="Marca de tiempo de la última actualización del conjunto de datos. Una sola fila; "
                                          "alimenta el texto de actualización del encabezado.",
         cat="Uncategorized", anot_col="User",
         cols=[col("Marca", "datetime", "General Number", desc="Fecha y hora exactas de la última actualización."),
               col("Hora_Texto", T, desc="Hora de la última actualización en formato HH:MM.")]),
]
ORDEN_CONSULTAS = [t["nombre"] for t in TABLAS]


def tabla_importada(t, medidas_dim_tiempo=()):
    nom = t["nombre"]
    out = [f"/// {t['desc']}", f"table {q(nom)}", f"\tlineageTag: {tag('table', nom)}", ""]
    for m in medidas_dim_tiempo:
        out += medida_tmdl(m)
    for c in t["cols"]:
        if c.get("desc"):
            out.append(f"\t/// {c['desc']}")
        out += [f"\tcolumn {q(c['nombre'])}", f"\t\tdataType: {DTYPE[c['tipo']]}"]
        if c.get("hidden"):
            out.append("\t\tisHidden")
        if c.get("nullable") is False:
            out.append("\t\tisNullable: false")
        if c["fmt"]:
            out.append(f"\t\tformatString: {c['fmt']}")
        out.append(f"\t\tlineageTag: {tag('col', nom, c['nombre'])}")
        if t.get("cat"):
            out.append(f"\t\tdataCategory: {t['cat']}")
        out += [f"\t\tsummarizeBy: {c['resumen']}", f"\t\tsourceColumn: {c['nombre']}"]
        if c.get("sort_by"):
            out.append(f"\t\tsortByColumn: {q(c['sort_by'])}")
        out += ["", f"\t\tannotation SummarizationSetBy = {t.get('anot_col', 'Automatic')}"]
        for k, v in (c.get("anot") or {}).items():
            out += ["", f"\t\tannotation {k} = {v}"]
        out.append("")
    for nombre, expr, ordenar in t.get("calculadas", []):
        out += [f"\tcolumn {q(nombre)} = {expr}", "\t\tdataType: string", f"\t\tlineageTag: {tag('col', nom, nombre)}",
                "\t\tsummarizeBy: none", f"\t\tsortByColumn: {q(ordenar)}", "", "\t\tannotation SummarizationSetBy = Automatic", ""]
    tipos = ", ".join(f'{{"{c["nombre"]}", {TIPO_M[c["tipo"]]}}}' for c in t["cols"])
    out += [f"\tpartition {q(nom)} = m", "\t\tmode: import", "\t\tsource =",
            "\t\t\t\tlet",
            f'\t\t\t\t    Origen = Csv.Document(File.Contents(RutaDatos & "{nom}.csv"), [Delimiter = ",", Encoding = 65001, '
            "QuoteStyle = QuoteStyle.Csv]),",
            "\t\t\t\t    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),",
            f'\t\t\t\t    Tipos = Table.TransformColumnTypes(Encabezados, {{{tipos}}}, "en-US")',
            "\t\t\t\tin", "\t\t\t\t    Tipos", "", "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(out) + "\n"


def tabla_estatica(nombre, desc, filas, columna):
    """DATATABLE con Orden y un texto (ordenado por Orden)."""
    filas_txt = ",\n".join("        { " + ", ".join([str(f[0])] + [f'"{v}"' for v in f[1:]]) + " }" for f in filas)
    src = f'DATATABLE(\n    "Orden", INTEGER, "{columna}", STRING,\n    {{\n{filas_txt}\n    }}\n)'
    return tabla_calculada(nombre, desc, [("Orden", "int64", "0", None, True), (columna, "string", None, "Orden", False)], src)


# ---------------------------------------------------------------------------------------------------------------------
# MEDIDAS
# ---------------------------------------------------------------------------------------------------------------------
def M(name, expr, folder, fmt=None, desc=None, hidden=False):
    return dict(name=name, expr=expr, folder=folder, fmt=fmt, desc=desc, hidden=hidden, tag=tag("measure", MT, name))


VENTANA = "VAR i = [Inicio periodo]\nVAR f = [Fin periodo]\n"


def ventana(expr, filtros=""):
    return VENTANA + f"RETURN CALCULATE({expr}, KEEPFILTERS(DATESBETWEEN(Dim_Tiempo[Fecha], i, f)){filtros})"


def ventana_inline(col_):
    return f"CALCULATE(SUM(Fact_HorasEquipo[{col_}]), KEEPFILTERS(DATESBETWEEN(Dim_Tiempo[Fecha], [Inicio periodo], [Fin periodo])))"


def ventana_inline_avg(col_):
    return (f"CALCULATE(AVERAGE(Fact_Ciclos[{col_}]) / 60, KEEPFILTERS(DATESBETWEEN(Dim_Tiempo[Fecha], [Inicio periodo], "
            "[Fin periodo])))")


def plan(col_semanal, item_mensual):
    """SEMANAL y JUE-DOM: plan semanal día a día (en blanco si falta algún día). MENSUAL: plan mensual de Planes_Mina."""
    return (VENTANA +
            'RETURN\n    IF([Periodo elegido] = "MENSUAL",\n'
            "        VAR fechas = CALCULATETABLE(VALUES(Dim_Tiempo[Fecha]), KEEPFILTERS(DATESBETWEEN(Dim_Tiempo[Fecha], i, f)))\n"
            f'        RETURN CALCULATE(SUM(Planes_Mina[value]), Planes_Mina[plan_type] = "Mensual", '
            f'Planes_Mina[property_name] = "{item_mensual}",\n'
            "            TREATAS(fechas, Planes_Mina[start_date])),\n"
            "        IF([Días sin plan semanal] = 0,\n"
            f"            CALCULATE(SUM(Plan_CAEX[{col_semanal}]), KEEPFILTERS(DATESBETWEEN(Dim_Tiempo[Fecha], i, f))))\n    )")


def fmt_txt(tipo, v):
    return {"pct": f'FORMAT({v}, "0.0%")', "tph": f'FORMAT({v}, "#,0")', "h": f'FORMAT({v}, "#,0")'}[tipo]


def semaforo(r, p, verde=VERDE, ambar=AMBAR, rojo=ROJO, sin_plan=CIELO):
    """Verde desde el 99,9 % del plan (evita que el real igual al plan salga ámbar por decimales), ámbar desde el 95 %."""
    return (f'VAR r = {r}\nVAR p = {p}\nRETURN\n    SWITCH(TRUE(),\n        ISBLANK(r), BLANK(),\n'
            f'        ISBLANK(p) || p = 0, "{sin_plan}",\n        r >= 0.999 * p, "{verde}",\n        r >= 0.95 * p, "{ambar}",\n'
            f'        "{rojo}"\n    )')


# Pérdidas o ganancias de menos del 0,1 % del plan de toneladas cuentan como «en plan» (sin rojo ni verde)
TOL = "VAR tol = 0.001 * [Producción plan]\n"


def medidas():
    ms = []
    P = "Periodo"
    ms.append(M("Fin periodo", 'SWITCH([Periodo elegido], "JUE-DOM", [Fin JD], "MENSUAL", [Fin mes], [Último día])', P, "dd-mm-yyyy",
                desc="Último día del periodo elegido."))
    ms.append(M("Inicio semana", "VAR f = [Último día]\nRETURN IF(ISBLANK(f), BLANK(), f - MOD(WEEKDAY(f, 2) - 1, 7))", P, "dd-mm-yyyy",
                desc="Lunes de la semana de ayer: de lunes a ayer (el lunes de la reunión, la semana completa hasta el domingo)."))
    ms.append(M("Inicio JD", "VAR f = [Último día]\nRETURN IF(ISBLANK(f), BLANK(), f - MOD(WEEKDAY(f, 2) - 4, 7))", P, "dd-mm-yyyy",
                desc="Jueves del último jueves a domingo hasta ayer (de lunes a miércoles, el que ya cerró)."))
    ms.append(M("Inicio mes", "VAR h = [Hoy datos]\nVAR f = [Último día]\nRETURN IF(ISBLANK(f), BLANK(),\n"
                "    IF([Mes anterior], DATE(YEAR(EOMONTH(h, -1)), MONTH(EOMONTH(h, -1)), 1), DATE(YEAR(f), MONTH(f), 1)))", P,
                "dd-mm-yyyy", desc="Día 1 del mes de ayer (mes a la fecha) o, el primer lunes del mes, día 1 del mes anterior."))
    ms.append(M("Periodo elegido", "SELECTEDVALUE('Periodo RD'[Periodo], \"SEMANAL\")", P))
    ms.append(M("Inicio periodo", 'SWITCH([Periodo elegido], "JUE-DOM", [Inicio JD], "MENSUAL", [Inicio mes], [Inicio semana])', P,
                "dd-mm-yyyy"))
    ms.append(M("Texto periodo", rango_txt("[Inicio periodo]", "[Fin periodo]"), P))
    ms.append(M("Texto plan", 'VAR n = [Días sin plan semanal]\nRETURN\n    IF([Periodo elegido] <> "MENSUAL" && n > 0,\n'
                '        "sin plan en " & n & " de " & [Días periodo] & IF([Días periodo] = 1, " día", " días"),\n'
                '        SWITCH([Periodo elegido],\n            "JUE-DOM", "contra el plan diario",\n'
                '            "MENSUAL", "contra el plan mensual",\n            "contra el plan semanal"))', P,
                desc="Con algún día sin plan semanal, JUE-DOM y SEMANAL dicen cuántos («sin plan en 4 de 7 días») en vez de "
                     "«contra el plan …»."))
    ms.append(M("Texto encabezado", 'VAR t = [Texto periodo]\nRETURN IF(ISBLANK(t), "Sin datos", t & " · " & [Texto plan])', P))
    ms.append(M("Texto copia", 'VAR m = MAX(Dim_Actualizacion[Marca])\nRETURN IF(ISBLANK(m), BLANK(), "Datos al " & '
                'SUBSTITUTE(FORMAT(m, "ddd dd-mm hh:mm"), ".", ""))', P,
                desc="Hora de los datos cargados (su última actualización)."))
    ms.append(M("Días periodo", "CALCULATE(COUNTROWS(Dim_Tiempo), KEEPFILTERS(DATESBETWEEN(Dim_Tiempo[Fecha], [Inicio periodo], "
                "[Fin periodo])))", P, "0", desc="Días del periodo elegido en el contexto (uno por día en los gráficos por día)."))

    R = "OEE\\Real"
    for n, c in [("HN real", "Horas Nominales"), ("HD real", "Horas Disponibles"), ("HE real", "Horas Efectivas"),
                 ("Movimiento real", "Movimiento Total")]:
        ms.append(M(n, ventana(f"SUM(Fact_HorasEquipo[{c}])"), R, "#,0",
                    desc=f"Suma de Fact_HorasEquipo[{c}] de los CAEX (Truck) en el periodo elegido."))
    ms.append(M("DF real", "DIVIDE([HD real], [HN real])", R, "0.0%", desc="Disponibilidad física: horas disponibles / nominales."))
    ms.append(M("UEBD real", "DIVIDE([HE real], [HD real])", R, "0.0%", desc="Utilización efectiva: horas efectivas / disponibles."))
    ms.append(M("Rendimiento real", "DIVIDE([Movimiento real], [HE real])", R, "#,0",
                desc="Rendimiento efectivo: movimiento total / horas efectivas (t/h)."))

    Pl = "OEE\\Plan"
    for n, c, it in [("HN plan", "Horas Nominales Plan", "Horas Nominales CAEX"), ("HD plan", "Horas Disponibles Plan", "Horas Disponibles CAEX"),
                     ("HE plan", "Horas Efectivas Plan", "Horas Efectivas CAEX"), ("Toneladas plan", "Toneladas Plan", "Total Toneladas CAEX")]:
        ms.append(M(n, plan(c, it), Pl, "#,0",
                    desc=f"SEMANAL y JUE-DOM: Plan_CAEX[{c}] (plan semanal, día a día), en blanco si a algún día del periodo le falta "
                         f"el plan. MENSUAL: «{it}» del plan mensual (Planes_Mina), día a día hasta el domingo de cierre."))
    ms.append(M("DF plan", "DIVIDE([HD plan], [HN plan])", Pl, "0.0%"))
    ms.append(M("UEBD plan", "DIVIDE([HE plan], [HD plan])", Pl, "0.0%"))
    ms.append(M("Rendimiento plan", "DIVIDE([Toneladas plan], [HE plan])", Pl, "#,0"))
    ms.append(M("Días sin plan semanal",
                VENTANA + "VAR conPlan = CALCULATE(DISTINCTCOUNT(Plan_CAEX[Fecha]), KEEPFILTERS(DATESBETWEEN(Dim_Tiempo[Fecha], i, f)),\n"
                "    NOT ISBLANK(Plan_CAEX[Toneladas Plan]), NOT ISBLANK(Plan_CAEX[Horas Nominales Plan]))\n"
                "RETURN MAX(0, [Días periodo] - conPlan)", Pl, "0",
                desc="Días del periodo elegido (en el contexto) sin plan semanal en Plan_CAEX: sin fila o con las toneladas o las horas "
                     "nominales en blanco. Con algún día sin plan, JUE-DOM y SEMANAL quedan sin plan en vez de comparar un plan a "
                     "medias con el real completo."))

    O = "OEE"
    base_vars = ("VAR hnp = [HN plan]\nVAR dfp = [DF plan]\nVAR up = [UEBD plan]\nVAR rp = [Rendimiento plan]\n"
                 "VAR hnr = [HN real]\nVAR dfr = [DF real]\nVAR ur = [UEBD real]\nVAR rr = [Rendimiento real]\n"
                 "VAR ok = NOT ISBLANK(hnp) && hnp <> 0 && NOT ISBLANK(hnr) && hnr <> 0\n")
    ms.append(M("Pérdida disponibilidad", base_vars + "RETURN IF(ok, hnp * (dfr - dfp) * up * rp)", O, "+#,0;-#,0",
                desc="Toneladas que se ganaron o perdieron por la disponibilidad: HN plan × (DF real − DF plan) × UEBD plan × "
                     "rendimiento plan."))
    ms.append(M("Pérdida UEBD", base_vars + "RETURN IF(ok, hnp * dfr * (ur - up) * rp)", O, "+#,0;-#,0",
                desc="Por la UEBD: HN plan × DF real × (UEBD real − UEBD plan) × rendimiento plan."))
    ms.append(M("Pérdida rendimiento", base_vars + "RETURN IF(ok, hnp * dfr * ur * (rr - rp))", O, "+#,0;-#,0",
                desc="Por el rendimiento efectivo: HN plan × DF real × UEBD real × (rendimiento real − plan)."))
    ms.append(M("Pérdida horas nominales", base_vars + "RETURN IF(ok, (hnr - hnp) * dfr * ur * rr)", O, "+#,0;-#,0",
                desc="Por las horas nominales (CAEX en flota): (HN real − HN plan) × DF real × UEBD real × rendimiento real."))
    ms.append(M("Producción plan", "[Toneladas plan]", O, "#,0", desc="Movimiento total plan de los CAEX (= HN × DF × UEBD × rendimiento del plan)."))
    ms.append(M("Producción real", "[Movimiento real]", O, "#,0", desc="Movimiento total real de los CAEX."))
    ms.append(M("Variación producción", "VAR p = [Producción plan]\nVAR r = [Producción real]\nRETURN IF(ISBLANK(p) || p = 0 || ISBLANK(r), "
                "BLANK(), r / p - 1)", O, "+0.00%;-0.00%"))
    ms.append(M("OEE plan", "[DF plan] * [UEBD plan]", O, "0.0%", desc="OEE del plan: DF × UEBD (el rendimiento del plan es la base, vale 1)."))
    ms.append(M("OEE real", "VAR rp = [Rendimiento plan]\nRETURN IF(ISBLANK(rp) || rp = 0, BLANK(), [DF real] * [UEBD real] * "
                "[Rendimiento real] / rp)", O, "0.0%", desc="OEE real: DF × UEBD × rendimiento real / rendimiento plan."))
    ms.append(M("Control cascada", "[Producción plan] + [Pérdida disponibilidad] + [Pérdida UEBD] + [Pérdida rendimiento] + "
                "[Pérdida horas nominales] - [Producción real]", O, "#,0", hidden=True,
                desc="Debe dar 0: el plan más las cuatro pérdidas es el real."))

    # Cascada (columnas apiladas: base invisible + total, pérdida o ganancia)
    Ca = "OEE\\Gráfico"
    niveles = ("VAR o = SELECTEDVALUE('Cascada OEE'[Orden])\nVAR p = [Producción plan]\n"
               "VAR d1 = [Pérdida disponibilidad]\nVAR d2 = [Pérdida UEBD]\nVAR d3 = [Pérdida rendimiento]\nVAR d4 = [Pérdida horas nominales]\n"
               "VAR l1 = p + d1\nVAR l2 = l1 + d2\nVAR l3 = l2 + d3\nVAR l4 = l3 + d4\n")
    ms.append(M("Cascada base", niveles + "RETURN IF(ISBLANK(p) || ISBLANK(d1), BLANK(),\n"
                "    SWITCH(o, 2, MIN(p, l1), 3, MIN(l1, l2), 4, MIN(l2, l3), 5, MIN(l3, l4)))", Ca, "#,0", hidden=True,
                desc="Parte invisible de cada barra de pérdida: el menor de los niveles antes y después de la palanca."))
    ms.append(M("Cascada total", "SWITCH(SELECTEDVALUE('Cascada OEE'[Orden]), 1, [Producción plan], 6, [Producción real])", Ca, "#,0",
                hidden=True))
    delta = ("VAR d = SWITCH(SELECTEDVALUE('Cascada OEE'[Orden]), 2, [Pérdida disponibilidad], 3, [Pérdida UEBD], "
             "4, [Pérdida rendimiento], 5, [Pérdida horas nominales])\n")
    ms.append(M("Cascada pérdida", delta + "RETURN IF(d < 0, -d)", Ca, "-#,0", hidden=True))
    ms.append(M("Cascada ganancia", delta + "RETURN IF(d > 0, d)", Ca, "+#,0", hidden=True))
    for k, expr in [("plan", "[Producción plan]"), ("real", "[Producción real]")]:
        ms.append(M(f"Txt movimiento {k}", f'VAR v = {expr}\nRETURN IF(ISBLANK(v), "—", FORMAT(v, "#,0") & " t")', Ca))
    for k, _, _, _, _, perd in PALANCAS:
        ms.append(M(f"Txt pérdida {k}", f'VAR v = {perd}\nRETURN IF(ISBLANK(v), "—", FORMAT(v, "+#,0;-#,0") & " t")', Ca))
        ms.append(M(f"Color pérdida {k}", f'VAR v = {perd}\n{TOL}RETURN IF(ISBLANK(v) || ABS(v) <= tol, "{PLOMO}", IF(v < 0, "{ROJO}", "{VERDE}"))',
                    Ca, hidden=True))
        ms.append(M(f"Color botón {k}", f'VAR v = {perd}\n{TOL}RETURN IF(NOT ISBLANK(v) && v < -tol, "{ROJO}", "{MEDIANOCHE}")', Ca,
                    hidden=True, desc="El botón de una palanca que perdió más del 0,1 % del plan va en rojo (es el foco de la reunión); "
                                      "las demás, en azul medianoche."))
    ms.append(M("Txt botón", '"Ver detalle  ›"', Ca, hidden=True))
    ms.append(M("Txt variación producción", 'VAR v = [Variación producción]\nRETURN IF(ISBLANK(v), "—", FORMAT(v, "+0.00%;-0.00%"))', Ca))
    ms.append(M("Color variación producción", f'VAR v = [Variación producción]\nRETURN IF(ISBLANK(v) || v >= -0.001, "{MEDIANOCHE}", "{ROJO}")',
                Ca, hidden=True))

    # Tabla «Datos Transporte»
    Tb = "OEE\\Tabla"
    o = "VAR o = SELECTEDVALUE('Datos OEE'[Orden])\n"
    ms.append(M("Tabla plan", o + "VAR v = SWITCH(o, 1, [Producción plan], 2, [DF plan], 3, [UEBD plan], 4, [Rendimiento plan], 5, [HN plan], 6, [OEE plan])\n"
                'RETURN IF(ISBLANK(v), "—", SWITCH(o, 2, FORMAT(v, "0.0%"), 3, FORMAT(v, "0.0%"), 6, FORMAT(v, "0.0%"), FORMAT(v, "#,0")))', Tb))
    ms.append(M("Tabla real", o + "VAR v = SWITCH(o, 1, [Producción real], 2, [DF real], 3, [UEBD real], 4, [Rendimiento real], 5, [HN real], 6, [OEE real])\n"
                'RETURN IF(ISBLANK(v), "—", SWITCH(o, 2, FORMAT(v, "0.0%"), 3, FORMAT(v, "0.0%"), 6, FORMAT(v, "0.0%"), FORMAT(v, "#,0")))', Tb))
    ms.append(M("Tabla variación num", o + "VAR r = SWITCH(o, 1, [Producción real], 2, [DF real], 3, [UEBD real], 4, [Rendimiento real], 5, [HN real], 6, [OEE real])\n"
                "VAR p = SWITCH(o, 1, [Producción plan], 2, [DF plan], 3, [UEBD plan], 4, [Rendimiento plan], 5, [HN plan], 6, [OEE plan])\n"
                "RETURN IF(ISBLANK(r) || ISBLANK(p) || p = 0, BLANK(), r / p - 1)", Tb, "+0.00%;-0.00%", hidden=True))
    ms.append(M("Tabla variación", 'VAR v = [Tabla variación num]\nRETURN IF(ISBLANK(v), "—", FORMAT(v, "+0.00%;-0.00%"))', Tb))
    ms.append(M("Tabla pérdida num", o + "RETURN SWITCH(o, 2, [Pérdida disponibilidad], 3, [Pérdida UEBD], 4, [Pérdida rendimiento], 5, [Pérdida horas nominales])",
                Tb, "+#,0;-#,0", hidden=True))
    ms.append(M("Tabla pérdida", 'VAR v = [Tabla pérdida num]\nRETURN IF(ISBLANK(v), "", FORMAT(v, "+#,0;-#,0"))', Tb))
    ms.append(M("Color tabla variación", f'VAR v = [Tabla variación num]\nRETURN IF(ISBLANK(v) || ABS(v) <= 0.001, "{PLOMO}", IF(v < 0, "{ROJO}", "{VERDE}"))',
                Tb, hidden=True))
    ms.append(M("Color tabla pérdida", f'VAR v = [Tabla pérdida num]\n{TOL}RETURN IF(ISBLANK(v) || ABS(v) <= tol, "{PLOMO}", IF(v < 0, "{ROJO}", "{VERDE}"))',
                Tb, hidden=True))

    # Encabezado de cada detalle: real, plan, diferencia y toneladas de la palanca
    E = "Detalle\\Encabezado"
    for k, nom, r, p, tipo, perd in PALANCAS:
        sufijo = ' & " t/h"' if tipo == "tph" else ' & " h"' if tipo == "h" else ""
        ms.append(M(f"Txt {k} real", f'VAR v = {r}\nRETURN IF(ISBLANK(v), "—", {fmt_txt(tipo, "v")}{sufijo})', E))
        if tipo == "pct":
            dif = 'FORMAT((r - p) * 100, "+0.0;-0.0") & " pp"'
        else:
            dif = 'FORMAT(r - p, "+#,0;-#,0")' + (' & " t/h"' if tipo == "tph" else ' & " h"')
        ms.append(M(f"Txt {k} plan", f'VAR r = {r}\nVAR p = {p}\nVAR t = {perd}\nRETURN IF(ISBLANK(p), "Sin plan",\n'
                    f'    "Plan " & {fmt_txt(tipo, "p")} & IF(ISBLANK(r), "", " · " & {dif}) & IF(ISBLANK(t), "", " · " & FORMAT(t, "+#,0;-#,0") & " t"))', E))
        ms.append(M(f"Color {k} encabezado", f'VAR t = {perd}\n{TOL}RETURN IF(ISBLANK(t) || t >= -tol, "{VERDE_CLARO}", "{ROJO_CLARO}")', E, hidden=True))

    D = "Detalle"
    ms.append(M("Color DF", semaforo("[DF real]", "[DF plan]"), D, hidden=True))
    ms.append(M("Color UEBD", semaforo("[UEBD real]", "[UEBD plan]"), D, hidden=True))
    ms.append(M("Color rendimiento", semaforo("[Rendimiento real]", "[Rendimiento plan]"), D, hidden=True))
    ms.append(M("CAEX en flota", "DIVIDE([HN real], 24 * [Días periodo])", D, "0.0",
                desc="CAEX equivalentes en flota: horas nominales / (24 × días). Por día es el número de CAEX que contó la flota."))
    ms.append(M("CAEX en flota plan", "DIVIDE([HN plan], 24 * [Días periodo])", D, "0.0", desc="CAEX equivalentes del plan."))
    ms.append(M("Color flota", semaforo("[CAEX en flota]", "[CAEX en flota plan]"), D, hidden=True))
    ms.append(M("Días en flota", "DIVIDE([HN real], 24)", D, "0.0", desc="Días de 24 h que el CAEX contó en la flota en el periodo."))

    Cd = "Detalle\\Códigos"
    no_disp = ", ".join(f'"{c}"' for c in CAT_NO_DISP)
    no_efe = ", ".join(f'"{c}"' for c in CAT_NO_EFECTIVO)
    ms.append(M("Horas no disponibles", ventana("SUM(Horas_Codigo_CAEX[Horas])", f", KEEPFILTERS(Horas_Codigo_CAEX[Categoria] IN {{{no_disp}}})"),
                Cd, "#,0.0", desc="Horas de mantención (programada, no programada, neumáticos y daño) por código."))
    ms.append(M("% del nominal", "DIVIDE([Horas no disponibles], CALCULATE([HN real], REMOVEFILTERS(Horas_Codigo_CAEX)))", Cd, "0.0%",
                desc="Horas del código sobre las horas nominales de la flota: los puntos de disponibilidad que se van en ese código."))
    ms.append(M("Horas no efectivas", ventana("SUM(Horas_Codigo_CAEX[Horas])", f", KEEPFILTERS(Horas_Codigo_CAEX[Categoria] IN {{{no_efe}}})"),
                Cd, "#,0.0", desc="Horas de demora programada, no programada y reserva por código."))
    ms.append(M("% del disponible", "DIVIDE([Horas no efectivas], CALCULATE([HD real], REMOVEFILTERS(Horas_Codigo_CAEX)))", Cd, "0.0%",
                desc="Horas del código sobre las horas disponibles de la flota: los puntos de UEBD que se van en ese código."))
    ms.append(M("Horas tipo UEBD", "SWITCH(SELECTEDVALUE('Tipos UEBD'[Orden]),\n" +
                ",\n".join(f"    {n}, {ventana_inline(c)}" for n, _, c in TIPOS_UEBD) + ")", Cd, "#,0",
                desc="Horas disponibles no efectivas de los CAEX por tipo: demoras, reserva y pérdida operacional."))

    Cy = "Detalle\\Ciclos"
    fc = f"CALCULATE(AVERAGE(Fact_Ciclos[payload]), Fact_Ciclos[payload] > {PAYLOAD_MIN}, Fact_Ciclos[payload] < {PAYLOAD_MAX})"
    ms.append(M("Factor de carga", ventana(fc), Cy, "#,0.0",
                desc=f"Promedio del payload de los ciclos con carga completa (Fact_Ciclos): entre {PAYLOAD_MIN} y {PAYLOAD_MAX} t."))
    ms.append(M("Factor de carga plan",
                VENTANA + "VAR p = CALCULATE(AVERAGE(Plan_FactorCarga[Plan]), KEEPFILTERS(DATESBETWEEN(Dim_Tiempo[Fecha], i, f)))\nRETURN\n"
                "    IF(ISBLANK(f), BLANK(), COALESCE(p,\n        CALCULATE(LASTNONBLANKVALUE(Plan_FactorCarga[Fecha], AVERAGE(Plan_FactorCarga[Plan])),\n"
                "            REMOVEFILTERS(Dim_Tiempo), Plan_FactorCarga[Fecha] <= f)))", Cy, "#,0",
                desc="Plan diario del factor de carga (Plan_FactorCarga); sin plan en el periodo, el último conocido."))
    ms.append(M("Color factor de carga", semaforo("[Factor de carga]", "[Factor de carga plan]"), Cy, hidden=True))
    ms.append(M("Ciclo componente (min)", "SWITCH(SELECTEDVALUE('Componentes ciclo'[Orden]),\n" +
                ",\n".join(f"    {n}, {ventana_inline_avg(c)}" for n, _, c in COMPONENTES) + ")", Cy, "0.0",
                desc="Minutos promedio por ciclo de cada componente (Fact_Ciclos, segundos / 60) en el periodo."))
    ms.append(M("Ciclos", ventana("COUNTROWS(Fact_Ciclos)"), Cy, "#,0", desc="Ciclos de acarreo en el periodo."))

    ms.append(M("Hoy datos", "VAR m = MAX(Dim_Actualizacion[Marca])\nRETURN IF(ISBLANK(m), [Fecha_Operacional_Actual], DATE(YEAR(m), MONTH(m), DAY(m)))",
                P, "dd-mm-yyyy", hidden=True, desc="Día calendario de la hora de los datos cargados."))
    ms.append(M("Último día", "VAR h = [Hoy datos]\nRETURN IF(ISBLANK(h), BLANK(), h - 1)", P, "dd-mm-yyyy",
                desc="Ayer: último día de los periodos (días operacionales de 08:00 a 08:00). El lunes es el domingo."))
    ms.append(M("Fin JD", "VAR i = [Inicio JD]\nRETURN IF(ISBLANK(i), BLANK(), MIN(i + 3, [Último día]))", P, "dd-mm-yyyy",
                desc="Domingo de ese jueves a domingo, sin pasar de ayer."))
    ms.append(M("Mes anterior", "VAR h = [Hoy datos]\nRETURN NOT ISBLANK(h) && WEEKDAY(h, 2) = 1 && DAY(h) <= 7", P, hidden=True,
                desc="Verdadero el primer lunes de cada mes: MENSUAL muestra el mes anterior completo."))
    ms.append(M("Fin mes", "VAR h = [Hoy datos]\nRETURN IF([Mes anterior], EOMONTH(h, -1), [Último día])", P, "dd-mm-yyyy",
                desc="Ayer o, el primer lunes del mes, el último día del mes anterior."))
    return ms


def tabla_medidas(ms):
    out = ["/// Medidas del OEE de transporte (CAEX) y de su detalle. La tabla solo aloja medidas. Generada por pbip/generador/gen_pbi_oee.py.",
           f"table {q(MT)}", f"\tlineageTag: {tag('table', MT)}", ""]
    for m in ms:
        out += medida_tmdl(m)
    out += ["\tcolumn Valor", "\t\tdataType: int64", "\t\tisHidden", "\t\tformatString: 0",
            f"\t\tlineageTag: {tag('col', MT, 'Valor')}", "\t\tsummarizeBy: none", "\t\tisNameInferred",
            "\t\tsourceColumn: [Valor]", "", "\t\tannotation SummarizationSetBy = Automatic", "",
            f"\tpartition {q(MT)} = calculated", "\t\tmode: import", '\t\tsource = ROW("Valor", 0)', ""]
    return "\n".join(out) + "\n"


RELACIONES = [  # (desde, hasta)
    ("Fact_HorasEquipo.Equipo", "Dim_Equipo.Equipo"), ("Fact_HorasEquipo.Turno", "Dim_Turno.Turno"),
    ("Fact_HorasEquipo.Fecha", "Dim_Tiempo.Fecha"), ("Fact_Ciclos.TruckName", "Dim_Equipo.Equipo"),
    ("Fact_Ciclos.shift", "Dim_Turno.Turno"),
    ("Fact_Ciclos.time", "Dim_Tiempo.Fecha"),  # time = día en que empieza el turno
    ("Plan_CAEX.Fecha", "Dim_Tiempo.Fecha"), ("Plan_FactorCarga.Fecha", "Dim_Tiempo.Fecha"),
    ("Horas_Codigo_CAEX.Fecha", "Dim_Tiempo.Fecha"), ("Horas_Codigo_CAEX.Turno", "Dim_Turno.Turno"),
    ("Horas_Codigo_CAEX.Equipo", "Dim_Equipo.Equipo"),
]
ESTATICAS = [("Periodo RD", "Periodos de la reunión de los lunes, hasta ayer: JUE-DOM (último jueves a domingo), SEMANAL (de lunes a "
                             "ayer; el lunes, la semana completa) y MENSUAL (mes a la fecha; el primer lunes del mes, el mes anterior "
                             "completo). Sin selección vale SEMANAL.",
              [(1, "JUE-DOM"), (2, "SEMANAL"), (3, "MENSUAL")], "Periodo"),
             ("Cascada OEE", "Barras de la cascada del OEE, en su orden: plan, las cuatro palancas y real.", PASOS, "Paso"),
             ("Datos OEE", "Filas de la tabla «Datos Transporte» bajo la cascada.", FILAS, "Medicion"),
             ("Tipos UEBD", "Tipos de horas disponibles no efectivas para ordenarlas de mayor a menor.",
              [(o, n) for o, n, _ in TIPOS_UEBD], "Tipo"),
             ("Componentes ciclo", "Componentes del ciclo del CAEX (Fact_Ciclos) para ordenarlos de mayor a menor.",
              [(o, n) for o, n, _ in COMPONENTES], "Componente")]


def escribir_modelo():
    ms = medidas()
    nombres = [m["name"] for m in ms]
    dup = {n for n in nombres if nombres.count(n) > 1}
    if dup:
        sys.exit(f"Medidas duplicadas: {dup}")
    if MODELO.exists():
        shutil.rmtree(MODELO)
    fecha_op = M("Fecha_Operacional_Actual", "CALCULATE(MAX(Dim_Tiempo[Fecha]), REMOVEFILTERS(Dim_Tiempo), Dim_Tiempo[Es_Hoy_Operacional] = TRUE())",
                 None, "General Number")
    for t in TABLAS:
        escribir(TDIR / f"{t['nombre']}.tmdl", tabla_importada(t, [fecha_op] if t.get("medidas_extra") else []))
    for nombre, desc, filas, columna in ESTATICAS:
        escribir(TDIR / f"{nombre}.tmdl", tabla_estatica(nombre, desc, filas, columna))
    escribir(TDIR / f"{MT}.tmdl", tabla_medidas(ms))
    calc = [e[0] for e in ESTATICAS] + [MT]
    model = ["model Model", "\tculture: es-ES", "\tdefaultPowerBIDataSourceVersion: powerBI_V3", "\tsourceQueryCulture: es-ES",
             "\tvalueFilterBehavior: independent", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
             "annotation __PBI_TimeIntelligenceEnabled = 0", "", 'annotation PBI_ProTooling = ["DevMode"]', "",
             "annotation PBI_QueryOrder = [" + ",".join(f'"{t}"' for t in ["RutaDatos"] + ORDEN_CONSULTAS) + "]", ""]
    model += [f"ref table {q(t)}" for t in ORDEN_CONSULTAS + calc] + ["", "ref expression RutaDatos", "", "ref cultureInfo es-ES", ""]
    escribir(SM / "model.tmdl", "\n".join(model))
    escribir(SM / "database.tmdl", "database\n\tcompatibilityLevel: 1606\n\n")
    escribir(SM / "expressions.tmdl",
             f'expression RutaDatos = "{PARAMETRO_RUTA}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
             f"\tlineageTag: {tag('expression', 'RutaDatos')}\n\n\tannotation PBI_ResultType = Text\n\n")
    escribir(SM / "cultures" / "es-ES.tmdl", "cultureInfo es-ES\n\n")
    rel = []
    for de, a in RELACIONES:
        rel += [f"relationship {tag('rel', de, a)}", f"\tfromColumn: {de}", f"\ttoColumn: {a}", ""]
    escribir(SM / "relationships.tmdl", "\n".join(rel))
    escribir_json(MODELO / "definition.pbism",
                  {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
                   "version": "4.2", "settings": {}})
    escribir_json(MODELO / ".platform", plataforma("SemanticModel"))
    return len(ms)


def plataforma(tipo):
    return {"$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": tipo, "displayName": NOMBRE}, "config": {"version": "2.0", "logicalId": tag("logicalId", tipo)}}


# ---------------------------------------------------------------------------------------------------------------------
# INFORME (PBIR)
# ---------------------------------------------------------------------------------------------------------------------
class Pagina(PaginaBase):
    def __init__(self, key, nombre):
        super().__init__("oee_" + key, nombre)
        self.id = hid("oee", "pagina", key)  # la app (gen_visor.py) usa este id para abrir la página «OEE Transporte»

    def selector(self, key, x, y, w, h, marco=False):
        """Mosaicos blancos con texto azul medianoche; el elegido sale oscuro. Con `marco`, borde para fondos blancos."""
        sel = cat_filter("x", "Periodo RD", "Periodo", ["'SEMANAL'"])["filter"]
        general = {"orientation": Dn(1), "filter": {"filter": sel}}
        items = {"fontColor": C(MEDIANOCHE), "background": C("#FFFFFF"), "textSize": Dn(9)}
        if marco:
            general.update({"outlineColor": C(MEDIANOCHE), "outlineWeight": Dn(1)})
            items["outline"] = S("Frame")
        objs = {"data": [{"properties": {"mode": S("Basic")}}],
                "general": [{"properties": general}],
                "selection": [{"properties": {"singleSelect": B(True), "strictSingleSelect": B(True), "selectAllCheckboxEnabled": B(False)}}],
                "header": [{"properties": {"show": B(False)}}],
                "items": [{"properties": items}]}
        apagado = [{"properties": {"show": B(False)}}]
        vis = {"visualType": "slicer", "query": {"queryState": {"Values": {"projections": [proj(CF("Periodo RD", "Periodo"), "Periodo", active=True)]}}},
               "objects": objs, "visualContainerObjects": {"background": apagado, "title": apagado, "dropShadow": apagado, "visualHeader": apagado,
                                                           "padding": [{"properties": {"top": Dn(0), "bottom": Dn(0), "left": Dn(0), "right": Dn(0)}}]},
               "syncGroup": {"groupName": "Periodo", "fieldChanges": True, "filterChanges": True}, "drillFilterOtherVisuals": True}
        return self.add(key, x, y, w, h, vis)

    def pastilla(self, key, x, y, w, h, texto, color_medida, destino, size=10):
        """Botón visible: tarjeta con el texto y el fondo de una medida, y encima un botón transparente que navega."""
        apagado = [{"properties": {"show": B(False)}}]
        objs = {"labels": [{"properties": {"color": C("#FFFFFF"), "fontSize": Dn(size), "fontFamily": S("Segoe UI Semibold")}}],
                "categoryLabels": apagado, "wordWrap": apagado}
        vco = {"title": apagado, "dropShadow": apagado, "visualHeader": apagado, "visualTooltip": apagado,
               "background": [{"properties": {"show": B(True), "color": CM(color_medida, MT), "transparency": Dn(0)}}],
               "border": [{"properties": {"show": B(True), "color": C("#FFFFFF"), "radius": Dn(h // 2)}}],
               "padding": [{"properties": {"top": Dn(0), "bottom": Dn(0), "left": Dn(0), "right": Dn(0)}}]}
        vis = {"visualType": "card", "query": {"queryState": {"Values": {"projections": [proj(MF(MT, texto), texto)]}}},
               "objects": objs, "visualContainerObjects": vco, "drillFilterOtherVisuals": True}
        self.add(key, x, y, w, h, vis)
        return self.boton(key + "_ir", x, y, w, h, destino, hover="#FFFFFF")

    def cifra(self, key, x, y, w, h, medida, size=10, color_medida=None, color=PLOMO, fondo=None, semibold=True):
        v = self.texto_medida(key, x, y, w, h, medida, size=size, color=color, color_medida=color_medida, semibold=semibold)
        if fondo:
            v["visual"]["visualContainerObjects"]["background"] = [{"properties": {"show": B(True), "color": C(fondo), "transparency": Dn(0)}}]
        return v

    def cascada(self, key, x, y, w, h):
        cat = CF("Cascada OEE", "Paso")
        base, tot, per, gan = (MF(MT, n) for n in ("Cascada base", "Cascada total", "Cascada pérdida", "Cascada ganancia"))
        qs = {"Category": {"projections": [proj(cat, "Paso", active=True)]},
              "Y": {"projections": [proj(base, "Base"), proj(tot, "Movimiento"), proj(per, "Pérdida"), proj(gan, "Ganancia")]}}
        query = {"queryState": qs, "sortDefinition": {"sort": [{"field": cat, "direction": "Ascending"}]}}
        objs = {"categoryAxis": [{"properties": {"show": B(True), "fontSize": Dn(9), "labelColor": C(PLOMO), "showAxisTitle": B(False),
                                                 "gridlineShow": B(False)}}],
                "valueAxis": [{"properties": {"show": B(False), "gridlineShow": B(False), "showAxisTitle": B(False), "start": Dn(0)}}],
                "legend": [{"properties": {"show": B(False)}}],
                "labels": [{"properties": {"show": B(False)}}],
                # La base va en blanco (fondo de la página): queda invisible y la barra de pérdida o ganancia «flota»
                "dataPoint": [{"properties": {"defaultColor": C(TOTAL)}},
                              {"properties": {"fill": C("#FFFFFF")}, "selector": {"metadata": qref(base)}},
                              {"properties": {"fill": C(TOTAL)}, "selector": {"metadata": qref(tot)}},
                              {"properties": {"fill": C(ROJO)}, "selector": {"metadata": qref(per)}},
                              {"properties": {"fill": C(VERDE)}, "selector": {"metadata": qref(gan)}}]}
        apagado = [{"properties": {"show": B(False)}}]
        vco = {"title": apagado, "subTitle": apagado, "background": apagado, "border": apagado, "dropShadow": apagado,
               "visualTooltip": apagado}
        vis = {"visualType": "columnChart", "query": query, "objects": objs, "visualContainerObjects": vco, "drillFilterOtherVisuals": True}
        return self.add(key, x, y, w, h, vis)

    def treemap(self, key, x, y, w, h, grupo, valor, titulo, filtros=None, tooltips=()):
        qs = {"Group": {"projections": [proj(grupo, active=True)]}, "Values": {"projections": [proj(valor, "Horas")]}}
        if tooltips:
            qs["Tooltips"] = {"projections": [proj(f, n) for f, n in tooltips]}
        objs = {"labels": [{"properties": {"show": B(True), "fontSize": Dn(9)}}],
                "categoryLabels": [{"properties": {"show": B(True), "fontSize": Dn(9)}}],
                "legend": [{"properties": {"show": B(False)}}]}
        vis = {"visualType": "treemap", "query": {"queryState": qs}, "objects": objs, "visualContainerObjects": caja(titulo),
               "drillFilterOtherVisuals": True}
        return self.add(key, x, y, w, h, vis, {"filterConfig": {"filters": filtros}} if filtros else None)


ANCHO = 1280
# Cascada: posición del gráfico y centros de sus 6 barras. Power BI deja ~89 px libres a la izquierda de la primera barra y
# ~63 a la derecha de la última (barras de 141 px cada 182,6 px).
CH_X, CH_Y, CH_W, CH_H = 16, 120, 1248, 296
PLOT_L, PLOT_R = 89, 63
BANDA = (CH_W - PLOT_L - PLOT_R) / 6
CENTROS = [round(CH_X + PLOT_L + (k + 0.5) * BANDA) for k in range(6)]


def pagina_oee(destinos):
    pag = Pagina("oee", "OEE Transporte")
    pag.texto("t1", 16, 4, 520, 40, "Equipos Mina", size=22, color=MEDIANOCHE, bold=True)
    pag.texto("t2", 16, 42, 520, 30, "Transporte", size=15, color=PLOMO)
    pag.selector("periodo", 852, 10, 412, 34, marco=True)
    pag.cifra("txtperiodo", 700, 50, 564, 22, "Texto encabezado", size=10, color=MEDIANOCHE)
    pag.texto("t3", 16, 80, 400, 26, "OEE Transporte", size=12, color=MEDIANOCHE, bold=True)
    # Corchete de la variación total, del centro de la primera barra al de la última
    y0, a, b = 104, CENTROS[0], CENTROS[-1]
    pag.rect("corchete_h", a, y0, b - a, 2, PLOMO)
    pag.rect("corchete_i", a, y0, 2, 16, PLOMO)
    pag.rect("corchete_d", b - 2, y0, 2, 16, PLOMO)
    pag.cifra("variacion", (a + b) // 2 - 80, y0 - 16, 160, 34, "Txt variación producción", size=18,
              color_medida="Color variación producción", fondo="#FFFFFF")
    pag.cascada("cascada", CH_X, CH_Y, CH_W, CH_H)
    # Cifra de cada barra (fija bajo su nombre) y, bajo las cuatro palancas, el botón a su detalle
    yv, yb = CH_Y + CH_H + 2, CH_Y + CH_H + 28
    w = 190
    pag.cifra("v_plan", CENTROS[0] - w // 2, yv, w, 22, "Txt movimiento plan", size=10, color=TOTAL)
    pag.cifra("v_real", CENTROS[5] - w // 2, yv, w, 22, "Txt movimiento real", size=10, color=TOTAL)
    for i, (k, *_r) in enumerate(PALANCAS, start=1):
        pag.cifra(f"v_{k}", CENTROS[i] - w // 2, yv, w, 22, f"Txt pérdida {k}", size=10, color_medida=f"Color pérdida {k}")
        pag.pastilla(f"b_{k}", CENTROS[i] - 66, yb, 132, 26, "Txt botón", f"Color botón {k}", destinos[k])
    # Tabla «Datos Transporte»
    yt = yb + 36
    pag.texto("t4", 16, yt, 300, 22, "Datos Transporte", size=11, color=MEDIANOCHE, bold=True)
    med = CF("Datos OEE", "Medicion")
    campos = [(med, "Medición"), (MF(MT, "Tabla plan"), "Plan CAEX"), (MF(MT, "Tabla real"), "Real CAEX"),
              (MF(MT, "Tabla variación"), "Variación"), (MF(MT, "Tabla pérdida"), "Pérdida/Ganancia CAEX (t)")]
    anchos = [(campos[0][0], 272), (campos[1][0], 224), (campos[2][0], 224), (campos[3][0], 192), (campos[4][0], 304)]
    alin = [(campos[i][0], "Right") for i in range(1, 5)]
    pag.tabla("datos", 16, yt + 24, 1248, 720 - (yt + 24) - 8, campos, anchos=anchos, alineacion=alin, orden=[(med, "Ascending")],
              cf=[(campos[3][0], None, "Color tabla variación"), (campos[4][0], None, "Color tabla pérdida")], font=10, padding=3,
              cabecera=TOTAL, borde=False, autoajuste=True)
    return pag


def encabezado_detalle(pag, titulo, k, etiqueta, oee_id):
    pag.rect("cab", 0, 0, ANCHO, 96, MEDIANOCHE)
    pag.logo("logo", 0, 8, 124.7, 48.3)
    pag.logo("logo_area", 126, 6, 56, 44, recurso=LOGO_AREA, nombre="Icono Minera Demo")
    caja = pag.texto("volver_txt", 16, 60, 120, 28, "← Volver al OEE", size=10, color="#FFFFFF", bold=True)
    caja["visual"]["visualContainerObjects"]["border"] = [{"properties": {"show": B(True), "color": C("#FFFFFF"), "radius": Dn(14)}}]
    caja["visual"]["visualContainerObjects"]["padding"] = [{"properties": {"top": Dn(4), "bottom": Dn(0), "left": Dn(10), "right": Dn(4)}}]
    pag.boton("volver", 16, 60, 120, 28, oee_id)
    pag.texto("t1", 196, 8, 520, 24, "Tablero de control", size=13, color="#FFFFFF")
    pag.texto("t2", 196, 32, 520, 32, titulo, size=18, color="#FFFFFF", bold=True)
    pag.selector("periodo", 720, 10, 330, 32)
    pag.cifra("txtperiodo", 700, 48, 370, 20, "Texto encabezado", size=9, color="#FFFFFF", semibold=False)
    pag.cifra("kpi", 1074, 4, 196, 44, f"Txt {k} real", size=24, color="#FFFFFF")
    pag.texto("kpi_et", 1074, 48, 196, 20, etiqueta, size=10, color="#FFFFFF", align="center")
    pag.cifra("kpi_plan", 1074, 70, 196, 20, f"Txt {k} plan", size=9, color_medida=f"Color {k} encabezado", semibold=True)


IZQ, DER, AW = 16, 648, 616
FILA1, FILA2, H1, H2 = 106, 404, 290, 308
SUB_PLAN = ("● Plan", MEDIANOCHE)  # la línea del plan va en azul medianoche: en otro color se perdía entre las columnas del semáforo


def filtro_categorias(pag, key, cats):
    return [cat_filter(hid(pag.key, key, "cat"), "Horas_Codigo_CAEX", "Categoria", [f"'{c}'" for c in cats])]


def filtro_flota(pag, key):
    """Sin los CAEX que casi no estuvieron en la flota (menos de 12 h nominales en el periodo)."""
    return [medida_filter(hid(pag.key, key, "flota"), "HN real", 12)]


def sin_miles(v):
    """Cifras completas («649», «4.215») en vez de «0,6 mil»."""
    objs = v["visual"]["objects"]
    objs["labels"][0]["properties"]["labelDisplayUnits"] = Dn(1)
    objs["valueAxis"][0]["properties"]["labelDisplayUnits"] = Dn(1)
    return v


def sin_encabezado(v):
    """Sin los íconos del visual (filtro, foco, «...»)."""
    v["visual"]["visualContainerObjects"]["visualHeader"] = [{"properties": {"show": B(False)}}]
    return v


def pagina_df(oee_id):
    pag = Pagina("df", "Disponibilidad CAEX")
    encabezado_detalle(pag, "DISPONIBILIDAD CAEX", "df", "Disponibilidad física CAEX", oee_id)
    dia, eq = CF("Dim_Tiempo", "Dia RD"), CF("Dim_Equipo", "Equipo")
    real, plan_ = MF(MT, "DF real"), MF(MT, "DF plan")
    pag.grafico("dia", IZQ, FILA1, AW, H1, "lineClusteredColumnComboChart", "Disponibilidad por día", categoria=dia,
                valores=[(real, "Real")], valores2=[(plan_, "Plan")], orden=(dia, "Ascending"), color_medida="Color DF",
                colores=[(plan_, MEDIANOCHE)], subtitulo=SUB_PLAN)
    pag.grafico("equipo", IZQ, FILA2, AW, H2, "clusteredBarChart", "Disponibilidad por CAEX", categoria=eq,
                valores=[(real, "Disponibilidad")], orden=(real, "Ascending"), color_medida="Color DF",
                filtros=filtros_equipo(pag, "equipo", "Truck") + filtro_flota(pag, "equipo"))
    cod, cat = CF("Horas_Codigo_CAEX", "Codigo"), CF("Horas_Codigo_CAEX", "Categoria")
    hnd = MF(MT, "Horas no disponibles")
    campos = [(cod, "Código"), (cat, "Categoría"), (hnd, "Horas"), (MF(MT, "% del nominal"), "% del nominal")]
    sin_encabezado(pag.tabla("codigos", DER, FILA1, AW, H1, campos, anchos=[(cod, 255), (cat, 185), (hnd, 66), (campos[3][0], 84)],
                             alineacion=[(hnd, "Right"), (campos[3][0], "Right")], orden=[(hnd, "Descending")], font=9, padding=3,
                             titulo="Horas no disponibles por código", filtros=filtro_categorias(pag, "codigos", CAT_NO_DISP),
                             autoajuste=True))
    pag.treemap("treemap", DER, FILA2, AW, H2, cod, hnd, "Horas no disponibles por código (mapa)",
                filtros=filtro_categorias(pag, "treemap", CAT_NO_DISP), tooltips=[(MF(MT, "% del nominal"), "% del nominal")])
    return pag


def pagina_uebd(oee_id):
    pag = Pagina("uebd", "UEBD CAEX")
    encabezado_detalle(pag, "UTILIZACIÓN EFECTIVA (UEBD) CAEX", "uebd", "UEBD CAEX", oee_id)
    dia, eq = CF("Dim_Tiempo", "Dia RD"), CF("Dim_Equipo", "Equipo")
    real, plan_ = MF(MT, "UEBD real"), MF(MT, "UEBD plan")
    pag.grafico("dia", IZQ, FILA1, AW, H1, "lineClusteredColumnComboChart", "UEBD por día", categoria=dia,
                valores=[(real, "Real")], valores2=[(plan_, "Plan")], orden=(dia, "Ascending"), color_medida="Color UEBD",
                colores=[(plan_, MEDIANOCHE)], subtitulo=SUB_PLAN)
    pag.grafico("equipo", IZQ, FILA2, AW, H2, "clusteredBarChart", "UEBD por CAEX", categoria=eq, valores=[(real, "UEBD")],
                orden=(real, "Ascending"), color_medida="Color UEBD",
                filtros=filtros_equipo(pag, "equipo", "Truck") + filtro_flota(pag, "equipo"))
    cod, cat = CF("Horas_Codigo_CAEX", "Codigo"), CF("Horas_Codigo_CAEX", "Categoria")
    hne = MF(MT, "Horas no efectivas")
    campos = [(cod, "Código"), (cat, "Categoría"), (hne, "Horas"), (MF(MT, "% del disponible"), "% del disponible")]
    sin_encabezado(pag.tabla("codigos", DER, FILA1, AW, H1, campos, anchos=[(cod, 290), (cat, 110), (hne, 76), (campos[3][0], 114)],
                             alineacion=[(hne, "Right"), (campos[3][0], "Right")], orden=[(hne, "Descending")], font=9, padding=3,
                             titulo="Horas de demora y reserva por código", filtros=filtro_categorias(pag, "codigos", CAT_NO_EFECTIVO),
                             autoajuste=True))
    tipo, ht = CF("Tipos UEBD", "Tipo"), MF(MT, "Horas tipo UEBD")
    sin_miles(pag.grafico("tipos", DER, FILA2, AW, H2, "clusteredBarChart", "Horas disponibles no efectivas por tipo", categoria=tipo,
                          valores=[(ht, "Horas")], orden=(ht, "Descending"), colores=[(ht, ROSA)]))
    return pag


def pagina_rend(oee_id):
    pag = Pagina("rend", "Rendimiento efectivo CAEX")
    encabezado_detalle(pag, "RENDIMIENTO EFECTIVO CAEX", "rend", "Rendimiento efectivo (t/h)", oee_id)
    dia, eq = CF("Dim_Tiempo", "Dia RD"), CF("Dim_Equipo", "Equipo")
    real, plan_ = MF(MT, "Rendimiento real"), MF(MT, "Rendimiento plan")
    sin_miles(pag.grafico("dia", IZQ, FILA1, AW, H1, "lineClusteredColumnComboChart", "Rendimiento efectivo por día (t/h)", categoria=dia,
                          valores=[(real, "Real")], valores2=[(plan_, "Plan")], orden=(dia, "Ascending"), color_medida="Color rendimiento",
                          colores=[(plan_, MEDIANOCHE)], subtitulo=SUB_PLAN))
    sin_miles(pag.grafico("equipo", IZQ, FILA2, AW, H2, "clusteredBarChart", "Rendimiento efectivo por CAEX (t/h)", categoria=eq,
                          valores=[(real, "Rendimiento")], orden=(real, "Ascending"), color_medida="Color rendimiento",
                          filtros=filtros_equipo(pag, "equipo", "Truck") + filtro_flota(pag, "equipo")))
    fc = MF(MT, "Factor de carga")
    sin_encabezado(pag.grafico("fc", DER, FILA1, AW, H1, "clusteredBarChart", "Factor de carga por CAEX (t por carga)", categoria=eq,
                               valores=[(fc, "Factor de carga")], orden=(fc, "Ascending"), color_medida="Color factor de carga",
                               filtros=filtros_equipo(pag, "fc", "Truck") + filtro_flota(pag, "fc")))
    comp, mn = CF("Componentes ciclo", "Componente"), MF(MT, "Ciclo componente (min)")
    pag.grafico("ciclo", DER, FILA2, AW, H2, "clusteredBarChart", "Tiempo de ciclo por componente (min por ciclo)", categoria=comp,
                valores=[(mn, "Minutos")], orden=(mn, "Descending"), colores=[(mn, CIELO)])
    return pag


def pagina_hn(oee_id):
    pag = Pagina("hn", "Horas nominales CAEX")
    encabezado_detalle(pag, "HORAS NOMINALES CAEX", "hn", "Horas nominales de la flota", oee_id)
    dia, eq = CF("Dim_Tiempo", "Dia RD"), CF("Dim_Equipo", "Equipo")
    fl, flp = MF(MT, "CAEX en flota"), MF(MT, "CAEX en flota plan")
    pag.grafico("dia", IZQ, FILA1, AW, H1, "lineClusteredColumnComboChart", "CAEX en flota por día (horas nominales / 24)", categoria=dia,
                valores=[(fl, "Real")], valores2=[(flp, "Plan")], orden=(dia, "Ascending"), color_medida="Color flota",
                colores=[(flp, MEDIANOCHE)], subtitulo=SUB_PLAN)
    hn = MF(MT, "HN real")
    sin_miles(pag.grafico("equipo", IZQ, FILA2, AW, H2, "clusteredBarChart", "Horas nominales por CAEX", categoria=eq,
                          valores=[(hn, "Horas nominales")], orden=(hn, "Ascending"), colores=[(hn, CIELO)],
                          filtros=filtros_equipo(pag, "equipo", "Truck") + filtro_flota(pag, "equipo")))
    campos = [(eq, "CAEX"), (MF(MT, "Días en flota"), "Días en flota"), (hn, "Horas nominales"), (MF(MT, "HD real"), "Horas disponibles"),
              (MF(MT, "HE real"), "Horas efectivas")]
    sin_encabezado(pag.tabla("tabla", DER, FILA1, AW, H1 + 8 + H2, campos,
                             anchos=[(eq, 120), (campos[1][0], 110), (hn, 130), (campos[3][0], 120), (campos[4][0], 110)],
                             alineacion=[(f, "Right") for f, _ in campos[1:]], orden=[(hn, "Ascending")], font=9, padding=3,
                             titulo="Horas por CAEX en el periodo",
                             filtros=filtros_equipo(pag, "tabla", "Truck") + filtro_flota(pag, "tabla")))
    return pag


def paginas():
    ids = {k: hid("oee", "pagina", k) for k in ("oee", "df", "uebd", "rend", "hn")}
    return [pagina_oee(ids), pagina_df(ids["oee"]), pagina_uebd(ids["oee"]), pagina_rend(ids["oee"]), pagina_hn(ids["oee"])]


def escribir_informe():
    if INFORME.exists():
        shutil.rmtree(INFORME)
    defn = INFORME / "definition"
    res = INFORME / "StaticResources" / "RegisteredResources"
    res.mkdir(parents=True, exist_ok=True)
    for r in (LOGO, LOGO_AREA):
        shutil.copyfile(RECURSOS / r, res / r)
    temas = INFORME / "StaticResources" / "SharedResources" / "BaseThemes"
    temas.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RECURSOS / f"BaseTheme_{TEMA_BASE}.json", temas / f"{TEMA_BASE}.json")
    version = {"visual": "2.11.0", "report": "3.4.0", "page": "2.3.1"}
    tema_propio = {"name": "Minera Demo RD", "dataColors": COLORES_TEMA, "background": "#FFFFFF", "foreground": PLOMO,
                   "tableAccent": MEDIANOCHE, "good": VERDE, "neutral": AMBAR, "bad": ROJO, "maximum": MEDIANOCHE, "center": CIELO_60,
                   "minimum": PLATA,
                   "textClasses": {"title": {"color": MEDIANOCHE, "fontFace": "Segoe UI Semibold"},
                                   "header": {"color": MEDIANOCHE, "fontFace": "Segoe UI Semibold"},
                                   "label": {"color": PLOMO, "fontFace": "Segoe UI"},
                                   "callout": {"color": MEDIANOCHE, "fontFace": "Segoe UI Semibold"}}}
    escribir_json(res / TEMA_PROPIO, tema_propio)
    informe = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {"baseTheme": {"name": TEMA_BASE, "reportVersionAtImport": version, "type": "SharedResources"},
                            "customTheme": {"name": TEMA_PROPIO, "reportVersionAtImport": version, "type": "RegisteredResources"}},
        "objects": {"section": [{"properties": {"verticalAlignment": {"expr": {"Literal": {"Value": "'Top'"}}}}}],
                    "outspacePane": [{"properties": {"expanded": {"expr": {"Literal": {"Value": "false"}}}}}]},
        "resourcePackages": [
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": LOGO, "path": LOGO, "type": "Image"}, {"name": LOGO_AREA, "path": LOGO_AREA, "type": "Image"},
                       {"name": TEMA_PROPIO, "path": TEMA_PROPIO, "type": "CustomTheme"}]},
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": TEMA_BASE, "path": f"BaseThemes/{TEMA_BASE}.json", "type": "BaseTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized", "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}}
    escribir_json(defn / "report.json", informe)
    escribir_json(defn / "version.json",
                  {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
                   "version": "2.0.0"})
    pags = paginas()
    pdir = defn / "pages"
    for pag in pags:
        base = pdir / pag.id
        escribir_json(base / "page.json", pag.json())
        for v in pag.visuales:
            escribir_json(base / "visuals" / v["name"] / "visual.json", v)
    escribir_json(pdir / "pages.json", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
                                        "pageOrder": [p.id for p in pags], "activePageName": pags[0].id})
    escribir_json(INFORME / "definition.pbir",
                  {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
                   "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NOMBRE}.SemanticModel"}}})
    escribir_json(INFORME / ".platform", plataforma("Report"))
    escribir_json(RAIZ / f"{NOMBRE}.pbip",
                  {"$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0",
                   "artifacts": [{"report": {"path": f"{NOMBRE}.Report"}}], "settings": {"enableAutoRecovery": True}})
    escribir(RAIZ / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    return pags


if __name__ == "__main__":
    n = escribir_modelo()
    pags = escribir_informe()
    print(f"Modelo: {len(TABLAS) + len(ESTATICAS) + 1} tablas, {n} medidas · informe: {len(pags)} páginas, "
          f"{sum(len(p.visuales) for p in pags)} visuales")
