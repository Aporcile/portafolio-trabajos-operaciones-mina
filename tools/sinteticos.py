# -*- coding: utf-8 -*-
"""Generadores de datos 100 % sintéticos para minería a rajo abierto.

Toda cifra sale de una semilla fija: no se usa ningún registro real. Rangos inventados dentro de lo habitual:
  - Movimiento mina en miles de t (kt) por día.
  - Velocidad CAEX 15-30 km/h (cargado más lento que vacío).
  - DF (disponibilidad física) y UEBD en %.
  - Chancado en t/h; granulometría en 3 fracciones de masa 60/20/20 (fina/media/gruesa).
Los nombres de equipos y de personas son inventados (CAEX-01, PALA-01, «Persona Demo 01»...).

Uso típico:
    from sinteticos import rng, FLOTA_CAEX, dias, movimiento_mina_dia
"""
import random
from datetime import date, datetime, timedelta

SEMILLA = 20261110
DOMINIO = "minera-demo.example"

FLOTA_CAEX = [f"CAEX-{i:02d}" for i in range(1, 27)]
FLOTA_PALAS = [f"PALA-{i:02d}" for i in range(1, 5)]
FLOTA_CARGADORES = [f"CARG-{i:02d}" for i in range(1, 3)]
FLOTA_PERFORADORAS = [f"PERF-{i:02d}" for i in range(1, 5)]
FASES = ["Fase 1", "Fase 2", "Fase 3", "Fase 4"]
DESTINOS = ["Chancado Primario", "Dump Leach", "Botadero Estéril", "Stockpile"]
AREAS = ["Mina", "Chancado", "Molienda", "Flotación", "Hidrometalurgia"]
FRACCIONES = ["Fina (<12 mm)", "Media (12-25 mm)", "Gruesa (>25 mm)"]
TURNOS = ["A", "B"]
GRUPOS = ["G1", "G2", "G3", "G4"]


def rng(nombre):
    """Generador determinista por nombre de conjunto de datos."""
    return random.Random(f"{SEMILLA}:{nombre}")


def personas(n, nombre="personas"):
    """Personas ficticias: 'Persona Demo 01' con correo @minera-demo.example. No imitan a nadie real."""
    cargos = ["Jefe de Turno", "Supervisor", "Planificador", "Analista", "Operador", "Ingeniero de Procesos"]
    r = rng(nombre)
    return [
        {"id": i, "nombre": f"Persona Demo {i:02d}", "correo": f"persona.demo{i:02d}@{DOMINIO}",
         "cargo": r.choice(cargos), "grupo": GRUPOS[(i - 1) % 4]}
        for i in range(1, n + 1)
    ]


def dias(inicio, n):
    d0 = inicio if isinstance(inicio, date) else date.fromisoformat(inicio)
    return [d0 + timedelta(days=k) for k in range(n)]


def turno_de_hora(hora):
    """Mina: turno A 08:00-19:59, turno B 20:00-07:59. Día operacional 08:00 a 08:00."""
    return "A" if 8 <= hora < 20 else "B"


def movimiento_mina_dia(r):
    """Movimiento diario en kt (miles de t): total 150-260, con 30-40 % mineral."""
    total = r.uniform(150, 260)
    mineral = total * r.uniform(0.30, 0.40)
    return {"mineral_kt": round(mineral, 1), "lastre_kt": round(total - mineral, 1), "total_kt": round(total, 1)}


def velocidad_caex(r, cargado):
    """km/h entre 15 y 30; cargado 15-24, vacío 22-30."""
    return round(r.uniform(15, 24) if cargado else r.uniform(22, 30), 1)


def horas_equipo(r, tipo="CAEX"):
    """Horas del día de un equipo y sus KPI. DF 82-94 %, UEBD 70-85 %."""
    base = {"CAEX": (0.86, 0.94, 0.72, 0.85), "PALA": (0.82, 0.92, 0.70, 0.83)}.get(tipo, (0.82, 0.94, 0.70, 0.85))
    df = r.uniform(base[0], base[1])
    uebd = r.uniform(base[2], base[3])
    nominal = 24.0
    disp = nominal * df
    efectivas = disp * uebd
    return {"horas_nominales": nominal, "horas_disponibles": round(disp, 2),
            "horas_efectivas": round(efectivas, 2), "horas_mantencion": round(nominal - disp, 2),
            "df_pct": round(df * 100, 1), "uebd_pct": round(uebd * 100, 1)}


def chancado_tph(r, hora):
    """Alimentación a chancado en t/h con ritmo diurno suave (3.200-4.800)."""
    base = 4000 + 500 * (1 if 8 <= hora < 20 else 0) * 0.4
    return round(max(3200, min(4800, r.gauss(base, 250))), 0)


def granulometria(r):
    """Tres fracciones de masa que suman 100: ~60/20/20 con ruido de ±3 puntos."""
    f = r.gauss(60, 2.5)
    m = r.gauss(20, 1.5)
    g = 100 - f - m
    return {FRACCIONES[0]: round(f, 1), FRACCIONES[1]: round(m, 1), FRACCIONES[2]: round(g, 1)}


def semaforo(real, plan):
    """verde si real >= plan, naranjo si real >= 95 % del plan, rojo si menos, gris sin plan."""
    if plan in (None, 0):
        return "gris"
    return "verde" if real >= plan else ("naranjo" if real >= 0.95 * plan else "rojo")


def marcas_horarias(d):
    """24 marcas horarias de un día."""
    d0 = datetime(d.year, d.month, d.day)
    return [d0 + timedelta(hours=h) for h in range(24)]
