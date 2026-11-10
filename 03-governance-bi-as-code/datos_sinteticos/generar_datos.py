# -*- coding: utf-8 -*-
"""Genera los CSV 100 % sintéticos del informe de gobernanza de uso de reportes (empresa ficticia Minera Demo).

Escribe en datos_sinteticos/csv/:
  dim_reporte.csv    inventario de reportes (report_id, report_nombre, workspace_id, workspace_nombre, url)
  fact_uso.csv       uso diario: fecha x reporte x usuario (aperturas y vistas de página)
  lecturas_area.csv  registro de la extracción: última lectura de cada área
y datos_sinteticos/esperados.json con las cifras que debe dar el modelo (las usa validacion_datos.dax).

Nada sale de un sistema real: workspaces, reportes, usuarios e identificadores son inventados y la semilla es fija,
así que cada ejecución reproduce los mismos archivos.

El perfil de uso incluye a propósito los casos que el informe debe detectar:
  - reportes con mucho uso, poco uso, abandonados y sin uso;
  - reportes que solo registran aperturas (sin vistas de página), típico de un acceso automatizado;
  - un reporte con el mismo nombre en dos áreas (la etiqueta única lo distingue);
  - un área cuya extracción se detuvo antes del final (cobertura incompleta);
  - una cuenta de mantenimiento cuyo uso se excluye del modelo (usuarios_excluidos).

Uso:  python generar_datos.py
"""
import csv
import json
import sys
import uuid
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.dont_write_bytecode = True   # no dejar __pycache__ dentro de tools/ al importar sinteticos
sys.path.insert(0, str(AQUI.parents[1] / "tools"))
from sinteticos import DOMINIO, dias, rng  # noqa: E402

SALIDA = AQUI / "csv"
INICIO = date(2025, 3, 3)          # lunes
N_DIAS = 90                        # 2025-03-03 a 2025-05-31
FIN = INICIO + timedelta(days=N_DIAS - 1)
ESPACIO = uuid.UUID("6f1d3c52-8a47-4b7e-9d21-3c5e7a9b1f04")  # solo para derivar identificadores inventados
URL_BASE = "https://powerbi.example.com"

# Workspaces: (clave corta, nombre). El modelo quita "WS-DEMO-" y "-PROD" y cambia "_" por espacio.
WORKSPACES = [
    ("operaciones", "WS-DEMO-Operaciones_Mina-PROD"),
    ("mantenimiento", "WS-DEMO-Mantenimiento_Mina-PROD"),
    ("planta", "WS-DEMO-Planta_Chancado-PROD"),
    ("control", "WS-DEMO-Centro_Control-PROD"),
]
AREA_SIN_LECTURA_FINAL = "planta"   # su extracción se detiene antes del final
DIAS_SIN_LECTURA = 13

# Reportes: (workspace, nombre, perfil). Perfiles: alto, medio, bajo, abandonado, solo_aperturas, sin_uso.
REPORTES = [
    ("operaciones", "Tablero Movimiento Mina", "alto"),
    ("operaciones", "Cumplimiento Plan Diario", "alto"),
    ("operaciones", "Productividad Flota CAEX", "alto"),
    ("operaciones", "Asignacion de Equipos", "medio"),
    ("operaciones", "Resumen Operativo", "medio"),
    ("operaciones", "Reporte Fin de Turno", "medio"),
    ("operaciones", "Seguimiento de Reconciliacion", "solo_aperturas"),
    ("mantenimiento", "Disponibilidad Fisica Flota", "alto"),
    ("mantenimiento", "Backlog de Ordenes", "medio"),
    ("mantenimiento", "Cumplimiento Plan Mantencion", "medio"),
    ("mantenimiento", "Resumen Operativo", "bajo"),
    ("mantenimiento", "Indicadores de Neumaticos", "abandonado"),
    ("mantenimiento", "Paradas No Programadas", "sin_uso"),
    ("planta", "Rendimiento Chancado", "alto"),
    ("planta", "Granulometria Alimentacion", "medio"),
    ("planta", "Utilizacion Chancador", "medio"),
    ("planta", "Balance de Planta", "bajo"),
    ("planta", "Alarmas de Proceso", "solo_aperturas"),
    ("planta", "Indicadores Planta", "sin_uso"),
    ("control", "Vista General Operacion", "alto"),
    ("control", "Alertas y Eventos", "medio"),
    ("control", "Seguimiento de Metas", "bajo"),
    ("control", "Calidad de Datos Operacionales", "solo_aperturas"),
    ("control", "Panel de Adopcion de Reportes", "sin_uso"),
]
# Usuarios medios diarios que abren un reporte en un día hábil, según su perfil
PERFIL_USUARIOS = {"alto": 5.0, "medio": 2.3, "bajo": 0.7, "abandonado": 2.0}
DIA_ABANDONO = 38      # un reporte "abandonado" deja de usarse a partir de este día

