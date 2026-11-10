# -*- coding: utf-8 -*-
"""Genera la parte de INFORME (PBIR) del proyecto Gobernanza_uso_reportes.

Escribe el .pbip, la carpeta .Report (6 páginas, visuales y tema) y los archivos .platform / definition.pbism que
acompañan al modelo semántico. El modelo (TMDL) lo genera generar_modelo.ps1; este script no lo toca.

Uso:
    python generar_reporte.py [carpeta_del_proyecto] [--solo-validar] [--esquemas CARPETA]

Si la biblioteca jsonschema está instalada y hay esquemas (python extraer_esquemas.py), valida cada archivo contra
los esquemas oficiales de Power BI Desktop. Sin ellos, solo escribe. Con --solo-validar valida lo que generaría y
no escribe nada (para validar lo que hay en disco está validar_disco.py).

La escritura es transaccional: la carpeta definition completa se prepara aparte y solo al final reemplaza a la
actual; si algún paso falla, se repone la anterior.
"""
import json
import os
import pathlib
import re
import shutil
import stat
import sys
import uuid

# La consola de Windows usa cp1252: sin esto, imprimir un texto con tildes o "⚠" puede romper el script
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

USO = "Uso: python generar_reporte.py [carpeta_del_proyecto] [--solo-validar] [--esquemas CARPETA]"
PROYECTO = "Gobernanza_uso_reportes"
AQUI = pathlib.Path(__file__).resolve().parent


def leer_argumentos(argv):
    posicionales, solo_validar, esquemas = [], False, AQUI / "esquemas_pbir"
    it = iter(argv)
    for a in it:
        if a == "--solo-validar":
            solo_validar = True
        elif a == "--esquemas":
            esquemas = pathlib.Path(next(it, ""))
        elif a.startswith("-"):
            # Una opción mal escrita no debe terminar en una escritura que nadie pidió
            sys.exit(f"Opción desconocida: {a}.\n{USO}")
        else:
            posicionales.append(a)
    if len(posicionales) > 1:
        sys.exit(f"Sobran argumentos: {posicionales}. Si la ruta tiene espacios, va entre comillas.\n{USO}")
    raiz = pathlib.Path(os.path.abspath(posicionales[0] if posicionales else AQUI.parent))
    return raiz, solo_validar, esquemas


RAIZ, SOLO_VALIDAR, ESQUEMAS = leer_argumentos(sys.argv[1:])
if not (RAIZ / f"{PROYECTO}.SemanticModel").is_dir():
    sys.exit(f"{RAIZ} no parece la carpeta del proyecto (no tiene {PROYECTO}.SemanticModel). No se escribió nada.\n{USO}")

# Versiones de esquema que escribe Power BI Desktop (se extraen de la propia instalación)
S = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
SCH_VISUAL = f"{S}/visualContainer/2.14.0/schema.json"
SCH_PAGE = f"{S}/page/2.1.0/schema.json"
SCH_PAGES = f"{S}/pagesMetadata/1.1.0/schema.json"
SCH_REPORT = f"{S}/report/3.3.0/schema.json"
SCH_VERSION = f"{S}/versionMetadata/1.0.0/schema.json"
TEMA = "reportThemeSchema"   # esquema de temas de Desktop (sin $id; ver validador())
VERSION_TEMA = {"visual": "2.14.0", "page": "2.1.0", "report": "3.3.0"}

# Paleta de Minera Demo: el azul medianoche es para fondos y paneles; el azul cielo y el violeta son acentos. Diseño
# oscuro: la página más oscura que los paneles, las cifras en blanco y los textos en gris azulado claro. Rojo, verde
# y ámbar se reservan para semáforos y alertas. Contraste sobre el panel: blanco 14:1, TEXTO 10:1, TEXTO_TENUE 6,5:1,
# ROJO 6:1; el azul cielo y el violeta (3:1) solo van en barras, líneas y cifras grandes.
MEDIANOCHE, AZUL, VIOLETA = "#1B2A41", "#4F9DDE", "#7B61C9"
FONDO, OSCURO, BORDE, FILA_ALTERNA = "#0F1827", "#142033", "#33476B", "#22344F"
BLANCO, TEXTO, TEXTO_TENUE = "#FFFFFF", "#D5DEEA", "#9FB0C8"
ROJO = "#FF8A80"             # "sin uso" y avisos
VERDE, AMBAR = "#5FD39A", "#F2A33A"   # solo semáforos del tema (bueno / atención)
AZUL_CLARO, VIOLETA_CLARO = "#9CCBF0", "#B9ABE8"
AZUL_MAPA = "#2F6FB5"        # máximo del mapa de calor: el blanco se lee sobre él (5:1)
MEDIDAS = "_Medidas"
LOGO = "logo_minera_demo_blanco.png"   # recurso estático del informe (StaticResources/RegisteredResources)
# Lienzo de 1920x1080: las listas cortas (áreas, segmentaciones, reportes sin uso) se ven enteras
ANCHO, ALTO = 1920, 1080
# Tamaños de letra (pt), los más grandes que caben sin barras en tablas y matrices con ancho automático
PT_TITULO, PT_TEXTO, PT_CIFRA, PT_TABLA = 14, 12, 34, 10

# El repositorio publica solo datos sintéticos. Con datos reales, poner False: el aviso rojo pasa a una nota gris.
DATOS_SINTETICOS = True
AVISO = "DATOS SINTÉTICOS · empresa ficticia Minera Demo · 03-03-2025 al 31-05-2025"
NOTA_FUENTE = "Fuente: métricas de uso de Power BI de los workspaces PROD (días UTC)."
LIMITACIONES_SINTETICOS = (
    "1) los datos son sintéticos y no describen ninguna operación real; 2) el informe de métricas de uso del servicio "
    "guarda unos 30 días, por lo que un histórico más largo necesita una extracción periódica (ver docs/GUIA.md); "
    "3) las aperturas no equivalen a vistas de página; 4) una persona puede tener más de una cuenta "
    "(por ejemplo una interna y una externa).")
LIMITACIONES_REALES = (
    "1) el servicio guarda 30 días de uso: un día que no se extraiga dentro de ese plazo se pierde; 2) las vistas de "
    "página las envía el navegador y pueden quedar por debajo de lo real; las aperturas son exactas; 3) los días son "
    "UTC; 4) una persona puede tener más de una cuenta (por ejemplo una interna y una externa).")

