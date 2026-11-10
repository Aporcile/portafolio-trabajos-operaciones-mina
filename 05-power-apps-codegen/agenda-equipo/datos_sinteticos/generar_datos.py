# -*- coding: utf-8 -*-
"""Genera los CSV sintéticos de la «Agenda del equipo» de la empresa ficticia Minera Demo.

Los nombres de tablas y columnas salen de generador/contrato.py (el mismo contrato que usa el generador de YAML), de modo
que los CSV calzan con lo que espera la app. Toda cifra, fecha y texto es inventado y reproducible: la semilla viene de
tools/sinteticos.py (en la raíz del repositorio). Periodo: desde 2025-03-03 por 90 días (hasta 2025-05-31).

Salida (esta misma carpeta, UTF-8 con BOM para que Excel respete las tildes):
  actividades.csv          tabla Actividades            (la lista principal; 60-120 filas)
  areas.csv                tabla Areas                  (catálogo y orden de las áreas)
  personas.csv             tabla Personas               (integrantes del equipo)
  por_revisar.csv          tabla PorRevisar             (temas por decidir y ya resueltos)
  highlights_lowlights.csv tabla HighlightsLowlights    (hitos buenos y malos del periodo)
  estados.csv              catálogo de estados          (referencia; la app los tiene fijos en sus fórmulas)
  historial_estados.csv    bitácora de cambios de estado de cada actividad (para auditoría; la app no la consulta)

Uso:  python generar_datos.py
"""
import csv
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True                        # no deja __pycache__ en generador/ ni en tools/

AQUI = Path(__file__).resolve().parent
RAIZ_REPO = AQUI.parents[2]
sys.path.insert(0, str(RAIZ_REPO / "tools"))          # sinteticos.py
sys.path.insert(0, str(AQUI.parent / "generador"))    # contrato.py, ids.py, comun.py

import contrato                                       # noqa: E402
from comun import ESTADOS as ESTADOS_UI               # noqa: E402
from ids import ID_REGEX, id_actividad                # noqa: E402
from sinteticos import dias, personas as personas_demo, rng  # noqa: E402

INICIO = date(2025, 3, 3)
N_DIAS = 90
FECHAS = dias(INICIO, N_DIAS)
ULTIMO = N_DIAS - 1                  # índice del último día del periodo (2025-05-31)
N_ACTIVIDADES = 96
YY = f"{INICIO.year % 100:02d}"

VERBOS = ["Actualizar", "Revisar", "Definir", "Preparar", "Documentar", "Validar", "Consolidar", "Diseñar", "Coordinar", "Estandarizar"]
OBJETOS = {
    "Planificación": ["plan semanal de producción", "programa de corto plazo", "calendario de hitos del trimestre", "matriz de prioridades del área",
                      "informe de cumplimiento del plan", "carta Gantt de proyectos", "plantilla de reunión de planificación",
                      "listado de requerimientos de insumos", "modelo de pronóstico simple", "bitácora de decisiones",
                      "propuesta de metas del próximo periodo", "resumen ejecutivo mensual"],
    "Operaciones": ["pauta de cambio de turno", "reporte diario de operación", "estándar de asignación de equipos", "checklist de inicio de turno",
                    "tablero de indicadores de turno", "registro de demoras operacionales", "procedimiento de cierre de turno",
                    "plan de capacitación de operadores", "análisis de causas de detenciones", "ronda de terreno semanal",
                    "matriz de turnos y reemplazos", "revisión de rutas de transporte"],
    "Mantención": ["plan de mantención preventiva", "backlog de órdenes de trabajo", "inventario de repuestos críticos", "pauta de inspección de equipos",
                   "análisis de fallas repetitivas", "programa de paradas planificadas", "indicador de cumplimiento de mantención",
                   "registro de lubricantes", "procedimiento de bloqueo y etiquetado", "contrato de servicios externos",
                   "lista de verificación de taller", "estándar de informes de falla"],
    "Procesos": ["diagrama de flujo del proceso", "balance de materiales simplificado", "protocolo de muestreo", "análisis de variabilidad del proceso",
                 "instructivo de control de calidad", "tablero de eficiencia de proceso", "estudio de cuellos de botella",
                 "estándar de registro de parámetros", "mapa de indicadores del proceso", "propuesta de mejora continua",
                 "revisión de puntos de ajuste", "informe de desempeño mensual"],
    "Seguridad": ["matriz de riesgos del área", "programa de inspecciones", "plan de charlas de seguridad", "registro de incidentes y acciones",
                  "procedimiento de trabajo seguro", "simulacro de emergencia", "auditoría de cumplimiento interno",
                  "revisión de equipos de protección", "indicadores de seguridad del equipo", "plan de acción de hallazgos",
                  "inducción para nuevos integrantes", "señalética del área"],
}
CALIFICADORES = ["(primera etapa)", "(segunda etapa)", "(versión ampliada)", "(para el equipo)", "(seguimiento)", "(propuesta)", "(revisión final)", "(piloto)"]
OBJETOS_SIN_AREA = ["solicitud pendiente de clasificar", "tema transversal del equipo", "propuesta recibida sin área asignada", "pendiente de la reunión semanal"]
CONTRAPARTES = ["Contratista Demo", "Proveedor Demo", "Equipo de Operaciones", "Equipo de Mantención", "Jefatura de Área", "Auditoría interna",
                "Persona Demo 12", "Persona Demo 15", ""]