N_INTERNOS, N_EXTERNOS = 16, 4
CUENTA_AUTOMATIZADA = f"ext.demo04@{DOMINIO}"          # abre reportes sin ver páginas
CUENTA_MANTENIMIENTO = f"admin.demo01@{DOMINIO}"       # mantiene el informe: su uso se excluye del modelo
USUARIOS_EXCLUIDOS = [CUENTA_MANTENIMIENTO]

COLUMNAS_FACT = ["fecha", "workspace_id", "workspace_nombre", "report_id", "report_nombre", "usuario",
                 "aperturas", "vistas_pagina", "es_sintetico"]


def nuevo_id(*partes):
    return str(uuid.uuid5(ESPACIO, ":".join(partes)))


def construir_inventario():
    ws = {clave: {"id": nuevo_id("ws", clave), "nombre": nombre, "clave": clave} for clave, nombre in WORKSPACES}
    reportes = []
    for i, (clave, nombre, perfil) in enumerate(REPORTES, 1):
        w = ws[clave]
        rid = nuevo_id("rep", f"{i:02d}")
        reportes.append({"id": rid, "nombre": nombre, "perfil": perfil, "ws": w,
                         "url": f"{URL_BASE}/groups/{w['id']}/reports/{rid}"})
    return ws, reportes


def construir_usuarios():
    internos = [f"persona.demo{i:02d}@{DOMINIO}" for i in range(1, N_INTERNOS + 1)]
    externos = [f"ext.demo{i:02d}@{DOMINIO}" for i in range(1, N_EXTERNOS + 1)]
    return internos, externos


def audiencia(r, usuarios, perfil):
    """Subconjunto de usuarios que abre un reporte, con pesos decrecientes (unos pocos concentran el uso)."""
    n = {"alto": 13, "medio": 8, "bajo": 4, "abandonado": 6}.get(perfil, 3)
    elegidos = r.sample(usuarios, min(n, len(usuarios)))
    return elegidos, [1.0 / (k + 1) ** 0.8 for k in range(len(elegidos))]


def factor_dia(d):
    """Más uso entre semana, poco el fin de semana, con una suave alza a lo largo del periodo."""
    base = 1.0 if d.weekday() < 5 else 0.22
    return base * (0.85 + 0.30 * (d - INICIO).days / N_DIAS)


