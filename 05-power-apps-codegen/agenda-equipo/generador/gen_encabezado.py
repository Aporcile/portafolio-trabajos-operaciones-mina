# -*- coding: utf-8 -*-
"""Genera 01_encabezado.yaml: fondo, franja superior con logos, resumen, botones, filtros y títulos de columna de «Por área»."""
import base64
from pathlib import Path

from comun import escribir
from contrato import ESTADOS, FILTRO_SIN_RESPONSABLE, FILTRO_TODOS, PERSONAS, lista_pf
from lib import C, ctrl, dropdown, label, radius, tinput

LOGOS = Path(__file__).resolve().parent / "logos"
BLANCO = "RGBA(255, 255, 255, 1)"
CLARO = "RGBA(205, 218, 235, 1)"        # texto secundario sobre la franja oscura
RESALTE_HTML = "#b8a8f0"                # violeta claro: legible sobre el azul medianoche
TEXTO_HTML = "#cddaeb"


def data_uri(archivo):
    """Los logos van incrustados como data URI: no hay que subirlos a Multimedia de Studio."""
    b64 = base64.b64encode((LOGOS / archivo).read_bytes()).decode()
    return '"data:image/png;base64,%s"' % b64


def imagen(name, archivo, x, y, w, h):
    return ctrl(name, "Image@2.2.3", {"Image": data_uri(archivo), "ImagePosition": "ImagePosition.Fit", "X": x, "Y": y, "Width": w, "Height": h}, 0)


def generar():
    y = ctrl("recFondo", "Rectangle@2.3.0", {"Fill": C["bg"], "X": 0, "Y": 0, "Width": "Parent.Width", "Height": "Parent.Height"}, 0)
    y += ctrl("recEncabezado", "Rectangle@2.3.0", {"Fill": C["accent"], "X": 0, "Y": 0, "Width": "Parent.Width", "Height": 64}, 0)
    # Logo corporativo ficticio (blanco, para fondo oscuro) y, al lado, el ícono del área
    y += imagen("imgLogoEmpresa", "logo_minera_demo_blanco.png", 24, 12, 150, 40)
    y += imagen("imgLogoArea", "icono_minera_demo.png", 190, 10, 44, 44)
    y += label("lblTitulo", '"Agenda del equipo"', 250, 12, 190, 40, 0, size=16, bold=True, color=BLANCO)
    y += label("lblPuntoVivo", '""', 444, 28, 8, 8, 0, extra={"Fill": "RGBA(76, 195, 138, 1)"})
    y += label("lblEnVivo", '"En vivo"', 456, 18, 60, 28, 0, size=9, color=CLARO, extra={"PaddingLeft": 2})
    y += ctrl("htmlResumen", "HtmlViewer@2.1.0", {
        "HtmlText": "\n".join([
            "\"<div style='font-family:Segoe UI,sans-serif;font-size:13px;color:%s'>\" &" % TEXTO_HTML,
            'CountRows(Filter(Actividades, Estado <> "Terminada")) & " activas · " &',
            "\"<b style='color:%s'>\" & CountRows(Filter(Actividades, Estado = \"Bloqueada\")) & \" bloqueadas</b> · \" &" % RESALTE_HTML,
            "\"<b style='color:%s'>\" & CountRows(Filter(Actividades, IsBlank(Responsable) && Estado <> \"Terminada\")) & \" sin responsable</b> · \" &" % RESALTE_HTML,
            'CountRows(Filter(PorRevisar, Decision = "Por decidir")) & " por revisar</div>"']),
        "X": 524, "Y": 15, "Width": 486, "Height": 34, "PaddingTop": 6, "PaddingLeft": 0}, 0)
    act = {"Text": '"↻  Actualizar"', "OnSelect": "Refresh(Actividades); Refresh(PorRevisar); Refresh(Areas); Refresh(Personas)",
           "Font": "Font.'Segoe UI'", "Size": 10, "FontWeight": "FontWeight.Semibold", "Fill": "RGBA(255, 255, 255, 0.08)", "Color": BLANCO,
           "HoverFill": "RGBA(255, 255, 255, 0.16)", "HoverColor": BLANCO, "PressedFill": "RGBA(255, 255, 255, 0.24)", "PressedColor": BLANCO,
           "BorderColor": "RGBA(255, 255, 255, 0.35)", "HoverBorderColor": "RGBA(255, 255, 255, 0.6)", "BorderThickness": 1,
           "X": 1018, "Y": 12, "Width": 134, "Height": 40}
    act.update(radius(8))
    y += ctrl("btnActualizar", "Classic/Button@2.2.0", act, 0)
    nva = {"Text": '"+ Nueva actividad"', "OnSelect": 'Set(varModo, "nuevo"); Set(varAct, Blank()); Select(btnReset); Set(varPanel, true)',
           "Font": "Font.'Segoe UI'", "Size": 11, "FontWeight": "FontWeight.Semibold", "Fill": BLANCO, "Color": C["accent"],
           "HoverFill": C["selFill"], "HoverColor": C["accent"], "PressedFill": "RGBA(200, 215, 238, 1)", "PressedColor": C["accent"],
           "BorderThickness": 0, "X": 1164, "Y": 12, "Width": 170, "Height": 40}
    nva.update(radius(8))
    y += ctrl("btnNueva", "Classic/Button@2.2.0", nva, 0)
    y += ctrl("recLineaTabs", "Rectangle@2.3.0", {"Fill": C["border"], "X": 32, "Y": 112, "Width": 1302, "Height": 1}, 0)
    y += tinput("txtBuscar", '""', 898, 74, 220, 34, 0, extra={"HintText": '"Buscar…"', "DelayOutput": "true", "FocusedBorderColor": C["accent"]})
    # El filtro de responsable lista a las personas del contrato más las dos opciones fijas
    responsables = [FILTRO_TODOS] + [p["Nombre"] for p in PERSONAS] + [FILTRO_SIN_RESPONSABLE]
    y += dropdown("ddResp", lista_pf(responsables), '"%s"' % FILTRO_TODOS, 1126, 74, 0,
                  w=208).replace("Height: =38", "Height: =34").replace("AllowEmptySelection: =true", "AllowEmptySelection: =false")
    # Títulos de columna de la vista «Por área» (recCubre los tapa en las demás vistas)
    titulos = [("lblColArea", '"ÁREA"', 32)]
    for (cod, estado), x in zip(ESTADOS, (238, 457, 676, 895, 1114)):
        titulos.append(("lblCol" + cod, '"%s · " & CountRows(Filter(Actividades, Estado = "%s"))' % (estado.upper(), estado), x))
    for name, texto, x in titulos:
        y += label(name, texto, x, 124, 190 if name == "lblColArea" else 211, 24, 0, size=9, bold=True, color="muted")
    escribir("01_encabezado.yaml", y)


if __name__ == "__main__":
    generar()
