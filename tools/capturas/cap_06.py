# -*- coding: utf-8 -*-
"""Renders de diseño del proyecto 06-sustentabilidad-agua («Minera Demo»).

Genera dos PNG de 1920x1080 en 06-sustentabilidad-agua/capturas/:
  vista_general.png     página «Vista general» del informe pbip/gestion-agua-demo.Report
  balance_hidrico.png   página «Balance hídrico»

NO son capturas de Power BI Desktop: son renders dibujados con Pillow que respetan la disposición, los títulos y el tema
(MineraDemo.json) del informe. Las cifras salen de los CSV de datos_sinteticos/ aplicando las mismas reglas que las
medidas DAX del modelo (estado de pozos, estanques, alarmas, balance a 7/30 días, etc.).

Uso:  python tools/capturas/cap_06.py        (se puede ejecutar desde cualquier carpeta)
"""
import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from lib_render import Lienzo, LOGO_BLANCO, ICONO, PAL, fmt  # noqa: E402
from PIL import ImageFont  # noqa: E402

RAIZ = AQUI.parents[1]
PROY = RAIZ / "06-sustentabilidad-agua"
DATOS = PROY / "datos_sinteticos"
SALIDA = PROY / "capturas"
LEYENDA = "Render del diseño · datos sintéticos · Minera Demo"

# ---------------------------------------------------------------------------------------------------------------------
# Paleta del tema del informe (pbip/.../RegisteredResources/MineraDemo.json) y colores de estado del modelo
# ---------------------------------------------------------------------------------------------------------------------
NAVY = "#1B2A41"
AZUL = "#4F9DDE"
VIOLETA = "#7B61C9"
ROJO = "#D64550"
AMBAR = "#F2A03D"
GRIS_EST = "#A9B6C4"
CELESTE = "#9CC7EC"
TXT2 = "#3A4A60"
GRIS_EJE = "#8FA3B8"
BORDE = "#C5D0DC"
GRID = "#E6ECF2"
BLANCO = "#FFFFFF"
FONDO_PAG = "#EFF3F7"          # #E6ECF2 con 35 % de transparencia sobre blanco (page.json)
DATA_COLORS = ["#1B2A41", "#4F9DDE", "#7B61C9", "#D64550", "#F2A03D", "#2F6FB5"]


