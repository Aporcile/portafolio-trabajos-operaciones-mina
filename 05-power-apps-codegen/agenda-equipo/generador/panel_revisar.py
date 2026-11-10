# -*- coding: utf-8 -*-
"""Panel «Nuevo / Editar tema por revisar»."""
from contrato import DECISIONES, lista_pf
from lib import button, dropdown, field_label, label, tinput
from panel_comun import RESP, dpick, eliminar, fdate, guardar

ed = 'varModoRev = "editar"'
reg = ('{Tema: Trim(txtTemaRev.Text), Detalle: txtDetalleRev.Text, Contraparte: txtContraRev.Text, ResponsablePropuesto: %s, '
       'Decision: Coalesce(ddDecRev.Selected.Value, "Por decidir"), Fecha: %s}') % (RESP % ("ddRespRev", "ddRespRev"), fdate("dpFechaRev"))
pc_rev = [
    label("lblPanelTituloRev", 'If(%s, "Editar tema por revisar", "Nuevo tema por revisar")' % ed, 24, 18, 600, 30, 10, size=13, bold=True),
    field_label("lblFTemaRev", '"Tema *"', 24, 56, 10),
    tinput("txtTemaRev", 'If(%s, varRev.Tema, "")' % ed, 24, 78, 672, 38, 10),
    field_label("lblFDetalleRev", '"Detalle"', 24, 124, 10),
    tinput("txtDetalleRev", 'If(%s, varRev.Detalle, "")' % ed, 24, 146, 672, 72, 10, multiline=True),
    field_label("lblFContraRev", '"Contraparte"', 24, 226, 10),
    tinput("txtContraRev", 'If(%s, varRev.Contraparte, "")' % ed, 24, 248, 324, 38, 10),
    field_label("lblFRespRev", '"Responsable propuesto"', 372, 226, 10),
    dropdown("ddRespRev", "ShowColumns(Personas, Nombre)", 'If(%s, varRev.ResponsablePropuesto, "")' % ed, 372, 248, 10),
    field_label("lblFDecRev", '"Decisión"', 24, 294, 10),
    dropdown("ddDecRev", lista_pf(DECISIONES),
             'If(%s, Coalesce(varRev.Decision, "Por decidir"), "Por decidir")' % ed, 24, 316, 10),
    field_label("lblFFechaRev", '"Fecha"', 372, 294, 10),
    dpick("dpFechaRev", 'If(%s && !IsBlank(varRev.Fecha), DateValue(varRev.Fecha), Blank())' % ed, 372, 316, 10),
    button("btnGuardarRev", '"Guardar"', guardar("varModoRev", "PorRevisar", "varPanelRev", reg, "varRev", "txtTemaRev", "Tema guardado."),
           24, 396, 110, "primary", 10),
    button("btnCancelarRev", '"Cancelar"', "Set(varPanelRev, false); Set(varConfirmDel, false)", 144, 396, 110, "ghost", 10),
    button("btnEliminarRev", 'If(varConfirmDel, "¿Confirmar?", "Eliminar")', eliminar("PorRevisar", "varRev", "varPanelRev", "Tema eliminado."),
           566, 396, 130, "danger", 10, extra={"Visible": ed}),
]
reset_rev = "Reset(txtTemaRev); Reset(txtDetalleRev); Reset(txtContraRev); Reset(ddRespRev); Reset(ddDecRev); Reset(dpFechaRev); Set(varConfirmDel, false)"
