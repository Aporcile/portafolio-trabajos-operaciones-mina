# -*- coding: utf-8 -*-
"""
Plan semanal de la flota CAEX en dos formatos.

El origen del plan puede entregar el bloque CAEX con dos contenidos distintos bajo las mismas propiedades:

  propiedad                       formato clásico            formato alternativo
  'Horas Nominales CAEX SEM'      horas nominales (624)      n.º de camiones (26)
  'Horas Operativas CAEX SEM'     (no se usa)                horas nominales (26 x 24 = 624)
  'Horas Efectivas CAEX SEM'      horas efectivas            horas disponibles
  'Horas Disponibles CAEX SEM'    horas disponibles          una razón (no se usa)
  'Total Toneladas CAEX SEM'      movimiento del plan (t)    rendimiento (t/h)

Con las medidas del formato clásico, un día en formato alternativo da disponibilidad y UEBD absurdas (miles de por ciento)
y la cascada de la flota lo marca como plan inconsistente. Esta receta reescribe tres medidas de `Planes_Mina` para que cada
dato se lea donde viene. El formato alternativo se reconoce día por día: horas operativas = 24 x nominales (nominales
< 100: camiones) y un rendimiento < 5.000 t/h en 'Total Toneladas CAEX SEM'; la misma condición en las tres medidas.
Con el formato alternativo, horas efectivas = movimiento del plan / rendimiento. Los días en formato clásico dan el mismo
resultado que antes.

    python generador/caex_plan_formato.py                 # simulación
    python generador/caex_plan_formato.py --aplicar       # escribe (Power BI Desktop debe estar cerrado)
    python generador/caex_plan_formato.py --raiz RUTA     # otra copia del proyecto

Es idempotente. Los datos sintéticos de este repositorio usan el formato clásico (la rama alternativa existe, pero los
días de ejemplo no la activan).
"""
import argparse
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from escritura_segura import escribir  # noqa: E402
from guardia_desktop import desktop_abierto  # noqa: E402

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent

# detección del formato alternativo, igual en las tres medidas de horas
DETECCION = '''    VAR _nom = CALCULATE ( SUM ( Planes_Mina[value] ), Planes_Mina[plan_type] = "Semanal", Planes_Mina[property_name] = "Horas Nominales CAEX SEM" )
    VAR _ope = CALCULATE ( SUM ( Planes_Mina[value] ), Planes_Mina[plan_type] = "Semanal", Planes_Mina[property_name] = "Horas Operativas CAEX SEM" )
    VAR _ren = CALCULATE ( SUM ( Planes_Mina[value] ), Planes_Mina[plan_type] = "Semanal", Planes_Mina[property_name] = "Total Toneladas CAEX SEM" )
    VAR _alt = _nom > 0 && _nom < 100 && ABS ( _ope - 24 * _nom ) < 0.5 && _ren > 0 && _ren < 5000'''

PLANES = {
    "PlanSemanal - Horas Nominales CAEX": '''SUMX (
    VALUES ( Planes_Mina[start_date] ),
%s
    RETURN IF ( _alt, _ope, _nom )
)''' % DETECCION,
    "PlanSemanal - Horas Disponible CAEX": '''SUMX (
    VALUES ( Planes_Mina[start_date] ),
%s
    RETURN
        IF (
            _alt,
            CALCULATE ( SUM ( Planes_Mina[value] ), Planes_Mina[plan_type] = "Semanal", Planes_Mina[property_name] = "Horas Efectivas CAEX SEM" ),
            CALCULATE ( SUM ( Planes_Mina[value] ), Planes_Mina[plan_type] = "Semanal", Planes_Mina[property_name] = "Horas Disponibles CAEX SEM" )
        )
)''' % DETECCION,
    "PlanSemanal - Horas efectivas CAEX": '''SUMX (
    VALUES ( Planes_Mina[start_date] ),
%s
    RETURN
        IF (
            _alt,
            DIVIDE ( [PlanSemanal Movimiento mina CAEX], _ren ),
            CALCULATE ( SUM ( Planes_Mina[value] ), Planes_Mina[plan_type] = "Semanal", Planes_Mina[property_name] = "Horas Efectivas CAEX SEM" )
        )
)''' % DETECCION,
}


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
    tmdl = raiz / "pbip" / "Informe Operaciones Demo.SemanticModel" / "definition" / "tables" / "Planes_Mina.tmdl"
    with io.open(tmdl, "r", encoding="utf-8", newline="") as f:
        t0 = f.read()
    eol = "\r\n" if "\r\n" in t0 else "\n"
    t = t0.replace("\r\n", "\n")
    for nombre, cuerpo in PLANES.items():
        t = reemplazar_medida(t, nombre, cuerpo)
    print(f"raíz: {raiz}")
    if t == t0.replace("\r\n", "\n"):
        print("sin cambios: ya estaba aplicado.")
        return 0
    if not a.aplicar:
        print("cambian: " + ", ".join(PLANES))
        print("(simulación: no se escribió nada; agrega --aplicar)")
        return 0
    if desktop_abierto(str(raiz)):
        print("ABORTADO: Power BI Desktop tiene abierto un informe de esta carpeta. Ciérralo y vuelve a ejecutar.")
        return 2
    print(f"{tmdl.name}: {escribir(str(tmdl), t0, t.replace(chr(10), eol), newline='')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