# Nombre visible (con tildes) de medidas y columnas en los visuales. El nombre en el modelo no cambia:
# lo usan validacion_datos.dax y las demás medidas.
VISIBLE = {
    "Vistas de pagina": "Vistas de página",
    "Usuarios unicos": "Usuarios únicos",
    "Pags por apertura": "Págs. por apertura",
    "Dias con actividad": "Días con actividad",
    "Ultima actividad": "Última actividad",
    "Dias desde ultima actividad": "Días desde última actividad",
    "Ultima lectura": "Última lectura",
    "Profundidad historico dias": "Días de histórico",
    "Vistas pagina interno": "Vistas de página interno",
    "Vistas pagina externo": "Vistas de página externo",
    "Area": "Área",
    "usuario": "Usuario",
    "tipo_usuario": "Tipo de usuario",
    "report_nombre": "Nombre del reporte",
    "Aperturas por area o reporte": "Aperturas",
    "Etiqueta": "Área o reporte",
}


# --------------------------------------------------------------------------- expresiones
def lit(valor):
    """Envuelve un literal tal como lo escribe Power BI."""
    return {"expr": {"Literal": {"Value": valor}}}


def texto(s):
    return lit("'" + s.replace("'", "''") + "'")


def numero(n):
    return lit(f"{n}D")


def booleano(b):
    return lit("true" if b else "false")


def color(hex_):
    """Color fijo con el formato que guarda Power BI. Un literal suelto (p. ej. "fontColor": '#1D2733') Desktop lo
    descarta al guardar."""
    return {"solid": {"color": texto(hex_)}}


def medida(nombre):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": MEDIDAS}}, "Property": nombre}}


def columna(tabla, col):
    return {"Column": {"Expression": {"SourceRef": {"Entity": tabla}}, "Property": col}}


def pm(nombre, mostrar=None):
    """Proyección de una medida."""
    p = {"field": medida(nombre), "queryRef": f"{MEDIDAS}.{nombre}", "nativeQueryRef": nombre}
    mostrar = mostrar or VISIBLE.get(nombre)
    if mostrar and mostrar != nombre:
        p["displayName"] = mostrar
    return p


def pc(tabla, col, mostrar=None):
    """Proyección de una columna."""
    p = {"field": columna(tabla, col), "queryRef": f"{tabla}.{col}", "nativeQueryRef": col}
    mostrar = mostrar or VISIBLE.get(col)
    if mostrar and mostrar != col:
        p["displayName"] = mostrar
    return p


def orden(campo, direccion="Descending"):
    return {"sort": [{"field": campo, "direction": direccion}], "isDefaultSort": False}


def filtro_medida(nombre, medida_nombre, comparacion, valor):
    """Filtro de visual sobre una medida entera.
    comparacion (QueryComparisonKind del esquema semanticQuery): 0 igual, 1 mayor que,
    2 mayor o igual, 3 menor que, 4 menor o igual.
    Son filtros estructurales (definen qué muestra el visual): van ocultos y bloqueados para quien
    lee el informe, y con el nombre visible de la medida si alguien los ve al editar."""
    return {
        "name": nombre,
        "displayName": VISIBLE.get(medida_nombre, medida_nombre),
        "isHiddenInViewMode": True,
        "isLockedInViewMode": True,
        "field": medida(medida_nombre),
        "type": "Advanced",
        "filter": {
            "Version": 2,
            "From": [{"Name": "m", "Entity": MEDIDAS, "Type": 0}],
            "Where": [{"Condition": {"Comparison": {
                "ComparisonKind": comparacion,
                "Left": {"Measure": {"Expression": {"SourceRef": {"Source": "m"}},
                                     "Property": medida_nombre}},
                "Right": {"Literal": {"Value": f"{valor}L"}},
            }}}],
        },
        "howCreated": "User",
    }


def filtro_columna(nombre, tabla, col, valor, mostrar):
    """Filtro de visual que deja un solo valor de una columna (valor: literal de Power BI, p. ej. "true").
    Estructural como filtro_medida: oculto y bloqueado para quien lee el informe."""
    return {
        "name": nombre,
        "displayName": mostrar,
        "isHiddenInViewMode": True,
        "isLockedInViewMode": True,
        "field": columna(tabla, col),
        "type": "Categorical",
        "filter": {
            "Version": 2,
            "From": [{"Name": "d", "Entity": tabla, "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": col}}],
                "Values": [[{"Literal": {"Value": valor}}]],
            }}}],
        },
        "howCreated": "User",
    }


def mapa_calor(medida_nombre, color_max):
    """Formato condicional de fondo en degradado (panel -> color_max) para las celdas de una matriz."""
    return {"values": [{
        "properties": {"backColor": {"solid": {"color": {"expr": {"FillRule": {
            "Input": medida(medida_nombre),
            "FillRule": {"linearGradient2": {
                "min": {"color": {"Literal": {"Value": f"'{MEDIANOCHE}'"}}},
                "max": {"color": {"Literal": {"Value": f"'{color_max}'"}}},
                "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}},
            }},
        }}}}}},
        "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                     "metadata": f"{MEDIDAS}.{medida_nombre}"},
    }]}


# --------------------------------------------------------------------------- visuales
_orden_tab = [0]

# Un color por medida en todos los gráficos (el orden de las series cambia de un visual a otro): vistas de página en
# azul, aperturas en violeta, y el estado de los reportes en azul (en uso), violeta (solo aperturas) y rojo (sin uso)
COLOR_MEDIDA = {
    "Vistas de pagina": AZUL, "Aperturas": VIOLETA, "Usuarios unicos": AZUL_CLARO,
    "Reportes en uso": AZUL, "Reportes solo aperturas": VIOLETA, "Reportes sin uso": ROJO,
    "Vistas pagina interno": AZUL, "Vistas pagina externo": AZUL_CLARO,
    "Aperturas interno": VIOLETA, "Aperturas externo": VIOLETA_CLARO,
    "Aperturas por area o reporte": VIOLETA,
}
GRAFICOS = {"lineChart", "barChart", "clusteredColumnChart"}


