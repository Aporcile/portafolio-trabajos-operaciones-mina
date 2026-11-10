# -*- coding: utf-8 -*-
"""Panel «Nuevo / Editar registro» de Highlights y Lowlights."""
from contrato import TIPOS_HL, lista_pf
from lib import button, dropdown, field_label, label, tinput
from panel_comun import RESP, dpick, eliminar, fdate, guardar

ed = 'varModoHL = "editar"'
reg = ('{Tipo: Coalesce(ddTipoHL.Selected.Value, "Highlight"), Fecha: %s, Tema: Trim(txtTemaHL.Text), Detalle: txtDetalleHL.Text, '
       'Impacto: txtImpactoHL.Text, Accion: txtAccionHL.Text, Responsable: %s}') % (fdate("dpFechaHL"), RESP % ("ddRespHL", "ddRespHL"))
pc_hl = [
    label("lblPanelTituloHL", 'If(%s, "Editar registro", "Nuevo registro")' % ed, 24, 18, 600, 30, 10, size=13, bold=True),
    field_label("lblFTipoHL", '"Tipo"', 24, 56, 10),
    dropdown("ddTipoHL", lista_pf(TIPOS_HL), 'If(%s, varHL.Tipo, varTipoHL)' % ed, 24, 78, 10),
    field_label("lblFFechaHL", '"Fecha"', 372, 56, 10),
    dpick("dpFechaHL", 'If(%s && !IsBlank(varHL.Fecha), DateValue(varHL.Fecha), Blank())' % ed, 372, 78, 10),
    field_label("lblFTemaHL", '"Tema *"', 24, 124, 10),
    tinput("txtTemaHL", 'If(%s, varHL.Tema, "")' % ed, 24, 146, 672, 38, 10),
    field_label("lblFDetalleHL", '"Detalle"', 24, 192, 10),
    tinput("txtDetalleHL", 'If(%s, varHL.Detalle, "")' % ed, 24, 214, 672, 72, 10, multiline=True),
    field_label("lblFImpactoHL", '"Impacto"', 24, 294, 10),
    tinput("txtImpactoHL", 'If(%s, varHL.Impacto, "")' % ed, 24, 316, 672, 56, 10, multiline=True),
    field_label("lblFAccionHL", '"Acción"', 24, 380, 10),
    tinput("txtAccionHL", 'If(%s, varHL.Accion, "")' % ed, 24, 402, 672, 56, 10, multiline=True),
    field_label("lblFRespHL", '"Responsable"', 24, 466, 10),
    dropdown("ddRespHL", "ShowColumns(Personas, Nombre)", 'If(%s, varHL.Responsable, "")' % ed, 24, 488, 10),
    button("btnGuardarHL", '"Guardar"', guardar("varModoHL", "HighlightsLowlights", "varPanelHL", reg, "varHL", "txtTemaHL", "Registro guardado."),
           24, 546, 110, "primary", 10),
    button("btnCancelarHL", '"Cancelar"', "Set(varPanelHL, false); Set(varConfirmDel, false)", 144, 546, 110, "ghost", 10),
    button("btnEliminarHL", 'If(varConfirmDel, "¿Confirmar?", "Eliminar")', eliminar("HighlightsLowlights", "varHL", "varPanelHL", "Registro eliminado."),
           566, 546, 130, "danger", 10, extra={"Visible": ed}),
]
reset_hl = ("Reset(ddTipoHL); Reset(dpFechaHL); Reset(txtTemaHL); Reset(txtDetalleHL); Reset(txtImpactoHL); Reset(txtAccionHL); Reset(ddRespHL); "
            "Set(varConfirmDel, false)")
