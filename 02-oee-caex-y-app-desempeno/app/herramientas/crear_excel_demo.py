# -*- coding: utf-8 -*-
"""Crea los Excel de datos de RD Terreno (uno por tabla) a partir de los CSV sintéticos de `datos_sinteticos/app/`.

Uso:  python crear_excel_demo.py [--salida CARPETA]
  Lee  <raíz del proyecto>/datos_sinteticos/app/<TABLA>.csv  (se generan con datos_sinteticos/generar_datos.py)
  Escribe <TABLA>.xlsx en CARPETA (por defecto app/salida_excel/, que no se versiona).
  Requiere openpyxl.

Reglas que la app da por hechas:
  - El nombre de la tabla de Excel es el nombre del origen de datos en Power Apps.
  - Fechas como TEXTO aaaa-mm-dd (y "aaaa-mm-dd hh:mm"): columna con formato "@".
  - Abierto = "Sí" / "No" (texto, no booleano).
  - Cada tabla trae al menos una fila para que Power Apps reconozca los tipos.
"""
import argparse
import csv
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.table import Table, TableStyleInfo

RAIZ = Path(__file__).resolve().parents[2]
ENTRADA = RAIZ / "datos_sinteticos" / "app"
SALIDA = Path(__file__).resolve().parent.parent / "salida_excel"
FILAS_CON_FORMATO = 1000  # filas con formato texto bajo la tabla; las nuevas filas heredan el formato de la columna

# (columna, tipo, ancho)  tipo: "t" texto, "n" número
ESQUEMAS = {
    "RD_Compromisos": [
        ("ID", "n", 6), ("Titulo", "t", 50), ("ResponsableNombre", "t", 20),
        ("FechaLimite", "t", 12), ("Estado", "t", 13), ("Abierto", "t", 9),
        ("FechaCreacion", "t", 13), ("FechaCierre", "t", 17), ("Comentario", "t", 40),
        ("EvidenciaUrl", "t", 30), ("Grupo", "t", 12), ("Prioridad", "t", 10),
        ("Origen", "t", 10), ("ResponsableEmail", "t", 20), ("SesionIdLocal", "t", 12),
        ("IdLocal", "t", 12),
    ],
    "RD_RevisionCompromisos": [
        ("FechaRevision", "t", 17), ("CompromisoId", "n", 8), ("Compromiso", "t", 50),
        ("EstadoAnterior", "t", 14), ("EstadoNuevo", "t", 14), ("Comentario", "t", 40),
        ("Grupo", "t", 12), ("SesionIdLocal", "t", 12), ("Clave", "t", 14),
    ],
    "RD_Sesiones": [
        ("Fecha", "t", 12), ("Titulo", "t", 26), ("Grupo", "t", 12), ("Area", "t", 16),
        ("Estado", "t", 9), ("HoraInicio", "t", 17), ("HoraTermino", "t", 17),
        ("MinutosDuracion", "n", 9), ("MinutosExceso", "n", 9), ("Asistentes", "n", 9),
        ("Animo1", "n", 7), ("Animo2", "n", 7), ("Animo3", "n", 7), ("Animo4", "n", 7),
        ("Animo5", "n", 7), ("TemaSeguridad", "t", 30), ("TiemposBloques", "t", 20),
        ("CompromisosNuevos", "n", 9), ("IdeasPresentadas", "n", 9), ("LiderNombre", "t", 20),
        ("LiderEmail", "t", 20), ("Motivo", "t", 12), ("Observaciones", "t", 20),
        ("RutaActa", "t", 12), ("IdLocal", "t", 12),
    ],
    "RD_Destacados": [
        ("FechaReunion", "t", 12), ("Tipo", "t", 11), ("Orden", "n", 7), ("Texto", "t", 60),
        ("Grupo", "t", 12), ("SesionIdLocal", "t", 12), ("IdLocal", "t", 12),
    ],
    "RD_KPI": [
        ("Periodo", "t", 12), ("Titulo", "t", 14), ("Grupo", "t", 10), ("Json", "t", 80),
    ],
    "RD_PlanSemanal": [
        ("SemanaInicio", "t", 12), ("Grupo", "t", 12), ("Meteorologia", "t", 40),
        ("Actividades", "t", 30), ("Tronaduras", "t", 20), ("Posicionamiento", "t", 20),
        ("Riesgos", "t", 30),
    ],
    # Preparación de la reunión (modo editor de la app). Una fila por reunión:
    # Clave = fecha de la reunión (aaaa-mm-dd), Json = tema de seguridad, estados de compromisos y destacados.
    # La escribe y la lee solo la app; nadie la edita a mano.
    "RD_Preparacion": [
        ("Clave", "t", 14), ("Json", "t", 80), ("Actualizado", "t", 17), ("Autor", "t", 24),
    ],
    # Convocados a la reunión: la lista se mantiene a mano. La minuta se envía a todos los activos, hayan asistido o no.
    # Correo es el identificador en Power Apps: no puede quedar vacío ni repetirse.
    "RD_Participantes": [
        ("Nombre", "t", 30), ("Correo", "t", 34), ("Cargo", "t", 24), ("Activo", "t", 8), ("Area", "t", 22),
    ],
    # Asistencia: una fila por reunión, la escribe la app al sincronizar.
    # Json = [{Nombre, Correo, Tipo (Convocado/Invitado), Presente}]. Una sola fila para no alargar la sincronización.
    "RD_Asistencia": [
        ("Fecha", "t", 12), ("SesionIdLocal", "t", 38), ("Convocados", "n", 11), ("Presentes", "n", 10),
        ("Invitados", "n", 10), ("Ausentes", "t", 40), ("Json", "t", 80), ("LiderEmail", "t", 30),
    ],
}

