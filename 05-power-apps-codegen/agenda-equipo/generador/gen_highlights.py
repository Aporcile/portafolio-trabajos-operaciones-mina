# -*- coding: utf-8 -*-
"""Genera 07_vista_highlights.yaml: dos columnas (Highlights y Lowlights) con tarjetas de altura flexible."""
from comun import TW, VERDE, auto, escribir, gallery, hit, qcond, rcond, with_qr
from lib import C, button, container, ctrl, label

FECHA = 'If(IsBlank(ThisItem.Fecha), "", Text(DateValue(ThisItem.Fecha), "dd-mm-yyyy"))'


def generar():
    vh = 'Coalesce(varVista, "area") = "hl"'
    y = ""
    for tipo, x, col, titulo in [("Highlight", 32, VERDE, "HIGHLIGHTS"), ("Lowlight", 694, C["rojo"], "LOWLIGHTS")]:
        k = tipo[0]
        y += container("conColH" + k, x, 124, 640, 632, C["cell"], 0, 10, extra={"Visible": vh})
        y += label("lblColH" + k, '"%s · " & CountRows(galH%s.AllItems)' % (titulo, k), x + 16, 134, 300, 22, 0, size=9.5, bold=True, color=col, extra={"Visible": vh})
        y += button("btnAgregarH" + k, '"+ Agregar"', 'Set(varModoHL, "nuevo"); Set(varTipoHL, "%s"); Select(btnResetHL); Set(varPanelHL, true)' % tipo,
                    x + 528, 130, 96, "ghost", 0, extra={"Visible": vh, "Height": 28, "Size": 9.5})
        # Tarjeta de altura flexible: tema, detalle, impacto/acción y responsable ocupan las líneas que necesiten
        tema, det, imp, resp, tarj = "lblTemaH" + k, "lblDetH" + k, "lblImpH" + k, "lblRespH" + k, "conTarjH" + k
        card = [container(tarj, 0, 0, TW, "%s.Y + %s.Height + 10" % (resp, resp), C["card"], 22, 6, border=C["border"]),
                label("lblBarraH" + k, '""', 0, 12, 3, 20, 22, extra={"Fill": col, "Height": "%s.Height - 24" % tarj}),
                label(tema, "ThisItem.Tema", 16, 10, TW + " - 130", 20, 22, size=10.5, bold=True, extra=auto()),
                label("lblFechaH" + k, FECHA, TW + " - 100", 10, 88, 18, 22, size=8.5, color="muted", extra={"Align": "Align.Right"}),
                label(det, 'Coalesce(ThisItem.Detalle, "Sin detalle")', 16, "%s.Y + %s.Height + 4" % (tema, tema), TW + " - 32", 20, 22, size=9,
                      color='If(IsBlank(ThisItem.Detalle), %s, %s)' % (C["dash"], C["text2"]), extra=auto()),
                label(imp,
                      'If(!IsBlank(ThisItem.Impacto), "Impacto: " & ThisItem.Impacto, "") & If(!IsBlank(ThisItem.Impacto) && !IsBlank(ThisItem.Accion), Char(10), "") & '
                      'If(!IsBlank(ThisItem.Accion), "Acción: " & ThisItem.Accion, "")',
                      16, "If(IsBlank(%s.Text), %s.Y, %s.Y + %s.Height + 6)" % (imp, det, det, det), TW + " - 32", 16, 22, size=8.5,
                      color=C["alerta"] if tipo == "Lowlight" else C["link"],
                      extra=auto({"Visible": "!IsBlank(%s.Text)" % imp})),
                label(resp, 'If(IsBlank(ThisItem.Responsable), "Sin responsable", ThisItem.Responsable)', 16,
                      "If(IsBlank(%s.Text), %s.Y + %s.Height, %s.Y + %s.Height) + 6" % (imp, det, det, imp, imp), TW + " - 32", 16, 22, size=8,
                      color='If(IsBlank(ThisItem.Responsable), %s, %s)' % (C["sinFg"], C["muted"]), extra=auto()),
                ctrl("btnHitH" + k, "Classic/Button@2.2.0", hit(tarj + ".Height"), 22),
                ctrl("recSepH" + k, "Rectangle@2.3.0", {"Fill": C["clear"], "X": 0, "Y": tarj + ".Height", "Width": 10, "Height": 8, "OnSelect": "false"}, 22)]
        items = with_qr(('Sort(\n    Filter(\n        HighlightsLowlights,\n        Tipo = "%s",\n        %s,\n        %s\n    ),\n    Fecha,\n    SortOrder.Descending\n)')
                        % (tipo, qcond(("Tema", "Detalle", "Impacto", "Accion")), rcond()))
        y += gallery("galH" + k, items, x + 8, 168, 630, 582, 150, card, variant="VariableHeight",
                     extra={"Visible": vh, "OnSelect": 'Set(varHL, ThisItem); Set(varModoHL, "editar"); Select(btnResetHL); Set(varPanelHL, true)'})
        y += label("lblVacioH" + k, '"Sin registros"', x, 180, 640, 20, 0, size=9, color="dash",
                   extra={"Visible": "%s && CountRows(galH%s.AllItems) = 0" % (vh, k), "Align": "Align.Center"})
    escribir("07_vista_highlights.yaml", y)


if __name__ == "__main__":
    generar()
