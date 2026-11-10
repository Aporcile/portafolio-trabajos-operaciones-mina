# -*- coding: utf-8 -*-
"""Panel «Editar / Nueva actividad». El ID no se edita: una actividad nueva toma el siguiente correlativo al guardar y una
existente conserva el suyo."""
from contrato import ESTADOS, PRIORIDADES, lista_pf
from ids import NEXT_ID
from lib import C, button, datepick, dropdown, field_label, label, tinput

ed = 'varModo = "editar"'

guardar = "\n".join([
    'With(',
    '    {nid: If(varModo = "editar", varAct.ID, lblNextID.Text)},',
    '    If(',
    '        IsBlank(Trim(txtActividad.Text)),',
    '            Notify("Escribe el nombre de la actividad.", NotificationType.Error),',
    '        ddEstado.Selected.Value = "Bloqueada" && IsBlank(Trim(txtBloqueo.Text)),',
    '            Notify("Una actividad bloqueada necesita el motivo en «Bloqueo / dependencia».", NotificationType.Error),',
    '        varModo = "nuevo" && !IsBlank(LookUp(Actividades, Lower(Trim(Actividad)) = Lower(Trim(txtActividad.Text)), ID)),',
    '            Notify("Ya existe una actividad con ese nombre. Búscala antes de crear otra.", NotificationType.Warning),',
    '        With(',
    '            {',
    '                reg: {',
    '                    ID: nid,',
    '                    Area: If(IsBlank(ddArea.Selected.Area), "", ddArea.Selected.Area),',
    '                    Actividad: Trim(txtActividad.Text),',
    '                    Descripcion: txtDescripcion.Text,',
    '                    Responsable: If(IsBlank(ddResponsable.Selected.Nombre), "", ddResponsable.Selected.Nombre),',
    '                    Contraparte: txtContraparte.Text,',
    '                    Prioridad: If(IsBlank(ddPrioridad.Selected.Value), "", ddPrioridad.Selected.Value),',
    '                    Estado: Coalesce(ddEstado.Selected.Value, "Por hacer"),',
    '                    FechaInicio: If(IsBlank(dpInicio.SelectedDate), "", Text(dpInicio.SelectedDate, "yyyy-mm-dd")),',
    '                    FechaTermino: If(',
    '                        !IsBlank(dpTermino.SelectedDate), Text(dpTermino.SelectedDate, "yyyy-mm-dd"),',
    '                        ddEstado.Selected.Value = "Terminada", Text(Today(), "yyyy-mm-dd"),',
    '                        ""',
    '                    ),',
    '                    StatusActual: txtStatus.Text,',
    '                    Bloqueo: txtBloqueo.Text',
    '                }',
    '            },',
    '            If(varModo = "editar", Patch(Actividades, varAct, reg), Patch(Actividades, Defaults(Actividades), reg))',
    '        );',
    '        If(',
    '            IsEmpty(Errors(Actividades)),',
    '                Set(varPanel, false); Notify("Actividad guardada.", NotificationType.Success),',
    '                Notify("No se pudo guardar: " & First(Errors(Actividades)).Message, NotificationType.Error)',
    '        )',
    '    )',
    ')'])

eliminar = ('If(varConfirmDel, Remove(Actividades, varAct); Set(varConfirmDel, false); Set(varPanel, false); '
            'Notify("Actividad eliminada.", NotificationType.Success), Set(varConfirmDel, true))')

reset = ("Reset(txtID); Reset(txtActividad); Reset(txtDescripcion); Reset(ddArea); Reset(ddResponsable); Reset(txtContraparte); "
         "Reset(ddPrioridad); Reset(ddEstado); Reset(dpInicio); Reset(dpTermino); Reset(txtStatus); Reset(txtBloqueo); Set(varConfirmDel, false)")

