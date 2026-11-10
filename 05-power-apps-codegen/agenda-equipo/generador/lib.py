# -*- coding: utf-8 -*-
"""Paleta de la app y constructores de YAML de Power Apps (controles, propiedades Power Fx).

Cada función devuelve texto YAML listo para pegar en Power Apps Studio. Los valores de las propiedades son fórmulas
Power Fx: el generador antepone «=» a cada una.
"""

# Paleta Minera Demo: azul medianoche en encabezado y botones principales, azul cielo y violeta solo como acentos.
# Rojo, verde y ámbar se reservan para semáforos y estados. Fondo gris claro y tarjetas blancas.
C = {
    "bg": "RGBA(245, 246, 248, 1)", "panel": "RGBA(255, 255, 255, 1)", "card": "RGBA(255, 255, 255, 1)",
    "cell": "RGBA(232, 236, 242, 1)", "input": "RGBA(255, 255, 255, 1)",
    "border": "RGBA(219, 225, 233, 1)", "border2": "RGBA(170, 182, 198, 1)",
    "text": "RGBA(33, 37, 41, 1)", "text2": "RGBA(73, 80, 87, 1)", "muted": "RGBA(108, 117, 125, 1)",
    "accent": "RGBA(27, 42, 65, 1)", "accentHover": "RGBA(44, 66, 98, 1)", "accentPress": "RGBA(18, 29, 46, 1)",
    "ink": "RGBA(255, 255, 255, 1)", "link": "RGBA(36, 100, 170, 1)",
    "alerta": "RGBA(91, 70, 168, 1)",                     # texto violeta oscuro (bloqueos), legible sobre blanco
    "altaBg": "RGBA(253, 232, 232, 1)", "altaFg": "RGBA(176, 32, 32, 1)",
    "sinBg": "RGBA(255, 243, 214, 1)", "sinFg": "RGBA(150, 100, 0, 1)",
    "dash": "RGBA(173, 181, 189, 1)", "clear": "RGBA(0, 0, 0, 0)", "rojo": "RGBA(198, 40, 40, 1)",
    "selFill": "RGBA(222, 232, 246, 1)",
    "cielo": "RGBA(79, 157, 222, 1)", "violeta": "RGBA(123, 97, 201, 1)", "verde": "RGBA(46, 125, 50, 1)",
    "chip": "RGBA(233, 236, 239, 1)",
    "hov": "RGBA(27, 42, 65, 0.06)", "press": "RGBA(27, 42, 65, 0.12)",
}


def ind(text, n):
    """Sangra n espacios cada línea no vacía."""
    pad = " " * n
    return "\n".join(pad + line if line else line for line in text.split("\n"))


def props(d, n):
    """Propiedades como «Nombre: =fórmula». Las fórmulas largas, multilínea o con «: » van en bloque literal |-."""
    lines = []
    for k, v in d.items():
        v = str(v)
        if "\n" in v or ": " in v or " #" in v or len(v) > 1000:
            lines.append(" " * n + k + ": |-")
            lines.append(ind("=" + v, n + 2))
        else:
            lines.append(" " * n + k + ": =" + v)
    return "\n".join(lines)


def ctrl(name, control, p, n, variant=None, children=None):
    """Un control: nombre, tipo@versión, propiedades y, opcionalmente, hijos ya renderizados."""
    s = " " * n + "- " + name + ":\n" + " " * (n + 4) + "Control: " + control + "\n"
    if variant:
        s += " " * (n + 4) + "Variant: " + variant + "\n"
    s += " " * (n + 4) + "Properties:\n" + props(p, n + 6) + "\n"
    if children:
        s += " " * (n + 4) + "Children:\n" + "".join(children)
    return s


def radius(r):
    return {"RadiusTopLeft": r, "RadiusTopRight": r, "RadiusBottomLeft": r, "RadiusBottomRight": r}


def label(name, text, x, y, w, h, n, size=10, color="text", bold=False, extra=None):
    p = {"Text": text, "Font": "Font.'Segoe UI'", "Size": size, "Color": C[color] if color in C else color,
         "X": x, "Y": y, "Width": w, "Height": h, "PaddingLeft": 0, "PaddingRight": 0, "PaddingTop": 0, "PaddingBottom": 0}
    if bold:
        p["FontWeight"] = "FontWeight.Bold"
    if extra:
        p.update(extra)
    return ctrl(name, "Label@2.5.1", p, n)


def chipbtn(name, text, x, y, w, h, fill, color, n, r, size=7, extra=None):
    """Botón con apariencia de chip (sin cambio al pasar el mouse); sirve de avatar, prioridad o estado."""
    p = {"Text": text, "Font": "Font.'Segoe UI'", "Size": size, "FontWeight": "FontWeight.Bold", "Fill": fill, "Color": color,
         "HoverFill": fill, "HoverColor": color, "PressedFill": fill, "PressedColor": color, "BorderThickness": 0,
         "FocusedBorderThickness": 0, "PaddingTop": 0, "PaddingBottom": 0, "PaddingLeft": 0, "PaddingRight": 0,
         "OnSelect": "Select(Parent)", "TabIndex": -1, "X": x, "Y": y, "Width": w, "Height": h}
    p.update(radius(r))
    if extra:
        p.update(extra)
    return ctrl(name, "Classic/Button@2.2.0", p, n)


