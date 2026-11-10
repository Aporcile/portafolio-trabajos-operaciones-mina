# -*- coding: utf-8 -*-
"""Piezas compartidas por las vistas: rutas de salida, fórmulas reutilizables, filtros, galerías y tarjetas."""
from pathlib import Path

from contrato import ESTADOS as _ESTADOS, FILTRO_SIN_RESPONSABLE, FILTRO_TODOS
from lib import C, container, ctrl, chipbtn, ind, label, radius

# Los YAML se escriben en ../yaml respecto de esta carpeta.
SALIDA = Path(__file__).resolve().parent.parent / "yaml"

# Las tarjetas dejan 30 a la derecha: barra de desplazamiento (~15) más un espacio libre que la separa de ellas.
TW = "(Parent.TemplateWidth - 30)"
OPEN_ACT = 'Set(varAct, ThisItem); Set(varModo, "editar"); Select(btnReset); Set(varPanel, true)'
RANK_PRIO = 'Switch(Prioridad, "Alta", 1, "Media", 2, 3)'
RANK_EST = 'Switch(Estado, "Bloqueada", 1, "En curso", 2, "En revisión", 3, "Por hacer", 4, 5)'
VERDE = C["verde"]

# Línea de color bajo cada columna del Tablero, por estado.
_COLOR_LINEA = {"PH": C["dash"], "EC": C["cielo"], "ER": "RGBA(232, 170, 30, 1)", "BQ": C["violeta"], "TE": VERDE}
ESTADOS = [(cod, nombre, _COLOR_LINEA[cod]) for cod, nombre in _ESTADOS]

# Chip de estado: (fondo, texto). «Terminada» es el valor por defecto del Switch.
_CHIP = {
    "Por hacer": ("RGBA(233, 236, 239, 1)", "RGBA(73, 80, 87, 1)"),
    "En curso": ("RGBA(221, 236, 250, 1)", "RGBA(28, 88, 150, 1)"),
    "En revisión": ("RGBA(255, 243, 214, 1)", "RGBA(150, 100, 0, 1)"),
    "Bloqueada": ("RGBA(236, 231, 248, 1)", "RGBA(91, 70, 168, 1)"),
    "Terminada": ("RGBA(225, 241, 226, 1)", "RGBA(46, 125, 50, 1)"),
}


def _switch_estado(i):
    previos = [n for _, n in _ESTADOS[:-1]]
    pares = ", ".join('"%s", %s' % (n, _CHIP[n][i]) for n in previos)
    return "Switch(ThisItem.Estado, %s, %s)" % (pares, _CHIP[_ESTADOS[-1][1]][i])


EST_FILL = _switch_estado(0)
EST_FG = _switch_estado(1)

# Texto secundario de una tarjeta: motivo del bloqueo, status actual o «Sin responsable».
SUB = ('If(ThisItem.Estado = "Bloqueada" && !IsBlank(ThisItem.Bloqueo), ThisItem.Bloqueo, '
       'Coalesce(ThisItem.StatusActual, ThisItem.Bloqueo, If(IsBlank(ThisItem.Responsable), "Sin responsable", "")))')
SUB_COLOR = ('If(ThisItem.Estado = "Bloqueada" || IsBlank(ThisItem.Responsable) || (IsBlank(ThisItem.StatusActual) && !IsBlank(ThisItem.Bloqueo)), %s, %s)'
             % (C["alerta"], C["muted"]))
# Iniciales del responsable (columna Iniciales de Personas o, si falta, las dos primeras letras).
INI = ('If(IsBlank(ThisItem.Responsable), "?", Coalesce(LookUp(Personas, Nombre = ThisItem.Responsable).Iniciales, '
       'Upper(Left(ThisItem.Responsable, 2))))')


def with_qr(body):
    """Envuelve una fórmula con las variables locales q (texto de búsqueda) y r (responsable elegido)."""
    return "With(\n    {q: Trim(txtBuscar.Text), r: ddResp.Selected.Value},\n" + ind(body, 4) + "\n)"


def qcond(cols):
    return "IsBlank(q) || " + " || ".join("q in %s" % c for c in cols)


def rcond(col="Responsable"):
    return 'r = "%s" || (r = "%s" && IsBlank(%s)) || %s = r' % (FILTRO_TODOS, FILTRO_SIN_RESPONSABLE, col, col)


ACT_COLS = ("Actividad", "ID", "Area", "Contraparte", "StatusActual", "Bloqueo")


def act_filter(conds, use_r=True, order=None):
    parts = ["Actividades"] + conds + [qcond(ACT_COLS)] + ([rcond()] if use_r else [])
    f = "Filter(\n    " + ",\n    ".join(parts) + "\n)"
    order = order or "%s * 10 + %s" % (RANK_EST, RANK_PRIO)
    return with_qr("Sort(\n" + ind(f, 4) + ",\n    " + order + ",\n    SortOrder.Ascending\n)")