def generar_filas(reportes, internos, externos):
    r = rng("fact_uso")
    usuarios = internos + externos[:3]          # la cuenta automatizada se trata aparte
    filas = []
    ultimo_dia_area = {w[0]: FIN for w in WORKSPACES}
    ultimo_dia_area[AREA_SIN_LECTURA_FINAL] = FIN - timedelta(days=DIAS_SIN_LECTURA)

    def fila(d, rep, usuario, aperturas, vistas):
        filas.append({"fecha": d.isoformat(), "workspace_id": rep["ws"]["id"], "workspace_nombre": rep["ws"]["nombre"],
                      "report_id": rep["id"], "report_nombre": rep["nombre"], "usuario": usuario,
                      "aperturas": aperturas, "vistas_pagina": vistas, "es_sintetico": "True"})

    aud = {}
    for rep in reportes:
        if rep["perfil"] in PERFIL_USUARIOS:
            pool = usuarios if rep["ws"]["clave"] != "control" else internos
            aud[rep["id"]] = audiencia(r, pool, rep["perfil"])

    for d in dias(INICIO, N_DIAS):
        f = factor_dia(d)
        for rep in reportes:
            perfil, clave = rep["perfil"], rep["ws"]["clave"]
            if d > ultimo_dia_area[clave]:
                continue
            if perfil == "abandonado" and (d - INICIO).days >= DIA_ABANDONO:
                continue
            # Uso normal: cada usuario de la audiencia abre el reporte con probabilidad proporcional a su peso
            if rep["id"] in aud:
                users, pesos = aud[rep["id"]]
                esperado = PERFIL_USUARIOS[perfil] * f
                total = sum(pesos)
                for u, p in zip(users, pesos):
                    if r.random() < min(0.95, esperado * p / total):
                        aperturas = 1 + int(r.random() < 0.35) + int(r.random() < 0.12)
                        # algunas aperturas se cierran antes de mostrar una página
                        vistas = 0 if r.random() < 0.08 else max(1, round(aperturas * r.uniform(0.9, 3.4)))
                        fila(d, rep, u, aperturas, vistas)
            # Reportes que solo registran aperturas: la cuenta automatizada los abre a diario sin ver páginas
            if perfil == "solo_aperturas" and r.random() < (0.9 if d.weekday() < 5 else 0.5):
                fila(d, rep, CUENTA_AUTOMATIZADA, r.randint(1, 4), 0)

        # La cuenta automatizada también abre algunos reportes en uso (sin vistas de página)
        if d.weekday() < 5 and d <= ultimo_dia_area["operaciones"]:
            for rep in reportes:
                if rep["perfil"] == "alto" and rep["ws"]["clave"] in ("operaciones", "control") and r.random() < 0.7:
                    fila(d, rep, CUENTA_AUTOMATIZADA, r.randint(1, 3), 0)

    # La cuenta de mantenimiento revisa todos los reportes (también los sin uso): se excluye del modelo
    rm = rng("mantenimiento")
    for d in dias(INICIO, N_DIAS):
        for rep in reportes:
            if d <= ultimo_dia_area[rep["ws"]["clave"]] and rm.random() < 0.32:
                fila(d, rep, CUENTA_MANTENIMIENTO, rm.randint(1, 2), rm.randint(1, 4))

    # Una fila por día x reporte x usuario (se suman repetidos, no deberían existir)
    agrupado = defaultdict(lambda: [0, 0])
    modelo = {}
    for x in filas:
        k = (x["fecha"], x["report_id"], x["usuario"])
        agrupado[k][0] += x["aperturas"]
        agrupado[k][1] += x["vistas_pagina"]
        modelo[k] = x
    salida = []
    for k in sorted(modelo, key=lambda k: (k[0], modelo[k]["workspace_nombre"], modelo[k]["report_nombre"], k[2])):
        x = dict(modelo[k])
        x["aperturas"], x["vistas_pagina"] = agrupado[k]
        salida.append(x)
    return salida, ultimo_dia_area


def escribir_csv(ruta, columnas, filas):
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columnas, lineterminator="\n")
        w.writeheader()
        w.writerows(filas)


def nombre_corto(nombre_ws):
    n = nombre_ws[len("WS-DEMO-"):] if nombre_ws.startswith("WS-DEMO-") else nombre_ws
    n = n[:-len("-PROD")] if n.endswith("-PROD") else n
    return n.replace("_", " ").strip()


def etiqueta_reporte(reportes):
    """Réplica de la columna Dim_Reporte[Reporte]: el nombre, y con el área si el nombre se repite."""
    cuenta = defaultdict(int)
    for rep in reportes:
        cuenta[rep["nombre"].lower()] += 1
    return {rep["id"]: (f"{rep['nombre']} · {nombre_corto(rep['ws']['nombre'])}" if cuenta[rep["nombre"].lower()] > 1
                        else rep["nombre"]) for rep in reportes}