def visual(nombre, tipo, caja, roles=None, titulo=None, alt=None,
           sort=None, filtros=None, objetos=None, sincronizar=None, fondo=None, titulo_medida=None):
    x, y, w, h = caja
    _orden_tab[0] += 1
    v = {"visualType": tipo}
    if roles:
        q = {"queryState": {rol: {"projections": proys} for rol, proys in roles.items()}}
        if sort:
            q["sortDefinition"] = sort
        v["query"] = q
    if tipo in GRAFICOS and roles and roles.get("Y"):
        series = [{"properties": {"fill": color(COLOR_MEDIDA[p["field"]["Measure"]["Property"]])},
                   "selector": {"metadata": p["queryRef"]}}
                  for p in roles["Y"] if p["field"].get("Measure", {}).get("Property") in COLOR_MEDIDA]
        if series:
            objetos = {**(objetos or {}), "dataPoint": series}
    if objetos:
        v["objects"] = objetos
    if sincronizar:
        v["syncGroup"] = {"groupName": sincronizar, "fieldChanges": True, "filterChanges": True}

    contenedor = {}
    if titulo is not None:
        # Fuente, tamaño y color salen del tema. En mayúsculas, como los paneles del diseño de referencia
        contenedor["title"] = [{"properties": {"show": booleano(True), "text": texto(titulo.upper())}}]
    elif titulo_medida:
        # Título que cambia con los filtros: lo escribe una medida (ya en mayúsculas)
        contenedor["title"] = [{"properties": {"show": booleano(True), "text": {"expr": medida(titulo_medida)}}}]
    if fondo:
        # El tema deja los cuadros de texto sin fondo: este lo lleva (la banda del título de cada página)
        contenedor["background"] = [{"properties": {
            "show": booleano(True), "color": color(fondo), "transparency": numero(0)}}]
        contenedor["border"] = [{"properties": {
            "show": booleano(True), "color": color(BORDE), "radius": numero(8)}}]
    if alt:
        contenedor["general"] = [{"properties": {"altText": texto(alt)}}]
    if contenedor:
        v["visualContainerObjects"] = contenedor

    cont = {
        "$schema": SCH_VISUAL,
        "name": nombre,
        "position": {"x": x, "y": y, "width": w, "height": h, "z": _orden_tab[0],
                     "tabOrder": _orden_tab[0] * 100},
        "visual": v,
    }
    if filtros:
        cont["filterConfig"] = {"filters": filtros}
    return cont


def cuadro_texto(nombre, caja, trozos, alt=None, alineacion=None, fondo=None):
    """trozos: lista de (texto, dict de estilo). alineacion: "left", "center" o "right"."""
    runs = []
    for t, estilo in trozos:
        run = {"value": t}
        if estilo:
            run["textStyle"] = estilo
        runs.append(run)
    parrafo = {"textRuns": runs}
    if alineacion:
        parrafo["horizontalTextAlignment"] = alineacion
    return visual(nombre, "textbox", caja,
                  objetos={"general": [{"properties": {"paragraphs": [parrafo]}}]},
                  alt=alt, fondo=fondo)


def encabezado(nombre, trozos, alt):
    """Banda del título de cada página, a todo el ancho: fondo azul medianoche y una marca violeta a la izquierda. A
    la derecha van el aviso de los datos y el logo, que se crean después y quedan encima."""
    # 18 pt en 50 px de alto: con 20 pt en 44 px la letra se cortaba por abajo (el cuadro de texto deja ~19 px arriba)
    marca = ("▍ ", {"fontSize": "18pt", "fontWeight": "bold", "color": VIOLETA})
    return cuadro_texto(nombre, (16, 8, ANCHO - 32, 50), [marca] + trozos, alt=alt, fondo=MEDIANOCHE)


def titulo_pagina(t):
    return (t, {"fontSize": "18pt", "fontWeight": "bold", "color": BLANCO})


LOGO_CAJA = (ANCHO - 28 - 150, 13, 150, 40)


def aviso_datos(nombre):
    """Dentro de la banda del título, a la derecha del texto y a la izquierda del logo. Con datos sintéticos, el aviso
    rojo; con datos reales, una nota gris con el origen de los datos."""
    caja = (LOGO_CAJA[0] - 12 - 820, 15, 820, 36)
    if DATOS_SINTETICOS:
        return cuadro_texto(nombre, caja,
                            [("⚠ " + AVISO, {"fontSize": "11pt", "fontWeight": "bold", "color": ROJO})],
                            alt="Aviso: los datos cargados son sintéticos", alineacion="right")
    return cuadro_texto(nombre, caja, [(NOTA_FUENTE, {"fontSize": "11pt", "color": TEXTO_TENUE})],
                        alt="Origen y actualización de los datos", alineacion="right")


def logo(nombre):
    """Logo de Minera Demo (imagen registrada en RegisteredResources), a la derecha de la banda del título."""
    item = {"ResourcePackageItem": {"PackageName": "RegisteredResources", "PackageType": 1, "ItemName": LOGO}}
    return visual(nombre, "image", LOGO_CAJA, alt="Logo de Minera Demo", objetos={
        "general": [{"properties": {"imageUrl": {"expr": item}}}],
        "imageScaling": [{"properties": {"imageScalingType": texto("Fit")}}],
    })


def letra_tabla(pt, objetos=None):
    """Letra de una tabla más grande que la del tema (PT_TABLA), para las que tienen ancho de sobra. Conserva las
    demás propiedades de esas secciones (p. ej. "totals")."""
    o = dict(objetos or {})
    for seccion in ("values", "columnHeaders", "total"):
        previas = o.get(seccion, [{"properties": {}}])[0]["properties"]
        o[seccion] = [{"properties": {**previas, "fontSize": numero(pt)}}]
    return o


def segmentacion(nombre, caja, tabla, col, titulo, grupo, desplegable=False):
    # El título del visual nombra el campo: se oculta el encabezado propio de la segmentación,
    # que repetiría el nombre (y mostraría el técnico, p. ej. "workspace_nombre")
    objetos = {"data": [{"properties": {"mode": texto("Dropdown" if desplegable else "Basic")}}],
               "header": [{"properties": {"show": booleano(False)}}]}
    return visual(nombre, "slicer", caja,
                  roles={"Values": [pc(tabla, col)]},
                  titulo=titulo, alt=f"Segmentación por {titulo.lower()}",
                  objetos=objetos, sincronizar=grupo)


def tarjeta(nombre, caja, medida_nombre, titulo, color_cifra=None):
    # El título del visual ya dice qué cifra es: se oculta la etiqueta de categoría (el nombre de la medida).
    # La cifra va en blanco (tema) o en el color de su significado (en uso, solo aperturas, sin uso...)
    objetos = {"categoryLabels": [{"properties": {"show": booleano(False)}}]}
    if color_cifra:
        objetos["labels"] = [{"properties": {"color": color(color_cifra)}}]
    return visual(nombre, "card", caja, roles={"Values": [pm(medida_nombre)]},
                  titulo=titulo, alt=f"Tarjeta con {titulo.lower()}", objetos=objetos)


# --------------------------------------------------------------------------- páginas
def pagina(nombre, mostrar, visuales, interacciones=None):
    p = {"$schema": SCH_PAGE, "name": nombre, "displayName": mostrar,
         "displayOption": "FitToPage", "height": ALTO, "width": ANCHO}
    if interacciones:
        p["visualInteractions"] = interacciones
    return {"pagina": p, "visuales": visuales}


# Area: nombre corto del workspace. Reporte: nombre único (los repetidos llevan el área), así dos reportes con el
# mismo nombre no se suman. Ambas columnas las calcula Power Query (consultas Dim_Reporte y Dim_Area).
AREA, REPORTE = ("Dim_Area", "Area"), ("Dim_Reporte", "Reporte")


