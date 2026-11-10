# -*- coding: utf-8 -*-
"""
Escritura segura de archivos del PBIP cuando más de un proceso puede tocarlos (varios scripts, Power BI Desktop, el editor).

`escribir(path, original, nuevo)`:
  - no escribe si `nuevo == original` (no se toca la fecha del archivo);
  - justo antes de escribir vuelve a leer el archivo y, si cambió desde que se leyó `original`, NO lo pisa y devuelve
    "conflicto".

Devuelve "sin cambios", "escrito" o "conflicto".
"""
import io


def escribir(path, original, nuevo, newline="\n"):
    if nuevo == original:
        return "sin cambios"
    with io.open(path, "r", encoding="utf-8", newline="") as f:
        ahora = f.read()
    # comparación tolerante al modo de lectura: el original pudo leerse con traducción de saltos
    if ahora != original and ahora.replace("\r\n", "\n") != original.replace("\r\n", "\n"):
        return "conflicto"
    with io.open(path, "w", encoding="utf-8", newline=newline) as f:
        f.write(nuevo)
    return "escrito"