DESCRIPCIONES = ["Alcance: {o}. Entregable acordado con la contraparte.", "Incluye levantamiento, borrador y validación de {o}.",
                 "Trabajo de seguimiento sobre {o}; se reporta avance en la reunión semanal.",
                 "Definir responsables, plazos y criterio de cierre para {o}.", "Mejora incremental de {o} con revisión del equipo."]
STATUS = {
    "Por hacer": ["", "", "Pendiente de iniciar", "Agendar reunión de arranque", "Esperando asignar fecha de inicio"],
    "En curso": ["Avance en desarrollo", "Borrador en elaboración", "Recopilando información de base", "En revisión interna de contenidos", ""],
    "En revisión": ["Enviado a la contraparte para comentarios", "A la espera de validación", "Versión 1 lista para revisión", "Comentarios en proceso de incorporación"],
    "Bloqueada": ["", "Detenida hasta resolver la dependencia", "Se retoma cuando se levante el bloqueo", "Avance parcial; falta una entrega externa"],
    "Terminada": ["Entregado y cerrado", "Documento publicado en la carpeta del equipo", "Implementado y en uso", "Cerrado sin pendientes", "Validado por la contraparte"],
}
BLOQUEOS = ["Depende de la entrega de la contraparte", "Falta acceso a la fuente de información", "Pendiente aprobación de presupuesto",
            "Sin disponibilidad del equipo asignado", "Esperando definición de alcance", "Requiere decisión de la jefatura"]

