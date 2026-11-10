"""Pasa una consulta DAX legible a una sola línea (como la que va en el flujo): sin comentarios // y con espacios simples."""
import re
import sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
lineas = []
for ln in src.read_text(encoding='utf-8').splitlines():
    # Comentario //: solo fuera de comillas (las consultas no usan // dentro de textos).
    partes = ln.split('"')
    for i in range(0, len(partes), 2):
        if '//' in partes[i]:
            partes[i] = partes[i].split('//', 1)[0]
            partes = partes[:i + 1]
            break
    ln = '"'.join(partes).strip()
    if ln:
        lineas.append(ln)
txt = ' '.join(lineas)
# Espacios simples fuera de comillas.
partes = txt.split('"')
for i in range(0, len(partes), 2):
    partes[i] = re.sub(r'\s+', ' ', partes[i])
txt = '"'.join(partes)
dst.write_text(txt, encoding='utf-8', newline='')
print(len(txt), 'caracteres')