def cabecera(prefijo, titulo, alt, extra=None):
    """Banda de título + aviso de datos + logo, comunes a todas las páginas."""
    return [encabezado(f"txt{prefijo}Titulo", [titulo_pagina(titulo)] + (extra or []), alt=alt),
            aviso_datos(f"txt{prefijo}Aviso"),
            logo(f"img{prefijo}Logo")]


def pagina_resumen():
    # Las segmentaciones de Área son desplegables en todas las páginas. A la izquierda las tendencias y el estado por
    # área; a la derecha la tabla de reportes, ancha para que no corte columnas y con todo el alto de la página.
    v = cabecera("Resumen", "Gobernanza de uso de reportes Power BI — workspaces PROD", "Título del informe") + [
        tarjeta("cardTotalReportes", (16, 64, 364, 100), "Total reportes", "Reportes monitoreados"),
        tarjeta("cardReportesEnUso", (396, 64, 364, 100), "Reportes en uso", "En uso", AZUL),
        tarjeta("cardReportesSoloAp", (776, 64, 364, 100), "Reportes solo aperturas", "Solo aperturas", VIOLETA),
        tarjeta("cardReportesSinUso", (1156, 64, 364, 100), "Reportes sin uso", "Sin uso", ROJO),
        segmentacion("slcResumenArea", (1536, 64, 368, 100), *AREA,
                     titulo="Área de trabajo", grupo="area", desplegable=True),
        visual("lineResumenTendencia", "lineChart", (16, 180, 560, 240),
               roles={"Category": [pc("Dim_Fecha", "Fecha")],
                      "Y": [pm("Aperturas"), pm("Vistas de pagina")]},
               titulo="Aperturas y vistas de página por día",
               alt="Gráfico de líneas con la tendencia diaria de aperturas y vistas de página"),
        visual("lineResumenUsuarios", "lineChart", (16, 436, 560, 220),
               roles={"Category": [pc("Dim_Fecha", "Fecha")], "Y": [pm("Usuarios unicos")]},
               titulo="Usuarios únicos por día",
               alt="Gráfico de líneas con los usuarios únicos de cada día"),
        # Hasta la mitad del ancho para los nombres de área (con 40 % aún se cortaban los más largos)
        visual("barResumenEstadoArea", "barChart", (16, 672, 560, 392),
               roles={"Category": [pc(*AREA)],
                      "Y": [pm("Reportes en uso"), pm("Reportes solo aperturas"), pm("Reportes sin uso")]},
               objetos={"categoryAxis": [{"properties": {"maxMarginFactor": lit("50L")}}]},
               titulo="Estado de los reportes por área",
               alt="Barras apiladas con la cantidad de reportes en uso, solo aperturas y sin uso por área"),
        visual("tblResumenReportes", "tableEx", (592, 180, 1312, 884),
               roles={"Values": [pc(*AREA), pc(*REPORTE), pm("Aperturas"), pm("Vistas de pagina"),
                                 pm("Usuarios unicos"), pm("Pags por apertura"), pm("Estado del reporte")]},
               sort=orden(medida("Vistas de pagina")),
               titulo="Detalle por reporte (más vistas primero)",
               alt="Tabla con área, reporte, aperturas, vistas de página, usuarios, páginas por apertura y estado"),
    ]
    return pagina("paginaResumen", "Resumen", v)


def pagina_vistas(por_semana=False):
    # Matrices de un solo nivel (Reporte ya es único): no hay que expandirlas a mano.
    # El mapa de calor va como formato condicional de fondo.
    # Con por_semana, la misma página por semana de lunes a domingo: Dim_Fecha[Semana] se ordena por su lunes y
    # marca "(parcial)" las semanas que los datos no cubren enteras.
    # Por día, las matrices muestran los últimos 28 días cargados con la fecha corta (Dim_Fecha[FechaCorta] y el filtro
    # Ultimos28): así caben a todo el ancho sin barra horizontal. La historia completa queda en la tendencia y en la
    # página semanal.
    if por_semana:
        p, grano, sufijo, tendencia = "Semanas", "semana", "PorSemana", "Tendencia semanal de la selección"
        tendencia_campo, columnas, periodo, filtros = "Semana", pc("Dim_Fecha", "Semana"), "", None
    else:
        p, grano, sufijo, tendencia = "Vistas", "día", "PorDia", "Tendencia diaria de la selección (todo el histórico)"
        tendencia_campo, columnas, periodo = "Fecha", pc("Dim_Fecha", "FechaCorta", "Día"), ", últimos 28 días"
        filtros = [filtro_columna("fltUltimos28", "Dim_Fecha", "Ultimos28", "true", "Últimos 28 días")]
    # Las dos matrices van a todo el ancho y del mismo tamaño, una sobre otra. La tendencia va arriba, junto a las
    # segmentaciones (desplegables), baja y ancha, con la leyenda a la derecha para no quitarle alto al gráfico.
    v = cabecera(p, f"Vistas y usuarios por {grano}", "Título de la página") + [
        segmentacion(f"slc{p}Area", (16, 64, 320, 76), *AREA,
                     titulo="Área de trabajo", grupo="area", desplegable=True),
        segmentacion(f"slc{p}TipoUsuario", (16, 148, 320, 76), "Dim_Usuario", "tipo_usuario",
                     titulo="Tipo de usuario", grupo="tipoUsuario", desplegable=True),
        # La semana es texto (eje de categorías): el orden cronológico se fija para no depender del orden por defecto
        visual(f"line{p}Tendencia", "lineChart", (352, 64, 1552, 160),
               roles={"Category": [pc("Dim_Fecha", tendencia_campo)],
                      "Y": [pm("Vistas de pagina"), pm("Aperturas")]},
               sort=orden(columna("Dim_Fecha", tendencia_campo), "Ascending") if por_semana else None,
               objetos={"legend": [{"properties": {"position": texto("RightCenter")}}]},
               titulo=tendencia,
               alt=f"Gráfico de líneas con vistas de página y aperturas por {grano}"),
        visual(f"mtxVistas{sufijo}", "pivotTable", (16, 240, 1888, 404),
               roles={"Rows": [pc(*REPORTE)],
                      "Columns": [columnas],
                      "Values": [pm("Vistas de pagina")]},
               filtros=filtros,
               objetos=mapa_calor("Vistas de pagina", AZUL_MAPA),
               titulo=f"Vistas de página por reporte y {grano}{periodo}",
               alt=f"Matriz de reportes por {grano}{periodo} con las vistas de página, coloreada como mapa de calor"),
        visual(f"mtxUsuarios{sufijo}", "pivotTable", (16, 660, 1888, 404),
               roles={"Rows": [pc(*REPORTE)],
                      "Columns": [columnas],
                      "Values": [pm("Usuarios unicos")]},
               filtros=filtros,
               objetos=mapa_calor("Usuarios unicos", AZUL_MAPA),
               titulo=f"Usuarios únicos por reporte y {grano}{periodo} (los totales no se suman)",
               alt=f"Matriz de reportes por {grano}{periodo} con los usuarios únicos, coloreada como mapa de calor"),
    ]
    return pagina(f"pagina{p}", "Vistas por semana" if por_semana else "Vistas", v)


