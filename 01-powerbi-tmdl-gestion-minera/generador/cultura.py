# -*- coding: utf-8 -*-
"""
Esquema lingüístico del modelo (cultures/es-ES.tmdl): quita las entidades y relaciones que apuntan a objetos que ya no
existen. Power BI Desktop agrega una entidad «Generated» por cada campo que usan los visuales; al borrar una medida, columna
o tabla su entidad quedaría colgando.

El JSON de `linguisticMetadata` se lee y se vuelve a escribir con json (indent 2, sin escapar acentos); `quitar()` verifica
que leer y reescribir el JSON reproduce el texto original antes de tocar nada.

    from cultura import quitar, quitar_inexistentes, objetos_del_modelo
    nuevo, quitadas = quitar(texto, medidas=[("dax_kpi_tabla", "Rd SVG Ampliacion")], columnas=[...], tablas=[...])
    nuevo, quitadas = quitar_inexistentes(texto, objetos_del_modelo("<carpeta definition>"))

El modelo de ejemplo trae un esquema lingüístico mínimo (sin entidades), así que no hay nada que limpiar; el módulo es para
modelos que sí acumulan entidades «Generated».
"""
import glob
import io
import json
import os
import re


def objetos_del_modelo(definicion):
    """{tabla: set(columnas, medidas, jerarquías y sus niveles)} leído de definition/tables/*.tmdl."""
    def unq(n):
        n = n.strip()
        return n[1:-1].replace("''", "'") if n.startswith("'") and n.endswith("'") else n
    out = {}
    for f in glob.glob(os.path.join(definicion, "tables", "*.tmdl"), include_hidden=True):
        lineas = io.open(f, encoding="utf-8-sig").read().splitlines()
        tabla = unq(re.match("table (.+)$", lineas[0]).group(1))
        props = out.setdefault(tabla, set())
        for l in lineas[1:]:
            m = re.match(r"^\t(column|measure|hierarchy) ('(?:[^']|'')+'|[^\s=]+)", l) or re.match(r"^\t\tlevel ('(?:[^']|'')+'|[^\s=]+)", l)
            if m:
                props.add(unq(m.group(m.lastindex)))
    return out


def _partes(texto):
    eol = "\r\n" if "\r\n" in texto else "\n"
    lineas = texto.split(eol)
    ini = [k for k, l in enumerate(lineas) if l.strip() == "linguisticMetadata ="]
    fin = [k for k, l in enumerate(lineas) if l.strip() == "contentType: json"]
    if len(ini) != 1 or len(fin) != 1 or fin[0] < ini[0]:
        raise RuntimeError("cultura: no encuentro un único bloque linguisticMetadata")
    js = lineas[ini[0] + 1:fin[0]]
    pref = "\t\t\t"
    if any(l and not l.startswith(pref) for l in js):
        raise RuntimeError("cultura: líneas JSON con otra sangría")
    return eol, lineas, ini[0], fin[0], "\n".join(l[len(pref):] for l in js), pref


def quitar_inexistentes(texto, modelo):
    """Quita las entidades cuyo Binding apunta a una tabla o propiedad que ya no existe en `modelo` (objetos_del_modelo).
    Solo enlaces simples (tabla, o tabla + propiedad): un Binding con otras claves (jerarquía, variación) no se toca."""
    return quitar(texto, _filtro=lambda t, p, b: (t is not None and t not in modelo)
                  or (p is not None and set(b) <= {"ConceptualEntity", "ConceptualProperty"} and p not in modelo.get(t, ())))


def quitar(texto, medidas=(), columnas=(), tablas=(), _filtro=None):
    """Devuelve (texto nuevo, [claves de entidades y relaciones quitadas]). medidas / columnas: pares (tabla, nombre)."""
    eol, lineas, i, j, js, pref = _partes(texto)
    d = json.loads(js)
    if json.dumps(d, indent=2, ensure_ascii=False) != js:
        raise RuntimeError("cultura: leer y reescribir el JSON no reproduce el archivo; no se toca")
    props = set(medidas) | set(columnas)
    tablas = set(tablas)
    ents = d.get("Entities", {})
    fuera = []
    for k, e in list(ents.items()):
        b = (e.get("Definition") or {}).get("Binding") or {}
        t, p = b.get("ConceptualEntity"), b.get("ConceptualProperty")
        if t in tablas or (t, p) in props or (_filtro is not None and _filtro(t, p, b)):
            del ents[k]
            fuera.append(k)
    rels = d.get("Relationships", {})
    for k, r in list(rels.items()):
        b = r.get("Binding") or {}
        objetivos = [(ro.get("Target") or {}).get("Entity") for ro in (r.get("Roles") or {}).values()]
        if b.get("ConceptualEntity") in tablas or (b.get("ConceptualEntity"), b.get("ConceptualProperty")) in props \
                or any(o in fuera for o in objetivos) \
                or (_filtro is not None and b and _filtro(b.get("ConceptualEntity"), b.get("ConceptualProperty"), b)):
            del rels[k]
            fuera.append(k)
    if not fuera:
        return texto, []
    nuevo = json.dumps(d, indent=2, ensure_ascii=False)
    for k in fuera:   # ninguna referencia que quede a lo quitado
        if f'"Entity": "{k}"' in nuevo:
            raise RuntimeError(f"cultura: queda una referencia a {k}")
    lineas[i + 1:j] = [pref + l for l in nuevo.split("\n")]
    return eol.join(lineas), fuera
