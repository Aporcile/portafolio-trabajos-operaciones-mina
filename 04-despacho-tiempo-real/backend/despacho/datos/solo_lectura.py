"""Barrera de solo lectura para las consultas SQL (segunda línea de defensa).

La primera barrera es el permiso del login de base de datos (solo SELECT). Esta segunda barrera
analiza el TEXTO de cada consulta antes de enviarla y rechaza todo lo que no sea una única
sentencia SELECT (opcionalmente precedida por CTE con WITH).

El análisis ignora el contenido de comentarios, cadenas ('...') e identificadores ([...] o "..."),
de modo que `SELECT 'DROP'` es válido y `SELECT 1; DROP TABLE x` no lo es.
"""
from __future__ import annotations

import re

PALABRAS_PROHIBIDAS = (
    "INSERT", "UPDATE", "DELETE", "MERGE", "DROP", "ALTER", "CREATE", "TRUNCATE",
    "EXEC", "EXECUTE", "GRANT", "REVOKE", "DENY", "INTO", "OPENROWSET", "OPENQUERY",
    "OPENDATASOURCE", "BULK", "BACKUP", "RESTORE", "DBCC", "KILL", "RECONFIGURE",
    "SHUTDOWN", "WAITFOR", "USE", "SET", "DECLARE", "PRINT", "GO",
)
_R_PROHIBIDAS = re.compile(r"\b(?:" + "|".join(PALABRAS_PROHIBIDAS) + r")\b", re.I)
_R_PROCEDIMIENTOS = re.compile(r"\b(?:xp|sp)_\w*", re.I)
_R_INICIO = re.compile(r"^\s*(SELECT|WITH)\b", re.I)


class ConsultaNoPermitida(ValueError):
    """La consulta no es una sentencia de solo lectura."""


def segmentar(sql: str) -> list[tuple[str, str]]:
    """Divide el SQL en segmentos (tipo, texto) con tipo en codigo | cadena | comentario | identificador."""
    segmentos: list[tuple[str, str]] = []
    buffer: list[str] = []
    i, n = 0, len(sql)

    def emitir(tipo: str, texto: str) -> None:
        if buffer:
            segmentos.append(("codigo", "".join(buffer)))
            buffer.clear()
        segmentos.append((tipo, texto))

    while i < n:
        c = sql[i]
        if c == "-" and sql.startswith("--", i):
            j = sql.find("\n", i)
            j = n if j < 0 else j
            emitir("comentario", sql[i:j])
            i = j
        elif c == "/" and sql.startswith("/*", i):
            profundidad, j = 1, i + 2
            while j < n and profundidad:
                if sql.startswith("/*", j):
                    profundidad, j = profundidad + 1, j + 2
                elif sql.startswith("*/", j):
                    profundidad, j = profundidad - 1, j + 2
                else:
                    j += 1
            if profundidad:
                raise ConsultaNoPermitida("comentario de bloque sin cerrar")
            emitir("comentario", sql[i:j])
            i = j
        elif c in ("'", '"', "["):
            cierre = "]" if c == "[" else c
            j = i + 1
            while True:
                if j >= n:
                    raise ConsultaNoPermitida("cadena o identificador sin cerrar")
                if sql[j] == cierre:
                    if j + 1 < n and sql[j + 1] == cierre:  # comilla o corchete duplicado = escape
                        j += 2
                        continue
                    break
                j += 1
            emitir("cadena" if c == "'" else "identificador", sql[i:j + 1])
            i = j + 1
        else:
            buffer.append(c)
            i += 1
    if buffer:
        segmentos.append(("codigo", "".join(buffer)))
    return segmentos


def limpiar(sql: str) -> str:
    """SQL sin comentarios y con cadenas e identificadores neutralizados (solo para analizar)."""
    partes = []
    for tipo, texto in segmentar(sql):
        if tipo == "codigo":
            partes.append(texto)
        elif tipo == "comentario":
            partes.append(" ")
        elif tipo == "cadena":
            partes.append("''")
        else:
            partes.append("ident")
    return "".join(partes)


def validar_solo_lectura(sql: str) -> str:
    """Devuelve el SQL limpio si es una única sentencia SELECT; si no, lanza ConsultaNoPermitida."""
    limpio = limpiar(sql).strip()
    if limpio.endswith(";"):
        limpio = limpio[:-1].rstrip()
    if not limpio:
        raise ConsultaNoPermitida("consulta vacía")
    if ";" in limpio:
        raise ConsultaNoPermitida("solo se permite una sentencia por consulta")
    if not _R_INICIO.match(limpio):
        raise ConsultaNoPermitida("la consulta debe comenzar con SELECT o WITH")
    prohibida = _R_PROHIBIDAS.search(limpio) or _R_PROCEDIMIENTOS.search(limpio)
    if prohibida:
        raise ConsultaNoPermitida(f"palabra no permitida en consultas de solo lectura: {prohibida.group(0).upper()}")
    return limpio


def es_solo_lectura(sql: str) -> bool:
    try:
        validar_solo_lectura(sql)
        return True
    except ConsultaNoPermitida:
        return False
