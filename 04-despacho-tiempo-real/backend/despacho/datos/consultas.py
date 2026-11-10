"""Carga de consultas SQL por dataset: lectura, validación de solo lectura y enlace de parámetros.

Cada dataset del contrato apunta a un archivo en `sql/consultas/`. Antes de devolver el texto,
`cargar_consulta` lo pasa por la barrera de solo lectura. Los parámetros se escriben como `@Nombre`;
`a_posicional` los convierte a `?` (estilo ODBC) y entrega los valores en el orden de aparición,
sin concatenar nunca valores dentro del texto SQL.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from despacho import contratos
from despacho.config import RAIZ
from despacho.datos.solo_lectura import segmentar, validar_solo_lectura

RUTA_CONSULTAS = RAIZ / "sql" / "consultas"
_R_PARAMETRO = re.compile(r"(?<![@\w])@([A-Za-z_]\w*)")


def parametros_de(sql: str) -> list[str]:
    """Nombres de parámetros (sin @) en orden de primera aparición, ignorando comentarios y cadenas."""
    vistos: list[str] = []
    for tipo, texto in segmentar(sql):
        if tipo != "codigo":
            continue
        for m in _R_PARAMETRO.finditer(texto):
            if m.group(1) not in vistos:
                vistos.append(m.group(1))
    return vistos


def cargar_consulta(dataset: str, carpeta: Path | None = None) -> str:
    """Lee la consulta del dataset y la valida como solo lectura. Lanza FileNotFoundError si no existe."""
    ds = contratos.DATASETS[dataset]
    ruta = (carpeta or RUTA_CONSULTAS) / ds.archivo_sql
    texto = ruta.read_text(encoding="utf-8")
    validar_solo_lectura(texto)
    return texto


def consultas_disponibles(carpeta: Path | None = None) -> list[str]:
    """Datasets del contrato que ya tienen su archivo SQL."""
    base = carpeta or RUTA_CONSULTAS
    return sorted(n for n, ds in contratos.DATASETS.items() if (base / ds.archivo_sql).exists())


def a_posicional(sql: str, valores: dict[str, Any]) -> tuple[str, list[Any]]:
    """Reemplaza cada @Nombre por '?' y devuelve (sql, lista de valores en orden de aparición)."""
    salida: list[str] = []
    lista: list[Any] = []

    def sustituir(m: re.Match) -> str:
        nombre = m.group(1)
        if nombre not in valores:
            raise KeyError(f"falta el parámetro @{nombre}")
        lista.append(valores[nombre])
        return "?"

    for tipo, texto in segmentar(sql):
        salida.append(_R_PARAMETRO.sub(sustituir, texto) if tipo == "codigo" else texto)
    return "".join(salida), lista