# ---------------------------------------------------------------------------------------------------------------------
# Datos: lectura de los CSV sintéticos y reglas equivalentes a las medidas DAX
# ---------------------------------------------------------------------------------------------------------------------
def _csv(nombre):
    with open(DATOS / f"{nombre}.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _f(x):
    return float(x) if x not in ("", None) else None


class Modelo:
    """Replica, sobre los CSV, las medidas del modelo que usan las dos páginas."""

    # mediciones que cuentan como «comunicación» (Medidas[Ultima marca comunicacion])
    COM = {"RUN", "Corriente", "Caudal", "Caudal total", "Totalizador", "Nivel pozo", "Profundidad", "pH", "CE",
           "Nivel estanque", "Nivel tranque", "Caudal aforador", "pH tranque", "Alarma alto nivel", "Detector fuga",
           "Modo auto", "Estado enlace"}
    # mediciones analógicas que pueden marcarse «congeladas» (Medidas[Tag congelado])
    CONG = {"Caudal", "Caudal total", "Nivel pozo", "Profundidad", "pH", "CE", "Nivel estanque", "Corriente",
            "Nivel tranque", "Caudal aforador", "pH tranque", "Bateria"}

    def __init__(self):
        self.cfg = {r["Parametro"]: float(r["Valor"]) for r in _csv("config")}
        self.activos = _csv("catalogo_activos")
        self.act = {a["ActivoID"]: a for a in self.activos}
        self.orden = {a["ActivoID"]: i for i, a in enumerate(self.activos)}
        self.tags = _csv("catalogo_senales")
        self.tag = {t["Tag"]: t for t in self.tags}
        self.tags_de = defaultdict(list)
        for t in self.tags:
            self.tags_de[t["ActivoID"]].append(t)
        self.fuentes = _csv("fuentes")
        self.med = defaultdict(list)
        for r in _csv("mediciones_horarias"):
            self.med[r["Tag"]].append((datetime.strptime(r["FechaHora"], "%Y-%m-%d %H:%M"), float(r["Valor"])))
        for s in self.med.values():
            s.sort()
        self.ultima_muestra = max(s[-1][0] for s in self.med.values())
        # Reloj del modelo (expresión HoraReferencia): última muestra del CSV + 20 min
        self.ahora = self.ultima_muestra + timedelta(minutes=20)
        self.inicio_ventana = min(s[0][0] for s in self.med.values())
        self.bal = _csv("balance_diario")
        self.umbral_sin_dato = self.cfg["Horas sin dato"] * 60

    # ---- base -------------------------------------------------------------------------------------------------
    def _tags(self, aid, med, principal=None):
        return [t for t in self.tags_de[aid] if t["Medicion"] == med and (principal is None or t["Principal"] == principal)]

    def valor(self, aid, med, principal=None, prom=False):
        v = [self.med[t["Tag"]][-1][1] for t in self._tags(aid, med, principal)]
        if not v:
            return None
        return sum(v) / len(v) if prom else sum(v)

    def valor_en(self, tag, ts):
        for t, v in self.med[tag]:
            if t == ts:
                return v
        return None

    def marca(self, aids, solo_com=True):
        m = [self.med[t["Tag"]][-1][0] for a in aids for t in self.tags_de[a] if (not solo_com or t["Medicion"] in self.COM)]
        return max(m) if m else None

    def minutos(self, aids):
        m = self.marca(aids)
        if m is None:
            return None
        return 0 if m > self.ahora else int((self.ahora - m).total_seconds() // 60)

    def congelado(self, aid, med, principal=None):
        n_cong = 0
        for t in self._tags(aid, med, principal):
            if t["Medicion"] not in self.CONG:
                continue
            s = self.med[t["Tag"]]
            t1, v1 = s[-1]
            t0 = t1 - timedelta(hours=self.cfg["Horas para congelado"])
            ult = [v for ts, v in s if ts >= t0]
            if s[0][0] <= t0 and len(ult) >= 8 and abs(v1) > 0.01 and max(ult) - min(ult) <= 1e-6:
                n_cong += 1
        return n_cong

    def delta(self, aid, med, dias):
        """Medidas[Delta 7 d]: último valor menos el de hace `dias` días (por señal, sumado)."""
        tot, hay = 0.0, False
        for t in self._tags(aid, med):
            s = self.med[t["Tag"]]
            t1, v1 = s[-1]
            previos = [(ts, v) for ts, v in s if ts <= t1 - timedelta(days=dias)]
            if previos:
                tot += v1 - previos[-1][1]
                hay = True
        return tot if hay else None

    def tasa_3h(self, aid, med):
        """%/h de las últimas 3 h (Tasa estanque / Tasa tranque)."""
        vs = []
        for t in self._tags(aid, med, "Si"):
            s = self.med[t["Tag"]]
            t1, v1 = s[-1]
            prev = [(ts, v) for ts, v in s if ts <= t1 - timedelta(hours=3)]
            if prev:
                t0, v0 = prev[-1]
                vs.append((v1 - v0) / ((t1 - t0).total_seconds() / 3600))
        return sum(vs) / len(vs) if vs else None

    # ---- recuperación -----------------------------------------------------------------------------------------
    def estado_pozo(self, aid):
        m = self.minutos([aid])
        run = self.valor(aid, "RUN")
        q = self.valor(aid, "Caudal")
        q = q / 3.6 if q is not None else None
        if m is None:
            return None
        if m > self.umbral_sin_dato:
            return 4
        if run is None and self.congelado(aid, "Caudal") > 0:
            return 5
        if (run is not None and run == 0) or (q is not None and q < self.cfg["Caudal minimo bombeo (L/s)"]):
            return 3
        return 1

    def inicio_detencion(self, aid):
        tags = self._tags(aid, "RUN")
        if tags:
            serie = self.med[tags[0]["Tag"]]
            ult1 = max((ts for ts, v in serie if v == 1), default=None)
            sig = [ts for ts, v in serie if ult1 is None or ts > ult1]
            return min(sig) if sig else None
        return None

    # ---- estanques y tranques ---------------------------------------------------------------------------------
    def nivel_estanque(self, aid):
        return self.valor(aid, "Nivel estanque", "Si", prom=True)

    def hi_estanque(self, aid):
        v = self.valor(aid, "Limite HI")
        return self.cfg["HI por defecto (%)"] if v is None else v

    def hh_estanque(self, aid):
        v = self.valor(aid, "Limite HH")
        return self.cfg["HH por defecto (%)"] if v is None else v

    def estado_estanque(self, aid):
        n = self.nivel_estanque(aid)
        if n is None:
            return None
        if self.minutos([aid]) > self.umbral_sin_dato:
            return 4
        if self.congelado(aid, "Nivel estanque", "Si") > 0:
            return 5
        if n >= self.hh_estanque(aid):
            return 3
        if n >= self.hi_estanque(aid):
            return 2
        return 1

    def horas_a_hh(self, aid, tipo):
        if tipo == "Estanque":
            n, hh, r = self.nivel_estanque(aid), self.hh_estanque(aid), self.tasa_3h(aid, "Nivel estanque")
        else:
            n, hh, r = self.valor(aid, "Nivel tranque", "Si", prom=True), _f(self.act[aid]["HH"]), self.tasa_3h(aid, "Nivel tranque")
        if hh is not None and r is not None and r > 0.05 and n < hh:
            return (hh - n) / r
        return None

    def rebalse_texto(self, aid, tipo):
        if tipo == "Estanque":
            n, hh = self.nivel_estanque(aid), self.hh_estanque(aid)
        else:
            n, hh = self.valor(aid, "Nivel tranque", "Si", prom=True), _f(self.act[aid]["HH"])
        h = self.horas_a_hh(aid, tipo)
        if n is None or hh is None:
            return "—"
        if n >= hh:
            return "Sobre HH"
        if h is None:
            return "Estable o bajando"
        if h < 1:
            return "Llega a HH en menos de 1 h"
        if h < 48:
            return f"Llega a HH en ~{int(h)} h"
        return f"Llega a HH en ~{int(h / 24)} d"

    def estado_tranque(self, aid):
        n = self.valor(aid, "Nivel tranque", "Si", prom=True)
        hi, hh = _f(self.act[aid]["HI"]), _f(self.act[aid]["HH"])
        if n is None:
            return None
        if self.minutos([aid]) > self.umbral_sin_dato:
            return 4
        if self.congelado(aid, "Nivel tranque", "Si") > 0:
            return 5
        if (self.valor(aid, "Detector fuga") or 0) >= 1:
            return 3
        if hh is not None and n >= hh:
            return 3
        if (hi is not None and n >= hi) or (self.valor(aid, "Alarma alto nivel") or 0) >= 1:
            return 2
        return 1

    def cruce(self, aid, med, limite, principal=None, desde_banda=False):
        """Primera marca posterior a la última con valor bajo el límite (Medidas[Alarma desde])."""
        for t in self._tags(aid, med, principal):
            s = self.med[t["Tag"]]
            bajo = [ts for ts, v in s if v < limite]
            ub = max(bajo) if bajo else None
            sig = [ts for ts, v in s if ub is None or ts > ub]
            return min(sig) if sig else None
        return None

    # ---- calidad ----------------------------------------------------------------------------------------------
    def estado_calidad(self, aid):
        p = self.valor(aid, "pH")
        if p is None:
            return None
        if self.minutos([aid]) > self.umbral_sin_dato:
            return 4
        if self.congelado(aid, "pH") > 0:
            return 5
        turb = self.valor(aid, "Turbidez") or 0
        if p < self.cfg["pH minimo"] or p > self.cfg["pH maximo"] or turb > self.cfg["Turbidez maxima (NTU)"]:
            return 2
        return 1

    # ---- agua fresca ------------------------------------------------------------------------------------------
    def caudal_pozo_ls(self, aid):
        q = self.valor(aid, "Caudal")
        if q is None:
            tot = self._tags(aid, "Totalizador")
            if not tot:
                return None
            s = self.med[tot[0]["Tag"]]
            t1, v1 = s[-1]
            prev = [(ts, v) for ts, v in s if ts <= t1 - timedelta(hours=1)]
            t0, v0 = prev[-1]
            q = (v1 - v0) / ((t1 - t0).total_seconds() / 3600)
        return q / 3.6

    def proyeccion_cupo(self, aid):
        """Medidas[% cupo pozo]: proyección al cierre del mes (volumen + ritmo de 24 h) frente al cupo mensual."""
        tags = self._tags(aid, "Volumen mes")
        cupo = self.valor(aid, "Cupo mes")
        if not tags or not cupo:
            return None, None, cupo
        s = self.med[tags[0]["Tag"]]
        t1, v1 = s[-1]
        prev = [(ts, v) for ts, v in s if ts <= t1 - timedelta(days=1)]
        inicio_mes = datetime(t1.year, t1.month, 1)
        if prev and prev[-1][0] >= inicio_mes and v1 >= prev[-1][1]:
            ritmo = v1 - prev[-1][1]
        else:
            ritmo = v1 / ((t1 - inicio_mes).total_seconds() / 86400)
        fin_mes = (datetime(t1.year + (t1.month == 12), t1.month % 12 + 1, 1))
        dias_rest = (fin_mes - t1).total_seconds() / 86400
        proy = v1 + ritmo * dias_rest
        return proy / cupo, proy, cupo

    def mes_vs_cupo(self):
        inicio_mes = datetime(self.ahora.year, self.ahora.month, 1)
        horas_mes = (self.ahora - inicio_mes).total_seconds() / 3600
        vals = [v for t in self.tags if t["Medicion"] == "Caudal total" for ts, v in self.med[t["Tag"]] if ts >= inicio_mes]
        q_prom = sum(vals) / len(vals)
        cupo = sum(self.valor(a["ActivoID"], "Cupo mes") or 0 for a in self.activos if a["Tipo"] == "Pozo agua fresca")
        return q_prom * horas_mes / cupo

    # ---- aguas abajo / UPS ------------------------------------------------------------------------------------
    def estado_aguas_abajo(self, aid):
        p = self.valor(aid, "Profundidad")
        d = self.delta(aid, "Profundidad", 7)
        a = -d if d is not None else None
        if p is None:
            return None, a
        if self.minutos([aid]) is not None and self.minutos([aid]) > self.umbral_sin_dato:
            return 4, a
        if self.congelado(aid, "Profundidad") > 0:
            return 5, a
        if a is not None and a >= self.cfg["Ascenso freatico alerta (m)"]:
            return 3, a
        if a is not None and a >= self.cfg["Ascenso freatico aviso (m)"]:
            return 2, a
        return 1, a

    def ups(self, aid):
        c = self.valor(aid, "UPS estado")
        if c is None:
            return None, None, None
        c = int(round(c))
        partes = []
        if c >= 8:
            partes.append("Sin alimentación")
        if (c // 4) % 2 == 1:
            partes.append("Falla")
        if (c // 2) % 2 == 1:
            partes.append("Bypass")
        if c % 2 == 1:
            partes.append("Batería")
        txt = "Normal" if c == 0 else " · ".join(partes)
        cod = 3 if c >= 8 else (2 if c > 0 else 1)
        return c, txt, cod

    def posible_corte(self, estacion):
        aids = [a["ActivoID"] for a in self.activos if a["Estacion"] == estacion and a["Tipo"] in ("Pozo recuperacion", "Bomba recuperacion")]
        if len(aids) < 2:
            return False
        est = [self.estado_pozo(a) for a in aids]
        ini = [self.inicio_detencion(a) for a in aids]
        if any(e != 3 for e in est) or any(i is None for i in ini):
            return False
        corr = sum(self.valor(a, "Corriente") or 0 for a in aids)
        return (min(ini) > self.inicio_ventana + timedelta(hours=1)
                and (max(ini) - min(ini)).total_seconds() / 60 <= self.cfg["Minutos simultaneidad corte"]
                and corr < 1)

    # ---- alarmas ----------------------------------------------------------------------------------------------
    @staticmethod
    def hhmm(d, ahora):
        return d.strftime("%H:%M") if d.date() == ahora.date() else d.strftime("%d-%m %H:%M")

    def duracion(self, d):
        m = int((self.ahora - d).total_seconds() // 60)
        if m >= 2880:
            return f"{m // 1440} d {(m % 1440) // 60} h"
        if m >= 60:
            return f"{m // 60} h {m % 60:02d} min"
        return f"{m} min"

    def alarmas(self):
        """Lista de alarmas (Medidas[Alarma severidad] > 0) con los textos de la tabla de la Vista general."""
        out = []
        for a in self.activos:
            aid, tipo, est = a["ActivoID"], a["Tipo"], a["Estacion"]
            n_est = sum(1 for x in self.activos if x["Estacion"] == est) if est else 0
            cae = n_est >= 2 and (self.minutos([x["ActivoID"] for x in self.activos if x["Estacion"] == est]) or 0) > self.umbral_sin_dato
            repr_ = min(self.orden[x["ActivoID"]] for x in self.activos if x["Estacion"] == est) == self.orden[aid] if est else False
            sev, cond, desde = None, None, None
            if tipo == "Pozo recuperacion":
                cod = self.estado_pozo(aid)
                sev = {3: 3, 4: 3, 5: 2}.get(cod)
            elif tipo == "Estanque":
                cod = self.estado_estanque(aid)
                sev = {3: 3, 2: 2, 4: 3, 5: 2}.get(cod)
            elif tipo == "Tranque":
                cod = self.estado_tranque(aid)
                sev = {3: 3, 2: 2, 4: 2, 5: 2}.get(cod)
            elif tipo == "Estacion calidad":
                cod = self.estado_calidad(aid)
                sev = {2: 2, 4: 2, 5: 2}.get(cod)
            elif tipo == "Pozo agua fresca":
                pc, _, _ = self.proyeccion_cupo(aid)
                sev = 2 if (pc is not None and pc > 1) else (1 if (pc is not None and pc > 0.9) else None)
            elif tipo == "Piezometro":
                if (self.minutos([aid]) or 0) > self.umbral_sin_dato or self.congelado(aid, "Profundidad") > 0:
                    sev = 1
            elif tipo == "Pozo monitoreo":
                cod, _ = self.estado_aguas_abajo(aid)
                sev = {3: 2, 2: 1, 4: 1, 5: 1}.get(cod)
            elif tipo == "Sala electrica":
                _, _, cod = self.ups(aid)
                sev = {3: 2, 2: 1}.get(cod)
            if cae:
                sev = 3 if repr_ else None
            if not sev:
                continue
            hc = f"{self.cfg['Horas para congelado']:.0f}"
            # ---- condición y «desde» (Medidas[Alarma condicion] / [Alarma desde])
            if cae:
                ult = self.marca([x["ActivoID"] for x in self.activos if x["Estacion"] == est])
                cond = f"{est} sin comunicación: {n_est} activos sin dato nuevo desde {ult.strftime('%d-%m %H:%M')}"
                desde = ult
            elif tipo == "Pozo recuperacion":
                cod = self.estado_pozo(aid)
                q = (self.valor(aid, "Caudal") or 0) / 3.6
                cond = f"Pozo detenido (RUN = 0 o caudal bajo el mínimo) · caudal {fmt(q, 1, '.')} L/s"
                if self.posible_corte(est):
                    cond += " · posible corte de energía en la estación"
                h_det = self.valor(aid, "Horas detenido")
                desde = self.ahora - timedelta(hours=h_det) if h_det else self.inicio_detencion(aid)
            elif tipo == "Estanque":
                cod = self.estado_estanque(aid)
                if cod == 5:
                    cond = f"Sensor de nivel congelado en {fmt(self.nivel_estanque(aid), 1, '.')} % (mismo valor hace más de {hc} h)"
                else:
                    lim = "HH (%d %%)" % self.hh_estanque(aid) if cod == 3 else "HI (%d %%)" % self.hi_estanque(aid)
                    tasa = self.tasa_3h(aid, "Nivel estanque")
                    cond = (f"Nivel {fmt(self.nivel_estanque(aid), 0, '.')} % sobre {lim} · tendencia "
                            f"{'+' if tasa >= 0 else '-'}{fmt(abs(tasa), 1, '.')} %/h · {self.rebalse_texto(aid, 'Estanque')}")
                desde = self.cruce(aid, "Nivel estanque", self.hi_estanque(aid), "Si")
            elif tipo == "Tranque":
                n = self.valor(aid, "Nivel tranque", "Si", prom=True)
                cond = f"Nivel {fmt(n, 1, '.')} %"
                if (self.valor(aid, "Alarma alto nivel") or 0) >= 1:
                    cond += " · alarma de nivel alto"
                cond += " · " + self.rebalse_texto(aid, "Tranque")
                desde = self.cruce(aid, "Nivel tranque", _f(a["HI"]), "Si")
            elif tipo == "Estacion calidad":
                cond = (f"pH {fmt(self.valor(aid, 'pH'), 1, '.')} · turbidez {fmt(self.valor(aid, 'Turbidez'), 1, '.')} NTU · fuera de la banda "
                        f"{fmt(self.cfg['pH minimo'], 1, '.')}–{fmt(self.cfg['pH maximo'], 1, '.')} (límite de ejemplo)")
                s = self.med[self._tags(aid, "pH")[0]["Tag"]]
                ok = [ts for ts, v in s if self.cfg["pH minimo"] <= v <= self.cfg["pH maximo"]]
                sig = [ts for ts, _ in s if ts > max(ok)]
                desde = min(sig) if sig else None
            elif tipo == "Pozo agua fresca":
                pc, proy, cupo = self.proyeccion_cupo(aid)
                cond = (f"Proyección al cierre del mes: {fmt(pc * 100, 0, '.')} % del cupo mensual "
                        f"({fmt(proy, 0, '.')} de {fmt(cupo, 0, '.')} m³)")
            elif tipo == "Pozo monitoreo":
                _, asc = self.estado_aguas_abajo(aid)
                cond = f"Nivel freático sube {fmt(asc, 2, '.')} m en 7 días · circuito asociado: {a['CircuitoAsociado']}"
            elif tipo == "Sala electrica":
                cond = "UPS: " + self.ups(aid)[1]
            ir_a = {"Pozo recuperacion": "Recuperación ›", "Estanque": "Estanques ›", "Tranque": "Tranques ›",
                    "Estacion calidad": "Calidad ›", "Pozo agua fresca": "Agua fresca ›", "Piezometro": "Agua fresca ›",
                    "Pozo monitoreo": "Aguas abajo ›", "Sala electrica": "Energía y reporte ›"}[tipo]
            out.append({"prio": 4 - sev, "sev": sev, "activo": a["Activo"], "cond": cond,
                        "desde": self.hhmm(desde, self.ahora) if desde else "—",
                        "dur": self.duracion(desde) if desde else "—", "ir_a": ir_a})
        out.sort(key=lambda r: (r["prio"], r["activo"]))
        return out


    # ---- fuentes de datos (Medidas[Estado fuente cod] y relacionadas) -----------------------------------------
    def fuentes_estado(self):
        filas = []
        for fu in self.fuentes:
            tg = [t for t in self.tags if t["Fuente"] == fu["Fuente"]]
            ok = sum(1 for t in tg if (self.ahora - self.med[t["Tag"]][-1][0]).total_seconds() / 60 <= self.umbral_sin_dato)
            if tg:
                com = [self.med[t["Tag"]][-1][0] for t in tg if t["Medicion"] in self.COM]
                ult = max(com) if com else max(self.med[t["Tag"]][-1][0] for t in tg)
            else:
                ult = None
            if fu["Tipo"] == "Sin tag":
                cod, det = 5, fu["Nota"]
            elif fu["Tipo"] == "Servidor":
                glob = self.marca([a["ActivoID"] for a in self.activos])
                cod = 1 if (self.ahora - glob).total_seconds() / 60 <= 30 else 3
                det, ult = "Última muestra " + glob.strftime("%H:%M"), glob
            else:
                cod = 1 if ok == len(tg) else (2 if ok >= 0.8 * len(tg) else 3)
                det = f"{ok} / {len(tg)} tags con dato < {self.cfg['Horas sin dato']:.0f} h"
            filas.append({"fuente": fu["Fuente"], "corta": fu["FuenteCorta"], "tipo": fu["Tipo"], "cod": cod, "det": det,
                          "ult": self.hhmm(ult, self.ahora) if ult else "—"})
        return filas

    # ---- balance hídrico (BalanceDiario) ----------------------------------------------------------------------
    def balance(self):
        dias = defaultdict(lambda: defaultdict(float))
        areas = defaultdict(lambda: defaultdict(float))     # consumo: area -> fecha -> m3
        for r in self.bal:
            dias[r["Fecha"]][r["Concepto"]] += float(r["Volumen_m3"])
            if r["Concepto"] == "Consumo":
                areas[r["Area"]][r["Fecha"]] += float(r["Volumen_m3"])
        fechas = sorted(dias)
        return fechas, dias, areas


# ---------------------------------------------------------------------------------------------------------------------
# Primitivas de dibujo propias (Segoe UI, símbolos, paneles, tarjetas, tablas y gráficos del informe)
# ---------------------------------------------------------------------------------------------------------------------
PT = 4 / 3                               # 1 pt = 1,333 px (el informe es de 1920x1080 px)
SIMBOLOS = set("●▲■◌◇✖◆▼")               # se dibujan con Segoe UI Symbol (como hace Power BI con su fuente de respaldo)
_FUENTES = {"r": ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"], "b": ["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],
            "sb": ["seguisb.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"], "sym": ["seguisym.ttf", "DejaVuSans.ttf"]}


def miles(v, dec=0):
    return fmt(v, dec, ".")


def pct(v, dec=0):
    return f"{fmt(v * 100, dec, '.')} %"


def nice_step(mx, n=5):
    """Paso «redondo» de eje para que haya como máximo n divisiones hasta mx."""
    import math
    mag = 10 ** math.floor(math.log10(mx / n))
    for m in (1, 2, 2.5, 5, 10):
        if mx / (m * mag) <= n:
            return m * mag
    return 10 * mag


class Pintor:
    """Envuelve un Lienzo con texto en Segoe UI (regular, bold, semibold) y símbolos, y los bloques del informe."""

    def __init__(self, c):
        self.c, self.s, self._f = c, c.ss, {}

    # ---- texto ------------------------------------------------------------------------------------------------
    def f(self, px, st):
        k = (round(px * self.s), st)
        if k not in self._f:
            for n in _FUENTES[st]:
                try:
                    self._f[k] = ImageFont.truetype(n, k[0])
                    break
                except OSError:
                    continue
            else:
                self._f[k] = ImageFont.load_default()
        return self._f[k]

    @staticmethod
    def trozos(txt):
        out, cur, cs = [], "", None
        for ch in txt:
            sym = ch in SIMBOLOS
            if cur and sym != cs:
                out.append((cur, cs))
                cur = ""
            cur, cs = cur + ch, sym
        if cur:
            out.append((cur, cs))
        return out

    def ancho(self, txt, px, st="r"):
        return sum(self.c.d.textlength(s, font=self.f(px, "sym" if sy else st)) / self.s for s, sy in self.trozos(str(txt)))

    def texto(self, x, yc, txt, px, color, st="r", al="l"):
        """Dibuja txt con su centro vertical en yc. al: l/m/r (ancla horizontal)."""
        txt = str(txt)
        w = self.ancho(txt, px, st)
        x0 = x - w / 2 if al == "m" else (x - w if al == "r" else x)
        base = yc + 0.35 * px
        for seg, sy in self.trozos(txt):
            font = self.f(px, "sym" if sy else st)
            self.c.d.text((x0 * self.s, base * self.s), seg, font=font, fill=color, anchor="ls")
            x0 += self.c.d.textlength(seg, font=font) / self.s
        return w

    def corta(self, txt, px, st, maxw):
        txt = str(txt)
        if self.ancho(txt, px, st) <= maxw:
            return txt
        while txt and self.ancho(txt + "…", px, st) > maxw:
            txt = txt[:-1]
        return txt.rstrip() + "…"

    def raya_h(self, x1, x2, y, color, ancho=2, dash=9, gap=5):
        x = x1
        while x < x2:
            self.c.linea([(x, y), (min(x + dash, x2), y)], color, ancho)
            x += dash + gap

    # ---- contenedores -----------------------------------------------------------------------------------------
    def ajusta(self, txt, px, st, maxw, minpx):
        """Reduce el cuerpo de letra hasta minpx para que txt quepa en maxw; si aun así no cabe, lo corta con «…»."""
        p = px
        while p > minpx and self.ancho(txt, p, st) > maxw:
            p -= 0.5
        return self.corta(txt, p, st, maxw), p

    def panel(self, x, y, w, h, titulo=None, pt=15):
        """Contenedor blanco con borde #C5D0DC (radio 6) y título centrado de 15 pt (negrita)."""
        self.c.caja(x, y, w, h, fill=BLANCO, borde=BORDE, r=6)
        if titulo:
            t, p = self.ajusta(titulo, pt * PT, "b", w - 24, 15.5)
            self.texto(x + w / 2, y + 20, t, p, NAVY, "b", "m")

    def tarjeta(self, x, y, w, h, titulo, valor, sub=None, pt_valor=32, pt_sub=13, color_valor=NAVY, st_valor="sb"):
        """Tarjeta del informe: título (15 pt), subtítulo (13 pt) y valor (Segoe UI Semibold) centrados."""
        self.panel(x, y, w, h, titulo)
        vpx = pt_valor * PT
        if sub:
            t, p = self.ajusta(sub, pt_sub * PT, "r", w - 20, 13.5)
            self.texto(x + w / 2, y + 46, t, p, TXT2, "r", "m")
            yv = y + h - 36 if h <= 120 else y + 60 + (h - 60) / 2
        else:
            yv = y + 20 + (h - 20) / 2 + 4
        v, vp = self.ajusta(valor, vpx, st_valor, w - 24, 16)
        self.texto(x + w / 2, yv, v, vp, color_valor, st_valor, "m")

    def parrafo(self, x, y, w, h, txt, px, color, st="r", lh=1.3):
        """Texto centrado (horizontal y verticalmente) con ajuste de línea dentro de la caja (x, y, w, h)."""
        palabras, lineas, cur = str(txt).split(), [], ""
        for pal in palabras:
            t = (cur + " " + pal).strip()
            if self.ancho(t, px, st) <= w:
                cur = t
            else:
                lineas.append(cur)
                cur = pal
        lineas.append(cur)
        alto = px * lh * len(lineas)
        yc = y + (h - alto) / 2 + px * lh / 2
        for ln in lineas:
            self.texto(x + w / 2, yc, ln, px, color, st, "m")
            yc += px * lh

    # ---- tabla ------------------------------------------------------------------------------------------------
    def tabla(self, x, y, w, h, titulo, cols, filas, anchos, aligns=None, estado=None, colores=None, fila_h=None, extra_filas=0,
              pt=11, pt_cab=None, tit_h=38):
        """tableEx del informe: cabecera #E6ECF2 en negrita, filas blancas con líneas #E6ECF2 y, si hay desborde, barra de
        desplazamiento. estado: índice (o lista de índices) de la columna cuyo fondo viene de una medida de color
        (colores[i] = hex por fila, o dict {columna: [hex...]})."""
        self.panel(x, y, w, h, titulo)
        px = pt * PT
        pxc = (pt_cab or min(pt, 11)) * PT
        fila_h = fila_h or round(px * 1.33 + 8)
        x0, inner = x + 10, w - 20
        k = inner / sum(anchos)
        anchos = [a * k for a in anchos]
        aligns = aligns or ["l"] * len(cols)
        est = [estado] if isinstance(estado, int) else list(estado or [])
        yh = y + tit_h
        self.c.caja(x0, yh, inner, fila_h, fill=GRID)
        cx = x0
        for i, nombre in enumerate(cols):
            self._celda(cx, yh, anchos[i], fila_h, nombre, pxc, NAVY, "b", aligns[i])
            cx += anchos[i]
        disp = int((h - tit_h - fila_h - 8) // fila_h)
        for r, fila in enumerate(filas[:disp]):
            ry = yh + fila_h + r * fila_h
            cx = x0
            for i, val in enumerate(fila):
                if i in est and colores:
                    col = colores[i][r] if isinstance(colores, dict) else colores[r]
                    if col:
                        self.c.caja(cx, ry, anchos[i], fila_h, fill=col)
                    self._celda(cx, ry, anchos[i], fila_h, val, px, NAVY, "r", aligns[i])
                else:
                    self._celda(cx, ry, anchos[i], fila_h, val, px, TXT2, "r", aligns[i])
                cx += anchos[i]
            self.c.caja(x0, ry + fila_h - 1, inner, 1, fill=GRID)
        if len(filas) + extra_filas > disp:                    # barra de desplazamiento vertical
            top, alto = yh + fila_h + 2, disp * fila_h - 4
            self.c.caja(x + w - 15, top, 6, alto, fill="#F1F4F8", r=3)
            self.c.caja(x + w - 15, top, 6, alto * disp / (len(filas) + extra_filas), fill="#C5D0DC", r=3)

    def _celda(self, cx, cy, cw, ch, txt, px, color, st, al):
        pad = 6
        t = self.corta(txt, px, st, cw - 2 * pad)
        if al == "r":
            self.texto(cx + cw - pad, cy + ch / 2, t, px, color, st, "r")
        else:
            self.texto(cx + pad, cy + ch / 2, t, px, color, st, "l")

    # ---- ejes y leyenda ---------------------------------------------------------------------------------------
    def leyenda(self, cx, yc, items, px=11 * PT, linea=True, max_w=None):
        """items: [(nombre, color)] centrados en cx; si no caben en max_w pasan a una segunda línea. Devuelve nº de filas."""
        gap, sw = 24, 18
        anchos = [sw + 6 + self.ancho(n, px) for n, _ in items]
        filas, cur, cw = [], [], 0
        for it, a in zip(items, anchos):
            if cur and max_w and cw + gap + a > max_w:
                filas.append(cur)
                cur, cw = [], 0
            cur.append((it, a))
            cw += a + (gap if len(cur) > 1 else 0)
        filas.append(cur)
        for fi, fila in enumerate(filas):
            tot = sum(a for _, a in fila) + gap * (len(fila) - 1)
            x = cx - tot / 2
            y = yc + fi * 24
            for (n, col), a in fila:
                if linea:
                    self.c.linea([(x, y), (x + sw, y)], col, 3)
                else:
                    self.c.caja(x, y - 6, 12, 12, fill=col, r=2)
                self.texto(x + (sw if linea else 18) + 6 - (6 if not linea else 0), y, n, px, TXT2)
                x += a + gap
        return len(filas)

    def lineas(self, x, y, w, h, titulo, series, xlabs, ymax, step, ymin=0, refs=(), leyenda=True, yfmt=miles, n_x=None,
               ancho_linea=2.5):
        """lineChart: series [(nombre, [valores], color)], xlabs [(índice, texto)], ejes con rejilla #E6ECF2."""
        self.panel(x, y, w, h, titulo)
        px = 11 * PT
        filas_ley = self.leyenda(x + w / 2, y + 52, [(s[0], s[2]) for s in series], px, max_w=w - 40) if leyenda else 0
        top = y + 52 + (24 * filas_ley + 6 if leyenda else 8)
        bot = y + h - 38
        ticks = [round(ymin + i * step, 6) for i in range(int(round((ymax - ymin) / step)) + 1)]
        lw = max(self.ancho(yfmt(t), px) for t in ticks)
        left, right = x + 14 + lw + 10, x + w - 22
        n = n_x or max(len(s[1]) for s in series)
        for t in ticks:
            yy = bot - (bot - top) * (t - ymin) / (ymax - ymin)
            self.c.caja(left, yy, right - left, 1, fill=GRID)
            self.texto(left - 8, yy, yfmt(t), px, TXT2, "r", "r")
        for i, txt in xlabs:
            xx = left + (right - left) * i / (n - 1)
            mw = self.ancho(txt, px) / 2 + 8
            self.texto(min(max(xx, x + mw), x + w - mw), bot + 20, txt, px, TXT2, "r", "m")
        for valor, txt, col in refs:
            yy = bot - (bot - top) * (valor - ymin) / (ymax - ymin)
            self.raya_h(left, right, yy, col)
            self.texto(left + 6, yy - 12, txt, px, col, "r", "l")
        for _, vals, col in series:
            pts = [(left + (right - left) * i / (n - 1), bot - (bot - top) * (min(max(v, ymin), ymax) - ymin) / (ymax - ymin))
                   for i, v in enumerate(vals)]
            self.c.linea(pts, col, ancho_linea)

    def barras_h(self, x, y, w, h, titulo, cats, series, vmax, step, leyenda_abajo=False, vfmt=miles, grupo=0.72):
        """barChart (barras horizontales agrupadas): series [(nombre, [valores], color)]."""
        self.panel(x, y, w, h, titulo)
        px = 11 * PT
        top = y + 48
        bot = y + h - (62 if leyenda_abajo else 40)
        lab = max(self.ancho(c, px) for c in cats)
        left, right = x + 14 + lab + 12, x + w - 40
        ticks = [i * step for i in range(int(vmax / step + 1e-9) + 1)]
        for t in ticks:
            xx = left + (right - left) * t / vmax
            self.c.caja(xx, top, 1, bot - top, fill=GRID)
            self.texto(xx, bot + 16, vfmt(t), px, TXT2, "r", "m")
        banda = (bot - top) / len(cats)
        n = len(series)
        bh = banda * grupo / n
        for ci, cat in enumerate(cats):
            yc = top + banda * (ci + 0.5)
            self.texto(left - 10, yc, cat, px, TXT2, "r", "r")
            for si, (_, vals, col) in enumerate(series):
                by = yc - banda * grupo / 2 + si * bh
                bw = (right - left) * vals[ci] / vmax
                if bw > 0:
                    self.c.caja(left, by + 1, bw, bh - 2, fill=col, r=2)
                self.texto(left + bw + 6, by + bh / 2, vfmt(vals[ci]), px, NAVY, "r", "l")
        self.c.caja(left, top, 1, bot - top, fill=GRIS_EJE)
        if leyenda_abajo:
            self.leyenda(x + w / 2, y + h - 18, [(s[0], s[2]) for s in series], px, linea=False)

    def columnas(self, x, y, w, h, titulo, cats, valores, colores, ymin, ymax, step, refs=(), etiquetas=True, vfmt=None,
                 yfmt=None, cat2=None):
        """clusteredColumnChart: una serie, color por columna, líneas de referencia y etiquetas de datos."""
        self.panel(x, y, w, h, titulo)
        px = 11 * PT
        vfmt = vfmt or (lambda v: fmt(v, 1, "."))
        yfmt = yfmt or (lambda v: fmt(v, 0, "."))
        top, bot = y + 52, y + h - (62 if cat2 else 40)
        ticks = [round(ymin + i * step, 6) for i in range(int(round((ymax - ymin) / step)) + 1)]
        lw = max(self.ancho(yfmt(t), px) for t in ticks)
        left, right = x + 14 + lw + 10, x + w - 20
        yp = lambda v: bot - (bot - top) * (v - ymin) / (ymax - ymin)
        for t in ticks:
            self.c.caja(left, yp(t), right - left, 1, fill=GRID)
            self.texto(left - 8, yp(t), yfmt(t), px, TXT2, "r", "r")
        banda = (right - left) / len(cats)
        bw = min(banda * 0.58, 70)
        y0 = yp(max(ymin, 0))
        for i, v in enumerate(valores):
            bx = left + banda * i + (banda - bw) / 2
            ya, yb = sorted((yp(v), y0))
            self.c.caja(bx, ya, bw, max(yb - ya, 1), fill=colores[i], r=2)
            if etiquetas:
                dentro = any(abs(v - rv) < (ymax - ymin) * 0.06 and v < rv for rv, _, _ in refs)
                if dentro:
                    self.texto(bx + bw / 2, ya + 12, vfmt(v), px, NAVY, "r", "m")
                else:
                    self.texto(bx + bw / 2, (ya - 11) if v >= 0 else (yb + 11), vfmt(v), px, NAVY, "r", "m")
            if cat2:
                a, b = cat2[i]
                self.texto(left + banda * (i + 0.5), bot + 18, a, px, TXT2, "r", "m")
                self.texto(left + banda * (i + 0.5), bot + 36, b, px, TXT2, "r", "m")
            else:
                self.texto(left + banda * (i + 0.5), yp(ymin) + 18, cats[i], px, TXT2, "r", "m")
        for rv, txt, col in refs:
            self.raya_h(left, right, yp(rv), col)
            self.texto(right - 4, yp(rv) - 12, txt, px, col, "r", "r")
        self.c.caja(left, y0, right - left, 1, fill=GRIS_EJE)

    def gauge(self, x, y, w, h, titulo, sub, valor, objetivo, color, vmin=0, vmax=100):
        """gauge: semicírculo con valor, marca objetivo (línea roja) y etiquetas de mínimo y máximo."""
        import math
        self.panel(x, y, w, h, titulo)
        if sub:
            t, p = self.ajusta(sub, 13 * PT, "r", w - 20, 14.5)
            self.texto(x + w / 2, y + 46, t, p, TXT2, "r", "m")
        cx, cy = x + w / 2, y + h - 52
        r, ancho = min(w / 2 - 50, h - 130), 34
        self.c.arco(cx, cy, r, 180, 360, GRID, ancho)
        frac = (valor - vmin) / (vmax - vmin)
        self.c.arco(cx, cy, r, 180, 180 + 180 * frac, color, ancho)
        ang = math.pi * (1 + (objetivo - vmin) / (vmax - vmin))
        r1, r2 = r - ancho / 2 - 4, r + ancho / 2 + 6
        self.c.linea([(cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)), (cx + r2 * math.cos(ang), cy + r2 * math.sin(ang))], ROJO, 3)
        rt = r2 + 14
        self.texto(cx + rt * math.cos(ang), cy + rt * math.sin(ang), fmt(objetivo, 0, "."), 12 * PT, ROJO, "r", "m")
        self.texto(cx - r, cy + 20, fmt(vmin, 0, "."), 12 * PT, TXT2, "r", "m")
        self.texto(cx + r, cy + 20, fmt(vmax, 0, "."), 12 * PT, TXT2, "r", "m")
        self.texto(cx, cy - 6, fmt(valor, 1, "."), 30 * PT * 0.9, NAVY, "sb", "m")

    def pivot_estado(self, x, y, w, h, titulo, filas, cols, estados, colores, fondo_vacio="#E6ECF2"):
        """pivotTable de 24 h: filas = pozos, columnas = horas, celdas coloreadas por estado (sin texto)."""
        self.panel(x, y, w, h, titulo)
        px = 11 * PT
        rh = round(px * 1.33 + 8)
        lw = max(self.ancho(f, px) for f in filas) + 20
        x0 = x + 10 + lw
        cw = (w - 20 - lw) / len(cols)
        yh = y + 38
        self.texto(x + 18, yh + rh / 2, "Pozo", px, NAVY, "b", "l")
        for j, c in enumerate(cols):
            self.texto(x0 + cw * (j + 0.5), yh + rh / 2, c, px, NAVY, "r", "m")
        for i, f in enumerate(filas):
            ry = yh + rh * (i + 1)
            self.texto(x + 18, ry + rh / 2, f, px, NAVY, "r", "l")
            for j in range(len(cols)):
                self.c.caja(x0 + cw * j + 1, ry + 1, cw - 2, rh - 2, fill=colores[estados[i][j]])
        self.c.caja(x + 10, yh + rh, w - 20, 1, fill=BORDE)

    def slicer(self, x, y, w, h, cabecera):
        """slicer en modo desplegable: cabecera en negrita y cuadro con flecha."""
        px = 11 * PT
        self.texto(x + 4, y + 14, cabecera, px, NAVY, "b", "l")
        self.c.caja(x + 2, y + 28, w - 4, h - 32, fill=BLANCO, borde=BORDE, r=2)
        xc, yc = x + w - 16, y + 28 + (h - 32) / 2
        self.c.linea([(xc - 4, yc - 2), (xc, yc + 2), (xc + 4, yc - 2)], TXT2, 1.6)


# ---------------------------------------------------------------------------------------------------------------------
# Cabecera común (textbox azul medianoche + logos + «DATOS AL dd-mm hh:mm»)
# ---------------------------------------------------------------------------------------------------------------------
def lienzo_pagina(M, titulo):
    c = Lienzo(1920, 1080, FONDO_PAG)
    P = Pintor(c)
    c.caja(0, 0, 1920, 96, fill=NAVY)
    c.pegar(LOGO_BLANCO, 22, 18, w=224)
    c.pegar(ICONO, 256, 8, h=80)
    P.texto(358, 25, "MINERA DEMO · GESTIÓN DEL AGUA EN LÍNEA", 10 * PT, CELESTE, "b")
    P.texto(358, 55, titulo, 21 * PT, BLANCO, "b")
    c.caja(1300, 20, 608, 56, fill=AZUL, r=8)                       # medida «Color datos al» (sin atraso: azul cielo)
    P.texto(1604, 48, "DATOS AL " + M.ultima_muestra.strftime("%d-%m %H:%M"), 16 * PT, BLANCO, "sb", "m")
    return c, P


def guardar(c, nombre, limite_kb=350):
    """Guarda el PNG con la leyenda al pie derecho (en el margen inferior, sin pisar los visuales). Si pesa más de
    limite_kb lo reduce a 256 colores (c.guardar(..., cuantizar=True)); se comprobó a ojo que el texto no se degrada."""
    SALIDA.mkdir(parents=True, exist_ok=True)
    Pintor(c).texto(c.w - 16, c.h - 6, LEYENDA, 11, "#5B6B82", "r", "r")
    ruta = SALIDA / nombre
    c.guardar(ruta)
    if ruta.stat().st_size / 1024 > limite_kb:
        c.guardar(ruta, None, cuantizar=True)
    return ruta


# ---------------------------------------------------------------------------------------------------------------------
# Página «Vista general»
# ---------------------------------------------------------------------------------------------------------------------
def vista_general(M):
    c, P = lienzo_pagina(M, "Vista general")
    al = M.alarmas()
    n_cri, n_ale, n_avi = (sum(1 for a in al if a["sev"] == k) for k in (3, 2, 1))

    # --- estados de activos
    rec = [a["ActivoID"] for a in M.activos if a["Tipo"] == "Pozo recuperacion"]
    est_rec = {r: M.estado_pozo(r) for r in rec}
    n_bomb = sum(1 for v in est_rec.values() if v == 1)
    n_det = sum(1 for v in est_rec.values() if v == 3)
    n_sd = sum(1 for v in est_rec.values() if v == 4)
    est = [a["ActivoID"] for a in M.activos if a["Tipo"] == "Estanque"]
    est_cod = {e: M.estado_estanque(e) for e in est}
    est_niv = {e: M.nivel_estanque(e) for e in est}
    n_hi = sum(1 for v in est_cod.values() if v in (2, 3))
    top = max(est, key=lambda e: est_niv[e])
    q_af = M.valor("CAP-TOTAL", "Caudal total") / 3.6
    cupo = M.cfg["Cupo captacion (L/s)"]
    pozos_af = [a["ActivoID"] for a in M.activos if a["Tipo"] == "Pozo agua fresca"]
    n_af = sum(1 for p in pozos_af if (M.caudal_pozo_ls(p) or 0) > M.cfg["Caudal minimo bombeo (L/s)"])
    ec = [a["ActivoID"] for a in M.activos if a["Tipo"] == "Estacion calidad"]
    ec_cod = {e: M.estado_calidad(e) for e in ec}
    n_banda = sum(1 for v in ec_cod.values() if v == 1)
    fuera = [e for e in ec if ec_cod[e] == 2]
    fu = M.fuentes_estado()
    areas = [f for f in fu if f["tipo"] == "Area"]
    n_ok = sum(1 for f in areas if f["cod"] == 1)
    malas = ", ".join(f["corta"] for f in areas if f["cod"] > 1)

    # --- fila de tarjetas
    P.tarjeta(12, 108, 243, 118, "Alarmas activas", str(n_cri + n_ale), f"{n_cri} críticas · {n_ale} alertas · {n_avi} avisos")
    P.tarjeta(273, 108, 241, 118, "Pozos de recuperación bombeando", f"{n_bomb} / {len(rec)}",
              f"{n_det} detenido · {n_sd} sin dato")
    P.tarjeta(529, 108, 270, 118, "Estanques sobre HI", f"{n_hi} / {len(est)}",
              f"Máx. {M.act[top]['Activo']} {fmt(est_niv[top], 0, '.')} %")
    P.tarjeta(818, 108, 342, 118, "Agua fresca (L/s)", fmt(q_af, 1, "."),
              f"{pct(q_af / cupo)} del cupo ({fmt(cupo, 1, '.')} L/s) · {n_af} / {len(pozos_af)} pozos")
    P.tarjeta(1177, 108, 304, 118, "pH en banda (estaciones)", f"{n_banda} / {len(ec)}",
              ("Fuera: " + ", ".join(f"{e} pH {fmt(M.valor(e, 'pH'), 1, '.')}" for e in fuera)) if fuera else "Todas en banda 6,5–8,5")
    P.tarjeta(1499, 108, 410, 118, "¿Llegan los datos?", f"{n_ok} / {len(areas)}",
              f"{malas} con atraso · meteorología y evaporación sin señal")

    # --- tablas superiores
    sev_txt = {3: "✖ Crítica", 2: "▲ Alerta", 1: "◆ Aviso"}
    sev_col = {3: ROJO, 2: AMBAR, 1: CELESTE}
    P.tabla(12, 238, 1135, 356, "Alarmas activas · por severidad y antigüedad",
            ["Prio.", "Severidad", "Activo", "Condición", "Desde", "Duración", "Ir a"],
            [[a["prio"], sev_txt[a["sev"]], a["activo"], a["cond"], a["desde"], a["dur"], a["ir_a"]] for a in al],
            [52, 95, 150, 460, 95, 105, 125], aligns=["r", "l", "l", "l", "l", "l", "l"],
            estado=1, colores=[sev_col[a["sev"]] for a in al])

    orden = {3: 0, 2: 1, 5: 2, 1: 3}
    fu_ord = sorted(fu, key=lambda f: (orden[f["cod"]], f["fuente"]))
    est_f = {1: "● OK", 2: "▲ Parcial", 3: "■ Sin datos", 5: "◌ Sin señal en el historiador"}
    col_f = {1: AZUL, 2: AMBAR, 3: ROJO, 5: GRID}
    P.tabla(1160, 238, 749, 356, "¿Llegan los datos? · última muestra por fuente", ["Fuente", "Estado", "Con dato", "Último"],
            [[f["fuente"], est_f[f["cod"]], f["det"], f["ult"]] for f in fu_ord], [235, 215, 215, 64],
            aligns=["l", "l", "l", "l"], estado=1, colores=[col_f[f["cod"]] for f in fu_ord])

    # --- recuperación: pozos por estado y circuito
    circ = ["Circuito Norte", "Circuito Sur"]
    def cuenta(cir, cod):
        return sum(1 for r in rec if M.act[r]["Circuito"] == cir and est_rec[r] == cod)
    P.barras_h(12, 615, 517, 205, "Recuperación · pozos por estado", circ,
               [("Bombeando", [cuenta(k, 1) for k in circ], AZUL), ("Detenido", [cuenta(k, 3) for k in circ], ROJO),
                ("Sin dato", [cuenta(k, 4) for k in circ], GRIS_EST)], vmax=3.5, step=1, leyenda_abajo=True)

    # --- estanques: nivel vs HI / HH
    col_estado = {1: AZUL, 2: AMBAR, 3: ROJO, 4: GRIS_EST, 5: AMBAR}
    P.columnas(541, 615, 434, 453, "Estanques · nivel (%) vs HI / HH", est, [est_niv[e] for e in est],
               [col_estado[est_cod[e]] for e in est], 0, 100, 20,
               refs=[(M.cfg["HI por defecto (%)"], "HI 80", AMBAR), (M.cfg["HH por defecto (%)"], "HH 90", ROJO)],
               cat2=[tuple(M.act[e]["Activo"].split(" ", 1)) for e in est])

    # --- agua fresca últimas 24 h (L/s)
    serie = [v / 3.6 for t, v in M.med[next(t["Tag"] for t in M.tags if t["Medicion"] == "Caudal total")]][-24:]
    horas = [t for t, _ in M.med[next(t["Tag"] for t in M.tags if t["Medicion"] == "Caudal total")]][-24:]
    P.lineas(990, 615, 462, 324, "Agua fresca · caudal total últimas 24 h (L/s)", [("L/s", serie, AZUL)],
             [(i, horas[i].strftime("%d-%m %H:%M")) for i in (0, 8, 16)] + [(23, horas[23].strftime("%H:%M"))],
             ymax=220, step=50, refs=[(cupo, f"Cupo {cupo:.0f} L/s", VIOLETA)], leyenda=False,
             yfmt=lambda v: fmt(v, 0, "."))

    # --- calidad
    est_q = {1: "● En banda", 2: "▲ Fuera de banda", 4: "◌ Sin dato", 5: "◇ pH congelado"}
    col_q = {1: AZUL, 2: AMBAR, 4: GRIS_EST, 5: AMBAR}
    P.tabla(1466, 615, 443, 453, "Calidad · estaciones de calidad", ["Estación", "pH", "CE µS/cm", "Estado"],
            [[e, fmt(M.valor(e, "pH"), 1, "."), miles(M.valor(e, "CE")), est_q[ec_cod[e]]] for e in ec],
            [94, 61, 103, 161], aligns=["l", "r", "r", "l"], estado=3, colores=[col_q[ec_cod[e]] for e in ec])

    # --- pozos fuera de servicio
    fuera_s = [r for r in rec if est_rec[r] != 1]
    est_p = {3: "■ Detenido", 4: "◌ Sin dato", 5: "◇ Caudal congelado"}
    col_p = {3: ROJO, 4: GRIS_EST, 5: AMBAR}
    P.tabla(12, 830, 517, 238, "Pozos fuera de servicio", ["Pozo", "Estado", "Último dato"],
            [[r, est_p[est_rec[r]], M.hhmm(M.marca([r]), M.ahora)] for r in fuera_s], [139, 162, 162],
            estado=1, colores=[col_p[est_rec[r]] for r in fuera_s])

    # --- tarjetas inferiores
    P.tarjeta(989, 951, 224, 116, "Pozos operando", f"{n_af} / {len(pozos_af)}", pt_valor=24)
    P.tarjeta(1227, 951, 224, 116, "Mes vs cupo", pct(M.mes_vs_cupo()), pt_valor=24)
    return guardar(c, "vista_general.png")


# ---------------------------------------------------------------------------------------------------------------------
# Página «Balance hídrico»
# ---------------------------------------------------------------------------------------------------------------------
def balance_hidrico(M):
    c, P = lienzo_pagina(M, "Balance hídrico")
    fechas, dias, areas = M.balance()
    corte = fechas[-1]
    def ult(n):
        return fechas[-n:]
    def suma(concepto, fs):
        return sum(dias[f][concepto] for f in fs)
    f7, f30 = ult(7), ult(30)
    fresca7, recup7, cons7 = suma("Agua fresca", f7), suma("Agua recuperada", f7), suma("Consumo", f7)
    var7 = suma("Variación de almacenamiento", f7)
    total7 = fresca7 + recup7
    err7 = total7 - cons7 - var7
    recirc7 = recup7 / total7
    cierre7 = 1 - abs(err7) / total7

    P.tarjeta(12, 108, 368, 118, "Agua fresca · 7 días (m³)", miles(fresca7), f"Promedio {miles(fresca7 / 7)} m³/día · reposición")
    P.tarjeta(394, 108, 368, 118, "Agua recuperada · 7 días (m³)", miles(recup7), "Pozos de recuperación + retorno del Tranque Demo")
    P.tarjeta(776, 108, 368, 118, "Consumo por áreas · 7 días (m³)", miles(cons7), "Chancado, molienda, flotación, mina y servicios")
    P.tarjeta(1158, 108, 368, 118, "Recirculación · 7 días", pct(recirc7, 1), "Recuperada / (fresca + recuperada) · 7 días")
    P.tarjeta(1540, 108, 368, 118, "Cierre del balance · 7 días", pct(cierre7, 1), f"Error 7 d: {miles(err7)} m³")

    # --- balance diario 90 días
    serie = lambda concepto: [dias[f][concepto] for f in fechas]
    cons_d = serie("Consumo")
    ymax_d = nice_step(max(max(serie("Agua recuperada")), max(cons_d)), 4)
    top_d = ymax_d * -(-max(max(serie("Agua recuperada")), max(cons_d)) // ymax_d)
    fd = [datetime.strptime(f, "%Y-%m-%d") for f in fechas]
    P.lineas(12, 238, 1100, 400, "Balance diario · 90 días (m³/día)",
             [("Agua fresca", serie("Agua fresca"), AZUL), ("Agua recuperada", serie("Agua recuperada"), VIOLETA),
              ("Consumo total", cons_d, NAVY)],
             [(i, fd[i].strftime("%d-%m-%Y")) for i in range(0, 90, 14)], ymax=top_d, step=ymax_d)

    # --- consumo por área: 30 días (barras)
    por_area = {a: (sum(areas[a][f] for f in f7), sum(areas[a][f] for f in f30)) for a in areas}
    orden = sorted(por_area, key=lambda a: -por_area[a][1])
    mx = por_area[orden[0]][1]
    stp = nice_step(mx, 5)
    P.barras_h(1124, 238, 784, 400, "Consumo por área · últimos 30 días (m³)", orden,
               [("Consumo 30 d", [por_area[a][1] for a in orden], AZUL)], vmax=stp * -(-mx // stp), step=stp)

    # --- consumo por área: últimas 72 h (líneas, una por área)
    tags_c = sorted((t for t in M.tags if t["Medicion"] == "Consumo"), key=lambda t: M.act[t["ActivoID"]]["Activo"])
    ser72, horas72 = [], None
    for i, t in enumerate(tags_c):
        s = M.med[t["Tag"]][-72:]
        horas72 = [ts for ts, _ in s]
        ser72.append((M.act[t["ActivoID"]]["Activo"], [v for _, v in s], DATA_COLORS[i]))
    mx72 = max(max(s[1]) for s in ser72)
    st72 = nice_step(mx72, 6)
    P.lineas(12, 650, 900, 418, "Consumo por área · últimas 72 h (m³/h)", ser72,
             [(i, horas72[i].strftime("%d-%m %H:%M")) for i in range(0, 72, 12)], ymax=st72 * -(-mx72 // st72), step=st72)

    # --- tablas
    filas_a = [[a, miles(por_area[a][0]), miles(por_area[a][1]), pct(por_area[a][1] / sum(v[1] for v in por_area.values()), 1)] for a in orden]
    P.tabla(924, 650, 460, 418, "Consumo por área", ["Área", "7 días m³", "30 días m³", "% del total"], filas_a,
            [172, 87, 97, 84], aligns=["l", "r", "r", "r"], pt_cab=10)
    filas_d = []
    for f in reversed(fechas):
        d = dias[f]
        tot = d["Agua fresca"] + d["Agua recuperada"]
        err = tot - d["Consumo"] - d["Variación de almacenamiento"]
        filas_d.append([datetime.strptime(f, "%Y-%m-%d").strftime("%d-%m-%Y"), miles(tot), miles(d["Consumo"]), miles(err),
                        pct(1 - abs(err) / tot, 1)])
    P.tabla(1396, 650, 512, 418, "Cierre del balance por día", ["Día", "Fresca + recup. m³", "Consumo m³", "Error m³", "Cierre"],
            filas_d, [88, 146, 100, 72, 86], aligns=["l", "r", "r", "r", "r"], extra_filas=0, pt_cab=10)
    return guardar(c, "balance_hidrico.png")


# ---------------------------------------------------------------------------------------------------------------------
# Utilidades comunes de las demás páginas
# ---------------------------------------------------------------------------------------------------------------------
COL_ESTADO = {1: AZUL, 2: AMBAR, 3: ROJO, 4: GRIS_EST, 5: AMBAR}


def serie_horaria(M, medicion, horas, aids, escala=1.0):
    """Medidas[Serie N h]: promedio por hora de las señales de cada activo en las últimas `horas` (HorasAtras <= horas)."""
    lim = M.ahora - timedelta(hours=horas)
    out = {}
    for a in aids:
        acc = defaultdict(list)
        for t in M._tags(a, medicion):
            for ts, v in M.med[t["Tag"]]:
                if ts >= lim:
                    acc[ts].append(v)
        out[a] = sorted((ts, sum(v) / len(v) / escala) for ts, v in acc.items())
    return out


def etiquetas_x(marcas, cada, fmt_="%d-%m %H:%M"):
    return [(i, marcas[i].strftime(fmt_)) for i in range(0, len(marcas), cada)]


def ids_tipo(M, tipo):
    return [a["ActivoID"] for a in M.activos if a["Tipo"] == tipo]


def hhmm_activo(M, aid):
    m = M.marca([aid])
    return M.hhmm(m, M.ahora) if m else "—"


def horas_detenidas_7d(M, aid):
    """Medidas[Horas detenidas 7 d]: muestras con RUN = 0 en los últimos 7 días (1 h por muestra)."""
    lim = M.ahora - timedelta(days=7)
    tags = M._tags(aid, "RUN")
    if tags:
        return sum(1 for ts, v in M.med[tags[0]["Tag"]] if ts > lim and v < 0.5)
    tags = M._tags(aid, "Caudal")
    return sum(1 for ts, v in M.med[tags[0]["Tag"]] if ts > lim and v < M.cfg["Caudal minimo bombeo (L/s)"] * 3.6) if tags else 0


def detenido_hace_txt(M, aid):
    h = M.valor(aid, "Horas detenido")
    if not h:
        return ""
    if h >= 48:
        return f"{int(h // 24)} d {int(h) % 24} h"
    return f"{int(h)} h {int(h * 60) % 60:02d} min"


def tiempo_sin_dato_txt(M, aid):
    m = M.minutos([aid])
    if m is None:
        return ""
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{m} min"


def estado_hora(M, aid, h):
    """Medidas[Estado hora cod] para la hora `h` horas atrás (1 bombeando, 3 detenido, 4 sin dato)."""
    t1 = M.ahora - timedelta(hours=h)
    t0 = M.ahora - timedelta(hours=h + 1)
    n, run_min, q_min = 0, None, None
    for t in M.tags_de[aid]:
        if t["Medicion"] not in ("RUN", "Caudal", "Corriente"):
            continue
        vals = [v for ts, v in M.med[t["Tag"]] if t0 < ts <= t1]
        n += len(vals)
        if vals and t["Medicion"] == "RUN":
            run_min = min(vals)
        if vals and t["Medicion"] == "Caudal":
            q_min = min(vals) / 3.6
    if n == 0:
        return 4
    if (run_min is not None and run_min == 0) or (q_min is not None and q_min < M.cfg["Caudal minimo bombeo (L/s)"]):
        return 3
    return 1


def estaciones(M, excluir=("Sala electrica", "Reporte externo", "Punto laboratorio"), solo=None):
    """Filas de «Comunicación por estación»: estado (3 sin comunicación, 2 posible corte, 1 comunicando), último dato y activos."""
    out = []
    est = []
    for a in M.activos:
        if a["Estacion"] and a["Estacion"] not in est and (a["Tipo"] in solo if solo else a["Tipo"] not in excluir):
            est.append(a["Estacion"])
    for e in est:
        aids = [a["ActivoID"] for a in M.activos if a["Estacion"] == e and (a["Tipo"] in solo if solo else True)]
        m = M.minutos(aids)
        marca = M.marca(aids)
        if marca is None:
            cod = None
        elif m > M.umbral_sin_dato:
            cod = 3
        elif M.posible_corte(e):
            cod = 2
        else:
            cod = 1
        out.append({"est": e, "cod": cod, "ult": M.hhmm(marca, M.ahora) if marca else "—", "n": len(aids)})
    return out


TXT_ESTACION = {1: "● Comunicando", 2: "▲ Posible corte de energía", 3: "■ Sin comunicación", None: ""}
ORD_SIMB = {"■": 0, "▲": 1, "◇": 2, "◌": 3, "●": 4, "": 5}


def ord_est(txt):
    return ORD_SIMB.get(txt[:1], 5)


def txt_pozo(cod):
    return {1: "● Bombeando", 3: "■ Detenido", 4: "◌ Sin dato", 5: "◇ Caudal congelado"}[cod]


def txt_estanque(cod):
    return {1: "● Normal", 2: "▲ Sobre HI", 3: "■ Sobre HH", 4: "◌ Sin dato", 5: "◇ Sensor congelado"}[cod]


def txt_tranque(cod, fuga=False):
    return {1: "● Normal", 2: "▲ Nivel alto", 3: "■ Fuga detectada" if fuga else "■ Sobre HH", 4: "◌ Sin dato", 5: "◇ Sensor congelado"}[cod]


def txt_aguas_abajo(cod):
    return {1: "● Estable o bajando", 2: "▲ Subiendo", 3: "■ Sube fuerte", 4: "◌ Sin dato", 5: "◇ Sensor congelado"}[cod]


def llega_hh_txt(M, aid, tipo):
    h = M.horas_a_hh(aid, tipo)
    if h is None:
        return "Sin riesgo a la tasa actual"
    return f"~{int(h)} h {int((h - int(h)) * 60):02d} min"


def tasa_txt(v):
    return "—" if v is None else f"{'+' if v >= 0 else '-'}{fmt(abs(v), 1, '.')}"


def bombas_txt(M, aid):
    tags = M._tags(aid, "RUN")
    return f"{int(sum(M.med[t['Tag']][-1][1] for t in tags))} / {len(tags)}"


def prox_hh(M):
    """Medidas[Rebalse proximo texto]: estanque o tranque que antes llega a HH."""
    c = [(M.horas_a_hh(a["ActivoID"], a["Tipo"]), a) for a in M.activos if a["Tipo"] in ("Estanque", "Tranque")]
    c = [(h, a) for h, a in c if h is not None]
    if not c:
        return "Ningún estanque ni tranque sube hacia HH"
    h, a = min(c, key=lambda x: x[0])
    return f"{a['Activo']} · {M.rebalse_texto(a['ActivoID'], a['Tipo'])}"


# ---------------------------------------------------------------------------------------------------------------------
# Página «Recuperación de agua»
# ---------------------------------------------------------------------------------------------------------------------
def recuperacion_agua(M):
    c, P = lienzo_pagina(M, "Recuperación de agua")
    rec = ids_tipo(M, "Pozo recuperacion")
    cod = {r: M.estado_pozo(r) for r in rec}
    n = lambda k: sum(1 for v in cod.values() if v == k)
    def q_circ(circ):
        return sum((M.valor(r, "Caudal") or 0) for r in rec if M.act[r]["Circuito"] == circ) / 3.6
    qn, qs = q_circ("Circuito Norte"), q_circ("Circuito Sur")
    mn, ms = M.cfg["Meta recuperacion Norte (L/s)"], M.cfg["Meta recuperacion Sur (L/s)"]
    P.tarjeta(12, 108, 368, 118, "Pozos bombeando", f"{n(1)} / {len(rec)}", f"{n(3)} detenido · {n(4)} sin dato")
    P.tarjeta(394, 108, 368, 118, "Detenidos", str(n(3)))
    P.tarjeta(776, 108, 368, 118, "Sin dato (más de 2 h)", str(n(4)))
    P.tarjeta(1158, 108, 368, 118, "Caudal recuperación Norte", f"{fmt(qn, 1, '.')} L/s",
              f"Meta {mn:.0f} L/s · {pct(qn / mn)} de la meta")
    P.tarjeta(1540, 108, 368, 118, "Caudal recuperación Sur", f"{fmt(qs, 1, '.')} L/s",
              f"Meta {ms:.0f} L/s · {pct(qs / ms)} de la meta")

    filas = [[M.act[r]["Grupo"], r, txt_pozo(cod[r]), detenido_hace_txt(M, r), f"{horas_detenidas_7d(M, r)} h",
              fmt((M.valor(r, "Caudal") or 0) / 3.6, 1, "."), fmt(M.valor(r, "Corriente") or 0, 1, "."), hhmm_activo(M, r),
              tiempo_sin_dato_txt(M, r)] for r in rec]
    P.tabla(12, 238, 928, 830, "Pozos de recuperación · estado actual (clic en un pozo para ver su detalle)",
            ["Circuito", "Pozo", "Estado", "Detenido hace", "Detenido 7 d", "Caudal L/s", "Corriente A", "Último dato", "Sin dato hace"],
            filas, [115, 64, 116, 112, 100, 90, 96, 96, 119], estado=2,
            colores=[COL_ESTADO[cod[r]] for r in rec], aligns=["l", "l", "l", "l", "l", "r", "r", "l", "l"])

    horas = list(range(24))
    P.pivot_estado(950, 238, 632, 830, "Bombeo últimas 24 h por hora (azul bombeando · rojo detenido · gris sin dato)", rec,
                   [f"{h:02d}" for h in horas], [[estado_hora(M, r, 23 - h) for h in horas] for r in rec],
                   {1: AZUL, 3: ROJO, 4: GRID})

    P.tarjeta(1597, 238, 311, 86, "Pozo seleccionado", "Seleccione un pozo en la tabla", pt_valor=19)
    P.tarjeta(1597, 336, 311, 80, "Estado", "● Bombeando", pt_valor=19)
    s24 = serie_horaria(M, "Caudal", 24, rec, 3.6)
    marcas = [ts for ts, _ in s24[rec[0]]]
    prom = [sum(s24[r][i][1] for r in rec) / len(rec) for i in range(len(marcas))]
    st = nice_step(max(prom) * 1.05, 4)
    P.lineas(1597, 428, 311, 260, "Caudal 24 h (L/s)", [("L/s", prom, AZUL)],
             [(0, marcas[0].strftime("%H:%M")), (12, marcas[12].strftime("%H:%M")), (23, marcas[23].strftime("%H:%M"))],
             ymax=st * -(-max(prom) * 1.12 // st), step=st, leyenda=False, yfmt=lambda v: fmt(v, 0, "."))
    P.tarjeta(1597, 700, 311, 110, "Señales del pozo", "—", pt_valor=13, st_valor="r")
    br = ids_tipo(M, "Bomba recuperacion")
    P.tabla(1597, 822, 311, 246, "Bombas de recuperación · Circuito Sur", ["Bomba", "RUN", "A"],
            [[M.act[b]["Activo"], f"{(M.valor(b, 'RUN') or 0):.0f}", fmt(M.valor(b, "Corriente") or 0, 1, ".")] for b in br],
            [185, 52, 54], aligns=["l", "r", "r"])
    return guardar(c, "recuperacion_agua.png")


# ---------------------------------------------------------------------------------------------------------------------
# Página «Aguas abajo»
# ---------------------------------------------------------------------------------------------------------------------
def aguas_abajo(M):
    c, P = lienzo_pagina(M, "Aguas abajo")
    mon = ids_tipo(M, "Pozo monitoreo")
    est = {m: M.estado_aguas_abajo(m) for m in mon}
    def kpi(circ):
        ids = [m for m in mon if M.act[m]["CircuitoAsociado"] == circ]
        return f"{sum(1 for m in ids if est[m][0] in (2, 3))} / {len(ids)}"
    sube = sum(1 for m in mon if est[m][0] in (2, 3))
    P.tarjeta(12, 108, 463, 118, "Aguas abajo · Circuito Norte", kpi("Circuito Norte"), "Pozos con nivel subiendo / pozos asociados", pt_valor=30)
    P.tarjeta(490, 108, 463, 118, "Aguas abajo · Circuito Sur", kpi("Circuito Sur"), "Pozos con nivel subiendo / pozos asociados", pt_valor=30)
    P.tarjeta(967, 108, 463, 118, "Sin circuito asignado", kpi("Por asignar"), "Pendientes de asignar a un circuito", pt_valor=30)
    P.tarjeta(1445, 108, 463, 118, "Pozos con el nivel subiendo", str(sube),
              f"Aviso si sube {M.cfg['Ascenso freatico aviso (m)']:.1f} m en 7 d · alerta desde {M.cfg['Ascenso freatico alerta (m)']:.1f} m (límites de ejemplo)".replace(".", ","),
              pt_valor=30)
    filas = []
    for m in mon:
        cod, asc = est[m]
        filas.append([m, M.act[m]["CircuitoAsociado"], f"{fmt(M.valor(m, 'Profundidad'), 2, '.')} m",
                      f"{'+' if asc >= 0 else '-'}{fmt(abs(asc), 2, '.')} m", txt_aguas_abajo(cod), hhmm_activo(M, m),
                      f"{fmt(M.valor(m, 'Bateria'), 2, '.')} V"])
    P.tabla(12, 238, 1010, 830, "Pozos de monitoreo · subida del nivel freático en 7 días",
            ["Pozo", "Circuito asociado", "Profundidad al agua", "Subida 7 d", "Estado", "Último dato", "Batería"], filas,
            [100, 150, 160, 110, 180, 100, 110], estado=4, colores=[COL_ESTADO[est[m][0]] for m in mon],
            aligns=["l", "l", "r", "r", "l", "l", "r"])
    s = serie_horaria(M, "Profundidad", 168, mon)
    marcas = [ts for ts, _ in s[mon[0]]]
    ser = [(m, [v for _, v in s[m]], DATA_COLORS[i % len(DATA_COLORS)]) for i, m in enumerate(mon)]
    P.lineas(1034, 238, 874, 830, "Profundidad al agua · últimos 7 días (m; si baja, el agua sube)", ser,
             etiquetas_x(marcas, 24), ymax=35, step=5, ymin=10, yfmt=lambda v: fmt(v, 0, "."))
    return guardar(c, "aguas_abajo.png")


# ---------------------------------------------------------------------------------------------------------------------
# Página «Estanques»
# ---------------------------------------------------------------------------------------------------------------------
def estanques(M):
    c, P = lienzo_pagina(M, "Estanques")
    est = ids_tipo(M, "Estanque")
    cod = {e: M.estado_estanque(e) for e in est}
    niv = {e: M.nivel_estanque(e) for e in est}
    hh = {e: M.hh_estanque(e) for e in est}
    hi = {e: M.hi_estanque(e) for e in est}
    top = max(est, key=lambda e: niv[e])
    n_hi = sum(1 for v in cod.values() if v in (2, 3))
    n_hh = sum(1 for v in cod.values() if v == 3)
    runs = [t for e in est for t in M._tags(e, "RUN")]
    en_serv = int(sum(M.med[t["Tag"]][-1][1] for t in runs))
    mn = min(est, key=lambda e: hh[e] - niv[e])
    P.tarjeta(12, 108, 463, 144, "Estanques sobre HI", f"{n_hi} / {len(est)}", f"Máx. {M.act[top]['Activo']} {fmt(niv[top], 0, '.')} %")
    P.tarjeta(489, 108, 463, 144, "Estanques sobre HH", str(n_hh))
    P.tarjeta(967, 108, 463, 144, "Bombas en servicio", f"{en_serv} / {len(runs)}", "Bombas de estanque con RUN = 1")
    P.tarjeta(1444, 108, 464, 144, "Menor margen a HH", f"{fmt(hh[mn] - niv[mn], 0, '.')} pts",
              f"{M.act[mn]['Activo']} · llega a HH {llega_hh_txt(M, mn, 'Estanque')}")
    pos = [(12, 261, 463, 280), (489, 261, 463, 280), (967, 263, 463, 280), (1444, 263, 464, 279)]
    for e, (x, y, w, h) in zip(est, pos):
        P.gauge(x, y, w, h, M.act[e]["Activo"], llega_hh_txt(M, e, "Estanque"), niv[e], hh[e], COL_ESTADO[cod[e]])
    s = serie_horaria(M, "Nivel estanque", 72, est)
    marcas = [ts for ts, _ in s[est[0]]]
    ser = sorted(((M.act[e]["Activo"], [v for _, v in s[e]], e) for e in est), key=lambda r: r[0])
    ser = [(nm, vals, DATA_COLORS[i]) for i, (nm, vals, _) in enumerate(ser)]
    P.lineas(12, 556, 702, 512, "Nivel de estanques · últimas 72 h (%)", ser, etiquetas_x(marcas, 24), ymax=120, step=20,
             refs=[(80, "HI 80", AMBAR), (90, "HH 90", ROJO)])
    filas = [[M.act[e]["Activo"], fmt(niv[e], 1, "."), txt_estanque(cod[e]), fmt(hi[e], 0, "."), fmt(hh[e], 0, "."),
              "Historiador" if M.valor(e, "Limite HI") is not None else "Por defecto (sin señal)", "(ejemplo)",
              tasa_txt(M.tasa_3h(e, "Nivel estanque")), llega_hh_txt(M, e, "Estanque"), bombas_txt(M, e)] for e in est]
    P.tabla(726, 556, 1182, 512, "Umbrales · límites de proceso y aviso de ejemplo",
            ["Estanque", "Nivel %", "Estado", "HI", "HH", "Límites", "Aviso (ejemplo)", "%/h", "Llega a HH", "Bombas"], filas,
            [150, 75, 145, 55, 55, 150, 115, 65, 200, 100], estado=2, colores=[COL_ESTADO[cod[e]] for e in est],
            aligns=["l", "r", "l", "r", "r", "l", "l", "r", "l", "l"])
    return guardar(c, "estanques.png")


# ---------------------------------------------------------------------------------------------------------------------
# Página «Tranques y pozas»
# ---------------------------------------------------------------------------------------------------------------------
def tranques_y_pozas(M):
    c, P = lienzo_pagina(M, "Tranques y pozas")
    trq = sorted(ids_tipo(M, "Tranque"), key=lambda a: M.act[a]["Activo"])
    cod = {t: M.estado_tranque(t) for t in trq}
    nivel = {t: M.valor(t, "Nivel tranque", "Si", prom=True) for t in trq}
    en_alerta = [t for t in trq if cod[t] in (2, 3, 5)]
    alarma_alta = [t for t in trq if (M.valor(t, "Alarma alto nivel") or 0) >= 1]
    em = "TRQ-EMER"
    bomba_a = M.valor(em, "RUN")
    modo = M.valor(em, "Modo auto")
    bombas = ("Bomba A " + ("en marcha" if bomba_a >= 1 else "detenida") if bomba_a is not None else "") + \
             ((" · Bomba B " + ("en automático" if modo >= 1 else "en manual")) if modo is not None else "")
    fuga = (M.valor(em, "Fuga") or M.valor(em, "Detector fuga") or 0) >= 1
    P.tarjeta(12, 108, 463, 118, "Tranques en alerta", f"{len(en_alerta)} / {len(trq)}",
              " · ".join(f"{M.act[t]['Activo']} {fmt(nivel[t], 1, '.')} %" for t in en_alerta) or "Todas en rango", pt_valor=30)
    P.tarjeta(490, 108, 463, 118, "Poza de emergencia", f"{fmt(nivel[em], 0, '.')} %",
              bombas + (" · FUGA DETECTADA" if fuga else " · sin fuga"), pt_valor=30)
    P.tarjeta(967, 108, 463, 118, "Estanques y tranques · próximo a HH", prox_hh(M),
              "Tiempo al rebalse = (HH − nivel) / subida de las últimas 3 h", pt_valor=15)
    P.tarjeta(1445, 108, 463, 118, "Alarmas de nivel alto", str(len(alarma_alta)),
              ("Alarma de nivel alto en " + ", ".join(M.act[t]["Activo"] for t in alarma_alta)) if alarma_alta
              else "Sin alarmas de nivel alto en tranques y pozas", pt_valor=30)
    filas = []
    for t in trq:
        a = M.act[t]
        filas.append([a["Activo"], a["Grupo"], f"{fmt(nivel[t], 1, '.')} %", fmt(_f(a["HI"]), 0, "."), fmt(_f(a["HH"]), 0, "."),
                      txt_tranque(cod[t], (M.valor(t, "Detector fuga") or 0) >= 1), tasa_txt(M.tasa_3h(t, "Nivel tranque")),
                      M.rebalse_texto(t, "Tranque"), hhmm_activo(M, t)])
    P.tabla(12, 238, 1110, 830, "Estado de tranques y pozas · umbrales de ejemplo",
            ["Tranque", "Área", "Nivel", "HI %", "HH %", "Estado", "Subida %/h", "Tiempo a HH", "Último dato"], filas,
            [230, 120, 80, 50, 50, 150, 85, 160, 90], estado=5, colores=[COL_ESTADO[cod[t]] for t in trq], pt=12,
            aligns=["l", "l", "r", "r", "r", "l", "r", "l", "l"])
    s = serie_horaria(M, "Nivel tranque", 72, trq)
    marcas = [ts for ts, _ in s[trq[0]]]
    ser = [(M.act[t]["Activo"], [v for _, v in s[t]], DATA_COLORS[i % len(DATA_COLORS)]) for i, t in enumerate(trq)]
    P.lineas(1134, 238, 774, 830, "Nivel de tranques y pozas · últimas 72 h (%)", ser, etiquetas_x(marcas, 24), ymax=110, step=10)
    return guardar(c, "tranques_y_pozas.png")


# ---------------------------------------------------------------------------------------------------------------------
# Página «Captación y agua fresca»
# ---------------------------------------------------------------------------------------------------------------------
def captacion(M):
    c, P = lienzo_pagina(M, "Captación y agua fresca")
    pozos = ids_tipo(M, "Pozo agua fresca")
    q = {p: M.caudal_pozo_ls(p) for p in pozos}
    cupo = M.cfg["Cupo captacion (L/s)"]
    q_af = M.valor("CAP-TOTAL", "Caudal total") / 3.6
    n_op = sum(1 for p in pozos if q[p] > M.cfg["Caudal minimo bombeo (L/s)"])
    pc = {p: M.proyeccion_cupo(p) for p in pozos}
    sobre = sum(1 for p in pozos if pc[p][0] and pc[p][0] > 1)
    cerca = sum(1 for p in pozos if pc[p][0] and 0.9 < pc[p][0] <= 1)
    pz = ids_tipo(M, "Piezometro")
    d7 = {p: M.delta(p, "Profundidad", 7) for p in pz}
    fuerte = M.cfg["Descenso piezometro fuerte (m)"]
    leve = M.cfg["Descenso piezometro leve (m)"]
    P.tarjeta(12, 108, 368, 118, "Captación ahora (L/s)", fmt(q_af, 1, "."),
              f"{pct(q_af / cupo)} del cupo ({fmt(cupo, 1, '.')} L/s) · {n_op} / {len(pozos)} pozos")
    P.tarjeta(394, 108, 368, 118, "% del cupo de captación", pct(q_af / cupo))
    P.tarjeta(776, 108, 368, 118, "Pozos operando", f"{n_op} / {len(pozos)}")
    P.tarjeta(1158, 108, 368, 118, "Mes vs cupo", pct(M.mes_vs_cupo()),
              f"{sobre} pozo(s) proyectan superar su cupo al cierre del mes · {cerca} sobre el 90 %")
    P.tarjeta(1540, 108, 368, 118, "Piezómetros con descenso fuerte", str(sum(1 for p in pz if d7[p] > fuerte)),
              f"{len(pz)} / {len(pz)} piezómetros con dato · umbral {fmt(fuerte, 1, '.')} m (ejemplo)")
    orden = sorted(pozos, key=lambda p: -q[p])
    filas, col_cupo = [], []
    for p in orden:
        a = M.act[p]
        ratio, proy, cup = pc[p]
        vol = M.valor(p, "Volumen mes")
        nivel_t = M._tags(p, "Nivel pozo")[0]["Tag"]
        s = M.med[nivel_t]
        prev = [v for ts, v in s if ts <= s[-1][0] - timedelta(days=1)]
        dn = s[-1][1] - prev[-1]
        filas.append([a["Sector"], p, fmt(q[p], 1, "."), "Medido" if M._tags(p, "Caudal") else "Calculado (totalizador)",
                      pct(ratio), f"{miles(vol)} m³", f"{miles(proy)} m³", fmt(M.valor(p, "Nivel pozo"), 1, "."),
                      f"{'+' if dn >= 0 else '-'}{fmt(abs(dn), 2, '.')}", hhmm_activo(M, p)])
        col_cupo.append(ROJO if ratio > 1 else (AMBAR if ratio > 0.9 else AZUL))
    P.tabla(12, 238, 948, 830, "Pozos de agua fresca",
            ["Sector", "Pozo", "Caudal L/s", "Origen", "% cupo (proy.)", "Vol. mes", "Proyección cierre", "Nivel m", "Δ 24 h m", "Último dato"],
            filas, [96, 62, 76, 156, 100, 80, 118, 60, 66, 82], estado=4, colores=col_cupo, pt_cab=10,
            aligns=["l", "l", "r", "l", "r", "r", "r", "r", "r", "l"])
    tag_ct = next(t["Tag"] for t in M.tags if t["Medicion"] == "Caudal total")
    s7 = [(ts, v / 3.6) for ts, v in M.med[tag_ct] if ts >= M.ahora - timedelta(hours=168)]
    P.lineas(975, 238, 933, 400, "Captación total · últimos 7 días (L/s)", [("L/s", [v for _, v in s7], AZUL)],
             etiquetas_x([ts for ts, _ in s7], 24), ymax=220, step=50, refs=[(cupo, f"Cupo {cupo:.0f} L/s", VIOLETA)],
             leyenda=False)
    col_pz = [ROJO if d7[p] > fuerte else AMBAR if d7[p] > leve else AZUL if d7[p] < -leve else GRIS_EJE for p in pz]
    P.columnas(975, 650, 933, 418, "Acuífero · cambio de profundidad en 7 días por piezómetro (m; + = baja el nivel)", pz,
               [d7[p] for p in pz], col_pz, -0.2, 0.8, 0.2, refs=[(fuerte, "Descenso fuerte 0,5 m", ROJO)], etiquetas=False,
               yfmt=lambda v: fmt(v, 1, "."))
    return guardar(c, "captacion.png")


# ---------------------------------------------------------------------------------------------------------------------
# Página «Calidad de agua»
# ---------------------------------------------------------------------------------------------------------------------
def calidad_agua(M):
    c, P = lienzo_pagina(M, "Calidad de agua")
    ec = ids_tipo(M, "Estacion calidad")
    cod = {e: M.estado_calidad(e) for e in ec}
    banda = sum(1 for v in cod.values() if v == 1)
    fuera = [e for e in ec if cod[e] == 2]
    ce_max = max(ec, key=lambda e: M.valor(e, "CE"))
    lab = _csv("lab_calidad")
    puntos = sorted({r["Punto"] for r in lab})
    ult = {}
    for p in puntos:
        fila = max((r for r in lab if r["Punto"] == p), key=lambda r: r["Fecha"])
        ult[p] = fila
    def est_sst(r):
        v = float(r["SST"])
        return 3 if v >= float(r["LimiteAlerta"]) else (2 if v >= float(r["LimiteAviso"]) else 1)
    sobre = sum(1 for p in puntos if est_sst(ult[p]) == 3)
    f_max = max(r["Fecha"] for r in lab)
    P.tarjeta(12, 108, 463, 118, "pH en banda", f"{banda} / {len(ec)}",
              ("Fuera: " + ", ".join(f"{e} pH {fmt(M.valor(e, 'pH'), 1, '.')}" for e in fuera)) if fuera else "Todas en banda 6,5–8,5")
    P.tarjeta(490, 108, 463, 118, "CE máxima (µS/cm)", miles(M.valor(ce_max, "CE")), f"{ce_max} · µS/cm")
    P.tarjeta(967, 108, 463, 118, "SST sobre límite de alerta", f"{sobre} / {len(puntos)}",
              "Laboratorio · último muestreo " + datetime.strptime(f_max, "%Y-%m-%d").strftime("%d-%m"))
    P.tarjeta(1445, 108, 463, 118, "Estaciones con dato", f"{sum(1 for v in cod.values() if v in (1, 2))} / {len(ec)}")
    txt_q = {1: "● En banda", 2: "▲ Fuera de banda", 4: "◌ Sin dato", 5: "◇ pH congelado"}
    col_q = {1: AZUL, 2: AMBAR, 4: GRIS_EST, 5: AMBAR}
    filas = [[e, M.act[e]["Grupo"], fmt(M.valor(e, "pH"), 1, "."), miles(M.valor(e, "CE")), fmt(M.valor(e, "Turbidez"), 1, "."),
              txt_q[cod[e]], hhmm_activo(M, e), M.act[e]["Confianza"]] for e in ec]
    P.tabla(12, 238, 851, 410, "Estaciones de calidad · pH, CE y turbidez en línea",
            ["Estación", "Ubicación", "pH", "CE µS/cm", "Turbidez NTU", "Estado", "Último dato", "Mapeo de señal"], filas,
            [75, 150, 50, 90, 110, 140, 95, 120], estado=5, pt_cab=10, colores=[col_q[cod[e]] for e in ec],
            aligns=["l", "l", "r", "r", "r", "l", "l", "l"])
    s = serie_horaria(M, "pH", 72, ec)
    marcas = [ts for ts, _ in s[ec[0]]]
    ser = [(e, [v for _, v in s[e]], DATA_COLORS[i]) for i, e in enumerate(ec)]
    refs = [(M.cfg["pH minimo"], "6,5", AMBAR), (M.cfg["pH maximo"], "8,5", AMBAR)]
    P.lineas(877, 238, 1031, 410, "pH · últimas 72 h", ser, etiquetas_x(marcas, 12), ymax=9, ymin=5, step=1, refs=refs)
    col_sst = {1: AZUL, 2: AMBAR, 3: ROJO}
    txt_sst = {1: "● Bajo aviso", 2: "▲ Sobre aviso", 3: "■ Sobre alerta"}
    filas = [[p, datetime.strptime(ult[p]["Fecha"], "%Y-%m-%d").strftime("%d-%m-%Y"), miles(float(ult[p]["SST"])),
              miles(float(ult[p]["LimiteAviso"])), miles(float(ult[p]["LimiteAlerta"])), txt_sst[est_sst(ult[p])]] for p in puntos]
    P.tabla(12, 660, 851, 408, "Sólidos suspendidos de laboratorio · último resultado por punto",
            ["Punto", "Muestra", "SST mg/L", "Aviso", "Alerta", "Estado"], filas, [149, 139, 130, 110, 110, 188], estado=5,
            colores=[col_sst[est_sst(ult[p])] for p in puntos], aligns=["l", "l", "r", "r", "r", "l"])
    P.lineas(877, 660, 508, 408, "EC-01 · pH últimas 72 h", [("EC-01", [v for _, v in s["EC-01"]], "#2F6FB5")],
             etiquetas_x(marcas, 24, "%d-%m"), ymax=8, ymin=5, step=1, refs=[(6.5, "6,5", AMBAR)], leyenda=False)
    ec1 = sorted((r for r in lab if r["Punto"] == "EC-01"), key=lambda r: r["Fecha"])
    fechas = [datetime.strptime(r["Fecha"], "%Y-%m-%d") for r in ec1]
    P.lineas(1400, 660, 508, 408, "EC-01 · sólidos suspendidos de laboratorio (mg/L)", [("SST", [float(r["SST"]) for r in ec1], ROJO)],
             [(i, fechas[i].strftime("%d-%m")) for i in range(0, len(fechas), 4)], ymax=100, step=20,
             refs=[(70, "Aviso", AMBAR), (90, "Alerta", ROJO)], leyenda=False)
    return guardar(c, "calidad_agua.png")


# ---------------------------------------------------------------------------------------------------------------------
# Página «Semáforos»
# ---------------------------------------------------------------------------------------------------------------------
def semaforos(M):
    c, P = lienzo_pagina(M, "Semáforos")
    al = M.alarmas()
    # severidad por activo (máxima por tipo / circuito), a partir de las alarmas calculadas
    por_activo = {r["activo"]: r["sev"] for r in al}
    def sev_de(aids):
        return max([por_activo.get(M.act[a]["Activo"], 0) for a in aids] + [0])
    rec = ids_tipo(M, "Pozo recuperacion")
    est_p = {r: M.estado_pozo(r) for r in rec}
    est = ids_tipo(M, "Estanque")
    trq = ids_tipo(M, "Tranque")
    mon = ids_tipo(M, "Pozo monitoreo")
    af = ids_tipo(M, "Pozo agua fresca")
    ec = ids_tipo(M, "Estacion calidad")
    est_ec = {e: M.estado_calidad(e) for e in ec}
    ests = estaciones(M)
    caidas = sum(1 for e in ests if e["cod"] == 3)
    cortes_circ = lambda circ: sum(1 for e in ests if e["cod"] == 2 and any(M.act[a["ActivoID"]]["Circuito"] == circ for a in M.activos if a["Estacion"] == e["est"]))
    q_circ = lambda circ: sum((M.valor(r, "Caudal") or 0) for r in rec if M.act[r]["Circuito"] == circ) / 3.6

    def sem_rec(circ):
        ids = [a for a in ids_tipo(M, "Pozo recuperacion") + ids_tipo(M, "Canal colector") if M.act[a]["Circuito"] == circ]
        cod = 3 if (cortes_circ(circ) > 0 or sev_de(ids) == 3) else (2 if sev_de(ids) >= 1 else 1)
        pozos = [r for r in rec if M.act[r]["Circuito"] == circ]
        det = f"{sum(1 for r in pozos if est_p[r] == 1)} de {len(pozos)} pozos bombeando · {fmt(q_circ(circ), 1, '.')} L/s"
        if cortes_circ(circ) > 0:
            det += " · posible corte de energía"
        return cod, det

    n_hi = sum(1 for e in est if M.estado_estanque(e) in (2, 3))
    mn = min(est, key=lambda e: M.hh_estanque(e) - M.nivel_estanque(e))
    sev_est = sev_de(est)
    en_alerta = [t for t in trq if M.estado_tranque(t) in (2, 3, 5)]
    alta = [M.act[t]["Activo"] for t in trq if (M.valor(t, "Alarma alto nivel") or 0) >= 1]
    ad = {m: M.estado_aguas_abajo(m)[0] for m in mon}
    sube = sum(1 for v in ad.values() if v in (2, 3))
    q_af = M.valor("CAP-TOTAL", "Caudal total") / 3.6
    pc_cupo = q_af / M.cfg["Cupo captacion (L/s)"]
    pc_pozo = {p: M.proyeccion_cupo(p)[0] for p in af}
    sobre_cupo = sum(1 for p in af if pc_pozo[p] and pc_pozo[p] > 1)
    ups = {s: M.ups(s)[2] for s in ids_tipo(M, "Sala electrica")}
    ups_alarma = sum(1 for v in ups.values() if v >= 2)
    ups_sin = sum(1 for v in ups.values() if v == 3)
    bat_baja = sum(1 for m in mon if M.valor(m, "Bateria") is not None and M.valor(m, "Bateria") < M.cfg["Bateria baja 12 V (V)"])
    cortes = sum(1 for e in ests if e["cod"] == 2)
    envio_a = [M.med[t["Tag"]][-1][1] for t in M.tags if t["Medicion"] == "Horas sin envio A"]
    envio_b = [M.med[t["Tag"]][-1][1] for t in M.tags if t["Medicion"] == "Errores envio B 12 h"]
    a_atras = sum(1 for v in envio_a if v > M.cfg["Horas sin envio A"])
    a_24 = sum(1 for v in envio_a if v > 24)
    b_err = sum(1 for v in envio_b if v >= M.cfg["Errores envio B 12 h"])
    tags_ok = sum(1 for t in M.tags if (M.ahora - M.med[t["Tag"]][-1][0]).total_seconds() / 60 <= M.umbral_sin_dato)
    congelados = 0                       # Medidas[Tags congelados]: se cuenta por señal
    for t in M.tags:
        if t["Medicion"] not in M.CONG:
            continue
        s = M.med[t["Tag"]]
        t1, v1 = s[-1]
        t0 = t1 - timedelta(hours=M.cfg["Horas para congelado"])
        ult = [v for ts, v in s if ts >= t0]
        if s[0][0] <= t0 and len(ult) >= 8 and abs(v1) > 0.01 and max(ult) - min(ult) <= 1e-6:
            congelados += 1
    datos_atras = (M.ahora - M.ultima_muestra).total_seconds() / 3600 > M.cfg["Horas datos atrasados"]
    pct_tags = tags_ok / len(M.tags)
    c_rn, d_rn = sem_rec("Circuito Norte")
    c_rs, d_rs = sem_rec("Circuito Sur")
    ec_fuera = [e for e in ec if est_ec[e] == 2]
    sistemas = [
        ("RECUPERACIÓN NORTE", c_rn, d_rn),
        ("RECUPERACIÓN SUR", c_rs, d_rs),
        ("ESTANQUES", 3 if sev_est == 3 else (2 if sev_est >= 1 else 1),
         f"{n_hi} de {len(est)} sobre HI · {M.act[mn]['Activo']} · llega a HH {llega_hh_txt(M, mn, 'Estanque')}"),
        ("TRANQUES Y POZAS", 3 if sev_de(trq) == 3 else (2 if sev_de(trq) >= 1 else 1),
         f"{len(en_alerta)} de {len(trq)} en alerta · emergencia {fmt(M.valor('TRQ-EMER', 'Nivel tranque', 'Si', prom=True), 0, '.')} % · "
         + (("Alarma de nivel alto en " + ", ".join(alta)) if alta else "Sin alarmas de nivel alto en tranques y pozas")),
        ("AGUAS ABAJO", 3 if any(v == 3 for v in ad.values()) else (2 if any(v in (2, 4, 5) for v in ad.values()) else 1),
         f"{sube} de {len(mon)} pozos de monitoreo con el nivel subiendo en 7 d · asociación a circuitos por validar"),
        ("AGUA FRESCA", 3 if (pc_cupo > 1 or sev_de(af) == 3) else (2 if (sev_de(af) >= 1 or (M.valor("CAP-TOTAL", "Pozos sin comunicacion") or 0) > 0) else 1),
         f"{fmt(q_af, 1, '.')} L/s ({pct(pc_cupo)} del cupo) · {sobre_cupo} pozo(s) sobre su cupo al cierre · "
         f"{fmt(M.valor('CAP-TOTAL', 'Pozos sin comunicacion') or 0, 0, '.')} sin comunicación"),
        ("CALIDAD DE AGUA", 3 if sev_de(ec) == 3 else (2 if sev_de(ec) >= 1 else 1),
         f"{sum(1 for v in est_ec.values() if v == 1)} / {len(ec)} estaciones en banda de pH · "
         + (("Fuera: " + ", ".join(f"{e} pH {fmt(M.valor(e, 'pH'), 1, '.')}" for e in ec_fuera)) if ec_fuera else "Todas en banda 6,5–8,5")),
        ("ENERGÍA Y COMUNICACIONES", 3 if (caidas > 0 or cortes > 0) else (2 if (ups_alarma > 0 or bat_baja > 0) else 1),
         f"{caidas} estación(es) sin comunicación · {cortes} posible corte · {ups_alarma} UPS en alarma · {bat_baja} baterías bajas"),
        ("REPORTE EXTERNO", 3 if a_24 > 0 else (2 if (a_atras > 0 or b_err > 0) else 1),
         f"Portal A: {a_atras} de {len(envio_a)} pozos atrasados · Portal B: {b_err} de {len(envio_b)} envíos con errores"),
        ("ACTUALIZACIÓN DE DATOS", 3 if datos_atras else (2 if (pct_tags < 0.9 or congelados > 0) else 1),
         f"Datos al {M.ultima_muestra.strftime('%d-%m %H:%M')} · {pct(pct_tags)} de los tags con dato · {congelados} congelados"),
    ]
    col_s = {3: ROJO, 2: AMBAR, 1: "#2E9E6B"}
    txt_s = {3: "CRÍTICO", 2: "ALERTA", 1: "NORMAL"}
    for i, (nombre, cod, det) in enumerate(sistemas):
        x = 12 + (i % 5) * 381
        y = 108 if i < 5 else 324
        fg = NAVY if cod == 2 else BLANCO
        c.caja(x, y, 369, 112, fill=col_s[cod], r=10)
        P.texto(x + 184.5, y + 22, nombre, 17 * PT, fg, "b", "m")
        P.texto(x + 184.5, y + 68, txt_s[cod], 34 * PT, fg, "sb", "m")
        c.caja(x, y + 112, 369, 92, fill=col_s[cod], r=10)
        P.parrafo(x + 10, y + 112 + 6, 349, 80, det, 12 * PT, fg)
    # --- alarmas críticas y alertas
    crit = [a for a in al if a["sev"] >= 2]
    sev_txt = {3: "✖ Crítica", 2: "▲ Alerta"}
    sev_col = {3: ROJO, 2: AMBAR}
    P.tabla(12, 540, 1240, 528, "Alarmas abiertas · críticas y alertas", ["Prio.", "Severidad", "Activo", "Condición", "Desde", "Duración"],
            [[a["prio"], sev_txt[a["sev"]], a["activo"], a["cond"], a["desde"], a["dur"]] for a in crit],
            [55, 105, 190, 580, 115, 110], estado=1, colores=[sev_col[a["sev"]] for a in crit], pt=13, pt_cab=12,
            aligns=["r", "l", "l", "l", "l", "l"])
    P.tarjeta(1264, 540, 644, 120, "Estanques y tranques · próximo en llegar a HH", prox_hh(M), pt_valor=17)
    for x, circ, nom in ((1264, "Circuito Norte", "Norte"), (1592, "Circuito Sur", "Sur")):
        ids = [r for r in rec if M.act[r]["Circuito"] == circ]
        hs = sum(horas_detenidas_7d(M, r) for r in ids)
        P.panel(x, 672, 316, 120, f"Recuperación {nom} · 7 días")
        P.parrafo(x + 10, 706, 296, 80, f"{miles(hs)} h·pozo detenidas en 7 d ({pct(hs / (len(ids) * 168))} del tiempo)", 13 * PT, NAVY)
    ests_t = [e for e in ests if e["cod"] in (2, 3)]
    ests_t.sort(key=lambda e: (ord_est(TXT_ESTACION[e["cod"]]), e["est"]))
    P.tabla(1264, 804, 644, 264, "Estaciones sin comunicación o con posible corte de energía", ["Estación", "Estado", "Último dato", "Activos"],
            [[e["est"], TXT_ESTACION[e["cod"]], e["ult"], e["n"]] for e in ests_t], [220, 215, 105, 70], estado=1,
            colores=[{2: AMBAR, 3: ROJO}[e["cod"]] for e in ests_t], pt=12, pt_cab=11, aligns=["l", "l", "l", "r"])
    return guardar(c, "semaforos.png")


# ---------------------------------------------------------------------------------------------------------------------
# Página «Energía y reporte»
# ---------------------------------------------------------------------------------------------------------------------
def energia_reporte(M):
    c, P = lienzo_pagina(M, "Energía y reporte")
    ests = estaciones(M, solo=("Pozo recuperacion", "Bomba recuperacion", "Caudal recuperacion", "Canal colector", "Estanque",
                                "Pozo agua fresca", "Campo de pozos", "Comunicacion", "Piezometro", "Estacion calidad", "Tranque",
                                "Aforador", "Pozo monitoreo"))
    ests_c = estaciones(M)
    caidas = [e["est"] for e in ests_c if e["cod"] == 3]
    cortes = [e for e in ests_c if e["cod"] == 2]
    salas = ids_tipo(M, "Sala electrica")
    ups = {s: M.ups(s) for s in salas}
    en_alarma = sum(1 for s in salas if ups[s][2] >= 2)
    sin_alim = sum(1 for s in salas if ups[s][2] == 3)
    tags_a = [t for t in M.tags if t["Medicion"] == "Horas sin envio A"]
    tags_b = [t for t in M.tags if t["Medicion"] == "Errores envio B 12 h"]
    va = {t["Tag"]: M.med[t["Tag"]][-1][1] for t in tags_a}
    vb = {t["Tag"]: M.med[t["Tag"]][-1][1] for t in tags_b}
    lim_a, lim_b = M.cfg["Horas sin envio A"], M.cfg["Errores envio B 12 h"]
    atrasados = sorted((t for t in tags_a if va[t["Tag"]] > lim_a), key=lambda t: -va[t["Tag"]])
    lista_a = ", ".join(f"{t['Descripcion'].split('· ')[-1]} ({fmt(va[t['Tag']], 0, '.')} h)" for t in atrasados[:6]) \
        or "Todos los pozos enviando al portal A"
    P.tarjeta(12, 108, 369, 118, "Estaciones sin comunicación", str(len(caidas)), ", ".join(caidas[:4]) or "Todas las estaciones comunicando",
              pt_valor=30, pt_sub=12)
    P.tarjeta(393, 108, 369, 118, "Posible corte de energía", str(len(cortes)),
              "Todas las bombas de la estación detenidas a la vez y sin corriente", pt_valor=30, pt_sub=12)
    P.tarjeta(774, 108, 369, 118, "UPS de salas eléctricas en alarma", f"{en_alarma} / {len(salas)}", f"{sin_alim} sin alimentación",
              pt_valor=30, pt_sub=12)
    P.tarjeta(1155, 108, 369, 118, "Envío al portal A atrasado", str(len(atrasados)), lista_a, pt_valor=30, pt_sub=12)
    P.tarjeta(1536, 108, 369, 118, "Envío al portal B con errores", str(sum(1 for v in vb.values() if v >= lim_b)),
              "Errores de envío en 12 h sobre el umbral de ejemplo", pt_valor=30, pt_sub=12)
    # --- comunicación por estación
    ests = [e for e in ests if e["cod"] is not None] + [e for e in ests if e["cod"] is None]
    ests.sort(key=lambda e: (ord_est(TXT_ESTACION[e["cod"]]), e["est"]))
    col_e = {1: AZUL, 2: AMBAR, 3: ROJO, None: None}
    P.tabla(12, 238, 600, 830, "Comunicación por estación", ["Estación", "Estado", "Último dato", "Activos"],
            [[e["est"], TXT_ESTACION[e["cod"]], e["ult"], e["n"]] for e in ests], [210, 210, 105, 75], estado=1,
            colores=[col_e[e["cod"]] for e in ests], pt=12, aligns=["l", "l", "l", "r"])
    # --- UPS
    txt_u = {1: "● Normal", 2: "▲ Alarma", 3: "■ Sin alimentación"}
    col_u = {1: AZUL, 2: AMBAR, 3: ROJO}
    sal = sorted(salas, key=lambda s: (ord_est(txt_u[ups[s][2]]), M.act[s]["Activo"]))
    P.tabla(624, 238, 640, 520, "UPS de salas eléctricas (Normal / Alarma)", ["Sala", "Área", "Estado", "Alarmas"],
            [[M.act[s]["Activo"], M.act[s]["Grupo"], txt_u[ups[s][2]], ups[s][1]] for s in sal], [150, 130, 185, 155], estado=2,
            colores=[col_u[ups[s][2]] for s in sal], pt=12)
    # --- batería
    mon = ids_tipo(M, "Pozo monitoreo")
    bat = sorted(mon, key=lambda m: M.valor(m, "Bateria"))
    baja = lambda m: M.valor(m, "Bateria") < M.cfg["Bateria baja 12 V (V)"]
    P.tabla(624, 770, 640, 298, "Batería de estaciones de monitoreo (V)", ["Estación", "Batería V"],
            [[m, fmt(M.valor(m, "Bateria"), 2, ".")] for m in bat], [260, 120], estado=1,
            colores=[ROJO if baja(m) else AZUL for m in bat], pt=12, aligns=["l", "r"])
    # --- envíos a portales
    filas = []
    for t in tags_a + tags_b:
        a = t["Medicion"] == "Horas sin envio A"
        v = va[t["Tag"]] if a else vb[t["Tag"]]
        if a:
            cod = 3 if v > 24 else (2 if v > lim_a else 1)
            txt = "Último mensaje hace " + (f"{v * 60:.0f} min" if v < 1 else f"{fmt(v, 1, '.')} h")
        else:
            cod = 2 if v >= lim_b else 1
            txt = f"{v:.0f} errores en 12 h"
        filas.append((t["Descripcion"], txt, {1: "● Al día", 2: "▲ Atrasado o con errores", 3: "■ Sin envío > 24 h"}[cod], cod))
    filas.sort(key=lambda r: (ord_est(r[2]), r[0]))
    P.tabla(1276, 238, 632, 830, "Envío de datos a portales externos (A y B)", ["Punto", "Envío", "Estado"],
            [[r[0], r[1], r[2]] for r in filas], [215, 200, 197], estado=2, colores=[col_u[r[3]] for r in filas], pt=11)
    return guardar(c, "energia_reporte.png")


# ---------------------------------------------------------------------------------------------------------------------
# Página «Señales y calidad del dato»
# ---------------------------------------------------------------------------------------------------------------------
def senales_calidad_dato(M):
    c, P = lienzo_pagina(M, "Señales y calidad del dato")
    tot = len(M.tags)
    ok = sum(1 for t in M.tags if (M.ahora - M.med[t["Tag"]][-1][0]).total_seconds() / 60 <= M.umbral_sin_dato)
    P.tarjeta(12, 108, 463, 118, "Señales en el modelo", miles(tot))
    P.tarjeta(490, 108, 463, 118, "Con dato en las últimas 2 h", miles(ok))
    P.tarjeta(967, 108, 463, 118, "Sin dato reciente", miles(tot - ok))
    P.tarjeta(1445, 108, 463, 118, "% de señales al día", pct(ok / tot))
    for x, w, cab in ((14, 121, "Módulo"), (141, 355, "Señal"), (502, 421, "Descripción"), (929, 121, "Activo"), (1056, 221, "Medición"),
                      (1283, 96, "Unidad"), (1615, 138, "Estado"), (1759, 105, "Confianza")):
        P.slicer(x, 238, w, 66, cab)
    orden = sorted(M.tags, key=lambda t: -int(M.med[t["Tag"]][-1][0].strftime("%H%M")) if M.med[t["Tag"]][-1][0].date() == M.ahora.date() else 0)
    filas, cols = [], []
    for t in orden[:40]:
        ts, v = M.med[t["Tag"]][-1]
        mins = (M.ahora - ts).total_seconds() / 60
        cod = 3 if mins > M.umbral_sin_dato else 1
        filas.append([t["Modulo"], t["Tag"], t["Descripcion"], M.act[t["ActivoID"]]["Activo"], t["Medicion"], t["Unidad"],
                      fmt(v, 1, "."), M.hhmm(ts, M.ahora), {1: "● Con dato", 3: "■ Atrasado"}[cod], t["Confianza"]])
        cols.append(COL_ESTADO[cod])
    P.tabla(12, 310, 1896, 758, "Catálogo de señales · último valor y estado del dato",
            ["Módulo", "Señal", "Descripción", "Activo", "Medición", "Unidad", "Valor", "Último dato", "Estado", "Confianza"], filas,
            [127, 361, 427, 127, 227, 102, 111, 119, 144, 111], estado=8, colores=cols, extra_filas=tot - 24,
            aligns=["l", "l", "l", "l", "l", "l", "r", "l", "l", "l"])
    return guardar(c, "senales_calidad_dato.png")


PAGINAS = (vista_general, balance_hidrico, recuperacion_agua, aguas_abajo, estanques, tranques_y_pozas, captacion, calidad_agua,
           semaforos, energia_reporte, senales_calidad_dato)

if __name__ == "__main__":
    modelo = Modelo()
    for fn in PAGINAS:
        ruta = fn(modelo)
        print(ruta.name, f"{ruta.stat().st_size / 1024:.0f} KB")
