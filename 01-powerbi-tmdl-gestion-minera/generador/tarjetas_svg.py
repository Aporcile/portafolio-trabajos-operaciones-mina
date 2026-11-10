# -*- coding: utf-8 -*-
"""
Generador de tarjetas KPI en SVG como medidas DAX.

Una visual de tabla con una medida de categoría `ImageUrl` pinta el SVG que devuelve la medida (data URI). Escribir cada
tarjeta a mano es repetitivo: este módulo genera el cuerpo DAX de la tarjeta «bullet» del día (real, proyección y plan en
una barra de tres capas) y reescribe las medidas dentro de `dax_kpi_tabla.tmdl`.

Las tarjetas que genera hoy:
  Rd SVG Movimiento   real [Movimiento]                   plan [PlanSemanal Movimiento mina CAEX]
  Rd SVG Ampliacion        real [Extraccion Mina (Ex- Pit)]    plan [PlanSemanal Ampliacion]
  Rd SVG Remanejo     real [Remanejo]                     plan [PlanSemanal Remanejo]

Anatomía de la barra (de atrás hacia adelante):
  1) contenedor gris: la meta (plan del día = 100 % del ancho);
  2) barra delgada, desde el real hasta la proyección a 24 h (solo en el día en curso);
  3) barra gruesa: el real acumulado, con color de semáforo (verde si la proyección alcanza el plan, rojo si no;
     azul si el día no tiene plan).
Debajo: tres valores (real del día, proyección, plan).

    python generador/tarjetas_svg.py                 # simulación: dice qué medidas cambiarían
    python generador/tarjetas_svg.py --aplicar       # escribe (Power BI Desktop debe estar cerrado)
    python generador/tarjetas_svg.py --raiz RUTA     # otra copia del proyecto
"""
import argparse
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from escritura_segura import escribir  # noqa: E402
from guardia_desktop import desktop_abierto  # noqa: E402

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent

# Paleta Minera Demo y semáforo (verde cumple, ámbar cerca, rojo lejos, gris sin dato)
PALETA = {
    "acento": "#4F9DDE",        # sin plan: no hay semáforo
    "acento_claro": "#8EC3EE",  # proyección con el día en curso
    "verde": "#2ECC71",
    "rojo": "#E74C3C",
    "meta_relleno": "#3F464D",
    "meta_borde": "#4A545E",
    "meta_marca": "#E6E6E6",
    "texto": "#FFFFFF",
    "texto_valor": "#E6E6E6",
    "texto_unidad": "#9AA5B1",
    "texto_rotulo": "#7F8C99",
    "sin_dato": "#5D6B7A",
}

# nombre de la medida -> (medida real, medida plan, tamaño del número, tamaño de la unidad)
TARJETAS = {
    "Rd SVG Movimiento": ("[Movimiento]", "[PlanSemanal Movimiento mina CAEX]", 52, 30),
    "Rd SVG Ampliacion": ("[Extraccion Mina (Ex- Pit)]", "[PlanSemanal Ampliacion]", 46, 28),
    "Rd SVG Remanejo": ("[Remanejo]", "[PlanSemanal Remanejo]", 46, 28),
}

FUENTE = "Segoe UI Semibold, Segoe UI"
FUENTE_NORMAL = "Segoe UI"


def _texto(x, y, tam, color, cuerpo, ancla=None, semibold=False, peso=None):
    a = f" text-anchor='{ancla}'" if ancla else ""
    fam = FUENTE if semibold else FUENTE_NORMAL
    p = f" font-weight='{peso}'" if peso else ""
    return f"<text x='{x}' y='{y}'{a} font-family='{fam}' font-size='{tam}'{p} fill='{color}'>{cuerpo}</text>"


