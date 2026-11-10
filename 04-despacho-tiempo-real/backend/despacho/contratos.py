"""Contratos de datos: la frontera única entre las fuentes (SQL / simulador) y el motor.

Cada `Dataset` describe un conjunto de registros (lista de dicts) con columnas y tipos fijos.
  - La fuente SQL ejecuta `sql/consultas/<archivo_sql>` y debe devolver EXACTAMENTE estas columnas.
  - El simulador debe producir EXACTAMENTE estas columnas.
  - El motor de KPI, las alertas y el panel de recomendaciones solo conocen estos registros:
    nunca saben de dónde vienen.

Tipos de columna (valores serializables a JSON):
  fecha      -> str 'YYYY-MM-DD'
  fechahora  -> str 'YYYY-MM-DDTHH:MM:SS' (hora local de la faena, sin desfase)
  texto      -> str
  entero     -> int
  decimal    -> float
  Sufijo '?' -> admite None.

Parámetros de las consultas (los calcula el programador con el reloj y los inyecta como parámetros
SQL con nombre; las consultas los referencian como @Nombre). Ver `datos.base.parametros_consulta`:
  @FechaOpHoy          DATE      día operacional actual
  @FechaOpAyer         DATE      día operacional anterior
  @InicioTurnoAnterior DATETIME  inicio del turno anterior (hora local)
  @AhoraLocal          DATETIME  ahora en hora local
  @DesdeUtc            DATETIME  ahora UTC - ventana GPS (minutos)
  @DesdeUtcHistoria    DATETIME  ahora UTC - ventana histórica corta (días)
  @HastaUtc            DATETIME  ahora UTC + 1 h (margen por diferencias de reloj)
  @DesfaseMinutos      INT       minutos entre hora local y UTC en este instante
  @FechaInicioPlanes   DATE      inicio de la ventana de planes (p. ej. 21 días)
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

TIPOS = ("fecha", "fechahora", "texto", "entero", "decimal")


@dataclass(frozen=True)
class Columna:
    nombre: str
    tipo: str          # uno de TIPOS, con '?' opcional
    descripcion: str = ""

    @property
    def nulo(self) -> bool:
        return self.tipo.endswith("?")

    @property
    def tipo_base(self) -> str:
        return self.tipo.rstrip("?")


@dataclass(frozen=True)
class Dataset:
    nombre: str
    descripcion: str
    servidor: str              # 'despacho' | 'planta'
    archivo_sql: str           # en sql/consultas/
    intervalo_s: int           # frecuencia de refresco en modo SQL
    timeout_s: int
    columnas: tuple[Columna, ...]
    parametros: tuple[str, ...] = ()   # nombres sin @, en orden de primera aparición en la consulta
    tabla_origen: str = ""             # tabla principal del esquema demo (ver sql/esquema_demo.sql)
    opcional: bool = False             # si falla no se considera caída la fuente
    maximo_edad_s: int = 0             # 0 = usar el general; edad máxima antes de marcar ATRASADO

    def nombres_columnas(self) -> list[str]:
        return [c.nombre for c in self.columnas]


def _c(nombre: str, tipo: str, descripcion: str = "") -> Columna:
    return Columna(nombre, tipo, descripcion)


# ---------------------------------------------------------------------------
# Columnas compartidas por los datasets de horas por equipo
# ---------------------------------------------------------------------------
_COLS_HORAS = (
    _c("Fecha", "fecha", "día operacional"),
    _c("Turno", "texto", "'A' | 'B'"),
    _c("Hora", "entero", "0..11 dentro del turno (0 = primera hora)"),
    _c("TipoEquipo", "texto", "Truck | Shovel | Loader | Drill"),
    _c("Equipo", "texto", "nombre del equipo, p. ej. CAEX-01, PALA-01, CARG-01, PERF-01"),
    _c("Flota", "texto", "modelo o flota del equipo"),
    _c("HorasNominales", "decimal"),
    _c("HorasOperativas", "decimal", "efectivo (incluye esperas y colas)"),
    _c("HorasEfectivas", "decimal", "operativas - espera (- cola en CAEX)"),
    _c("HorasPOEspera", "decimal", "CAEX esperando pala / pala esperando CAEX"),
    _c("HorasPOCola", "decimal", "solo CAEX: cola en descarga"),
    _c("HorasDNP", "decimal", "demora no programada"),
    _c("HorasDP", "decimal", "demora programada"),
    _c("HorasReserva", "decimal"),
    _c("HorasDisponibles", "decimal", "operativas + DNP + DP + reserva"),
    _c("HorasMP", "decimal", "mantención programada"),
    _c("HorasMNP", "decimal", "mantención no programada"),
    _c("Tonelaje", "decimal", "CAEX: descargado; carguío: cargado"),
    _c("MaterialExtraido", "decimal", "solo CAEX: material que no es stock ni remanejo"),
    _c("MaterialRemanejo", "decimal", "solo CAEX: material movido desde stock"),
    _c("MovimientoTotal", "decimal", "extraído + remanejo"),
    _c("MetrosPerforados", "decimal", "solo perforadoras"),
)

DATASETS: dict[str, Dataset] = {}


def _registrar(ds: Dataset) -> Dataset:
    DATASETS[ds.nombre] = ds
    return ds


# --- Mina: horas por equipo-hora (base de movimiento, DF/UEBD/rendimiento, equipos en uso, gaviota)
_registrar(Dataset(
    nombre="horas_equipo",
    descripcion="Horas por estado y producción por equipo-hora de la flota principal (hoy y ayer operacional).",
    servidor="despacho", archivo_sql="horas_equipo.sql", intervalo_s=60, timeout_s=60,
    columnas=_COLS_HORAS, parametros=("FechaOpAyer", "FechaOpHoy"),
    tabla_origen="horas_equipo", maximo_edad_s=15 * 60,
))

_registrar(Dataset(
    nombre="horas_equipo_aux",
    descripcion="Igual que horas_equipo pero solo para la flota auxiliar (equipos con sufijo _AUX).",
    servidor="despacho", archivo_sql="horas_equipo_aux.sql", intervalo_s=60, timeout_s=60,
    columnas=_COLS_HORAS, parametros=("FechaOpAyer", "FechaOpHoy"),
    tabla_origen="horas_equipo", opcional=True,
))

# --- Ciclos de acarreo (turno actual y anterior)
_registrar(Dataset(
    nombre="ciclos",
    descripcion="Un registro por ciclo de acarreo CAEX-carguío-destino desde el inicio del turno anterior.",
    servidor="despacho", archivo_sql="ciclos.sql", intervalo_s=30, timeout_s=60,
    columnas=(
        _c("DiaOperativo", "fecha"),
        _c("Turno", "texto"),
        _c("CAEX", "texto"),
        _c("FlotaCAEX", "texto?"),
        _c("EquipoCarguio", "texto"),
        _c("FlotaCarguio", "texto?"),
        _c("Origen", "texto", "frente, fase o stock de carga"),
        _c("TipoOrigen", "texto?"),
        _c("Destino", "texto", "chancado, botadero o stock de descarga"),
        _c("TipoDestino", "texto?"),
        _c("Material", "texto?"),
        _c("HoraSalida", "fechahora", "inicio del ciclo"),
        _c("HoraLlegada", "fechahora?", "llegada a destino"),
        _c("HoraLleno", "fechahora?", "fin de carga"),
        _c("HoraVacio", "fechahora?", "fin de descarga"),
        _c("Tonelaje", "decimal"),
        _c("Distancia", "decimal?", "metros"),
        _c("TiempoViajeS", "decimal", "viaje vacío hacia la pala"),
        _c("TiempoEsperaS", "decimal", "CAEX esperando pala"),
        _c("TiempoAculatamientoS", "decimal", "maniobra de posicionamiento en la pala"),
        _c("TiempoCargaS", "decimal"),
        _c("TiempoAcarreoS", "decimal", "cargado hacia el destino"),
        _c("TiempoColaS", "decimal", "CAEX en cola para descargar"),
        _c("TiempoRetrocesoS", "decimal"),
        _c("TiempoDescargaS", "decimal"),
        _c("PalaEsperandoS", "decimal", "carguío esperando CAEX"),
        _c("Ciclos", "entero"),
        _c("Cargas", "entero"),
    ),
    parametros=("InicioTurnoAnterior",),
    tabla_origen="ciclos", maximo_edad_s=20 * 60,
))

# --- Chancado
_registrar(Dataset(
    nombre="chancado_descargas",
    descripcion="Descargas en chancado del día operacional actual, por carguío/CAEX/origen con ley CuT.",
    servidor="despacho", archivo_sql="chancado_descargas.sql", intervalo_s=60, timeout_s=60,
    columnas=(
        _c("Fecha", "fecha"), _c("Turno", "texto"), _c("EquipoCarguio", "texto?"), _c("CAEX", "texto?"),
        _c("Ley", "texto?", "categoría de ley del material"), _c("Origen", "texto?"), _c("Destino", "texto"),
        _c("Material", "texto?"), _c("Tonelaje", "decimal"), _c("Viajes", "entero"),
        _c("CuT", "decimal?", "% CuT"),
    ),
    parametros=("FechaOpAyer", "FechaOpHoy"),
    tabla_origen="descargas",
))

_registrar(Dataset(
    nombre="chancado_hora",
    descripcion="Tonelaje a chancado por hora de reloj y origen (hoy y ayer operacional).",
    servidor="despacho", archivo_sql="chancado_hora.sql", intervalo_s=60, timeout_s=60,
    columnas=(
        _c("Fecha", "fecha", "día operativo de la descarga"),
        _c("Hora", "entero", "hora de reloj local 0..23 (de la marca UTC convertida)"),
        _c("HoraTurno", "entero?", "1..12 dentro del turno; None si cae fuera"),
        _c("Turno", "texto"),
        _c("Origen", "texto", "código de origen: F01..F04 (fases) o STK (stock)"),
        _c("Tonelaje", "decimal"),
    ),
    parametros=("DesfaseMinutos", "FechaOpAyer", "FechaOpHoy"),
    tabla_origen="descargas",
))

_registrar(Dataset(
    nombre="ley_hora",
    descripcion="Ley CuT ponderada por hora y origen de la alimentación a chancado (hoy operacional).",
    servidor="despacho", archivo_sql="ley_hora.sql", intervalo_s=60, timeout_s=60,
    columnas=(
        _c("Fecha", "fecha"), _c("Turno", "texto"), _c("Origen", "texto"),
        _c("OrdenHoraDia", "entero", "1..24"), _c("Tonelaje", "decimal"), _c("LeyxTon", "decimal"),
    ),
    parametros=("FechaOpAyer", "FechaOpHoy"),
    tabla_origen="descargas",
))

# --- Velocidad CAEX por hora (incluye flota auxiliar con columna Flota)
_registrar(Dataset(
    nombre="velocidad_hora",
    descripcion="Lecturas GPS de velocidad agregadas por día operacional, turno, hora y CAEX (últimos días).",
    servidor="despacho", archivo_sql="velocidad_hora.sql", intervalo_s=60, timeout_s=90,
    columnas=(
        _c("Fecha", "fecha"), _c("Turno", "texto"), _c("OrdenHoraDia", "entero"), _c("Equipo", "texto"),
        _c("Flota", "texto", "'Principal' | 'Auxiliar'"),
        _c("Lecturas", "entero"), _c("SumaVelocidad", "decimal"),
        _c("LecturasMovimiento", "entero"), _c("SumaVelocidadMovimiento", "decimal"),
    ),
    parametros=("DesfaseMinutos", "DesdeUtcHistoria", "HastaUtc"),
    tabla_origen="gps_lecturas",
))

# --- GPS en vivo (todos los equipos, últimos minutos)
_registrar(Dataset(
    nombre="gps",
    descripcion="Últimas posiciones GPS de CAEX, palas, cargadores y perforadoras (ventana de minutos).",
    servidor="despacho", archivo_sql="gps.sql", intervalo_s=10, timeout_s=30,
    columnas=(
        _c("Equipo", "texto"), _c("TipoEquipo", "texto?"),
        _c("FechaHora", "fechahora", "hora local"),
        _c("Latitud", "decimal", "milisegundos de arco (grados = valor / 3.600.000)"),
        _c("Longitud", "decimal", "milisegundos de arco"),
        _c("Velocidad", "decimal", "km/h"),
    ),
    parametros=("DesdeUtc", "HastaUtc", "DesfaseMinutos"),
    tabla_origen="gps_lecturas", maximo_edad_s=5 * 60,
))

# --- Estado actual de cada equipo (opcional: si falta, se deriva de horas_equipo y gps)
_registrar(Dataset(
    nombre="estado_equipos",
    descripcion="Estado vigente de cada equipo (categoría, motivo, desde cuándo). Opcional: si no está, se deriva de horas_equipo y gps.",
    servidor="despacho", archivo_sql="estado_equipos.sql", intervalo_s=30, timeout_s=30,
    columnas=(
        _c("Equipo", "texto"), _c("TipoEquipo", "texto?"),
        _c("Categoria", "texto", "Operativo | DemoraOperacional | DemoraProgramada | MantencionProgramada | MantencionNoProgramada | Reserva"),
        _c("Motivo", "texto?", "razón o estado detallado"),
        _c("Desde", "fechahora", "inicio del estado, hora local"),
    ),
    parametros=("AhoraLocal",),
    tabla_origen="estados_equipo", opcional=True,
))

# --- Planes
_cols_plan_horas = (
    _c("HorasDisponiblesPlan", "decimal?"), _c("HorasEfectivasPlan", "decimal?"),
    _c("HorasNominalesPlan", "decimal?"), _c("HorasOperativasPlan", "decimal?"),
)
_registrar(Dataset(
    nombre="plan_caex",
    descripcion="Plan semanal diario de la flota CAEX: horas y toneladas (movimiento total mina).",
    servidor="despacho", archivo_sql="plan_caex.sql", intervalo_s=1800, timeout_s=60,
    columnas=(_c("Fecha", "fecha"),) + _cols_plan_horas + (_c("ToneladasPlan", "decimal?"),),
    parametros=("FechaInicioPlanes",), tabla_origen="planes",
))
_registrar(Dataset(
    nombre="plan_carguio",
    descripcion="Plan diario por equipo de carguío (palas y cargadores): horas y toneladas.",
    servidor="despacho", archivo_sql="plan_carguio.sql", intervalo_s=1800, timeout_s=60,
    columnas=(_c("Fecha", "fecha"), _c("Equipo", "texto")) + _cols_plan_horas + (_c("ToneladasPlan", "decimal?"),),
    parametros=("FechaInicioPlanes",), tabla_origen="planes",
))
_registrar(Dataset(
    nombre="plan_perforadoras",
    descripcion="Plan semanal diario por perforadora: horas y metros.",
    servidor="despacho", archivo_sql="plan_perforadoras.sql", intervalo_s=1800, timeout_s=60,
    columnas=(_c("Fecha", "fecha"), _c("Equipo", "texto")) + _cols_plan_horas + (_c("MetrosPlan", "decimal?"),),
    parametros=("FechaInicioPlanes",), tabla_origen="planes",
))
_registrar(Dataset(
    nombre="plan_chancador",
    descripcion="Plan semanal diario del chancador: toneladas y ley CuT.",
    servidor="despacho", archivo_sql="plan_chancador.sql", intervalo_s=1800, timeout_s=60,
    columnas=(_c("Fecha", "fecha"), _c("ToneladasPlan", "decimal?"), _c("LeyCuTPlan", "decimal?", "% CuT")),
    parametros=("FechaInicioPlanes",), tabla_origen="planes",
))
_registrar(Dataset(
    nombre="plan_indicadores",
    descripcion="Plan mensual de indicadores de la flota auxiliar (base de planta): DF, UEBD y rendimiento por tag y fecha.",
    servidor="planta", archivo_sql="plan_indicadores.sql", intervalo_s=1800, timeout_s=60,
    columnas=(_c("Tag", "texto"), _c("Fecha", "fecha"), _c("Valor", "decimal")),
    parametros=("FechaInicioPlanes",), tabla_origen="valores", opcional=True,
))

# --- Catálogo de equipos
_registrar(Dataset(
    nombre="equipos",
    descripcion="Catálogo de equipos con tipo, flota y bandera ActivoKPI (0 = flota auxiliar o equipo de test).",
    servidor="despacho", archivo_sql="equipos.sql", intervalo_s=3600, timeout_s=60,
    columnas=(_c("Equipo", "texto"), _c("TipoEquipo", "texto"), _c("Flota", "texto?"), _c("ActivoKPI", "entero")),
    parametros=(), tabla_origen="equipos",
))


# ---------------------------------------------------------------------------
# Validación de registros (la usan los tests, el simulador y la fuente SQL al activarse)
# ---------------------------------------------------------------------------
def _tipo_ok(valor: Any, tipo: str) -> bool:
    if tipo == "fecha":
        if not isinstance(valor, str):
            return False
        try:
            dt.date.fromisoformat(valor)
            return True
        except ValueError:
            return False
    if tipo == "fechahora":
        if not isinstance(valor, str):
            return False
        try:
            dt.datetime.fromisoformat(valor)
            return True
        except ValueError:
            return False
    if tipo == "texto":
        return isinstance(valor, str)
    if tipo == "entero":
        return isinstance(valor, int) and not isinstance(valor, bool)
    if tipo == "decimal":
        return isinstance(valor, (int, float)) and not isinstance(valor, bool)
    return False


def validar_registros(nombre: str, filas: list[dict[str, Any]], maximo_errores: int = 20) -> list[str]:
    """Devuelve una lista de problemas (vacía si todo calza con el contrato)."""
    ds = DATASETS[nombre]
    errores: list[str] = []
    esperadas = ds.nombres_columnas()
    for i, fila in enumerate(filas):
        faltan = [c for c in esperadas if c not in fila]
        sobran = [c for c in fila if c not in esperadas]
        if faltan:
            errores.append(f"{nombre}[{i}]: faltan columnas {faltan}")
        if sobran:
            errores.append(f"{nombre}[{i}]: columnas no esperadas {sobran}")
        for col in ds.columnas:
            if col.nombre not in fila:
                continue
            valor = fila[col.nombre]
            if valor is None:
                if not col.nulo:
                    errores.append(f"{nombre}[{i}].{col.nombre}: None no permitido")
                continue
            if not _tipo_ok(valor, col.tipo_base):
                errores.append(f"{nombre}[{i}].{col.nombre}: valor {valor!r} no es {col.tipo_base}")
        if len(errores) >= maximo_errores:
            errores.append("... (se omiten más errores)")
            break
    return errores


def normalizar_valor(valor: Any, tipo: str) -> Any:
    """Convierte valores crudos de un driver SQL al tipo del contrato (fechas -> ISO, Decimal -> float)."""
    if valor is None:
        return None
    base = tipo.rstrip("?")
    if base == "fecha":
        if isinstance(valor, dt.datetime):
            return valor.date().isoformat()
        if isinstance(valor, dt.date):
            return valor.isoformat()
        return str(valor)[:10]
    if base == "fechahora":
        if isinstance(valor, dt.datetime):
            return valor.replace(microsecond=0, tzinfo=None).isoformat()
        return str(valor).replace(" ", "T")[:19]
    if base == "texto":
        return str(valor).strip()
    if base == "entero":
        return int(valor)
    if base == "decimal":
        return float(valor)
    return valor


def normalizar_filas(nombre: str, filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ds = DATASETS[nombre]
    salida = []
    for fila in filas:
        salida.append({c.nombre: normalizar_valor(fila.get(c.nombre), c.tipo) for c in ds.columnas})
    return salida
