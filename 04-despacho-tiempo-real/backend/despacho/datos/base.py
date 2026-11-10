"""Interfaz común de las fuentes de datos y parámetros de consulta.

Una fuente entrega registros que cumplen `contratos.DATASETS`. Hay tres tipos:
  - FuenteSQL   (prevista)   datos de las bases de despacho y planta, solo lectura
  - FuenteDemo  (prevista)   simulador
  - FuenteFija  (aquí)       filas fijas para tests
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Protocol

from despacho import tiempo


class Fuente(Protocol):
    nombre: str  # 'sql' | 'demo' | 'fija'

    def obtener(self, dataset: str, parametros: dict[str, Any]) -> list[dict[str, Any]]:
        """Devuelve las filas del dataset. Lanza excepción si falla (el programador la registra)."""
        ...

    def estado(self) -> dict[str, Any]:
        """Información para /api/health (sin secretos)."""
        ...


@dataclass
class CacheDataset:
    """Último resultado conocido de un dataset (lo mantiene el programador)."""
    nombre: str
    filas: list[dict[str, Any]] = field(default_factory=list)
    actualizado: dt.datetime | None = None   # último éxito (hora local, consciente)
    intento: dt.datetime | None = None       # último intento
    ok: bool = False
    error: str | None = None
    ms: int = 0
    exitos: int = 0
    fallos_seguidos: int = 0

    def resumen(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "filas": len(self.filas),
            "ms": self.ms,
            "actualizado": tiempo.iso(self.actualizado),
            "intento": tiempo.iso(self.intento),
            "error": self.error,
            "fallos_seguidos": self.fallos_seguidos,
        }


class FuenteFija:
    """Fuente de tests: devuelve las filas que se le entregan por dataset."""

    nombre = "fija"

    def __init__(self, filas_por_dataset: dict[str, list[dict[str, Any]]] | None = None):
        self.filas = dict(filas_por_dataset or {})
        self.llamadas: list[tuple[str, dict[str, Any]]] = []

    def obtener(self, dataset: str, parametros: dict[str, Any]) -> list[dict[str, Any]]:
        self.llamadas.append((dataset, dict(parametros)))
        return [dict(f) for f in self.filas.get(dataset, [])]

    def estado(self) -> dict[str, Any]:
        return {"tipo": "fija", "datasets": sorted(self.filas)}


def parametros_consulta(ahora: dt.datetime, *, historia_corta_dias: int = 7, planes_dias: int = 21,
                        gps_minutos: int = 15) -> dict[str, Any]:
    """Calcula los parámetros estándar de las consultas en vivo para un instante dado.

    Los valores son datetimes/dates de Python (las fuentes los convierten al tipo del driver).
    """
    ahora = tiempo.a_local(ahora)
    turno = tiempo.turno_de(ahora)
    anterior = tiempo.turno_anterior(turno)
    ahora_utc = ahora.astimezone(tiempo.UTC).replace(tzinfo=None)
    return {
        "FechaOpHoy": turno.fecha_operacional,
        "FechaOpAyer": turno.fecha_operacional - dt.timedelta(days=1),
        "FechaOpInicioHist": turno.fecha_operacional - dt.timedelta(days=historia_corta_dias),
        "InicioTurnoAnterior": anterior.inicio.replace(tzinfo=None),
        "InicioTurnoActual": turno.inicio.replace(tzinfo=None),
        "AhoraLocal": ahora.replace(tzinfo=None, microsecond=0),
        "DesdeUtc": ahora_utc - dt.timedelta(minutes=gps_minutos),
        "DesdeUtcHistoria": ahora_utc - dt.timedelta(days=historia_corta_dias + 1),
        "HastaUtc": ahora_utc + dt.timedelta(hours=1),
        "DesfaseMinutos": tiempo.desfase_minutos(ahora),
        "FechaInicioPlanes": turno.fecha_operacional - dt.timedelta(days=planes_dias),
    }