def pagina_sin_uso():
    v = cabecera("SinUso", "Reportes sin uso", "Título de la página") + [
        tarjeta("cardSinUsoCant", (16, 64, 460, 100), "Reportes sin uso", "Sin uso", ROJO),
        tarjeta("cardSoloAperturasCant", (492, 64, 460, 100), "Reportes solo aperturas", "Solo aperturas", VIOLETA),
        segmentacion("slcSinUsoArea", (968, 64, 460, 100), *AREA,
                     titulo="Área de trabajo", grupo="area", desplegable=True),
        # Sin fila de total: el estado, la última actividad y los días son de cada reporte
        visual("tblSinUso", "tableEx", (16, 180, 1888, 884),
               roles={"Values": [pc(*AREA), pc(*REPORTE), pm("Estado del reporte"),
                                 pm("Aperturas"), pm("Vistas de pagina"),
                                 pm("Ultima actividad"), pm("Dias desde ultima actividad")]},
               sort=orden(medida("Aperturas")),
               filtros=[filtro_medida("fltSinVistas", "Vistas de pagina", 3, 1)],
               objetos=letra_tabla(12, {"total": [{"properties": {"totals": booleano(False)}}]}),
               titulo="Reportes sin vistas de página (candidatos a revisar)",
               alt="Tabla de reportes sin vistas de página, con área, estado, aperturas y última actividad"),
    ]
    return pagina("paginaSinUso", "Sin uso", v)


def pagina_detalle():
    v = cabecera("Detalle", "Detalle por reporte", "Título e instrucciones de la página", extra=[
        ("   Elija un reporte para ver su uso diario y sus usuarios.", {"fontSize": "12pt", "color": TEXTO_TENUE}),
    ]) + [
        segmentacion("slcDetalleArea", (16, 64, 400, 100), *AREA,
                     titulo="Área de trabajo", grupo="area", desplegable=True),
        segmentacion("slcDetalleReporte", (432, 64, 704, 100), *REPORTE,
                     titulo="Reporte", grupo="reporte", desplegable=True),
        tarjeta("cardDetalleAperturas", (1152, 64, 240, 100), "Aperturas", "Aperturas", VIOLETA),
        tarjeta("cardDetalleVistas", (1408, 64, 240, 100), "Vistas de pagina", "Vistas de página", AZUL),
        tarjeta("cardDetalleRatio", (1664, 64, 240, 100), "Pags por apertura", "Págs. por apertura"),
        # A la izquierda los gráficos; a la derecha los usuarios con todo el alto de la página.
        # Internos frente a externos va en la información sobre herramientas del uso diario.
        visual("lineDetalleUso", "lineChart", (16, 180, 1032, 260),
               roles={"Category": [pc("Dim_Fecha", "Fecha")],
                      "Y": [pm("Vistas de pagina"), pm("Aperturas")],
                      "Tooltips": [pm("Aperturas interno"), pm("Aperturas externo"),
                                   pm("Vistas pagina interno"), pm("Vistas pagina externo")]},
               titulo="Uso diario del reporte seleccionado",
               alt="Gráfico de líneas con vistas de página y aperturas por día del reporte seleccionado"),
        visual("lineDetalleUsuarios", "lineChart", (16, 456, 1032, 230),
               roles={"Category": [pc("Dim_Fecha", "Fecha")], "Y": [pm("Usuarios unicos")]},
               titulo="Usuarios únicos por día",
               alt="Gráfico de líneas con los usuarios únicos por día del reporte seleccionado"),
        # Aperturas de más a menos: por área o, con un área elegida en la segmentación, por reporte de esa área
        # (Eje_Detalle y [Aperturas por area o reporte]), con el valor en cada barra. El eje de valores sobra con las
        # etiquetas. La segmentación de Reporte no lo filtra (ver interacciones): así se ve dónde queda el reporte
        # elegido, y con «Todas» no aparece su área con una sola barra que parece el total.
        visual("colDetalleRanking", "clusteredColumnChart", (16, 702, 1032, 362),
               roles={"Category": [pc("Eje_Detalle", "Etiqueta")], "Y": [pm("Aperturas por area o reporte")]},
               sort=orden(medida("Aperturas por area o reporte")),
               objetos={
                   "labels": [{"properties": {"show": booleano(True), "labelPosition": texto("OutsideEnd"),
                                              "labelDisplayUnits": numero(1), "color": color(BLANCO),
                                              "fontSize": numero(PT_TEXTO)}}],
                   "valueAxis": [{"properties": {"show": booleano(False), "gridlineShow": booleano(False)}}],
                   "categoryAxis": [{"properties": {"showAxisTitle": booleano(False), "maxMarginFactor": lit("40L")}}],
               },
               titulo_medida="Titulo grafico detalle",
               alt="Columnas con las aperturas de cada área, de más a menos; con un área elegida, las de sus reportes"),
        # Filtro Usuarios unicos > 0: sin él, el +0 de las medidas listaría a todos los usuarios
        # con ceros, aunque nunca hayan abierto el reporte elegido.
        visual("tblDetalleUsuarios", "tableEx", (1064, 180, 840, 884),
               roles={"Values": [pc("Dim_Usuario", "usuario"), pc("Dim_Usuario", "tipo_usuario"),
                                 pm("Aperturas"), pm("Vistas de pagina"), pm("Pags por apertura")]},
               sort=orden(medida("Vistas de pagina")),
               filtros=[filtro_medida("fltConUso", "Usuarios unicos", 1, 0)],
               objetos=letra_tabla(11),
               titulo="Usuarios del reporte (más vistas primero)",
               alt="Tabla con los usuarios que usaron el reporte: tipo, aperturas, vistas de página y páginas por apertura"),
    ]
    return pagina("paginaDetalle", "Detalle", v,
                  interacciones=[{"source": "slcDetalleReporte", "target": "colDetalleRanking", "type": "NoFilter"}])


