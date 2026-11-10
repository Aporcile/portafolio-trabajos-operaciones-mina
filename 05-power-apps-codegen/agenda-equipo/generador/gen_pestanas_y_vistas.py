# -*- coding: utf-8 -*-
"""Genera las pestañas (01b) y las vistas Tablero (04), Lista (05) y Por persona (06)."""
from comun import (ACT_COLS, ESTADOS, EST_FG, EST_FILL, INI, OPEN_ACT, RANK_EST, RANK_PRIO, SUB, SUB_COLOR, TW, act_card, act_filter,
                   auto, escribir, gallery, hit, qcond, rcond, with_qr)
from lib import C, chipbtn, container, ctrl, ind, label, radius

# Vista activa; «area» es la de arranque cuando varVista está vacía.
VISTA_ACTUAL = 'Coalesce(varVista, "area")'

# (control, texto, clave de vista, x, ancho)
VISTAS = [("tabTablero", "Tablero", "tablero", 32, 84), ("tabArea", "Por área", "area", 120, 88), ("tabLista", "Lista", "lista", 212, 64),
          ("tabPersona", "Por persona", "persona", 280, 108), ("tabHL", "Highlights y Lowlights", "hl", 392, 180),
          ("tabRevisar", "Por revisar", "revisar", 576, 108), ("tabHistorial", "Historial", "historial", 688, 96)]


def _switch_vista(d, por_defecto):
    return "Switch(%s, %s, %s)" % (VISTA_ACTUAL, ", ".join('"%s", %s' % (k, d[k]) for k in d), por_defecto)


def generar_pestanas():
    cur = VISTA_ACTUAL
    y = ""
    for name, text, k, x, w in VISTAS:
        p = {"Text": '"%s"' % text, "OnSelect": 'Set(varVista, "%s")' % k, "Font": "Font.'Segoe UI'", "Size": 10.5, "FontWeight": "FontWeight.Semibold",
             "Fill": C["clear"], "Color": 'If(%s = "%s", %s, %s)' % (cur, k, C["accent"], C["text2"]),
             "HoverFill": C["hov"], "HoverColor": 'If(%s = "%s", %s, %s)' % (cur, k, C["accent"], C["text"]),
             "PressedFill": C["press"], "BorderThickness": 0, "X": x, "Y": 72, "Width": w, "Height": 40}
        y += ctrl(name, "Classic/Button@2.2.0", p, 0)
    # Subrayado de la pestaña activa (la pestaña «area» es el valor por defecto del Switch)
    xs = {k: x for _, _, k, x, _ in VISTAS if k != "area"}
    ws = {k: w for _, _, k, _, w in VISTAS if k != "area"}
    y += ctrl("recTabActiva", "Rectangle@2.3.0", {
        "Fill": C["cielo"], "X": _switch_vista(xs, 120), "Y": 110, "Width": _switch_vista(ws, 88), "Height": 2}, 0)
    escribir("01b_pestanas.yaml", y)


def generar_tablero():
    """Vista Tablero: cinco columnas por estado. Tapa la vista «Por área» cuando no está activa."""
    cur = VISTA_ACTUAL
    y = ctrl("recCubre", "Rectangle@2.3.0", {"Fill": C["bg"], "X": 0, "Y": 116, "Width": "Parent.Width", "Height": "Parent.Height - 116",
                                             "Visible": '%s <> "area"' % cur, "OnSelect": "false"}, 0)
    vt = '%s = "tablero"' % cur
    cw, gap = 250, 13
    for i, (k, estado, col) in enumerate(ESTADOS):
        x = 32 + i * (cw + gap)
        y += container("conColT" + k, x, 124, cw, 632, C["cell"], 0, 10, extra={"Visible": vt})
        y += label("lblColT" + k, '"%s · " & CountRows(galT%s.AllItems)' % (estado.upper(), k), x + 12, 132, cw - 24, 20, 0, size=9, bold=True,
                   color="muted", extra={"Visible": vt})
        y += ctrl("recColT" + k, "Rectangle@2.3.0", {"Fill": col, "X": x + 12, "Y": 156, "Width": cw - 24, "Height": 2, "Visible": vt}, 0)
        items = act_filter(['Estado = "%s"' % estado], order=RANK_PRIO)
        # La galería llega casi al borde de la columna: la barra queda en ese margen, separada de las tarjetas
        y += gallery("galT" + k, items, x + 6, 164, cw - 8, 586, 80, act_card("T" + k, "tab"), extra={"Visible": vt, "OnSelect": OPEN_ACT},
                     variant="VariableHeight")
        y += label("lblVacioT" + k, '"—"', x, 168, cw, 20, 0, size=9, color="dash",
                   extra={"Visible": "%s && CountRows(galT%s.AllItems) = 0" % (vt, k), "Align": "Align.Center"})
    escribir("04_vista_tablero.yaml", y)


