# -*- coding: utf-8 -*-
"""Genera 08_vista_revisar.yaml: temas por decidir (con acciones Crear / Posponer / Descartar) y temas ya resueltos."""
from comun import TW, VERDE, auto, escribir, gallery, hit, qcond, rcond, with_qr
from lib import C, button, chipbtn, container, ctrl, label

META = ('If(IsBlank(ThisItem.Contraparte), "", "Contraparte: " & ThisItem.Contraparte & "  ·  ") & "Propone: " & Coalesce(ThisItem.ResponsablePropuesto, "sin asignar") & '
        'If(IsBlank(ThisItem.Fecha), "", "  ·  " & Text(DateValue(ThisItem.Fecha), "dd-mm-yyyy"))')
# Cambia la decisión y avisa del resultado (o del error devuelto por la fuente de datos)
ACC = ('Patch(PorRevisar, ThisItem, {Decision: "%s"}); If(IsEmpty(Errors(PorRevisar)), Notify("%s", NotificationType.Information), '
       'Notify("No se pudo actualizar: " & First(Errors(PorRevisar)).Message, NotificationType.Error))')
# Crea una actividad a partir del tema, marca el tema como «Aprobado» y abre el panel de edición para completar el resto
CREAR = "\n".join([
    'With(',
    '    {',
    '        nueva: Patch(',
    '            Actividades,',
    '            Defaults(Actividades),',
    '            {',
    '                ID: lblNextID.Text,',
    '                Area: "",',
    '                Actividad: ThisItem.Tema,',
    '                Descripcion: Coalesce(ThisItem.Detalle, ""),',
    '                Responsable: Coalesce(ThisItem.ResponsablePropuesto, ""),',
    '                Contraparte: Coalesce(ThisItem.Contraparte, ""),',
    '                Prioridad: "",',
    '                Estado: "Por hacer",',
    '                FechaInicio: Text(Today(), "yyyy-mm-dd"),',
    '                FechaCompromiso: "",',
    '                FechaTermino: "",',
    '                StatusActual: "Creada desde Por revisar el " & Text(Today(), "dd-mm-yyyy"),',
    '                Bloqueo: ""',
    '            }',
    '        )',
    '    },',
    '    If(',
    '        IsEmpty(Errors(Actividades)),',
    '            Patch(PorRevisar, ThisItem, {Decision: "Aprobado"});',
    '            Set(varAct, nueva); Set(varModo, "editar"); Select(btnReset); Set(varPanel, true);',
    '            Notify("Actividad creada. Completa área, prioridad y fechas.", NotificationType.Success),',
    '            Notify("No se pudo crear la actividad: " & First(Errors(Actividades)).Message, NotificationType.Error)',
    '    )',
    ')'])