def pagina_calidad():
    v = cabecera("Calidad", "Calidad de los datos", "Título de la página") + [
        tarjeta("cardProfundidad", (16, 64, 460, 100), "Profundidad historico dias", "Días de histórico"),
        tarjeta("cardDiasActividad", (492, 64, 460, 100), "Dias con actividad", "Días con datos"),
        tarjeta("cardDatosDesde", (968, 64, 460, 100), "Datos desde", "Datos desde"),
        segmentacion("slcCalidadArea", (1444, 64, 460, 100), *AREA,
                     titulo="Área de trabajo", grupo="area", desplegable=True),
        # A la izquierda, con todo el alto, los reportes con aperturas sin vistas: solo los que tienen alguna (por el +0
        # de las medidas saldrían todos los reportes, con ceros al final). A la derecha las tablas por área, de nombres
        # repetidos y de usuarios (esta, ordenada de menor a mayor, deja arriba lo que importa).
        visual("tblAperturasSinVistas", "tableEx", (16, 180, 1060, 812),
               roles={"Values": [pc(*AREA), pc(*REPORTE), pm("Aperturas"),
                                 pm("Aperturas sin vistas"), pm("Vistas de pagina")]},
               sort=orden(medida("Aperturas sin vistas")),
               filtros=[filtro_medida("fltConAperturasSinVistas", "Aperturas sin vistas", 1, 0)],
               titulo="Aperturas sin vistas de página (posible acceso automatizado)",
               alt="Tabla de reportes con aperturas que no registraron vistas de página"),
        # Última lectura: la última lectura de la extracción en cada área. Si un área se queda atrás, la extracción dejó
        # de leerla. Encabezados cortos para que las 6 columnas quepan sin barra.
        visual("tblCobertura", "tableEx", (1092, 180, 812, 330),
               roles={"Values": [pc(*AREA), pm("Total reportes", "Reportes"), pm("Reportes en uso", "En uso"),
                                 pm("Reportes solo aperturas", "Solo aperturas"), pm("Reportes sin uso", "Sin uso"),
                                 pm("Ultima lectura")]},
               titulo="Cobertura por área",
               alt="Tabla con el total de reportes, su estado y la fecha de la última lectura de la extracción por área"),
        visual("tblNombresDuplicados", "tableEx", (1092, 526, 812, 170),
               roles={"Values": [pc("Dim_Reporte", "report_nombre"), pm("Total reportes", "Reportes con ese nombre")]},
               filtros=[filtro_medida("fltDuplicados", "Total reportes", 1, 1)],
               objetos=letra_tabla(12),
               titulo="Nombres de reporte usados por más de un reporte",
               alt="Tabla con los nombres de reporte que comparten dos o más reportes"),
        # Filtro Aperturas > 0: sin él, los usuarios sin actividad (0 aperturas) encabezarían el orden ascendente
        visual("tblRatioUsuario", "tableEx", (1092, 712, 812, 280),
               roles={"Values": [pc("Dim_Usuario", "usuario"), pc("Dim_Usuario", "tipo_usuario"),
                                 pm("Aperturas"), pm("Vistas de pagina"), pm("Pags por apertura")]},
               sort=orden(medida("Pags por apertura"), "Ascending"),
               filtros=[filtro_medida("fltConAperturas", "Aperturas", 1, 0)],
               titulo="Páginas por apertura según usuario (menor primero)",
               alt="Tabla de usuarios con aperturas, ordenada por páginas por apertura de menor a mayor"),
        cuadro_texto("txtLimitaciones", (16, 1008, 1888, 56), [
            ("Limitaciones: ", {"fontSize": "12pt", "fontWeight": "bold", "color": TEXTO}),
            (LIMITACIONES_SINTETICOS if DATOS_SINTETICOS else LIMITACIONES_REALES,
             {"fontSize": "12pt", "color": TEXTO_TENUE}),
        ], alt="Limitaciones conocidas de los datos"),
    ]
    # Las tarjetas describen el histórico completo: ni la segmentación de Área ni un clic en las tablas
    # las filtran (si no, "Días con datos" < "Días de histórico" parecería una laguna que no existe).
    # La tabla de nombres repetidos tampoco se filtra por Área ni por clics en las otras tablas: un nombre
    # repetido entre áreas (o entre reportes) desaparecería al quedar uno solo.
    tarjetas = ["cardProfundidad", "cardDiasActividad", "cardDatosDesde"]
    fuentes = ["slcCalidadArea", "tblAperturasSinVistas", "tblCobertura", "tblRatioUsuario", "tblNombresDuplicados"]
    interacciones = [{"source": f, "target": t, "type": "NoFilter"} for f in fuentes for t in tarjetas]
    interacciones += [{"source": f, "target": "tblNombresDuplicados", "type": "NoFilter"}
                      for f in fuentes if f != "tblNombresDuplicados"]
    return pagina("paginaCalidad", "Calidad", v, interacciones)