HIGHLIGHTS = [
    ("Plan semanal cumplido sin desvíos", "Todas las actividades comprometidas para la semana se cerraron en la fecha acordada.",
     "Mayor previsibilidad para la planificación del periodo.", "Mantener la revisión de inicio de semana."),
    ("Nuevo formato de reporte de turno adoptado", "El equipo comenzó a usar la plantilla simplificada de reporte.",
     "Menos tiempo de preparación y datos más comparables.", "Evaluar ajustes tras algunas semanas de uso."),
    ("Capacitación en el tablero de seguimiento completada", "Todos los integrantes participaron y resolvieron sus dudas en la sesión práctica.",
     "Mejor uso del tablero en las reuniones.", ""),
    ("Coordinación efectiva con contratistas", "Se acordó un canal único de consultas y una pauta de entregas.",
     "Menos reprocesos por información dispersa.", "Replicar la pauta con otros proveedores."),
    ("Inspecciones del área sin hallazgos críticos", "Las inspecciones programadas se realizaron y quedaron registradas.",
     "", "Programar la siguiente ronda."),
    ("Backlog de órdenes de trabajo ordenado por prioridad", "Se depuró el listado y se reasignaron las órdenes sin responsable.",
     "Foco en lo prioritario y menos pendientes antiguos.", "Revisar el backlog cada semana."),
    ("Estándar de registro de parámetros aprobado", "La contraparte validó el estándar propuesto por el equipo.",
     "Registros homogéneos entre turnos.", "Difundir el estándar y recoger comentarios."),
    ("Reunión de planificación más breve y enfocada", "Con agenda fija y acuerdos escritos, la reunión se resolvió sin extenderse.",
     "", ""),
    ("Propuesta de mejora aceptada por la jefatura", "La propuesta de mejora continua fue aprobada para su implementación.",
     "Se habilita trabajo conjunto entre áreas.", "Armar el plan de implementación."),
    ("Simulacro de emergencia realizado según lo planificado", "Participó todo el equipo y se levantaron oportunidades de mejora.",
     "Mejor preparación ante contingencias.", "Cerrar las oportunidades de mejora levantadas."),
    ("Documentación del proceso actualizada y publicada", "Los instructivos vigentes quedaron en la carpeta compartida del equipo.",
     "Una única versión de referencia.", ""),
    ("Integración exitosa de una nueva persona al equipo", "Completó la inducción y ya participa en las actividades del tablero.",
     "Más capacidad disponible para el periodo.", "Asignar su primera actividad con seguimiento."),
]
LOWLIGHTS = [
    ("Retraso en la entrega de insumos de la contraparte", "El proveedor reprogramó la entrega y el equipo debió ajustar el plan.",
     "Varias actividades quedaron a la espera.", "Acordar fechas firmes y un contacto de respaldo."),
    ("Informe mensual publicado con observaciones", "Se detectaron datos inconsistentes después de la publicación.",
     "Se debió reemitir el informe.", "Agregar una revisión cruzada antes de publicar."),
    ("Baja asistencia a la capacitación", "Varias personas no pudieron conectarse por coincidencia con otras tareas.",
     "Conocimiento desigual sobre la herramienta.", "Repetir la sesión en otro horario."),
    ("Dependencia de una sola persona en una actividad crítica", "El conocimiento del procedimiento no está documentado.",
     "Riesgo de continuidad si la persona no está disponible.", "Documentar el procedimiento y definir un respaldo."),
    ("Reprogramación de la auditoría interna", "La auditoría se movió por falta de evidencia lista.",
     "", "Reunir la evidencia faltante."),
    ("Datos incompletos en el registro de demoras", "Algunos turnos no completaron el registro.",
     "Análisis de causas menos confiable.", "Recordar el registro en el cambio de turno."),
    ("Reuniones sin acta ni acuerdos registrados", "Se repitieron temas ya conversados por falta de registro.",
     "Pérdida de tiempo y acuerdos ambiguos.", "Usar una plantilla única de acta."),
    ("Acceso pendiente a una fuente de información", "El permiso solicitado sigue en trámite.",
     "Una actividad quedó detenida.", "Escalar la solicitud a la jefatura."),
    ("Solicitudes urgentes alteraron el plan semanal", "Llegaron pedidos no planificados que desplazaron actividades comprometidas.",
     "Se movieron fechas de entrega.", "Definir un cupo semanal para urgencias."),
    ("Inspección postergada por falta de disponibilidad", "El equipo asignado estaba cubriendo otra prioridad.",
     "", "Reprogramar con fecha confirmada."),
    ("Estándar sin validar por la contraparte", "El borrador sigue sin comentarios.", "No se puede publicar la versión final.",
     "Pedir una fecha de respuesta."),
    ("Desfase en el cierre de acciones de seguridad", "Varias acciones superaron la fecha comprometida.",
     "", "Revisar el avance en la reunión semanal."),
]
TEMAS_REVISAR = [
    ("Evaluar plantilla única de acta de reunión", "Unificar el formato de actas para todos los equipos del área."),
    ("Definir criterio común de prioridad", "Acordar qué significa prioridad alta, media y baja en el tablero."),
    ("Incorporar revisión cruzada en los reportes", "Una segunda persona revisa antes de publicar."),
    ("Proponer ventana fija para reuniones de coordinación", "Reducir interrupciones concentrando las reuniones."),
    ("Centralizar el listado de contrapartes", "Un solo listado con contacto y tema de cada contraparte."),
    ("Automatizar el resumen semanal del equipo", "Generar el resumen desde el tablero en lugar de armarlo a mano."),
    ("Revisar la matriz de responsabilidades", "Verificar que cada actividad tenga una sola persona responsable."),
    ("Agregar campo de riesgo a las actividades", "Permitiría priorizar mejor las actividades en curso."),
    ("Reducir pasos del flujo de aprobación", "Eliminar aprobaciones intermedias que no agregan control."),
    ("Crear glosario de términos del área", "Evitar malentendidos con siglas y nombres de documentos."),
    ("Estandarizar nombres de archivos compartidos", "Definir un patrón simple de nombres y versiones."),
    ("Piloto de reunión de cierre quincenal", "Revisar logros y pendientes cada dos semanas."),
    ("Ordenar la carpeta de documentos del equipo", "Depurar duplicados y definir una estructura única."),
    ("Medir tiempos de respuesta a solicitudes", "Entender cuánto tardan las solicitudes más frecuentes."),
    ("Publicar un calendario compartido de hitos", "Visibilizar fechas clave para todo el equipo."),
    ("Revisar permisos de acceso del equipo", "Confirmar quién necesita acceso a qué carpeta o herramienta."),
]


def iso(i):
    """Fecha ISO del día i del periodo (0 = 2025-03-03)."""
    return FECHAS[i].isoformat()