def calcular_esperados(filas_csv, reportes, internos, externos):
    """Lo que debe dar el modelo tras excluir a USUARIOS_EXCLUIDOS (validacion_datos.dax)."""
    en_modelo = [x for x in filas_csv if x["usuario"] not in USUARIOS_EXCLUIDOS]
    etiquetas = etiqueta_reporte(reportes)
    por_rep = defaultdict(lambda: {"ap": 0, "vi": 0})
    por_area = defaultdict(lambda: {"ap": 0, "vi": 0})
    usuarios = set()
    for x in en_modelo:
        por_rep[x["report_id"]]["ap"] += x["aperturas"]
        por_rep[x["report_id"]]["vi"] += x["vistas_pagina"]
        usuarios.add(x["usuario"])
    estado = {}
    for rep in reportes:
        d = por_rep[rep["id"]]
        estado[rep["id"]] = "En uso" if d["vi"] >= 1 else ("Solo aperturas" if d["ap"] > 0 else "Sin uso")
        a = por_area[nombre_corto(rep["ws"]["nombre"])]
        a["total"] = a.get("total", 0) + 1
        a["ap"] += d["ap"]
        a["vi"] += d["vi"]
        a[estado[rep["id"]]] = a.get(estado[rep["id"]], 0) + 1
    ap = sum(x["aperturas"] for x in en_modelo)
    vi = sum(x["vistas_pagina"] for x in en_modelo)
    fechas = sorted({x["fecha"] for x in en_modelo})
    externos_set = {u for u in usuarios if u.startswith("ext.")}
    de = lambda pred: sum(x["aperturas"] for x in en_modelo if pred(x["usuario"]))  # noqa: E731
    dv = lambda pred: sum(x["vistas_pagina"] for x in en_modelo if pred(x["usuario"]))  # noqa: E731

    def elegir(estado_buscado):
        for rep in reportes:
            if estado[rep["id"]] == estado_buscado and rep["perfil"] in ("alto", "solo_aperturas", "sin_uso"):
                return etiquetas[rep["id"]]
        return None

    cuenta = defaultdict(int)
    for rep in reportes:
        cuenta[estado[rep["id"]]] += 1
    return {
        "filas_csv": len(filas_csv),
        "filas_excluidas": len(filas_csv) - len(en_modelo),
        "filas_modelo": len(en_modelo),
        "reportes": len(reportes),
        "areas": len(WORKSPACES),
        "dias": len(fechas),
        "datos_desde": fechas[0],
        "ultima_actividad": fechas[-1],
        "usuarios": len(usuarios),
        "usuarios_externos": len(externos_set),
        "aperturas": ap,
        "vistas_pagina": vi,
        "paginas_por_apertura": round(vi / ap, 2) if ap else 0,
        "aperturas_sin_vistas": sum(x["aperturas"] for x in en_modelo if x["vistas_pagina"] == 0),
        "aperturas_internos": de(lambda u: not u.startswith("ext.")),
        "aperturas_externos": de(lambda u: u.startswith("ext.")),
        "vistas_internos": dv(lambda u: not u.startswith("ext.")),
        "vistas_externos": dv(lambda u: u.startswith("ext.")),
        "reportes_en_uso": cuenta["En uso"],
        "reportes_solo_aperturas": cuenta["Solo aperturas"],
        "reportes_sin_uso": cuenta["Sin uso"],
        "reporte_en_uso": elegir("En uso"),
        "reporte_solo_aperturas": elegir("Solo aperturas"),
        "reporte_sin_uso": elegir("Sin uso"),
        "nombres_repetidos": sorted({rep["nombre"] for rep in reportes
                                     if sum(1 for o in reportes if o["nombre"].lower() == rep["nombre"].lower()) > 1}),
        "por_area": {k: v for k, v in sorted(por_area.items())},
    }


def main():
    ws, reportes = construir_inventario()
    internos, externos = construir_usuarios()
    filas, ultimo_dia_area = generar_filas(reportes, internos, externos)
    SALIDA.mkdir(parents=True, exist_ok=True)

    escribir_csv(SALIDA / "dim_reporte.csv",
                 ["report_id", "report_nombre", "workspace_id", "workspace_nombre", "url"],
                 [{"report_id": rep["id"], "report_nombre": rep["nombre"], "workspace_id": rep["ws"]["id"],
                   "workspace_nombre": rep["ws"]["nombre"], "url": rep["url"]} for rep in reportes])
    escribir_csv(SALIDA / "fact_uso.csv", COLUMNAS_FACT, filas)
    # La lectura corre de madrugada del día siguiente al último día cargado de cada área
    escribir_csv(SALIDA / "lecturas_area.csv", ["workspace_id", "ultima_lectura"],
                 [{"workspace_id": w["id"],
                   "ultima_lectura": f"{(ultimo_dia_area[w['clave']] + timedelta(days=1)).isoformat()} 06:00"}
                  for w in ws.values()])

    esperados = calcular_esperados(filas, reportes, internos, externos)
    esperados["usuarios_excluidos"] = USUARIOS_EXCLUIDOS
    assert esperados["datos_desde"] == INICIO.isoformat() and esperados["ultima_actividad"] == FIN.isoformat(), \
        "el modelo debe cubrir el periodo completo"
    assert esperados["usuarios"] == N_INTERNOS + N_EXTERNOS, "se esperaban todos los usuarios en el modelo"
    (AQUI / "esperados.json").write_text(json.dumps(esperados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"dim_reporte.csv: {len(reportes)} reportes en {len(ws)} áreas")
    print(f"fact_uso.csv: {len(filas)} filas ({esperados['filas_modelo']} tras excluir cuentas de mantenimiento)")
    print(f"periodo: {INICIO} a {FIN} ({N_DIAS} días) | usuarios en el modelo: {esperados['usuarios']}")
    print(f"estado: {esperados['reportes_en_uso']} en uso, {esperados['reportes_solo_aperturas']} solo aperturas, "
          f"{esperados['reportes_sin_uso']} sin uso")


if __name__ == "__main__":
    main()
