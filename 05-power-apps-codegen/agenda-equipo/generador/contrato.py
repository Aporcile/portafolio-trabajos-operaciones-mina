# -*- coding: utf-8 -*-
"""Contrato de datos de la «Agenda del equipo».

Es la única fuente de verdad compartida por el generador de YAML (esta carpeta) y por el generador de datos
sintéticos (../datos_sinteticos/generar_datos.py): nombres de tablas, columnas, catálogos y listas de opciones.
Si cambia una columna, un estado o una persona, se cambia aquí y se vuelve a generar todo.
"""

# Fuentes de datos que la app espera encontrar con exactamente estos nombres y columnas.
# Las fechas se guardan como texto ISO (yyyy-mm-dd) y se convierten con DateValue() al mostrarlas.
TABLAS = {
    "Actividades": ["ID", "Area", "Actividad", "Descripcion", "Responsable", "Contraparte", "Prioridad", "Estado",
                    "FechaInicio", "FechaCompromiso", "FechaTermino", "StatusActual", "Bloqueo"],
    "Areas": ["Area", "Orden"],
    "Personas": ["Nombre", "NombreCompleto", "Iniciales", "Correo"],
    "PorRevisar": ["Tema", "Detalle", "Contraparte", "ResponsablePropuesto", "Decision", "Fecha"],
    "HighlightsLowlights": ["Tipo", "Fecha", "Tema", "Detalle", "Impacto", "Accion", "Responsable"],
}

# Columnas calculadas que la galería «Por área» agrega con AddColumns (no existen en ninguna tabla).
COLUMNAS_CALCULADAS = ["Acts", "Total", "nPH", "nEC", "nER", "nBQ", "nTE"]

# Flujo de estados: (código corto usado en nombres de controles, texto guardado en la columna Estado).
ESTADOS = [("PH", "Por hacer"), ("EC", "En curso"), ("ER", "En revisión"), ("BQ", "Bloqueada"), ("TE", "Terminada")]
PRIORIDADES = ["Alta", "Media", "Baja"]
DECISIONES = ["Por decidir", "Aprobado", "Descartado", "Pospuesto"]
TIPOS_HL = ["Highlight", "Lowlight"]

# Áreas genéricas, en el orden en que se muestran en el tablero (columna Orden).
AREAS = ["Planificación", "Operaciones", "Mantención", "Procesos", "Seguridad"]

# Integrantes del equipo. La vista «Por persona» muestra a las tres primeras y una columna «Sin responsable».
DOMINIO_CORREO = "minera-demo.example"
PERSONAS = [
    {"Nombre": f"Persona Demo {i:02d}", "NombreCompleto": f"Persona Demo {i:02d}", "Iniciales": f"P{i}",
     "Correo": f"persona.demo{i:02d}@{DOMINIO_CORREO}"}
    for i in range(1, 4)
]

# Textos fijos del filtro de responsable (los usan las fórmulas de todas las vistas).
FILTRO_TODOS = "Todos los responsables"
FILTRO_SIN_RESPONSABLE = "Sin responsable"


def lista_pf(valores):
    """Lista de textos en sintaxis Power Fx: ["a", "b"]."""
    return "[" + ", ".join('"%s"' % v for v in valores) + "]"
