# -*- coding: utf-8 -*-
"""Utilidades de los paneles de edición de Highlights/Lowlights y Por revisar (selector de fecha, guardar, eliminar)."""
from lib import C, ctrl


def dpick(name, default, x, y, n):
    p = {"DefaultDate": default, "Format": '"dd-mm-yyyy"', "InputTextPlaceholder": '"dd-mm-aaaa"', "Font": "Font.'Segoe UI'", "Size": 10,
         "Fill": C["input"], "Color": C["text"], "BorderColor": C["border"], "BorderThickness": 1,
         "IconFill": C["text2"], "IconBackground": C["input"], "DateTimeZone": "DateTimeZone.Local", "PaddingLeft": 12, "X": x, "Y": y, "Width": 324, "Height": 38}
    return ctrl(name, "Classic/DatePicker@2.6.0", p, n)


def fdate(dp):
    """Fecha del selector como texto ISO; si está vacío, la de hoy."""
    return 'If(IsBlank(%s.SelectedDate), Text(Today(), "yyyy-mm-dd"), Text(%s.SelectedDate, "yyyy-mm-dd"))' % (dp, dp)


RESP = 'If(IsBlank(%s.Selected.Nombre), "", %s.Selected.Nombre)'
SAVE_END = ('If(IsEmpty(Errors(%(t)s)), Set(%(v)s, false); Notify("%(ok)s", NotificationType.Success), '
            'Notify("No se pudo guardar: " & First(Errors(%(t)s)).Message, NotificationType.Error))')


def guardar(modo, tabla, var, reg, nom_var, texto_tema, ok):
    """Valida el tema, hace Patch (editar o crear) y avisa del resultado."""
    return "\n".join([
        "If(",
        "    IsBlank(Trim(%s.Text))," % texto_tema,
        '        Notify("Escribe el tema.", NotificationType.Error),',
        "    With(",
        "        {reg: " + reg + "},",
        '        If(%s = "editar", Patch(%s, %s, reg), Patch(%s, Defaults(%s), reg))' % (modo, tabla, nom_var, tabla, tabla),
        "    );",
        "    " + SAVE_END % {"t": tabla, "v": var, "ok": ok},
        ")"])


def eliminar(tabla, nom_var, var, ok):
    """Elimina con confirmación en dos clics (varConfirmDel)."""
    return ('If(varConfirmDel, Remove(%s, %s); Set(varConfirmDel, false); Set(%s, false); Notify("%s", NotificationType.Success), '
            'Set(varConfirmDel, true))') % (tabla, nom_var, var, ok)