def container(name, x, y, w, h, fill, n, r, border=None, extra=None, children=None):
    p = {"Fill": fill, "X": x, "Y": y, "Width": w, "Height": h, "DropShadow": "DropShadow.None"}
    p.update(radius(r))
    if border:
        p.update({"BorderColor": border, "BorderThickness": 1})
    else:
        p["BorderThickness"] = 0
    if extra:
        p.update(extra)
    return ctrl(name, "GroupContainer@1.5.0", p, n, variant="ManualLayout", children=children)


def field_label(name, text, x, y, n, w=324):
    return label(name, text, x, y, w, 20, n, size=9, color="muted")


def tinput(name, default, x, y, w, h, n, multiline=False, extra=None):
    p = {"Default": default, "Font": "Font.'Segoe UI'", "Size": 10, "Fill": C["input"], "HoverFill": C["input"], "Color": C["text"],
         "HoverColor": C["text"], "BorderColor": C["border"], "HoverBorderColor": C["border2"], "FocusedBorderColor": C["accent"],
         "BorderThickness": 1, "FocusedBorderThickness": 1, "PaddingLeft": 12, "X": x, "Y": y, "Width": w, "Height": h}
    p.update(radius(8))
    if multiline:
        p["Mode"] = "TextMode.MultiLine"
        p["PaddingTop"] = 8
    if extra:
        p.update(extra)
    return ctrl(name, "Classic/TextInput@2.3.2", p, n)


def dropdown(name, items, default, x, y, n, w=324):
    p = {"Items": items, "Default": default, "AllowEmptySelection": "true", "Font": "Font.'Segoe UI'", "Size": 10,
         "Fill": C["input"], "Color": C["text"], "HoverFill": C["cell"], "HoverColor": C["text"], "PressedFill": C["cell"],
         "PressedColor": C["text"], "SelectionFill": C["selFill"], "SelectionColor": C["accent"], "BorderColor": C["border"],
         "HoverBorderColor": C["border2"], "BorderThickness": 1, "ChevronBackground": C["input"], "ChevronFill": C["text2"],
         "ChevronHoverBackground": C["cell"], "ChevronHoverFill": C["text"], "PaddingLeft": 12, "X": x, "Y": y, "Width": w, "Height": 38}
    return ctrl(name, "Classic/DropDown@2.3.1", p, n)


def datepick(name, col, x, y, n, w=324, hoy=False):
    """Selector de fecha ligado a una columna de texto ISO de varAct.

    hoy=True: una actividad nueva parte con la fecha de hoy (editable); una existente muestra la suya o queda vacía.
    """
    default = ('If(varModo = "editar", If(IsBlank(varAct.%s), Blank(), DateValue(varAct.%s)), Today())' if hoy
               else 'If(varModo = "editar" && !IsBlank(varAct.%s), DateValue(varAct.%s), Blank())') % (col, col)
    p = {"DefaultDate": default,
         "Format": '"dd-mm-yyyy"', "InputTextPlaceholder": '"dd-mm-aaaa"', "Font": "Font.'Segoe UI'", "Size": 10,
         "Fill": C["input"], "Color": C["text"], "BorderColor": C["border"], "BorderThickness": 1,
         "IconFill": C["text2"], "IconBackground": C["input"], "DateTimeZone": "DateTimeZone.Local", "PaddingLeft": 12, "X": x, "Y": y, "Width": w, "Height": 38}
    return ctrl(name, "Classic/DatePicker@2.6.0", p, n)


def button(name, text, onselect, x, y, w, kind, n, extra=None):
    """Botón de panel: kind = primary | danger | ghost."""
    if kind == "primary":
        p = {"Fill": C["accent"], "Color": C["ink"], "HoverFill": C["accentHover"], "HoverColor": C["ink"], "PressedFill": C["accentPress"],
             "PressedColor": C["ink"], "BorderThickness": 0}
    elif kind == "danger":
        p = {"Fill": C["clear"], "Color": C["altaFg"], "HoverFill": "RGBA(198, 40, 40, 0.08)", "HoverColor": C["altaFg"],
             "PressedFill": C["altaBg"], "PressedColor": C["altaFg"], "BorderColor": C["rojo"], "HoverBorderColor": C["rojo"], "BorderThickness": 1}
    else:
        p = {"Fill": C["panel"], "Color": C["text"], "HoverFill": C["cell"], "HoverColor": C["text"], "PressedFill": C["cell"],
             "PressedColor": C["text"], "BorderColor": C["border"], "HoverBorderColor": C["border2"], "BorderThickness": 1}
    p.update({"Text": text, "OnSelect": onselect, "Font": "Font.'Segoe UI'", "Size": 10.5, "FontWeight": "FontWeight.Semibold",
              "X": x, "Y": y, "Width": w, "Height": 38})
    p.update(radius(8))
    if extra:
        p.update(extra)
    return ctrl(name, "Classic/Button@2.2.0", p, n)