def generar_lista():
    """Vista Lista: encabezados clicables que ordenan (un segundo clic invierte el orden) y filas de altura flexible."""
    cur = VISTA_ACTUAL
    vl = '%s = "lista"' % cur
    y = ""
    cols = [("id", "ID", 44, 56), ("actividad", "ACTIVIDAD", 104, 360), ("area", "ÁREA", 474, 170), ("responsable", "RESPONSABLE", 654, 120),
            ("prioridad", "PRIORIDAD", 784, 74), ("estado", "ESTADO", 862, 108), ("inicio", "INICIO", 980, 90), ("status", "STATUS / BLOQUEO", 1080, 220)]
    for key, t, x, w in cols:
        act = 'varOrdenL = "%s"' % key
        p = {"Text": '"%s" & If(%s, If(Coalesce(varAscL, true), " ▲", " ▼"), "")' % (t, act),
             "OnSelect": 'If(%s, Set(varAscL, !Coalesce(varAscL, true)), Set(varOrdenL, "%s"); Set(varAscL, true)); Reset(galLista)' % (act, key),
             "Font": "Font.'Segoe UI'", "Size": 8.5, "FontWeight": "FontWeight.Bold", "Align": "Align.Left",
             "Fill": C["clear"], "Color": 'If(%s, %s, %s)' % (act, C["accent"], C["muted"]), "HoverFill": C["hov"],
             "HoverColor": C["text"], "PressedFill": C["press"], "PressedColor": C["text"], "BorderThickness": 0,
             "FocusedBorderThickness": 0, "PaddingLeft": 4, "PaddingRight": 0, "PaddingTop": 0, "PaddingBottom": 0,
             "X": x - 4, "Y": 122, "Width": w, "Height": 28, "Visible": vl}
        p.update(radius(4))
        y += ctrl("btnOrd" + key.capitalize(), "Classic/Button@2.2.0", p, 0)
    orden = 'If(Coalesce(varAscL, true), SortOrder.Ascending, SortOrder.Descending)'
    lista_items = with_qr("\n".join([
        'With(',
        '    {base: Filter(Actividades, %s, %s)},' % (qcond(ACT_COLS), rcond()),
        '    Switch(',
        '        varOrdenL,',
        '        "id", Sort(base, Right(ID, 2) & Left(ID, 4), %s),' % orden,
        '        "actividad", Sort(base, Actividad, %s),' % orden,
        '        "area", Sort(base, Coalesce(Area, "zzz"), %s),' % orden,
        '        "responsable", Sort(base, Coalesce(Responsable, "zzz"), %s),' % orden,
        '        "prioridad", Sort(base, %s, %s),' % (RANK_PRIO, orden),
        '        "estado", Sort(base, %s, %s),' % (RANK_EST, orden),
        '        "inicio", Sort(base, Coalesce(FechaInicio, "9999"), %s),' % orden,
        '        "status", Sort(base, Coalesce(StatusActual, Bloqueo, "zzz"), %s),' % orden,
        '        Sort(base, %s * 10 + %s, SortOrder.Ascending)' % (RANK_EST, RANK_PRIO),
        '    )',
        ')']))
    # Filas de altura flexible: cada una mide lo que ocupe su texto más largo; los demás datos se centran en vertical
    rh = "conFilaL.Height"

    def cy(nombre):
        return "(%s - %s.Height) / 2" % (rh, nombre)

    def cy_fijo(alto):
        return "(%s - %d) / 2" % (rh, alto)

    row = []
    row.append(container("conFilaL", 0, 0, TW, "Max(lblLAct.Height, lblLSub.Height, lblLArea.Height, 20) + 24", C["panel"], 22, 8, border=C["border"]))
    row.append(label("lblLID", "ThisItem.ID", 12, cy("lblLID"), 56, 14, 22, size=8.5, color="muted", extra=auto()))
    row.append(label("lblLAct", "ThisItem.Actividad", 72, cy("lblLAct"), 360, 16, 22, size=9, bold=True, extra=auto()))
    row.append(label("lblLArea", 'Coalesce(ThisItem.Area, "Sin área")', 442, cy("lblLArea"), 170, 16, 22, size=9, color="link", extra=auto()))
    row.append(chipbtn("btnLAv", INI, 622, cy_fijo(20), 20, 20, 'If(IsBlank(ThisItem.Responsable), %s, %s)' % (C["sinBg"], C["link"]),
                       'If(IsBlank(ThisItem.Responsable), %s, %s)' % (C["sinFg"], C["ink"]), 22, 10, size=6.5))
    row.append(label("lblLResp", 'Coalesce(ThisItem.Responsable, "Sin asignar")', 648, cy("lblLResp"), 100, 16, 22, size=9,
                     color='If(IsBlank(ThisItem.Responsable), %s, %s)' % (C["sinFg"], C["text"]), extra=auto()))
    row.append(chipbtn("btnLAlta", '"Alta"', 752, cy_fijo(18), 40, 18, C["altaBg"], C["altaFg"], 22, 9, size=7.5, extra={"Visible": 'ThisItem.Prioridad = "Alta"'}))
    row.append(label("lblLPrio", 'Coalesce(ThisItem.Prioridad, "—")', 752, cy("lblLPrio"), 70, 16, 22, size=9, color="muted",
                     extra=auto({"Visible": 'ThisItem.Prioridad <> "Alta"'})))
    row.append(chipbtn("btnLEst", "ThisItem.Estado", 830, cy_fijo(18), 96, 18, EST_FILL, EST_FG, 22, 9, size=7.5))
    row.append(label("lblLFecha", 'If(IsBlank(ThisItem.FechaInicio), "—", Text(DateValue(ThisItem.FechaInicio), "dd-mm-yyyy"))', 948, cy("lblLFecha"), 90, 16, 22,
                     size=9, color="text2", extra=auto()))
    row.append(label("lblLSub", SUB, 1048, cy("lblLSub"), 230, 16, 22, size=8.5, color=SUB_COLOR, extra=auto()))
    row.append(ctrl("btnLHit", "Classic/Button@2.2.0", hit(rh), 22))
    # Separación bajo la fila (la altura de cada elemento la define el control más bajo)
    row.append(ctrl("recSepL", "Rectangle@2.3.0", {"Fill": C["clear"], "X": 0, "Y": rh, "Width": 10, "Height": 6, "OnSelect": "false"}, 22))
    # Default = primera fila del orden actual: al reordenar, la lista vuelve arriba.
    # Ancho 1332: las filas terminan en 1334 como el resto y la barra queda en el margen derecho de la pantalla.
    y += gallery("galLista", lista_items, 32, 152, 1332, 604, 50, row, variant="VariableHeight",
                 extra={"Visible": vl, "OnSelect": OPEN_ACT, "Default": "First(\n" + ind(lista_items, 4) + "\n)"})
    y += label("lblLVacio", '"No hay actividades que coincidan con la búsqueda o el filtro."', 32, 170, 1302, 40, 0, size=11, color="muted",
               extra={"Visible": "%s && CountRows(galLista.AllItems) = 0" % vl, "Align": "Align.Center"})
    escribir("05_vista_lista.yaml", y)


