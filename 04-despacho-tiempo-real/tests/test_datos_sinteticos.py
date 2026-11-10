"""Tests del generador de datos sintéticos: rangos, reproducibilidad, contrato y coherencia del snapshot."""
import csv
import json
import sys
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "datos_sinteticos"))

import generar_datos as gen  # noqa: E402
from despacho import contratos, tiempo  # noqa: E402


def leer_csv(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class TestDatosSinteticos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.salida = Path(cls._tmp.name) / "csv"
        cls.docs = Path(cls._tmp.name) / "docs"
        cls.cuenta = gen.generar(cls.salida, cls.docs)

    @classmethod
    def tearDownClass(cls):
        tiempo.configurar_zona("UTC")
        cls._tmp.cleanup()

    def test_archivos_pequenos(self):
        for ruta in self.salida.glob("*.csv"):
            self.assertLess(ruta.stat().st_size, 2 * 1024 * 1024, ruta.name)
        self.assertTrue((self.docs / "snapshot_ejemplo.json").exists())

    def test_periodo_de_90_dias(self):
        filas = leer_csv(self.salida / "plan_gaviota_hora.csv")
        fechas = sorted({f["fecha"] for f in filas})
        self.assertEqual(len(fechas), 90)
        self.assertEqual((fechas[0], fechas[-1]), ("2025-03-03", "2025-05-31"))

    def test_solo_horas_completas_hasta_el_instante_del_snapshot(self):
        filas = leer_csv(self.salida / "chancado_hora.csv")
        self.assertLessEqual(filas[-1]["hora_inicio"], "2025-05-31T14:00:00")
        self.assertEqual(len(filas), 89 * 24 + 7)

    def test_velocidad_caex_entre_15_y_30(self):
        filas = leer_csv(self.salida / "velocidad_caex_hora.csv")
        self.assertGreater(len(filas), 1000)
        for f in filas:
            for col in ("velocidad_cargado_kmh", "velocidad_vacio_kmh", "velocidad_media_kmh"):
                self.assertTrue(15 <= float(f[col]) <= 30, (col, f[col]))
        camiones = {f["camion"] for f in filas}
        self.assertTrue(camiones <= {f"CAEX-{i:02d}" for i in range(1, 27)})

    def test_alimentacion_a_chancado_en_rango(self):
        filas = leer_csv(self.salida / "chancado_hora.csv")
        self.assertTrue(all(3200 <= float(f["alimentacion_tph"]) <= 4800 for f in filas))

    def test_granulometria_en_tres_fracciones_60_20_20(self):
        filas = leer_csv(self.salida / "granulometria_hora.csv")
        por_hora, por_fraccion = defaultdict(float), defaultdict(list)
        for f in filas:
            por_hora[f["hora_inicio"]] += float(f["masa_pct"])
            por_fraccion[f["fraccion"]].append(float(f["masa_pct"]))
        self.assertEqual(len(por_fraccion), 3)
        self.assertTrue(all(abs(s - 100) < 0.2 for s in por_hora.values()))
        medias = sorted(sum(v) / len(v) for v in por_fraccion.values())
        self.assertAlmostEqual(medias[0], 20, delta=1.0)
        self.assertAlmostEqual(medias[1], 20, delta=1.0)
        self.assertAlmostEqual(medias[2], 60, delta=1.0)

    def test_gaviota_plan_y_real_diarios(self):
        filas = leer_csv(self.salida / "plan_gaviota_hora.csv")
        plan, real = defaultdict(float), defaultdict(float)
        for f in filas:
            plan[f["fecha"]] += float(f["plan_kt"])
            real[f["fecha"]] += float(f["real_kt"])
        completos = [d for d in plan if d != "2025-05-31"]
        for d in completos:
            self.assertAlmostEqual(plan[d], 192.0, delta=0.2)
            self.assertTrue(150 <= real[d] <= 260, (d, real[d]))

    def test_ciclos_por_hora_pala_camion(self):
        filas = leer_csv(self.salida / "ciclos_hora_pala_camion.csv")
        palas = {f["pala"] for f in filas}
        self.assertTrue(palas <= set(gen.sin.FLOTA_PALAS) | set(gen.sin.FLOTA_CARGADORES))
        self.assertTrue(all(int(f["ciclos"]) >= 1 for f in filas))
        self.assertTrue(all(20 <= float(f["tiempo_ciclo_min"]) <= 70 for f in filas))
        self.assertEqual({f["fecha"] for f in filas}, {f"2025-05-{d}" for d in range(25, 32)})

    def test_equipos_y_gps_cumplen_el_contrato(self):
        equipos = [{"Equipo": f["Equipo"], "TipoEquipo": f["TipoEquipo"], "Flota": f["Flota"] or None,
                    "ActivoKPI": int(f["ActivoKPI"])} for f in leer_csv(self.salida / "equipos.csv")]
        self.assertEqual(contratos.validar_registros("equipos", equipos), [])
        self.assertEqual(sum(1 for e in equipos if e["ActivoKPI"] == 0), 1)
        gps = [{"Equipo": f["Equipo"], "TipoEquipo": f["TipoEquipo"], "FechaHora": f["FechaHora"],
                "Latitud": float(f["Latitud"]), "Longitud": float(f["Longitud"]), "Velocidad": float(f["Velocidad"])}
               for f in leer_csv(self.salida / "gps.csv")]
        self.assertEqual(contratos.validar_registros("gps", gps), [])
        for g in gps:   # coordenadas ficticias dentro del rectángulo de calibración del mapa
            self.assertTrue(12.0 <= g["Latitud"] / 3_600_000 <= 12.12)
            self.assertTrue(-35.0 <= g["Longitud"] / 3_600_000 <= -34.84)

    def test_snapshot_es_coherente(self):
        snap = json.loads((self.docs / "snapshot_ejemplo.json").read_text(encoding="utf-8"))
        for clave in ("version", "generado", "modo", "estado_datos", "fuente", "turno", "reloj", "tarjetas",
                      "gaviota", "ciclos", "flota", "chancado", "equipos", "mapa", "alertas"):
            self.assertIn(clave, snap)
        self.assertEqual((snap["modo"], snap["estado_datos"]), ("demo", "DEMO"))
        self.assertEqual((snap["turno"]["turno"], snap["turno"]["hora_turno"]), ("A", 8))
        acum = [x for x in snap["gaviota"]["acumulado_kt"] if x is not None]
        self.assertEqual(acum, sorted(acum))
        tarjeta = snap["tarjetas"]["movimiento_mina"]
        self.assertLessEqual(tarjeta["cierre_p10_kt"], tarjeta["cierre_p50_kt"])
        self.assertLessEqual(tarjeta["cierre_p50_kt"], tarjeta["cierre_p90_kt"])
        self.assertTrue(0 <= tarjeta["prob_cumplir"] <= 1)
        self.assertTrue(15 <= snap["tarjetas"]["velocidad_caex"]["mina_kmh"] <= 30)
        gran = snap["chancado"]["granulometria_pct"]
        self.assertAlmostEqual(sum(gran.values()), 100, delta=0.3)
        flota = {f["flota"]: f for f in snap["flota"]["filas"]}
        self.assertTrue(82 <= flota["CAEX"]["df_pct"] <= 94 and 70 <= flota["CAEX"]["uebd_pct"] <= 85)
        alerta = snap["alertas"]["activas"][0]
        self.assertGreaterEqual(alerta["valor"], alerta["umbral"])
        self.assertEqual(snap["alertas"]["resumen"]["total"], len(snap["alertas"]["activas"]))

    def test_es_reproducible(self):
        with tempfile.TemporaryDirectory() as otra:
            otra = Path(otra)
            gen.generar(otra / "csv", otra / "docs")
            for ruta in sorted(self.salida.glob("*.csv")):
                self.assertEqual(ruta.read_bytes(), (otra / "csv" / ruta.name).read_bytes(), ruta.name)
            self.assertEqual((self.docs / "snapshot_ejemplo.json").read_bytes(),
                             (otra / "docs" / "snapshot_ejemplo.json").read_bytes())

    def test_lo_publicado_coincide_con_el_generador(self):
        """datos_sinteticos/*.csv y docs/snapshot_ejemplo.json deben ser la salida actual del generador."""
        def norm(b: bytes) -> bytes:
            return b.replace(b"\r\n", b"\n")
        for ruta in sorted(self.salida.glob("*.csv")):
            publicado = RAIZ / "datos_sinteticos" / ruta.name
            self.assertTrue(publicado.exists(), f"falta {ruta.name}: ejecutar generar_datos.py")
            self.assertEqual(norm(publicado.read_bytes()), norm(ruta.read_bytes()), ruta.name)
        self.assertEqual(norm((RAIZ / "docs" / "snapshot_ejemplo.json").read_bytes()),
                         norm((self.docs / "snapshot_ejemplo.json").read_bytes()))


if __name__ == "__main__":
    unittest.main()