HOJAS = {
    "RD_Compromisos": "Compromisos", "RD_RevisionCompromisos": "Revisiones",
    "RD_Sesiones": "Sesiones", "RD_Destacados": "Destacados",
    "RD_KPI": "KPI", "RD_PlanSemanal": "PlanSemanal", "RD_Preparacion": "Preparacion",
    "RD_Participantes": "Participantes", "RD_Asistencia": "Asistencia",
}


def numero(texto):
    """Número de una celda CSV: entero si lo parece, decimal si no, 0 si viene vacía."""
    texto = (texto or "").strip()
    if texto == "":
        return 0
    try:
        return int(texto)
    except ValueError:
        return float(texto)


def leer_filas(nombre, entrada):
    ruta = entrada / f"{nombre}.csv"
    if not ruta.exists():
        sys.exit(f"Falta {ruta}: genera los CSV con datos_sinteticos/generar_datos.py")
    with open(ruta, encoding="utf-8-sig", newline="") as fh:
        lector = csv.DictReader(fh)
        esperadas = [c for c, _, _ in ESQUEMAS[nombre]]
        if lector.fieldnames != esperadas:
            sys.exit(f"{ruta.name}: columnas {lector.fieldnames} distintas del esquema {esperadas}")
        filas = list(lector)
    if not filas:
        sys.exit(f"{ruta.name} no tiene filas: Power Apps necesita al menos una para reconocer los tipos")
    return filas


def crear(nombre, filas, salida):
    cols = ESQUEMAS[nombre]
    wb = Workbook()
    ws = wb.active
    ws.title = HOJAS[nombre]
    ws.append([c for c, _, _ in cols])
    for f in filas:
        ws.append([numero(f[c]) if t == "n" else f[c] for c, t, _ in cols])
    for i, (c, t, ancho) in enumerate(cols, start=1):
        letra = ws.cell(row=1, column=i).column_letter
        ws.column_dimensions[letra].width = ancho
        if t == "t":
            for r in range(2, FILAS_CON_FORMATO + 2):
                celda = ws.cell(row=r, column=i)
                celda.number_format = "@"
                if celda.value is not None:
                    celda.value = str(celda.value)
                    celda.alignment = Alignment(vertical="top", wrap_text=ancho >= 40)
    ultima = ws.cell(row=1, column=len(cols)).column_letter
    tabla = Table(displayName=nombre, ref=f"A1:{ultima}{len(filas) + 1}")
    tabla.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    ws.add_table(tabla)
    ws.freeze_panes = "A2"
    for celda in ws[1]:
        celda.font = Font(bold=True, color="FFFFFF")
    salida.mkdir(parents=True, exist_ok=True)
    ruta = salida / f"{nombre}.xlsx"
    wb.save(ruta)
    return ruta, len(filas)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--salida", type=Path, default=SALIDA, help="carpeta donde se escriben los .xlsx")
    ap.add_argument("--entrada", type=Path, default=ENTRADA, help="carpeta con los CSV (una por tabla)")
    ap.add_argument("--solo", nargs="*", help="crea únicamente estas tablas (por ejemplo RD_Preparacion)")
    a = ap.parse_args()
    for nombre in (a.solo or ESQUEMAS):
        ruta, n = crear(nombre, leer_filas(nombre, a.entrada), a.salida)
        print(f"{ruta.name}: {n} filas")


if __name__ == "__main__":
    main()