def generar():
    vr = 'Coalesce(varVista, "area") = "revisar"'
    open_rev = 'Set(varRev, ThisItem); Set(varModoRev, "editar"); Select(btnResetRev); Set(varPanelRev, true)'
    rq = qcond(("Tema", "Detalle", "Contraparte"))
    y = ""
    y += container("conColRevA", 32, 124, 800, 632, C["cell"], 0, 10, extra={"Visible": vr})
    y += label("lblColRevA", '"POR DECIDIR · " & CountRows(galRevA.AllItems)', 48, 134, 400, 22, 0, size=9.5, bold=True, color=C["sinFg"], extra={"Visible": vr})
    y += button("btnAgregarRev", '"+ Agregar tema"', 'Set(varModoRev, "nuevo"); Select(btnResetRev); Set(varPanelRev, true)', 696, 130, 124, "ghost", 0,
                extra={"Visible": vr, "Height": 28, "Size": 9.5})
    # Tarjetas de altura flexible: tema, detalle y meta ocupan las líneas que necesiten (mínimo 90 por los botones de la derecha)
    card = [container("conTarjRevA", 0, 0, TW, "Max(lblMetaRevA.Y + lblMetaRevA.Height + 10, 90)", C["card"], 22, 6, border=C["border"]),
            label("lblTemaRevA", "ThisItem.Tema", 14, 8, TW + " - 330", 20, 22, size=10.5, bold=True, extra=auto()),
            label("lblDetRevA", 'Coalesce(ThisItem.Detalle, "Sin detalle")', 14, "lblTemaRevA.Y + lblTemaRevA.Height + 3", TW + " - 330", 16, 22, size=9,
                  color='If(IsBlank(ThisItem.Detalle), %s, %s)' % (C["dash"], C["text2"]), extra=auto()),
            label("lblMetaRevA", META, 14, "lblDetRevA.Y + lblDetRevA.Height + 5", TW + " - 330", 16, 22, size=8, color="muted", extra=auto()),
            ctrl("btnHitRevA", "Classic/Button@2.2.0", hit("conTarjRevA.Height", w=TW + " - 310"), 22)]
    card.append(button("btnCrearRev", '"Crear actividad"', CREAR, TW + " - 296", 10, 158, "primary", 22, extra={"Height": 30, "Size": 9.5}))
    card.append(button("btnDescartarRev", '"Descartar"', ACC % ("Descartado", "Tema descartado."), TW + " - 130", 10, 116, "ghost", 22, extra={"Height": 30, "Size": 9.5}))
    card.append(button("btnPosponerRev", '"Posponer"', ACC % ("Pospuesto", "Tema pospuesto."), TW + " - 296", 50, 158, "ghost", 22, extra={"Height": 28, "Size": 9.5}))
    card.append(ctrl("recSepRevA", "Rectangle@2.3.0", {"Fill": C["clear"], "X": 0, "Y": "conTarjRevA.Height", "Width": 10, "Height": 8, "OnSelect": "false"}, 22))
    items = with_qr('Filter(\n    PorRevisar,\n    Coalesce(Decision, "Por decidir") = "Por decidir",\n    %s,\n    %s\n)' % (rq, rcond("ResponsablePropuesto")))
    y += gallery("galRevA", items, 38, 168, 792, 582, 98, card, extra={"Visible": vr, "OnSelect": open_rev}, variant="VariableHeight")
    y += label("lblVacioRevA", '"No hay temas por decidir."', 32, 190, 800, 20, 0, size=9, color="dash",
               extra={"Visible": "%s && CountRows(galRevA.AllItems) = 0" % vr, "Align": "Align.Center"})

    y += container("conColRevB", 846, 124, 488, 632, C["cell"], 0, 10, extra={"Visible": vr})
    y += label("lblColRevB", '"RESUELTOS · " & CountRows(galRevB.AllItems)', 862, 134, 300, 22, 0, size=9.5, bold=True, color=VERDE, extra={"Visible": vr})
    chip_fill = 'Switch(ThisItem.Decision, "Aprobado", RGBA(225, 241, 226, 1), "Pospuesto", %s, %s)' % (C["sinBg"], C["chip"])
    chip_fg = 'Switch(ThisItem.Decision, "Aprobado", %s, "Pospuesto", %s, %s)' % (VERDE, C["sinFg"], C["text2"])
    card = [container("conTarjRevB", 0, 0, TW, "If(IsBlank(lblDetRevB.Text), lblMetaRevB.Y + lblMetaRevB.Height, lblDetRevB.Y + lblDetRevB.Height) + 10",
                      C["card"], 22, 6, border=C["border"]),
            label("lblTemaRevB", "ThisItem.Tema", 12, 8, TW + " - 120", 20, 22, size=9.5, bold=True, extra=auto()),
            chipbtn("btnDecRevB", "ThisItem.Decision", TW + " - 100", 9, 88, 18, chip_fill, chip_fg, 22, 9, size=7.5),
            label("lblMetaRevB", META, 12, "lblTemaRevB.Y + lblTemaRevB.Height + 3", TW + " - 24", 16, 22, size=8, color="muted", extra=auto()),
            label("lblDetRevB", 'Coalesce(ThisItem.Detalle, "")', 12, "If(IsBlank(lblDetRevB.Text), lblMetaRevB.Y, lblMetaRevB.Y + lblMetaRevB.Height + 3)",
                  TW + " - 24", 16, 22, size=8, color=C["text2"],
                  extra=auto({"Visible": "!IsBlank(lblDetRevB.Text)"})),
            ctrl("btnHitRevB", "Classic/Button@2.2.0", hit("conTarjRevB.Height"), 22),
            ctrl("recSepRevB", "Rectangle@2.3.0", {"Fill": C["clear"], "X": 0, "Y": "conTarjRevB.Height", "Width": 10, "Height": 8, "OnSelect": "false"}, 22)]
    items = with_qr('Filter(\n    PorRevisar,\n    Coalesce(Decision, "Por decidir") <> "Por decidir",\n    %s,\n    %s\n)' % (rq, rcond("ResponsablePropuesto")))
    y += gallery("galRevB", items, 852, 168, 480, 582, 78, card, extra={"Visible": vr, "OnSelect": open_rev}, variant="VariableHeight")
    y += label("lblVacioRevB", '"Aquí aparecen los temas ya decididos."', 846, 190, 488, 20, 0, size=9, color="dash",
               extra={"Visible": "%s && CountRows(galRevB.AllItems) = 0" % vr, "Align": "Align.Center"})
    escribir("08_vista_revisar.yaml", y)


if __name__ == "__main__":
    generar()
