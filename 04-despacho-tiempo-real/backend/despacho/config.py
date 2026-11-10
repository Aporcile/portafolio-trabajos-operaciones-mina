"""Carga de configuración en dos niveles.

1. `.env` (secretos, modo de datos, red): se lee con un parser propio (sin dependencias),
   NO pisa variables de entorno ya definidas en el proceso y nunca se escribe a logs.
2. Archivos TOML legibles en `config/` (umbrales, reglas de alerta, planes por defecto,
   mapa, escenarios): se leen con `tomllib` (incluido en Python 3.11+).

Uso:
    cfg = cargar_config()            # raíz del proyecto detectada automáticamente
    cfg.dashboard["refresco"]["snapshot_s"]
    cfg.env("DESPACHO_PASSWORD")     # secreto (no loguear)
    cfg.resumen_sin_secretos()       # para /api/health y logs
"""
from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("despacho.config")

RAIZ = Path(__file__).resolve().parents[2]  # raíz del proyecto (contiene backend/, config/, docs/)
CLAVES_SECRETAS = ("PASSWORD", "API_KEY", "TOKEN", "SECRET", "CONTRASENA")

# Valores por defecto genéricos: nunca contienen credenciales ni nombres de servidores reales.
VALORES_POR_DEFECTO_ENV = {
    "DATA_SOURCE": "auto",
    "WEB_HOST": "127.0.0.1",
    "WEB_PORT": "8080",
    "WEB_TOKEN": "",
    "DESPACHO_SERVER": "servidor-demo",
    "DESPACHO_DATABASE": "despacho_demo",
    "DESPACHO_USER": "",
    "DESPACHO_PASSWORD": "",
    "DESPACHO_AUTH": "sql",
    "PLANTA_SERVER": "servidor-demo",
    "PLANTA_DATABASE": "planta_demo",
    "PLANTA_USER": "",
    "PLANTA_PASSWORD": "",
    "PLANTA_AUTH": "sql",
    "SQL_ENCRYPT": "yes",
    "SQL_TRUST_SERVER_CERTIFICATE": "no",
    "SQL_TIMEOUT_S": "30",
    "ZONA_HORARIA": "UTC",
    "ZONA_DESFASE_RESPALDO_H": "0",
    "IA_PROVEEDOR": "reglas",
    "IA_API_KEY": "",
    "DEMO_ESCENARIO": "turno_normal",
    "DEMO_SEMILLA": "42",
    "DEMO_FACTOR_TIEMPO": "1",
    "DEMO_INICIO": "",
    "LOG_NIVEL": "INFO",
}


def leer_env(ruta: Path) -> dict[str, str]:
    """Parser mínimo de .env: CLAVE=VALOR, comentarios con #, comillas opcionales."""
    valores: dict[str, str] = {}
    if not ruta.exists():
        return valores
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip()
        valor = valor.strip()
        if valor[:1] in ("'", '"') and valor[-1:] == valor[:1] and len(valor) >= 2:
            valor = valor[1:-1]
        else:
            # permitir comentario al final de la línea
            if " #" in valor:
                valor = valor.split(" #", 1)[0].rstrip()
        valores[clave] = valor
    return valores


def es_secreto(clave: str) -> bool:
    c = clave.upper()
    return any(s in c for s in CLAVES_SECRETAS)


def _leer_toml(ruta: Path, *, opcional: bool = False) -> dict[str, Any]:
    if not ruta.exists():
        if not opcional:
            log.warning("Archivo de configuración no encontrado: %s", ruta)
        return {}
    with ruta.open("rb") as f:
        return tomllib.load(f)


