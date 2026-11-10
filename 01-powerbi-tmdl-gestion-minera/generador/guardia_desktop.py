# -*- coding: utf-8 -*-
"""
Guardia común de las recetas: ¿Power BI Desktop tiene abierto un informe de esta carpeta?

Power BI Desktop reescribe los archivos del PBIP al guardar, así que ninguna receta debe escribir con el informe abierto.
La guardia lista los procesos PBIDesktop.exe y busca la carpeta en su línea de comandos. PowerShell escribe en UTF-8 y aquí
se decodifica igual (con la página de códigos por defecto, los acentos de las rutas llegarían cambiados).

    from guardia_desktop import desktop_abierto
    if APLICAR and desktop_abierto(RAIZ): ...abortar...
"""
import subprocess

_PS = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
       "Get-CimInstance Win32_Process -Filter \"Name='PBIDesktop.exe'\" | ForEach-Object { [string]$_.CommandLine }")


def desktop_abierto(raiz):
    """True si algún PBIDesktop.exe tiene en su línea de comandos un archivo dentro de `raiz`."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", _PS], capture_output=True, timeout=60)
    except FileNotFoundError:     # sin PowerShell (Linux/macOS): Power BI Desktop no corre ahí
        return False
    if r.returncode != 0:
        raise RuntimeError("no pude listar los procesos de Power BI Desktop: " + r.stderr.decode("utf-8", "replace")[:300])
    salida = r.stdout.decode("utf-8", "replace")
    return any(str(raiz).lower() in l.lower() for l in salida.splitlines())