# --------------------------------------------------------------------------- tema
def tema():
    """Tema oscuro con la paleta de Minera Demo (ver la paleta al inicio). main() lo valida contra el esquema de temas de
    Desktop (extraer_esquemas.py)."""
    def c(h):
        return {"solid": {"color": h}}
    # Panel de todos los visuales. El título no se fuerza a mostrarse: solo se le da estilo
    panel = {
        "background": [{"show": True, "color": c(MEDIANOCHE), "transparency": 0}],
        "border": [{"show": True, "color": c(BORDE), "radius": 8, "width": 1}],
        "title": [{"fontColor": c(TEXTO), "fontSize": PT_TITULO, "fontFamily": "Segoe UI Semibold"}],
        "dropShadow": [{"show": False}],
        "visualHeader": [{"background": c(MEDIANOCHE), "foreground": c(TEXTO), "border": c(BORDE), "transparency": 0}],
        # Tooltips (al pasar el mouse): sin esto el fondo sale del tema pero el texto queda oscuro y no se lee.
        # Las variantes "themed" son las del estilo de tooltip por defecto: se fijan igual
        "visualTooltip": [{"background": c(OSCURO), "titleFontColor": c(TEXTO), "valueFontColor": c(BLANCO),
                           "themedBackground": c(OSCURO), "themedTitleFontColor": c(TEXTO),
                           "themedValueFontColor": c(BLANCO), "actionFontColor": c(AZUL_CLARO), "transparency": 0}],
        "visualHeaderTooltip": [{"background": c(OSCURO), "titleFontColor": c(BLANCO), "themedBackground": c(OSCURO),
                                 "themedTitleFontColor": c(BLANCO), "transparency": 0}],
    }
    ejes = {
        "categoryAxis": [{"labelColor": c(TEXTO_TENUE), "titleColor": c(TEXTO_TENUE), "gridlineColor": c(BORDE),
                          "fontSize": PT_TEXTO}],
        "valueAxis": [{"labelColor": c(TEXTO_TENUE), "titleColor": c(TEXTO_TENUE), "gridlineColor": c(BORDE),
                       "fontSize": PT_TEXTO}],
        "legend": [{"labelColor": c(TEXTO), "fontSize": PT_TEXTO}],
    }
    # La letra de cada sección de tablas y matrices va explícita: si no, sale del tema base y no de textClasses
    celdas = {
        "columnHeaders": [{"fontColor": c(BLANCO), "backColor": c(OSCURO), "fontFamily": "Segoe UI Semibold",
                           "fontSize": PT_TABLA}],
        "values": [{"fontColorPrimary": c(BLANCO), "backColorPrimary": c(MEDIANOCHE),
                    "fontColorSecondary": c(BLANCO), "backColorSecondary": c(FILA_ALTERNA), "fontSize": PT_TABLA}],
        "grid": [{"gridHorizontalColor": c(BORDE), "gridVerticalColor": c(BORDE), "outlineColor": c(BORDE)}],
    }
    total = [{"fontColor": c(BLANCO), "backColor": c(OSCURO), "fontSize": PT_TABLA}]
    sin_panel = {"background": [{"show": False}], "border": [{"show": False}]}
    return {
        "name": PROYECTO,
        "dataColors": [AZUL, VIOLETA, AZUL_CLARO, VIOLETA_CLARO, ROJO, TEXTO_TENUE, "#5E7AA3", "#E6EEF7"],
        "firstLevelElements": BLANCO,
        "secondLevelElements": TEXTO,
        "thirdLevelElements": BORDE,
        "fourthLevelElements": TEXTO_TENUE,
        "background": MEDIANOCHE,
        "secondaryBackground": OSCURO,
        "tableAccent": AZUL,
        "good": VERDE,
        "neutral": AMBAR,
        "bad": ROJO,
        "minimum": MEDIANOCHE,
        "center": "#24456F",
        "maximum": AZUL_MAPA,
        "hyperlink": AZUL_CLARO,
        "visitedHyperlink": AZUL_CLARO,
        "textClasses": {
            "callout": {"fontFace": "Segoe UI Semibold", "fontSize": PT_CIFRA, "color": BLANCO},
            "title": {"fontFace": "Segoe UI Semibold", "fontSize": PT_TITULO, "color": TEXTO},
            "header": {"fontFace": "Segoe UI Semibold", "fontSize": PT_TEXTO, "color": BLANCO},
            "label": {"fontFace": "Segoe UI", "fontSize": PT_TEXTO, "color": TEXTO},
        },
        "visualStyles": {
            "*": {"*": panel},
            "page": {"*": {"background": [{"color": c(FONDO), "transparency": 0}],
                           "outspace": [{"color": c(FONDO), "transparency": 0}]}},
            "textbox": {"*": sin_panel},
            "image": {"*": sin_panel},
            "card": {"*": {"labels": [{"color": c(BLANCO), "fontSize": PT_CIFRA, "fontFamily": "Segoe UI Semibold"}]}},
            "slicer": {"*": {"items": [{"fontColor": c(BLANCO), "background": c(MEDIANOCHE), "textSize": PT_TEXTO}],
                             "header": [{"textSize": PT_TEXTO}]}},
            "tableEx": {"*": {**celdas, "total": total}},
            "pivotTable": {"*": {**celdas, "rowHeaders": [{"fontColor": c(BLANCO), "backColor": c(MEDIANOCHE), "fontSize": PT_TABLA}],
                                 "columnTotal": total, "rowTotal": total}},
            "lineChart": {"*": ejes},
            "barChart": {"*": ejes},
            "clusteredColumnChart": {"*": ejes},
        },
    }


# --------------------------------------------------------------------------- validación
def validador():
    """Devuelve una función validar(obj, id_esquema) -> lista de errores, o None si no hay jsonschema o esquemas."""
    try:
        from jsonschema import Draft7Validator
        from referencing import Registry, Resource
    except ImportError:
        return None
    if not ESQUEMAS.is_dir():
        return None
    recursos = []
    for f in ESQUEMAS.glob("*.json"):
        obj = json.loads(f.read_text(encoding="utf-8"))
        if "$id" in obj:
            recursos.append((obj["$id"], Resource.from_contents(obj)))
    if not recursos:
        return None
    registro = Registry().with_resources(recursos)
    por_id = {sid: r.contents for sid, r in recursos}
    # El esquema de temas no tiene $id: se toma la versión más alta que haya (reportThemeSchema-<versión>.json)
    temas = sorted(ESQUEMAS.glob("reportThemeSchema-*.json"), key=lambda f: [int(n) for n in re.findall(r"\d+", f.stem)])
    if temas:
        por_id[TEMA] = json.loads(temas[-1].read_text(encoding="utf-8"))
    else:
        print("AVISO: falta reportThemeSchema-*.json en los esquemas (python extraer_esquemas.py); el tema no se valida.")
        por_id[TEMA] = {}

    def validar(obj, id_esquema):
        esquema = por_id.get(id_esquema)
        if esquema is None:
            return [f"falta el esquema {id_esquema}"]
        v = Draft7Validator(esquema, registry=registro)
        return [f"{'/'.join(str(p) for p in e.path) or '(raiz)'}: {e.message}"
                for e in sorted(v.iter_errors(obj), key=lambda e: list(e.path))]

    return validar