def paso(r, d, prev, nuevo, eventos, rango=(1, 12)):
    """Agrega una transición de estado unos días después de la anterior, sin salirse del periodo."""
    d = min(d + r.randint(*rango), ULTIMO)
    eventos.append((d, prev, nuevo))
    return d


def ciclo_de_vida(r, d0, final):
    """Transiciones [(día, estado_anterior, estado_nuevo)] coherentes con el estado final."""
    ev = [(d0, "", "Por hacer")]
    if final == "Por hacer":
        return ev
    d = paso(r, d0, "Por hacer", "En curso", ev)
    previo = "En curso"
    if final != "En curso" and r.random() < 0.15:          # un bloqueo que se resuelve antes del estado final
        d = paso(r, d, "En curso", "Bloqueada", ev)
        d = paso(r, d, "Bloqueada", "En curso", ev)
    if final == "En revisión":
        paso(r, d, previo, "En revisión", ev)
    elif final == "Bloqueada":
        paso(r, d, previo, "Bloqueada", ev)
    elif final == "Terminada":
        if r.random() < 0.6:
            d = paso(r, d, previo, "En revisión", ev)
            previo = "En revisión"
        paso(r, d, previo, "Terminada", ev)
    return ev


def construir_actividades():
    r = rng("agenda_actividades")
    usados, borradores, veces = set(), [], Counter()
    for _ in range(N_ACTIVIDADES):
        area = "" if r.random() < 0.04 else r.choices(contrato.AREAS, weights=[1.0, 1.2, 1.3, 1.0, 0.8])[0]
        objetos = OBJETOS[area] if area else OBJETOS_SIN_AREA
        # Reparte los objetos por turnos: el repetido lleva un calificador para que el nombre siga siendo único y distinto
        minimo = min(veces[(area, o)] for o in objetos)
        objeto = r.choice([o for o in objetos if veces[(area, o)] == minimo])
        repetido = veces[(area, objeto)]
        veces[(area, objeto)] += 1
        while True:
            nombre = f"{r.choice(VERBOS)} {objeto}" + (f" {CALIFICADORES[(repetido - 1) % len(CALIFICADORES)]}" if repetido else "")
            if nombre not in usados:
                usados.add(nombre)
                break
        final = r.choices([e for _, e in contrato.ESTADOS], weights=[16, 28, 14, 13, 29])[0]
        d0 = r.randint(0, 85 if final == "Por hacer" else 78)
        borradores.append({"area": area, "objeto": objeto, "nombre": nombre, "final": final, "d0": d0})
    # IDs correlativos por fecha de inicio (como los asigna la app)
    borradores.sort(key=lambda b: (b["d0"], b["nombre"]))

    nombres_personas = [p["Nombre"] for p in contrato.PERSONAS]
    filas, historial = [], []
    for n, b in enumerate(borradores, 1):
        final = b["final"]
        resp = r.choices(nombres_personas + [""], weights=[29, 29, 29, 13 if final != "Terminada" else 2])[0]
        eventos = ciclo_de_vida(r, b["d0"], final)
        compromiso = iso(min(b["d0"] + r.randint(7, 45), ULTIMO)) if r.random() < 0.55 else ""
        status = r.choice(STATUS[final])
        id_ = id_actividad(n, YY)
        filas.append({
            "ID": id_, "Area": b["area"], "Actividad": b["nombre"],
            "Descripcion": r.choice(DESCRIPCIONES).format(o=b["objeto"]), "Responsable": resp,
            "Contraparte": r.choice(CONTRAPARTES),
            "Prioridad": r.choices(contrato.PRIORIDADES + [""], weights=[25, 45, 20, 10])[0],
            "Estado": final, "FechaInicio": iso(b["d0"]), "FechaCompromiso": compromiso,
            "FechaTermino": iso(eventos[-1][0]) if final == "Terminada" else "",
            "StatusActual": status, "Bloqueo": r.choice(BLOQUEOS) if final == "Bloqueada" else "",
        })
        for d, ant, nuevo in eventos:
            historial.append({"ID": id_, "Fecha": iso(d), "EstadoAnterior": ant, "EstadoNuevo": nuevo,
                              "Usuario": resp or nombres_personas[0]})
    historial.sort(key=lambda h: (h["Fecha"], h["ID"]))
    return filas, historial


def construir_highlights():
    r = rng("agenda_highlights")
    nombres = [p["Nombre"] for p in contrato.PERSONAS]
    filas = []
    for tipo, catalogo in (("Highlight", HIGHLIGHTS), ("Lowlight", LOWLIGHTS)):
        for tema, detalle, impacto, accion in catalogo:
            filas.append({"Tipo": tipo, "Fecha": iso(r.randint(0, ULTIMO)), "Tema": tema,
                          "Detalle": "" if r.random() < 0.1 else detalle, "Impacto": impacto, "Accion": accion,
                          "Responsable": r.choices(nombres + [""], weights=[3, 3, 3, 1])[0]})
    filas.sort(key=lambda f: (f["Fecha"], f["Tipo"]))
    return filas


