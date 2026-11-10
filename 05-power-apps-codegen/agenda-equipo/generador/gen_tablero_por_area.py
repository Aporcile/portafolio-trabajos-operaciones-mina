# -*- coding: utf-8 -*-
"""Genera 02_tablero_por_area.yaml: una fila por área y una celda por estado.

Las filas son de altura flexible; cada celda muestra dos tarjetas, se extiende con «+N más» y se recoge con «Recoger».
"""
from comun import ESTADOS, TW, OPEN_ACT, SUB, SUB_COLOR, INI, auto, escribir, gallery, hit, qcond, rcond
from lib import C, chipbtn, container, ctrl, label, radius

CELL_X = (206, 425, 644, 863, 1082)
CELL_W = 211
PTW = "Parent.TemplateWidth"
# Status o bloqueo de una actividad escrito sobre sus propias columnas (igual que SUB, que usa ThisItem)
SUBR = 'If(Estado = "Bloqueada" && !IsBlank(Bloqueo), Bloqueo, Coalesce(StatusActual, Bloqueo, If(IsBlank(Responsable), "Sin responsable", "")))'
LABW = CELL_W - 12 - 16     # ancho del título y del status dentro de una tarjeta


def formula_items():
    """Áreas del catálogo (más «Sin área») con sus actividades filtradas y los conteos por estado."""
    cuentas = ['                Total, CountRows(Acts)'] + [
        '                n%s, CountRows(Filter(Acts, Estado = "%s"))' % (cod, nombre) for cod, nombre, _ in ESTADOS]
    return "\n".join([
        'With(',
        '    {q: Trim(txtBuscar.Text), r: ddResp.Selected.Value},',
        '    Sort(',
        '        Filter(',
        '            AddColumns(',
        '                AddColumns(',
        '                    Table(ShowColumns(Sort(Areas, Value(Orden)), Area), {Area: "Sin área"}) As a,',
        '                    Acts,',
        '                    Filter(',
        '                        Actividades As x,',
        '                        Coalesce(x.Area, "Sin área") = a.Area,',
        '                        ' + qcond(("x.Actividad", "x.ID", "x.Contraparte", "x.StatusActual", "x.Bloqueo")) + ',',
        '                        ' + rcond("x.Responsable"),
        '                    )',
        '                ),',
        ",\n".join(cuentas),
        '            ),',
        '            Total > 0',
        '        ),',
        '        Total,',
        '        SortOrder.Descending',
        '    )',
        ')'])


def clave(k):
    # Las celdas abiertas se guardan en varExp como "|<área>#<estado>|"
    return '"|" & ThisItem.Area & "#%s|"' % k


def abierta(k):
    return '(%s) in Coalesce(varExp, "")' % clave(k)


def filas(k, estado):
    """Tarjetas que muestra la celda: las 2 primeras o, si está abierta, todas."""
    return 'FirstN(Filter(ThisItem.Acts, Estado = "%s"), If(%s, 999, 2))' % (estado, abierta(k))


def tarjeta(k):
    """Tarjeta de altura flexible: título y status ocupan las líneas que necesiten."""
    n = 22
    tit, sub, tarj = "lblTTit" + k, "lblTSub" + k, "conTarj" + k
    return [container(tarj, 0, 0, PTW, "If(IsBlank(%s.Text), %s.Y + %s.Height, %s.Y + %s.Height) + 8" % (sub, tit, tit, sub, sub),
                      C["card"], n, 6, border=C["border"]),
            label("lblTID" + k, "ThisItem.ID", 8, 5, 54, 16, n, size=8, color="muted"),
            chipbtn("btnTAlta" + k, '"Alta"', 58, 6, 30, 14, C["altaBg"], C["altaFg"], n, 4, extra={"Visible": 'ThisItem.Prioridad = "Alta"'}),
            chipbtn("btnTAv" + k, INI, PTW + " - 28", 5, 20, 20, 'If(IsBlank(ThisItem.Responsable), %s, %s)' % (C["sinBg"], C["link"]),
                    'If(IsBlank(ThisItem.Responsable), %s, %s)' % (C["sinFg"], C["ink"]), n, 10, size=6.5),
            label(tit, "ThisItem.Actividad", 8, 22, PTW + " - 16", 17, n, size=9, bold=True, extra=auto()),
            label(sub, SUB, 8, "If(IsBlank(%s.Text), %s.Y, %s.Y + %s.Height + 2)" % (sub, tit, tit, tit), PTW + " - 16", 15, n, size=8,
                  color=SUB_COLOR, extra=auto({"Visible": "!IsBlank(%s.Text)" % sub})),
            ctrl("btnTHit" + k, "Classic/Button@2.2.0", hit(tarj + ".Height", w=PTW), n),
            ctrl("recSepCel" + k, "Rectangle@2.3.0", {"Fill": C["clear"], "X": 0, "Y": tarj + ".Height", "Width": 10, "Height": 6, "OnSelect": "false"}, n)]


