"""Tiempo operacional: turnos, día operacional, zona horaria y reloj inyectable.

Reglas:
  - Turno A: 08:00 a 19:59.  Turno B: 20:00 a 07:59 del día calendario siguiente.
  - Día operacional: las horas 00:00-07:59 pertenecen al día operacional ANTERIOR.
  - HoraTurno: 1..12 dentro del turno (1 = primera hora del turno).
  - OrdenHoraDia: 1..24 contando desde las 08:00 (1 = 08:00, 13 = 20:00).

Zona horaria (se fija una vez al arrancar con `configurar_zona`):
  1. "UTC" usa `datetime.timezone.utc` (no necesita base de zonas).
  2. Cualquier otro nombre IANA se resuelve con `zoneinfo` (base del sistema o paquete `tzdata`).
  3. Si la base de zonas no existe, se usa un desfase fijo configurable y se registra una advertencia.

Todo el código debe obtener la hora a través de un `Reloj`, nunca de `datetime.now()` directo:
así la demo puede acelerar o desplazar el tiempo y los tests son deterministas.
"""
from __future__ import annotations

import datetime as dt
import logging
import time
from dataclasses import dataclass

log = logging.getLogger("despacho.tiempo")

INICIO_TURNO_A = 8   # 08:00
INICIO_TURNO_B = 20  # 20:00
HORAS_TURNO = 12

DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
            "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

UTC = dt.timezone.utc


# ---------------------------------------------------------------------------
# Zona horaria
# ---------------------------------------------------------------------------
_ZONA: dict = {"nombre": "UTC", "desfase_respaldo_h": 0.0, "tz": None, "origen": ""}


def configurar_zona(nombre: str = "UTC", desfase_respaldo_h: float = 0.0) -> dt.tzinfo:
    """Fija la zona horaria de la faena y devuelve el `tzinfo` resultante."""
    _ZONA.update(nombre=(nombre or "").strip() or "UTC", desfase_respaldo_h=float(desfase_respaldo_h),
                 tz=None, origen="")
    return zona_horaria()


def zona_horaria() -> dt.tzinfo:
    """Devuelve la zona horaria vigente con la mejor estrategia disponible (ver docstring del módulo)."""
    if _ZONA["tz"] is not None:
        return _ZONA["tz"]
    nombre = _ZONA["nombre"]
    if nombre.upper() == "UTC":
        tz, origen = UTC, "UTC"
    else:
        try:
            from zoneinfo import ZoneInfo  # la base de zonas puede faltar (p. ej. Windows sin tzdata)
            tz, origen = ZoneInfo(nombre), f"zoneinfo {nombre}"
        except Exception:
            horas = _ZONA["desfase_respaldo_h"]
            tz = dt.timezone(dt.timedelta(hours=horas))
            origen = f"desfase fijo {horas:+g} h (sin base de zonas para '{nombre}')"
            log.warning("Zona horaria: %s", origen)
    _ZONA["tz"] = tz
    _ZONA["origen"] = origen
    log.info("Zona horaria resuelta con: %s", origen)
    return tz


def origen_zona_horaria() -> str:
    zona_horaria()
    return _ZONA["origen"]


def a_local(valor: dt.datetime | str, *, origen_utc: bool = False) -> dt.datetime:
    """Convierte un datetime (o texto ISO) a un datetime consciente en la hora local de la faena.

    - Si `valor` ya trae zona, se convierte.
    - Si es naive y origen_utc=True, se interpreta como UTC (marcas de tiempo de GPS y auditoría).
    - Si es naive y origen_utc=False, se interpreta como hora local.
    """
    if isinstance(valor, str):
        valor = dt.datetime.fromisoformat(valor)
    tz = zona_horaria()
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=UTC if origen_utc else tz)
    return valor.astimezone(tz)