def construir_por_revisar():
    r = rng("agenda_por_revisar")
    nombres = [p["Nombre"] for p in contrato.PERSONAS]
    filas = []
    for tema, detalle in TEMAS_REVISAR:
        filas.append({"Tema": tema, "Detalle": detalle, "Contraparte": r.choice(CONTRAPARTES),
                      "ResponsablePropuesto": r.choices(nombres + [""], weights=[3, 3, 3, 1])[0],
                      "Decision": r.choices(contrato.DECISIONES, weights=[50, 20, 15, 15])[0], "Fecha": iso(r.randint(0, ULTIMO))})
    filas.sort(key=lambda f: f["Fecha"])
    return filas


def rgba_a_hex(rgba):
    r, g, b = (int(v) for v in re.findall(r"\d+", rgba)[:3])
    return f"#{r:02X}{g:02X}{b:02X}"


def escribir_csv(nombre, columnas, filas):
    with open(AQUI / nombre, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columnas, lineterminator="\n")
        w.writeheader()
        w.writerows(filas)
    print(f"{nombre}: {len(filas)} filas")


def validar(actividades, historial, highlights, por_revisar):
    """Invariantes que la app y la bitácora esperan; falla si alguno no se cumple."""
    inicio, fin = FECHAS[0].isoformat(), FECHAS[-1].isoformat()
    estados = {e for _, e in contrato.ESTADOS}
    assert 60 <= len(actividades) <= 120, "se piden entre 60 y 120 actividades"
    assert len({a["ID"] for a in actividades}) == len(actividades), "IDs repetidos"
    ultimo_estado = {}
    for h in historial:
        ultimo_estado[h["ID"]] = h["EstadoNuevo"]
    for a in actividades:
        assert re.fullmatch(ID_REGEX, a["ID"]), a["ID"]
        assert a["Estado"] in estados and ultimo_estado[a["ID"]] == a["Estado"], a["ID"]
        assert (a["Estado"] == "Terminada") == bool(a["FechaTermino"]), a["ID"]
        assert (a["Estado"] != "Bloqueada") or a["Bloqueo"], a["ID"]
        for col in ("FechaInicio", "FechaCompromiso", "FechaTermino"):
            assert not a[col] or inicio <= a[col] <= fin, (a["ID"], col)
        assert not a["FechaTermino"] or a["FechaTermino"] >= a["FechaInicio"], a["ID"]
    for fila in historial + highlights + por_revisar:
        assert inicio <= fila["Fecha"] <= fin, fila


def main():
    # Las personas del contrato deben coincidir con las de tools/sinteticos.py
    assert [p["nombre"] for p in personas_demo(len(contrato.PERSONAS))] == [p["Nombre"] for p in contrato.PERSONAS]
    actividades, historial = construir_actividades()
    highlights = construir_highlights()
    por_revisar = construir_por_revisar()
    validar(actividades, historial, highlights, por_revisar)

    escribir_csv("actividades.csv", contrato.TABLAS["Actividades"], actividades)
    escribir_csv("areas.csv", contrato.TABLAS["Areas"], [{"Area": a, "Orden": i} for i, a in enumerate(contrato.AREAS, 1)])
    escribir_csv("personas.csv", contrato.TABLAS["Personas"], contrato.PERSONAS)
    escribir_csv("por_revisar.csv", contrato.TABLAS["PorRevisar"], por_revisar)
    escribir_csv("highlights_lowlights.csv", contrato.TABLAS["HighlightsLowlights"], highlights)
    escribir_csv("estados.csv", ["Codigo", "Estado", "Orden", "ColorHex"],
                 [{"Codigo": c, "Estado": e, "Orden": i, "ColorHex": rgba_a_hex(col)} for i, (c, e, col) in enumerate(ESTADOS_UI, 1)])
    escribir_csv("historial_estados.csv", ["ID", "Fecha", "EstadoAnterior", "EstadoNuevo", "Usuario"], historial)

    por_estado = {e: sum(a["Estado"] == e for a in actividades) for _, e in contrato.ESTADOS}
    print("Actividades por estado:", por_estado)
    print(f"Periodo: {FECHAS[0]} a {FECHAS[-1]} ({N_DIAS} días)")


if __name__ == "__main__":
    main()