@dataclass
class Config:
    raiz: Path
    _env: dict[str, str] = field(default_factory=dict, repr=False)
    dashboard: dict[str, Any] = field(default_factory=dict)
    alertas: dict[str, Any] = field(default_factory=dict)
    ia: dict[str, Any] = field(default_factory=dict)
    plan_horario: dict[str, Any] = field(default_factory=dict)
    mapa: dict[str, Any] = field(default_factory=dict)

    # ----- .env -----
    def env(self, clave: str, defecto: str | None = None) -> str:
        if clave in self._env:
            return self._env[clave]
        if defecto is not None:
            return defecto
        return VALORES_POR_DEFECTO_ENV.get(clave, "")

    def env_bool(self, clave: str) -> bool:
        return self.env(clave).strip().lower() in ("1", "true", "yes", "si", "sí", "on")

    def env_int(self, clave: str, defecto: int = 0) -> int:
        try:
            return int(float(self.env(clave) or defecto))
        except ValueError:
            return defecto

    def env_float(self, clave: str, defecto: float = 0.0) -> float:
        try:
            return float(self.env(clave) or defecto)
        except ValueError:
            return defecto

    @property
    def modo_datos(self) -> str:
        valor = self.env("DATA_SOURCE").strip().lower() or "auto"
        return valor if valor in ("auto", "demo", "sql") else "auto"

    def credenciales_completas(self, servidor: str = "DESPACHO") -> bool:
        """True si hay lo necesario para intentar una conexión real a ese servidor."""
        servidor = servidor.upper()
        if self.env(f"{servidor}_AUTH").lower() == "windows":
            return bool(self.env(f"{servidor}_SERVER"))
        return bool(self.env(f"{servidor}_SERVER") and self.env(f"{servidor}_USER") and self.env(f"{servidor}_PASSWORD"))

    # ----- utilidades -----
    def resumen_sin_secretos(self) -> dict[str, str]:
        salida = {}
        for clave in sorted(set(VALORES_POR_DEFECTO_ENV) | set(self._env)):
            valor = self.env(clave)
            salida[clave] = ("***" if valor else "") if es_secreto(clave) else valor
        return salida

    def ruta(self, *partes: str) -> Path:
        return self.raiz.joinpath(*partes)

    def escenario(self, nombre: str | None = None) -> dict[str, Any]:
        nombre = nombre or self.env("DEMO_ESCENARIO") or "turno_normal"
        ruta = self.raiz / "config" / "escenarios" / f"{nombre}.toml"
        datos = _leer_toml(ruta, opcional=True)
        if not datos and nombre != "turno_normal":
            log.warning("Escenario '%s' no existe; se usa turno_normal", nombre)
            datos = _leer_toml(self.raiz / "config" / "escenarios" / "turno_normal.toml", opcional=True)
        datos.setdefault("nombre", nombre)
        return datos

    def escenarios_disponibles(self) -> list[str]:
        carpeta = self.raiz / "config" / "escenarios"
        return sorted(p.stem for p in carpeta.glob("*.toml")) if carpeta.exists() else []


def cargar_config(raiz: Path | None = None, env_extra: dict[str, str] | None = None) -> Config:
    """Carga .env + TOML. `env_extra` permite inyectar valores en tests."""
    raiz = Path(raiz) if raiz else RAIZ
    env: dict[str, str] = {}
    env.update(leer_env(raiz / ".env"))
    # Las variables del proceso tienen prioridad sobre .env
    for clave in list(VALORES_POR_DEFECTO_ENV) + list(env):
        if clave in os.environ:
            env[clave] = os.environ[clave]
    if env_extra:
        env.update(env_extra)
    carpeta = raiz / "config"
    return Config(
        raiz=raiz,
        _env=env,
        dashboard=_leer_toml(carpeta / "dashboard.toml"),
        alertas=_leer_toml(carpeta / "alertas.toml", opcional=True),
        ia=_leer_toml(carpeta / "ia.toml", opcional=True),
        plan_horario=_leer_toml(carpeta / "plan_horario.toml"),
        mapa=_leer_toml(carpeta / "mapa.toml"),
    )


def obtener(diccionario: dict[str, Any], ruta: str, defecto: Any = None) -> Any:
    """obtener(cfg.dashboard, 'refresco.snapshot_s', 10)."""
    actual: Any = diccionario
    for parte in ruta.split("."):
        if not isinstance(actual, dict) or parte not in actual:
            return defecto
        actual = actual[parte]
    return actual