def desfase_minutos(momento: dt.datetime) -> int:
    """Minutos de diferencia entre la hora local y UTC en `momento` (negativo al oeste de Greenwich)."""
    return int(a_local(momento).utcoffset().total_seconds() // 60)


def iso(valor: dt.datetime | None) -> str | None:
    """ISO 8601 con desfase y sin microsegundos (formato único del snapshot)."""
    if valor is None:
        return None
    return valor.replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------
# Reloj inyectable
# ---------------------------------------------------------------------------
class Reloj:
    """Reloj real. `ahora()` devuelve un datetime consciente en hora local."""

    simulado = False

    def ahora(self) -> dt.datetime:
        return dt.datetime.now(tz=zona_horaria())


class RelojSimulado(Reloj):
    """Reloj virtual para demo y tests: parte en `inicio` y avanza `factor` veces más rápido.

    factor = 1 -> tiempo real; factor = 60 -> un minuto virtual por segundo real; factor = 0 -> congelado.
    """

    simulado = True

    def __init__(self, inicio: dt.datetime, factor: float = 1.0):
        self.inicio = a_local(inicio)
        self.factor = float(factor)
        self._t0 = time.monotonic()

    def ahora(self) -> dt.datetime:
        transcurrido = (time.monotonic() - self._t0) * self.factor
        return self.inicio + dt.timedelta(seconds=transcurrido)

    def avanzar(self, segundos: float) -> None:
        """Desplaza el reloj (útil en tests): el tiempo virtual salta `segundos`."""
        self.inicio += dt.timedelta(seconds=segundos)


# ---------------------------------------------------------------------------
# Turnos y día operacional
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Turno:
    fecha_operacional: dt.date
    turno: str                 # 'A' | 'B'
    inicio: dt.datetime        # consciente, hora local
    fin: dt.datetime           # consciente, hora local (exclusivo)
    hora_turno: int            # 1..12
    orden_hora_dia: int        # 1..24

    @property
    def nombre(self) -> str:
        return f"Turno {self.turno}"

    @property
    def etiqueta_corta(self) -> str:
        return f"T{self.turno}"

    def horas_transcurridas(self, ahora: dt.datetime) -> float:
        return max(0.0, min(HORAS_TURNO, (ahora - self.inicio).total_seconds() / 3600))

    def horas_restantes(self, ahora: dt.datetime) -> float:
        return max(0.0, (self.fin - ahora).total_seconds() / 3600)


def turno_de(momento: dt.datetime) -> Turno:
    """Clasifica un instante (consciente, hora local) en su turno y día operacional."""
    momento = a_local(momento)
    hora = momento.hour
    tz = momento.tzinfo
    if INICIO_TURNO_A <= hora < INICIO_TURNO_B:
        turno = "A"
        fecha_op = momento.date()
        inicio = dt.datetime.combine(fecha_op, dt.time(INICIO_TURNO_A), tzinfo=tz)
        hora_turno = hora - INICIO_TURNO_A + 1
    else:
        turno = "B"
        fecha_op = momento.date() if hora >= INICIO_TURNO_B else momento.date() - dt.timedelta(days=1)
        inicio = dt.datetime.combine(fecha_op, dt.time(INICIO_TURNO_B), tzinfo=tz)
        hora_turno = (hora - INICIO_TURNO_B + 1) if hora >= INICIO_TURNO_B else (hora + 24 - INICIO_TURNO_B + 1)
    fin = inicio + dt.timedelta(hours=HORAS_TURNO)  # aritmética de reloj de pared: fin a las 20:00 / 08:00
    orden = ((hora - INICIO_TURNO_A + 24) % 24) + 1
    return Turno(fecha_op, turno, inicio, fin, hora_turno, orden)


def turno_anterior(actual: Turno) -> Turno:
    """El turno inmediatamente anterior (A -> B del día operacional anterior; B -> A del mismo día)."""
    return turno_de(actual.inicio - dt.timedelta(minutes=1))


def turno_siguiente(actual: Turno) -> Turno:
    return turno_de(actual.fin + dt.timedelta(minutes=1))


def inicio_dia_operacional(fecha_op: dt.date) -> dt.datetime:
    return dt.datetime.combine(fecha_op, dt.time(INICIO_TURNO_A), tzinfo=zona_horaria())


def fraccion_dia_operacional(momento: dt.datetime) -> float:
    """Fracción transcurrida del día operacional (0..1) en tiempo de reloj de pared."""
    t = turno_de(momento)
    inicio = inicio_dia_operacional(t.fecha_operacional)
    return max(0.0, min(1.0, (a_local(momento) - inicio).total_seconds() / (24 * 3600)))


def hora_reloj_de_hora_turno(turno: str, hora_turno: int) -> int:
    """HoraTurno (1..12) -> hora de reloj (0..23)."""
    base = INICIO_TURNO_A if turno == "A" else INICIO_TURNO_B
    return (base + hora_turno - 1) % 24


def orden_hora_dia_de(turno: str, hora_turno: int) -> int:
    return hora_turno if turno == "A" else hora_turno + 12


# ---------------------------------------------------------------------------
# Textos en español
# ---------------------------------------------------------------------------
def fecha_texto(fecha: dt.date) -> str:
    """'martes, 4 de marzo'."""
    return f"{DIAS_ES[fecha.weekday()]}, {fecha.day} de {MESES_ES[fecha.month - 1]}"


def hora_texto_12h(momento: dt.datetime) -> str:
    """'03:03 p.m.'."""
    h = momento.hour % 12 or 12
    sufijo = "a.m." if momento.hour < 12 else "p.m."
    return f"{h:02d}:{momento.minute:02d} {sufijo}"


def hora_texto_24h(momento: dt.datetime) -> str:
    return momento.strftime("%H:%M")


def duracion_texto(minutos: float) -> str:
    """325 -> '5 h 25'; 48 -> '48 min'."""
    minutos = int(round(minutos))
    if minutos < 60:
        return f"{minutos} min"
    h, m = divmod(minutos, 60)
    return f"{h} h {m:02d}"