def generar_persona():
    """Vista Por persona: una columna por cada una de las tres primeras personas y una de «Sin responsable»."""
    vp = '%s = "persona"' % VISTA_ACTUAL
    y = ""
    pw = 315
    for i in range(1, 5):
        x = 32 + (i - 1) * (pw + 14)
        k = "P%d" % i
        if i < 4:
            filt = 'Responsable = Index(Personas, %d).Nombre' % i
            nombre = "Index(Personas, %d).NombreCompleto" % i
            ini = "Index(Personas, %d).Iniciales" % i
            fill, fg = C["link"], C["ink"]
        else:
            filt = "IsBlank(Responsable)"
            nombre = '"Sin responsable"'
            ini = '"?"'
            fill, fg = C["sinBg"], C["sinFg"]
        y += container("conCol" + k, x, 124, pw, 632, C["cell"], 0, 10, extra={"Visible": vp})
        y += chipbtn("btnAv" + k, ini, x + 14, 136, 32, 32, fill, fg, 0, 16, size=9, extra={"Visible": vp, "OnSelect": "false"})
        y += label("lblNom" + k, nombre, x + 56, 134, pw - 70, 22, 0, size=11, bold=True, extra={"Visible": vp})
        y += label("lblCnt" + k,
                   ('CountRows(Filter(galP%d.AllItems, Estado <> "Terminada")) & " activas  ·  " & CountRows(Filter(galP%d.AllItems, Estado = "Bloqueada")) & " bloqueadas  ·  " & '
                    'CountRows(Filter(galP%d.AllItems, Estado = "Terminada")) & " terminadas"') % (i, i, i),
                   x + 56, 156, pw - 66, 16, 0, size=8, color="muted", extra={"Visible": vp})
        y += gallery("galP%d" % i, act_filter([filt], use_r=False), x + 6, 184, pw - 8, 566, 80, act_card(k, "per"),
                     extra={"Visible": vp, "OnSelect": OPEN_ACT}, variant="VariableHeight")
        y += label("lblVacio" + k, '"—"', x, 190, pw, 20, 0, size=9, color="dash",
                   extra={"Visible": "%s && CountRows(galP%d.AllItems) = 0" % (vp, i), "Align": "Align.Center"})
    escribir("06_vista_persona.yaml", y)


def generar():
    generar_pestanas()
    generar_tablero()
    generar_lista()
    generar_persona()


if __name__ == "__main__":
    generar()
