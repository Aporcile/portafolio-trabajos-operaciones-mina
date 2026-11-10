# -*- coding: utf-8 -*-
"""Extrae los esquemas JSON de PBIR que trae la instalación local de Power BI Desktop.

Power BI Desktop los lleva incrustados en bin/WebView2Resources/minerva/scripts/*.js como JSON.parse('...').
Los validadores (generar_reporte.py y validar_disco.py) los usan para comprobar cada archivo del informe.
No se versionan en el repositorio: cada persona los extrae de su propia instalación.

Uso:
    python extraer_esquemas.py                      # escribe en desarrollo/esquemas_pbir/
    python extraer_esquemas.py --destino CARPETA    # otra carpeta
    python extraer_esquemas.py --reemplazar         # sobrescribe los existentes
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

QUIETOS = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v"}


def carpeta_bin():
    """Carpeta bin de Power BI Desktop: instalación MSI si existe; si no, la de Microsoft Store."""
    msi = Path(os.environ.get("ProgramFiles", "")) / "Microsoft Power BI Desktop" / "bin"
    if (msi / "WebView2Resources").is_dir():
        return msi
    r = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                        "(Get-AppxPackage -Name 'Microsoft.MicrosoftPowerBIDesktop').InstallLocation"],
                       capture_output=True, text=True)
    base = r.stdout.strip()
    return Path(base) / "bin" if base else None


def literal_js(s, i, comilla):
    """Lee un literal de texto JavaScript que empieza en s[i] (justo después de la comilla de apertura)."""
    out = []
    while i < len(s):
        c = s[i]
        if c == comilla:
            return "".join(out)
        if c != "\\":
            out.append(c)
            i += 1
            continue
        d = s[i + 1]
        if d in QUIETOS:
            out.append(QUIETOS[d])
            i += 2
        elif d == "x":
            out.append(chr(int(s[i + 2:i + 4], 16)))
            i += 4
        elif d == "u" and s[i + 2] == "{":
            j = s.index("}", i)
            out.append(chr(int(s[i + 3:j], 16)))
            i = j + 1
        elif d == "u":
            out.append(chr(int(s[i + 2:i + 6], 16)))
            i += 6
        elif d in "\r\n":
            i += 2
        else:
            out.append(d)
            i += 2
    raise ValueError("literal sin cerrar")


def objetos_json(texto):
    """Cada argumento literal de JSON.parse(...) que se pueda leer como JSON."""
    for m in re.finditer(r"JSON\.parse\(\s*(['\"`])", texto):
        try:
            yield json.loads(literal_js(texto, m.end(), m.group(1)))
        except (ValueError, IndexError):
            continue


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--destino", default=str(Path(__file__).resolve().parent / "esquemas_pbir"))
    ap.add_argument("--reemplazar", action="store_true")
    a = ap.parse_args()
    destino = Path(a.destino)

    bin_dir = carpeta_bin()
    scripts = bin_dir / "WebView2Resources" / "minerva" / "scripts" if bin_dir else None
    if not scripts or not scripts.is_dir():
        print("ERROR: no se encontró una instalación de Power BI Desktop")
        return 1

    encontrados = {}
    for f in sorted(scripts.glob("*.js")):
        s = f.read_text(encoding="utf-8", errors="replace")
        if "json-schemas/fabric/item/report/definition" not in s:
            continue
        for obj in objetos_json(s):
            for o in (obj if isinstance(obj, list) else [obj]):
                sid = o.get("$id", "") if isinstance(o, dict) else ""
                v = re.search(r"/item/report/definition/([^/]+)/(\d+\.\d+\.\d+)/schema\.json$", sid)
                if v and not v.group(2).startswith("9999"):  # 9999.x son versiones de desarrollo
                    encontrados.setdefault(f"{v.group(1)}-{v.group(2)}.json", o)

    # Esquema de los temas: no tiene $id; su versión va en "description"
    for f in sorted(scripts.glob("*reportThemeSchema*.js")):
        s = f.read_text(encoding="utf-8", errors="replace")
        for obj in objetos_json(s):
            if isinstance(obj, dict) and re.fullmatch(r"\d+(\.\d+)*", str(obj.get("description", ""))):
                encontrados.setdefault(f"reportThemeSchema-{obj['description']}.json", obj)
                break

    destino.mkdir(parents=True, exist_ok=True)
    nuevos = 0
    for nombre, obj in sorted(encontrados.items()):
        ruta = destino / nombre
        if ruta.exists() and not a.reemplazar:
            continue
        if nombre.startswith("reportThemeSchema"):
            ruta.write_text(json.dumps(obj, ensure_ascii=True) + "\n", encoding="utf-8")
        else:
            ruta.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        nuevos += 1
    print(f"{len(encontrados)} esquemas encontrados; {nuevos} escrito(s) en {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