def cuerpo_bullet(real, plan, tam_num=46, tam_uni=28, p=PALETA):
    """Cuerpo DAX (sin sangría base) de la tarjeta bullet del día. `real` y `plan` son medidas entre corchetes."""
    L = [
        "VAR _d = [Rd Día]",
        f"VAR _real = CALCULATE ( {real}, Calendario[Fecha] = _d )",
        "VAR _proy = _real * [Rd Factor Proyección]",
        f"VAR _plan = CALCULATE ( {plan}, Calendario[Fecha] = _d )",
        "VAR _curso = [Rd Día En Curso]",
        'VAR _num = FORMAT ( _real / 1000, "#,0.0" )',
        'VAR _uni = "mil"',
        "VAR _W = 322",
        "VAR _H = 16",
        "VAR _Y = 57",
        "VAR _tope = MAX ( MAX ( _plan, _proy ), MAX ( _real, 1 ) )",
        "VAR _esc = DIVIDE ( _W, _tope )",
        "VAR _wPlan = ROUND ( _plan * _esc, 0 )",
        "VAR _wReal = ROUND ( _real * _esc, 0 )",
        "VAR _wProy = ROUND ( _proy * _esc, 0 )",
        "VAR _hayPlan = NOT ISBLANK ( _plan ) && _plan > 0",
        f'VAR _color = IF ( NOT _hayPlan, "{p["acento"]}", IF ( _proy >= _plan, "{p["verde"]}", "{p["rojo"]}" ) )',
        'VAR _vProy = IF ( _curso, FORMAT ( _proy / 1000, "#,0.0" ) & " mil", "—" )',
        'VAR _vPlan = IF ( NOT _hayPlan, "Sin plan", FORMAT ( _plan / 1000, "#,0.0" ) & " mil" )',
        "VAR _svg =",
        "    \"<svg xmlns='http://www.w3.org/2000/svg' width='326' height='118' viewBox='0 0 326 118'>\"",
        f"        & \"<text x='2' y='48' font-family='{FUENTE}' font-size='{tam_num}' font-weight='600' fill='{p['texto']}'>\" & _num",
        f"        & \"<tspan dx='10' font-family='{FUENTE_NORMAL}' font-size='{tam_uni}' font-weight='400' fill='{p['texto_unidad']}'>\" & _uni & \"</tspan></text>\"",
        "        & IF ( _wPlan > 0, \"<rect x='2' y='\" & FORMAT ( _Y, \"0\" ) & \"' width='\" & FORMAT ( _wPlan, \"0\" ) & \"' height='\" & FORMAT ( _H, \"0\" ) & "
        f"\"' rx='4' fill='{p['meta_relleno']}' stroke='{p['meta_borde']}' stroke-width='1'/>\" )",
        "        & IF ( _wProy > _wReal, \"<rect x='\" & FORMAT ( _wReal + 2, \"0\" ) & \"' y='\" & FORMAT ( _Y + _H / 4, \"0\" ) & \"' width='\" & "
        "FORMAT ( _wProy - _wReal, \"0\" ) & \"' height='\" & FORMAT ( _H / 2, \"0\" ) & \"' rx='\" & FORMAT ( _H / 4, \"0\" ) & \"' fill='\" & _color & \"' fill-opacity='0.55'/>\" )",
        "        & IF ( _wReal > 0, \"<rect x='2' y='\" & FORMAT ( _Y, \"0\" ) & \"' width='\" & FORMAT ( _wReal, \"0\" ) & \"' height='\" & FORMAT ( _H, \"0\" ) & "
        "\"' rx='4' fill='\" & _color & \"'/>\" )",
        "        & IF ( _wPlan > 0, \"<line x1='\" & FORMAT ( _wPlan + 2, \"0\" ) & \"' y1='\" & FORMAT ( _Y - 4, \"0\" ) & \"' x2='\" & FORMAT ( _wPlan + 2, \"0\" ) & "
        f"\"' y2='\" & FORMAT ( _Y + _H + 4, \"0\" ) & \"' stroke='{p['meta_marca']}' stroke-width='2'/>\" )",
        "        & \"" + _texto(2, 94, 15, p["texto_rotulo"], "Real día") + '"',
        "        & \"" + _texto(2, 114, 18, p["texto_valor"], "\" & _num & \" mil\" & \"", semibold=True, peso=600) + '"',
        "        & \"" + _texto(163, 94, 15, p["texto_rotulo"], "Proy. día", ancla="middle") + '"',
        "        & \"<text x='163' y='114' text-anchor='middle' font-family='" + FUENTE + "' font-size='18' font-weight='600' fill='\" & "
        f"IF ( _curso, \"{p['acento_claro']}\", \"{p['sin_dato']}\" ) & \"'>\" & _vProy & \"</text>\"",
        "        & \"" + _texto(324, 94, 15, p["texto_rotulo"], "Plan día", ancla="end") + '"',
        "        & \"" + _texto(324, 114, 18, p["texto_valor"], "\" & _vPlan & \"", ancla="end", semibold=True, peso=600) + '"',
        "        & \"</svg>\"",
        'RETURN "data:image/svg+xml;utf8," & SUBSTITUTE ( SUBSTITUTE ( _svg, "%", "%25" ), "#", "%23" )',
    ]
    return "\n".join(L)


def reemplazar_medida(texto, nombre, cuerpo):
    """Cambia la expresión de una medida (líneas con 3 tabuladores bajo `\\tmeasure 'x' =`) y deja sus propiedades."""
    lineas = texto.split("\n")
    cab = [k for k, l in enumerate(lineas) if l == f"\tmeasure '{nombre}' ="]
    if len(cab) != 1:
        raise RuntimeError(f"medida {nombre}: {len(cab)} apariciones")
    i = cab[0]
    j = i + 1
    while j < len(lineas) and (lineas[j].startswith("\t\t\t") or lineas[j].strip() == ""):
        j += 1
    while j > i + 1 and lineas[j - 1].strip() == "":
        j -= 1
    nuevas = [lineas[i]] + [("\t\t\t" + l) if l.strip() else "" for l in cuerpo.split("\n")]
    return "\n".join(lineas[:i] + nuevas + lineas[j:])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", default=str(RAIZ_PROYECTO))
    ap.add_argument("--aplicar", action="store_true")
    a = ap.parse_args()
    raiz = Path(a.raiz).resolve()
    tmdl = raiz / "pbip" / "Informe Operaciones Demo.SemanticModel" / "definition" / "tables" / "dax_kpi_tabla.tmdl"
    with io.open(tmdl, "r", encoding="utf-8", newline="") as f:
        t0 = f.read()
    eol = "\r\n" if "\r\n" in t0 else "\n"
    t = t0.replace("\r\n", "\n")
    cambian = []
    for nombre, (real, plan, tn, tu) in TARJETAS.items():
        nuevo = reemplazar_medida(t, nombre, cuerpo_bullet(real, plan, tn, tu))
        if nuevo != t:
            cambian.append(nombre)
        t = nuevo
    print(f"raíz: {raiz}")
    if not cambian:
        print("sin cambios: las tarjetas ya coinciden con la plantilla.")
        return 0
    print("cambian: " + ", ".join(cambian))
    if not a.aplicar:
        print("(simulación: no se escribió nada; agrega --aplicar)")
        return 0
    if desktop_abierto(str(raiz)):
        print("ABORTADO: Power BI Desktop tiene abierto un informe de esta carpeta. Ciérralo y vuelve a ejecutar.")
        return 2
    print(f"{tmdl.name}: {escribir(str(tmdl), t0, t.replace(chr(10), eol), newline='')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