# --------------------------------------------------------------------------- escritura
def contenido(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def escribir(ruta, obj):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(contenido(obj))


def borrar_carpeta(ruta):
    """Borra una carpeta quitando atributos de solo lectura. Devuelve False si no pudo."""
    def quitar_solo_lectura(func, p, _):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if not ruta.exists():
        return True
    try:
        if sys.version_info >= (3, 12):  # onerror quedó obsoleto en 3.12
            shutil.rmtree(ruta, onexc=quitar_solo_lectura)
        else:
            shutil.rmtree(ruta, onerror=quitar_solo_lectura)
        return True
    except OSError as e:
        print(f"AVISO: no se pudo borrar {ruta} ({e}).")
        return False


ESPACIO_ID = uuid.UUID("0b8f2b52-6d3a-4d0e-9a41-5a6f7a1d9e11")


def logical_id(ruta_platform, tipo):
    """Conserva el logicalId del .platform existente (es la identidad del elemento en Fabric/Git). Si no existe, lo
    deriva del nombre del proyecto, así regenerar desde cero produce siempre los mismos archivos."""
    if not ruta_platform.exists():
        return str(uuid.uuid5(ESPACIO_ID, f"{PROYECTO}:{tipo}"))
    try:
        return json.loads(ruta_platform.read_text(encoding="utf-8-sig"))["config"]["logicalId"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        sys.exit(f"No se pudo leer el logicalId de {ruta_platform} ({e}). Revísalo: regenerar le daría "
                 "otra identidad al elemento. No se escribió nada.")


def main():
    paginas = [pagina_resumen(), pagina_vistas(), pagina_vistas(por_semana=True), pagina_sin_uso(),
               pagina_detalle(), pagina_calidad()]

    dir_rep = RAIZ / f"{PROYECTO}.Report"
    dir_def = dir_rep / "definition"
    dir_sm = RAIZ / f"{PROYECTO}.SemanticModel"
    dir_recursos = dir_rep / "StaticResources" / "RegisteredResources"
    if not (dir_recursos / LOGO).is_file():
        sys.exit(f"Falta el logo {dir_recursos / LOGO} (copiarlo de assets/ del repositorio). No se escribió nada.")

    # Archivos a escribir: (ruta, contenido, id de esquema para validar)
    pendientes = [
        (RAIZ / f"{PROYECTO}.pbip", {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
            "version": "1.0",
            "artifacts": [{"report": {"path": f"{PROYECTO}.Report"}}],
            "settings": {"enableAutoRecovery": True},
        }, None),
        (dir_rep / ".platform", {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "Report", "displayName": PROYECTO},
            "config": {"version": "2.0", "logicalId": logical_id(dir_rep / ".platform", "Report")},
        }, None),
        (dir_rep / "definition.pbir", {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
            "version": "4.0",
            "datasetReference": {"byPath": {"path": f"../{PROYECTO}.SemanticModel"}},
        }, None),
        (dir_def / "version.json", {"$schema": SCH_VERSION, "version": "2.0.0"}, SCH_VERSION),
        (dir_def / "report.json", {
            "$schema": SCH_REPORT,
            # El tema se nombra como lo hace Desktop: nombre = ruta = archivo, con .json. Con un nombre sin .json,
            # al abrir de nuevo Desktop no encuentra el archivo y usa el tema por defecto (fondo blanco).
            "themeCollection": {"customTheme": {
                "name": f"{PROYECTO}.json", "reportVersionAtImport": VERSION_TEMA,
                "type": "RegisteredResources"}},
            "resourcePackages": [{
                "name": "RegisteredResources", "type": "RegisteredResources",
                "items": [{"name": f"{PROYECTO}.json", "path": f"{PROYECTO}.json", "type": "CustomTheme"},
                          {"name": LOGO, "path": LOGO, "type": "Image"}],
            }],
            # Panel de filtros contraído al abrir (despeja el diseño oscuro)
            "objects": {"outspacePane": [{"properties": {"expanded": booleano(False)}}]},
            "settings": {
                "useStylableVisualContainerHeader": True,
                "defaultDrillFilterOtherVisuals": True,
                "allowChangeFilterTypes": True,
                "useEnhancedTooltips": True,
                "useDefaultAggregateDisplayName": True,
                "exportDataMode": "AllowSummarized",
            },
        }, SCH_REPORT),
        (dir_def / "pages" / "pages.json", {
            "$schema": SCH_PAGES,
            "pageOrder": [p["pagina"]["name"] for p in paginas],
            "activePageName": paginas[0]["pagina"]["name"],
        }, SCH_PAGES),
        (dir_recursos / f"{PROYECTO}.json", tema(), TEMA),
        (dir_sm / ".platform", {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "SemanticModel", "displayName": PROYECTO},
            "config": {"version": "2.0", "logicalId": logical_id(dir_sm / ".platform", "SemanticModel")},
        }, None),
        (dir_sm / "definition.pbism", {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
            "version": "4.2",
            "settings": {},
        }, None),
    ]
    for p in paginas:
        base = dir_def / "pages" / p["pagina"]["name"]
        pendientes.append((base / "page.json", p["pagina"], SCH_PAGE))
        for vis in p["visuales"]:
            pendientes.append((base / "visuals" / vis["name"] / "visual.json", vis, SCH_VISUAL))

    validar = validador()
    if validar:
        errores = 0
        for ruta, obj, esquema in pendientes:
            if not esquema:
                continue
            for e in validar(obj, esquema):
                print(f"  INVÁLIDO {ruta.name} [{ruta.parent.name}] -> {e}")
                errores += 1
        if errores:
            print(f"\n{errores} error(es) de esquema. No se escribió nada.")
            return 1
        print("Validación contra los esquemas de Power BI Desktop: sin errores.")
    else:
        print("AVISO: sin jsonschema o sin esquemas (python extraer_esquemas.py); se escribe sin validar.")

    if SOLO_VALIDAR:
        return 0

    # Archivos sueltos (fuera de definition/) y carpetas temporales. Los nombres temporales no son más largos que
    # "definition", así que no alargan las rutas (límite de 260 caracteres de Windows).
    fijos = [(ruta, obj) for ruta, obj, _ in pendientes if dir_def not in ruta.parents]
    nuevo, viejo = dir_rep / "_gen_nuevo", dir_rep / "_gen_anterior"
    if not dir_def.exists() and viejo.exists():      # resto de una corrida cortada a mitad
        os.replace(viejo, dir_def)
        print("AVISO: una corrida anterior se cortó a mitad; se repuso el informe anterior.")
    for d in (nuevo, viejo):
        if not borrar_carpeta(d):
            print(f"NO SE REGENERÓ: no se pudo borrar la carpeta temporal {d} (¿abierta en otro programa?).")
            return 3

    # 1) Todo lo nuevo se prepara aparte, sin tocar el informe actual
    try:
        for ruta, obj, _ in pendientes:
            if dir_def in ruta.parents:
                escribir(nuevo / ruta.relative_to(dir_def), obj)
    except OSError as e:
        borrar_carpeta(nuevo)
        print(f"NO SE REGENERÓ: no se pudo preparar el informe nuevo ({e}). El actual quedó intacto.")
        return 3

    # 2) Cambio de lo actual por lo nuevo; si falla, se repone lo anterior
    try:
        if dir_def.exists():
            os.replace(dir_def, viejo)
        os.replace(nuevo, dir_def)
    except OSError as e:
        if viejo.exists() and not dir_def.exists():
            os.replace(viejo, dir_def)
        borrar_carpeta(nuevo)
        print(f"NO SE REGENERÓ: no se pudo reemplazar el informe ({e}). Cierra Power BI Desktop y vuelve a intentarlo.")
        return 3
    borrar_carpeta(viejo)
    for ruta, obj in fijos:
        escribir(ruta, obj)

    n_vis = sum(len(p["visuales"]) for p in paginas)
    print(f"Escrito: {PROYECTO}.pbip | {len(paginas)} páginas | {n_vis} visuales | {len(pendientes)} archivos")
    for p in paginas:
        print(f"  {p['pagina']['displayName']:20} {len(p['visuales']):2} visuales")
    return 0


if __name__ == "__main__":
    sys.exit(main())
