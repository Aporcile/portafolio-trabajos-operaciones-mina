# -*- coding: utf-8 -*-
"""Genera 09_vista_historial.yaml: actividades terminadas, la más reciente primero."""
from comun import ACT_COLS, INI, OPEN_ACT, TW, VERDE, auto, escribir, gallery, hit, qcond, rcond, with_qr
from lib import C, chipbtn, container, ctrl, label

FECHA = 'If(IsBlank(ThisItem.%s), "—", Text(DateValue(ThisItem.%s), "dd-mm-yyyy"))'


def generar():
    vhi = 'Coalesce(varVista, "area") = "historial"'
    y = label("lblHistTitulo", '"ACTIVIDADES TERMINADAS · " & CountRows(galHist.AllItems)', 44, 124, 500, 20, 0, size=9.5, bold=True,
              color=VERDE, extra={"Visible": vhi})
    for t, x, w in [("ID", 44, 56), ("ACTIVIDAD", 104, 330), ("ÁREA", 444, 150), ("RESPONSABLE", 604, 120), ("INICIO", 734, 90),
                    ("TÉRMINO", 834, 90), ("STATUS FINAL", 934, 370)]:
        y += label("lblHH" + t.replace("Á", "A").replace("É", "E").split()[0], '"%s"' % t, x, 150, w, 20, 0, size=8.5, bold=True, color="muted",
                   extra={"Visible": vhi})
    # Filas de altura flexible: cada una mide lo que ocupe su texto más largo y los demás datos quedan centrados
    rh = "conFilaH.Height"

    def cy(nombre):
        return "(%s - %s.Height) / 2" % (rh, nombre)

    def cy_fijo(alto):
        return "(%s - %d) / 2" % (rh, alto)

    row = [container("conFilaH", 0, 0, TW, "Max(lblHiAct.Height, lblHiSub.Height, lblHiArea.Height, 20) + 24", C["panel"], 22, 8, border=C["border"]),
           label("lblHiID", "ThisItem.ID", 12, cy("lblHiID"), 56, 14, 22, size=8.5, color="muted", extra=auto()),
           label("lblHiAct", "ThisItem.Actividad", 72, cy("lblHiAct"), 330, 16, 22, size=9, bold=True, extra=auto()),
           label("lblHiArea", 'Coalesce(ThisItem.Area, "Sin área")', 412, cy("lblHiArea"), 150, 16, 22, size=9, color="link", extra=auto()),
           chipbtn("btnHiAv", INI, 572, cy_fijo(20), 20, 20, 'If(IsBlank(ThisItem.Responsable), %s, %s)' % (C["sinBg"], C["link"]),
                   'If(IsBlank(ThisItem.Responsable), %s, %s)' % (C["sinFg"], C["ink"]), 22, 10, size=6.5),
           label("lblHiResp", 'Coalesce(ThisItem.Responsable, "Sin asignar")', 598, cy("lblHiResp"), 100, 16, 22, size=9,
                 color='If(IsBlank(ThisItem.Responsable), %s, %s)' % (C["sinFg"], C["text"]), extra=auto()),
           label("lblHiIni", FECHA % ("FechaInicio", "FechaInicio"), 702, cy("lblHiIni"), 90, 16, 22, size=9, color="text2", extra=auto()),
           label("lblHiFin", FECHA % ("FechaTermino", "FechaTermino"), 802, cy("lblHiFin"), 90, 16, 22, size=9, color=VERDE, extra=auto()),
           label("lblHiSub", 'Coalesce(ThisItem.StatusActual, ThisItem.Bloqueo, "")', 902, cy("lblHiSub"), 370, 16, 22, size=8.5, color="muted", extra=auto()),
           ctrl("btnHiHit", "Classic/Button@2.2.0", hit(rh), 22),
           ctrl("recSepH", "Rectangle@2.3.0", {"Fill": C["clear"], "X": 0, "Y": rh, "Width": 10, "Height": 6, "OnSelect": "false"}, 22)]
    items = with_qr('Sort(\n    Filter(Actividades, Estado = "Terminada", %s, %s),\n    Coalesce(FechaTermino, "0000"),\n    SortOrder.Descending\n)'
                    % (qcond(ACT_COLS), rcond()))
    y += gallery("galHist", items, 32, 174, 1332, 582, 50, row, extra={"Visible": vhi, "OnSelect": OPEN_ACT}, variant="VariableHeight")
    y += label("lblHistVacio", '"Aún no hay actividades terminadas. Cuando una pase a «Terminada» aparecerá aquí con su fecha de término."',
               32, 200, 1302, 40, 0, size=11, color="muted",
               extra={"Visible": "%s && CountRows(galHist.AllItems) = 0" % vhi, "Align": "Align.Center"})
    escribir("09_vista_historial.yaml", y)


if __name__ == "__main__":
    generar()