def alto_celda(k, estado):
    """Alto de la galería de la celda = suma de sus tarjetas.

    Cada tarjeta mide 36 + las líneas de su título (+ 2 + las de su status, si lo tiene). Las líneas se miden con dos
    etiquetas ocultas (lblMedT / lblMedS) que reúnen los títulos y los status de las tarjetas visibles con el mismo ancho
    y letra, de modo que el alto no depende de la fuente.
    """
    f = filas(k, estado)
    con_sub = "CountRows(Filter(f, !IsBlank(%s)))" % SUBR
    return ("With({f: %s}, If(CountRows(f) = 0, 0, lblMedT%s.Height + If(%s = 0, 0, lblMedS%s.Height) + CountRows(f) * 36 + %s * 2 + 2))"
            % (f, k, con_sub, k, con_sub))


def generar():
    n = 10
    celdas = [(cod, nombre, x) for (cod, nombre, _), x in zip(ESTADOS, CELL_X)]
    # Las etiquetas de medida van primero (al fondo, tapadas por el panel de la fila) y con letra transparente
    medidas = []
    for k, estado, x in celdas:
        medidas.append(label("lblMedT" + k, "Concat(%s, Actividad, Char(10))" % filas(k, estado), 4, 0, LABW, 17, n, size=9, bold=True,
                             color=C["clear"], extra=auto()))
        medidas.append(label("lblMedS" + k, "Concat(Filter(%s, !IsBlank(%s)), %s, Char(10))" % (filas(k, estado), SUBR, SUBR), 4, 0, LABW, 15, n,
                             size=8, color=C["clear"], extra=auto()))
    row = medidas + [
        # Alto de la fila = la celda más alta + márgenes (14 arriba y abajo) + el botón «+N más» si alguna celda lo tiene
        container("conFila", 0, 0, TW, "Max(lblFilaB.Y + 34, %s)" % ", ".join("gal%s.Height + 28 + If(ThisItem.n%s > 2, 30, 0)" % (k, k) for k, _, _ in celdas),
                  C["panel"], n, 10, border=C["border"]),
        label("lblFilaArea", "ThisItem.Area", 16, 14, 180, 24, n, size=12, bold=True, extra={"AutoHeight": "true"}),
        label("lblFilaN", 'ThisItem.Total & If(ThisItem.Total = 1, " actividad", " actividades")', 16, "lblFilaArea.Y + lblFilaArea.Height + 2", 180, 20, n,
              size=9, color="muted"),
        label("lblFilaB", 'ThisItem.nBQ & If(ThisItem.nBQ = 1, " bloqueada", " bloqueadas")', 16, "lblFilaN.Y + 20", 180, 20, n, size=9, color="alerta",
              extra={"Visible": "ThisItem.nBQ > 0"})]
    for k, estado, x in celdas:
        # Todas las celdas de la fila toman la altura de la más alta
        row.append(container("conCelda" + k, x, 8, CELL_W, "conFila.Height - 16", C["cell"], n, 8))
        # Los Items son solo las tarjetas visibles: así no asoma el borde de la siguiente bajo la celda cerrada
        row.append(gallery("gal" + k, filas(k, estado), x + 6, 14, CELL_W - 12,
                           alto_celda(k, estado), 64, tarjeta(k), n=n, variant="VariableHeight",
                           extra={"ShowScrollbar": "false", "OnSelect": OPEN_ACT}))
        tog = {"Text": 'If(%s, "Recoger ↑", "+" & (ThisItem.n%s - 2) & " más ↓")' % (abierta(k), k),
               "OnSelect": 'With({c: %s}, Set(varExp, If(c in Coalesce(varExp, ""), Substitute(varExp, c, ""), Coalesce(varExp, "") & c)))' % clave(k),
               "Font": "Font.'Segoe UI'", "Size": 8, "FontWeight": "FontWeight.Semibold", "Align": "Align.Left",
               "Fill": C["clear"], "Color": C["link"], "HoverFill": C["hov"], "HoverColor": C["accent"],
               "PressedFill": C["press"], "PressedColor": C["text"], "BorderThickness": 0, "FocusedBorderThickness": 0,
               "PaddingLeft": 6, "PaddingRight": 6, "PaddingTop": 0, "PaddingBottom": 0,
               "X": x + 2, "Y": "gal%s.Y + gal%s.Height + 6" % (k, k), "Width": 110, "Height": 24, "Visible": "ThisItem.n%s > 2" % k}
        tog.update(radius(4))
        row.append(ctrl("btnMas" + k, "Classic/Button@2.2.0", tog, n))
        row.append(label("lblVacio" + k, '"—"', x, 16, CELL_W, 20, n, size=9, color="dash",
                         extra={"Visible": "ThisItem.n%s = 0" % k, "Align": "Align.Center"}))
    # Separación entre filas (la altura de cada fila la define el control más bajo)
    row.append(ctrl("recFilaSep", "Rectangle@2.3.0", {"Fill": C["clear"], "X": 0, "Y": "conFila.Height", "Width": 10, "Height": 8, "OnSelect": "false"}, n))

    y = gallery("galAreas", formula_items(), 32, 152, 1332, 600, 196, row, variant="VariableHeight",
                extra={"Visible": 'Coalesce(varVista, "area") = "area"'})
    y += label("lblSinResultados", '"No hay actividades que coincidan con la búsqueda o el filtro."', 32, 170, 1302, 40, 0, size=11, color="muted",
               extra={"Visible": "CountRows(galAreas.AllItems) = 0", "Align": "Align.Center"})
    escribir("02_tablero_por_area.yaml", y)


if __name__ == "__main__":
    generar()