def hit(h, w=TW, x=0):
    """Botón transparente que cubre una tarjeta y recibe el clic."""
    p = {"Text": '""', "Fill": C["clear"], "HoverFill": "RGBA(27, 42, 65, 0.05)", "PressedFill": "RGBA(27, 42, 65, 0.10)",
         "BorderThickness": 0, "FocusedBorderThickness": 1, "FocusedBorderColor": C["link"], "OnSelect": "Select(Parent)",
         "X": x, "Y": 0, "Width": w, "Height": h}
    p.update(radius(6))
    return p


def gallery(name, items, x, y, w, h, size, children, extra=None, n=0, variant="Vertical"):
    g = {"Items": items, "X": x, "Y": y, "Width": w, "Height": h, "TemplateSize": size, "TemplatePadding": 0, "ShowScrollbar": "true",
         "Fill": C["clear"], "TemplateFill": C["clear"], "BorderThickness": 0}
    if extra:
        g.update(extra)
    return ctrl(name, "Gallery@2.15.0", g, n, variant=variant, children=children)


def auto(extra=None):
    """Etiqueta de altura automática: ocupa las líneas que necesite su texto, sin cortarlo."""
    d = {"AutoHeight": "true"}
    if extra:
        d.update(extra)
    return d


def act_card(pref, variant):
    """Tarjeta de actividad para galerías de altura flexible (variant: «tab» = tablero, otro = persona)."""
    n = 22
    tit, area_l, sub, tarj = "lblTit" + pref, "lblArea" + pref, "lblSub" + pref, "conTarj" + pref
    alto = "If(IsBlank(%s.Text), %s.Y + %s.Height, %s.Y + %s.Height) + 8" % (sub, area_l, area_l, sub, sub)
    c = [container(tarj, 0, 0, TW, alto, C["card"], n, 6, border=C["border"]),
         label("lblID" + pref, "ThisItem.ID", 8, 6, 54, 16, n, size=8, color="muted"),
         chipbtn("btnAlta" + pref, '"Alta"', 58, 7, 30, 14, C["altaBg"], C["altaFg"], n, 4, extra={"Visible": 'ThisItem.Prioridad = "Alta"'})]
    if variant == "tab":
        c.append(chipbtn("btnAv" + pref, INI, TW + " - 30", 5, 22, 22,
                         'If(IsBlank(ThisItem.Responsable), %s, %s)' % (C["sinBg"], C["link"]),
                         'If(IsBlank(ThisItem.Responsable), %s, %s)' % (C["sinFg"], C["ink"]), n, 11, size=6.5))
        area = 'Coalesce(ThisItem.Area, "Sin área") & If(IsBlank(ThisItem.Responsable), "", "  ·  " & ThisItem.Responsable)'
    else:
        c.append(chipbtn("btnEst" + pref, "ThisItem.Estado", TW + " - 88", 6, 80, 16, EST_FILL, EST_FG, n, 8, size=7))
        area = 'Coalesce(ThisItem.Area, "Sin área")'
    c.append(label(tit, "ThisItem.Actividad", 8, 24, TW + " - 16", 16, n, size=9, bold=True, extra=auto()))
    c.append(label(area_l, area, 8, "%s.Y + %s.Height + 1" % (tit, tit), TW + " - 16", 14, n, size=8, color="link", extra=auto()))
    # Sin status ni bloqueo, la línea se oculta y se sube a la del área: la tarjeta no deja hueco ni sobresale.
    c.append(label(sub, SUB, 8, "If(IsBlank(%s.Text), %s.Y, %s.Y + %s.Height + 1)" % (sub, area_l, area_l, area_l), TW + " - 16", 14, n, size=8,
                   color=SUB_COLOR, extra=auto({"Visible": "!IsBlank(%s.Text)" % sub})))
    c.append(ctrl("btnHit" + pref, "Classic/Button@2.2.0", hit(tarj + ".Height"), n))
    # Separación bajo la tarjeta (la altura de cada elemento la define el control más bajo).
    c.append(ctrl("recSep" + pref, "Rectangle@2.3.0", {"Fill": C["clear"], "X": 0, "Y": tarj + ".Height", "Width": 10, "Height": 8,
                                                       "OnSelect": "false"}, n))
    return c


def escribir(nombre, texto):
    """Escribe un YAML en la carpeta de salida (UTF-8, saltos de línea LF)."""
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / nombre).write_text(texto, encoding="utf-8", newline="\n")
    print(f"{nombre}: {len(texto.encode('utf-8')):,} bytes")
