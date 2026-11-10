# -*- coding: utf-8 -*-
"""Genera 03_paneles.yaml: velo, los tres paneles de edición y los botones ocultos «reset» que los reinician."""
import panel_actividad
from comun import escribir
from lib import C, container, ctrl
from panel_highlights import pc_hl, reset_hl
from panel_revisar import pc_rev, reset_rev


def generar():
    y = ctrl("recVelo", "Rectangle@2.3.0", {"Fill": "RGBA(0, 0, 0, 0.45)", "X": 0, "Y": 0, "Width": "Parent.Width", "Height": "Parent.Height",
                                            "Visible": "varPanel || varPanelHL || varPanelRev", "OnSelect": "false"}, 0)
    sombra = {"DropShadow": "DropShadow.ExtraBold"}
    y += container("conPanel", 323, 68, 720, 632, C["panel"], 0, 12, border=C["border"], extra=dict(sombra, Visible="varPanel"), children=panel_actividad.pc)
    y += container("conPanelHL", 323, 84, 720, 600, C["panel"], 0, 12, border=C["border"], extra=dict(sombra, Visible="varPanelHL"), children=pc_hl)
    y += container("conPanelRev", 323, 149, 720, 470, C["panel"], 0, 12, border=C["border"], extra=dict(sombra, Visible="varPanelRev"), children=pc_rev)
    # Botones invisibles: las galerías y el botón «Nueva» los activan con Select() para limpiar los campos del panel
    for nm, rs in [("btnReset", panel_actividad.reset), ("btnResetHL", reset_hl), ("btnResetRev", reset_rev)]:
        y += ctrl(nm, "Classic/Button@2.2.0", {"Text": '"reset"', "OnSelect": rs, "Visible": "false", "X": 0, "Y": 0, "Width": 40, "Height": 20}, 0)
    escribir("03_paneles.yaml", y)


if __name__ == "__main__":
    generar()