pc = [
    # Al editar, el título es solo el nombre de la actividad
    label("lblPanelTitulo", 'If(%s, varAct.Actividad, "Nueva actividad")' % ed, 24, 18, 672, 30, 10, size=13, bold=True, extra={"Wrap": "false"}),
    label("lblNextID", NEXT_ID, 0, 0, 10, 10, 10, size=8, extra={"Visible": "false"}),
    field_label("lblFID", '"ID (automático)"', 24, 56, 10, w=140),
    # Solo lectura: muestra el ID de la actividad o, si es nueva, el que va a recibir
    tinput("txtID", 'If(%s, varAct.ID, lblNextID.Text)' % ed, 24, 78, 140, 38, 10,
           extra={"DisplayMode": "DisplayMode.Disabled", "DisabledFill": C["bg"], "DisabledColor": C["text2"], "DisabledBorderColor": C["border"]}),
    field_label("lblFActividad", '"Actividad *"', 176, 56, 10, w=520),
    tinput("txtActividad", 'If(%s, varAct.Actividad, "")' % ed, 176, 78, 520, 38, 10),
    field_label("lblFDescripcion", '"Descripción / alcance"', 24, 124, 10),
    tinput("txtDescripcion", 'If(%s, varAct.Descripcion, "")' % ed, 24, 146, 672, 56, 10, multiline=True),
    field_label("lblFArea", '"Área"', 24, 210, 10),
    # Las áreas se ofrecen en orden alfabético
    dropdown("ddArea", "ShowColumns(Sort(Areas, Area), Area)", 'If(%s, varAct.Area, "")' % ed, 24, 232, 10),
    field_label("lblFResponsable", '"Responsable (uno solo)"', 372, 210, 10),
    dropdown("ddResponsable", "ShowColumns(Personas, Nombre)", 'If(%s, varAct.Responsable, "")' % ed, 372, 232, 10),
    field_label("lblFContraparte", '"Contraparte / externos"', 24, 278, 10),
    tinput("txtContraparte", 'If(%s, varAct.Contraparte, "")' % ed, 24, 300, 324, 38, 10),
    field_label("lblFPrioridad", '"Prioridad"', 372, 278, 10),
    dropdown("ddPrioridad", lista_pf(PRIORIDADES), 'If(%s, varAct.Prioridad, "")' % ed, 372, 300, 10),
    field_label("lblFEstado", '"Estado"', 24, 346, 10, w=208),
    dropdown("ddEstado", lista_pf([nombre for _, nombre in ESTADOS]),
             'If(%s, varAct.Estado, "Por hacer")' % ed, 24, 368, 10, w=208),
    field_label("lblFInicio", '"Fecha inicio"', 248, 346, 10, w=208),
    datepick("dpInicio", "FechaInicio", 248, 368, 10, w=208, hoy=True),
    field_label("lblFTermino", '"Fecha término"', 472, 346, 10, w=224),
    datepick("dpTermino", "FechaTermino", 472, 368, 10, w=224),
    field_label("lblFStatus", '"Status actual / pendientes"', 24, 414, 10),
    tinput("txtStatus", 'If(%s, varAct.StatusActual, "")' % ed, 24, 436, 672, 56, 10, multiline=True),
    label("lblFBloqueo", '"Bloqueo / dependencia" & If(ddEstado.Selected.Value = "Bloqueada", " *", "")', 24, 500, 400, 20, 10, size=9,
          color='If(ddEstado.Selected.Value = "Bloqueada", %s, %s)' % (C["alerta"], C["muted"])),
    tinput("txtBloqueo", 'If(%s, varAct.Bloqueo, "")' % ed, 24, 522, 672, 44, 10, multiline=True),
    button("btnGuardar", '"Guardar"', guardar, 24, 576, 110, "primary", 10),
    button("btnCancelar", '"Cancelar"', "Set(varPanel, false); Set(varConfirmDel, false)", 144, 576, 110, "ghost", 10),
    button("btnEliminar", 'If(varConfirmDel, "¿Confirmar?", "Eliminar")', eliminar, 566, 576, 130, "danger", 10, extra={"Visible": ed}),
]
