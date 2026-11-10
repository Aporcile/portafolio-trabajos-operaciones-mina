"""Tests de despacho.contratos, despacho.datos.base y la coherencia contrato <-> consultas SQL."""
import datetime as dt
import decimal
import unittest

from despacho import contratos, tiempo
from despacho.datos import base, consultas, solo_lectura


class TestContratos(unittest.TestCase):
    def test_todos_los_datasets_tienen_sql_y_columnas(self):
        for nombre, ds in contratos.DATASETS.items():
            self.assertTrue(ds.archivo_sql.endswith(".sql"), nombre)
            self.assertGreater(len(ds.columnas), 0, nombre)
            self.assertIn(ds.servidor, ("despacho", "planta"), nombre)
            for col in ds.columnas:
                self.assertIn(col.tipo_base, contratos.TIPOS, f"{nombre}.{col.nombre}")

    def test_nombres_de_columna_unicos_por_dataset(self):
        for nombre, ds in contratos.DATASETS.items():
            nombres = ds.nombres_columnas()
            self.assertEqual(len(nombres), len(set(nombres)), nombre)

    def test_validar_detecta_errores(self):
        filas = [
            {"Equipo": "CAEX-01", "TipoEquipo": "Truck", "Flota": None, "ActivoKPI": 1},
            {"Equipo": "CAEX-02", "TipoEquipo": "Truck", "Flota": "f", "ActivoKPI": "1"},
            {"Equipo": None, "TipoEquipo": "Truck", "Flota": "f", "ActivoKPI": 1, "Extra": 2},
            {"TipoEquipo": "Truck", "Flota": "f", "ActivoKPI": True},
        ]
        errores = contratos.validar_registros("equipos", filas)
        self.assertTrue(any("ActivoKPI" in e and "no es entero" in e for e in errores))
        self.assertTrue(any("None no permitido" in e for e in errores))
        self.assertTrue(any("no esperadas" in e for e in errores))
        self.assertTrue(any("faltan columnas" in e for e in errores))
        self.assertTrue(any("[3].ActivoKPI" in e for e in errores), "bool no es entero")

    def test_validar_fechas(self):
        fila = {"Fecha": "2025-03-04", "ToneladasPlan": 1.0, "LeyCuTPlan": None}
        self.assertEqual(contratos.validar_registros("plan_chancador", [fila]), [])
        fila["Fecha"] = "04-03-2025"
        self.assertTrue(contratos.validar_registros("plan_chancador", [fila]))

    def test_normalizar_filas(self):
        filas = contratos.normalizar_filas("plan_chancador", [
            {"Fecha": dt.datetime(2025, 3, 4, 5, 0), "ToneladasPlan": decimal.Decimal("96000.5"),
             "LeyCuTPlan": None, "Basura": 1}
        ])
        self.assertEqual(filas, [{"Fecha": "2025-03-04", "ToneladasPlan": 96000.5, "LeyCuTPlan": None}])
        gps = contratos.normalizar_filas("gps", [{
            "Equipo": " CAEX-01 ", "TipoEquipo": None, "FechaHora": dt.datetime(2025, 3, 4, 15, 3, 5, 123),
            "Latitud": 43344000, "Longitud": -126000000, "Velocidad": decimal.Decimal("12.5")}])
        self.assertEqual(gps[0]["Equipo"], "CAEX-01")
        self.assertEqual(gps[0]["FechaHora"], "2025-03-04T15:03:05")
        self.assertEqual(contratos.validar_registros("gps", gps), [])


class TestConsultasSQL(unittest.TestCase):
    """Cada archivo SQL incluido debe ser de solo lectura y respetar el contrato de su dataset."""

    def test_hay_consultas_de_referencia(self):
        self.assertGreaterEqual(len(consultas.consultas_disponibles()), 5)

    def test_solo_lectura_parametros_y_columnas(self):
        for nombre in consultas.consultas_disponibles():
            ds = contratos.DATASETS[nombre]
            sql = consultas.cargar_consulta(nombre)  # valida solo lectura
            self.assertEqual(tuple(consultas.parametros_de(sql)), ds.parametros, f"{nombre}: parámetros")
            for col in ds.columnas:
                self.assertRegex(sql, rf"\bAS\s+{col.nombre}\b|\n\s*{col.nombre}[,\s]", f"{nombre}.{col.nombre}")

    def test_parametros_estandar_cubren_las_consultas(self):
        p = base.parametros_consulta(tiempo.a_local(dt.datetime(2025, 3, 4, 15, 3)))
        for nombre in consultas.consultas_disponibles():
            sql_pos, valores = consultas.a_posicional(consultas.cargar_consulta(nombre), p)
            self.assertEqual(consultas.parametros_de(sql_pos), [], nombre)
            codigo = "".join(t for tipo, t in solo_lectura.segmentar(sql_pos) if tipo == "codigo")
            self.assertEqual(len(valores), codigo.count("?"), nombre)


class TestParametrosConsulta(unittest.TestCase):
    def setUp(self):
        tiempo.configurar_zona("Region/Inexistente", desfase_respaldo_h=-3)

    def tearDown(self):
        tiempo.configurar_zona("UTC")

    def test_parametros_turno_a(self):
        ahora = tiempo.a_local(dt.datetime(2025, 3, 4, 15, 3))
        p = base.parametros_consulta(ahora, historia_corta_dias=7, planes_dias=21, gps_minutos=15)
        self.assertEqual(p["FechaOpHoy"], dt.date(2025, 3, 4))
        self.assertEqual(p["FechaOpAyer"], dt.date(2025, 3, 3))
        self.assertEqual(p["InicioTurnoAnterior"], dt.datetime(2025, 3, 3, 20, 0))
        self.assertEqual(p["InicioTurnoActual"], dt.datetime(2025, 3, 4, 8, 0))
        self.assertEqual(p["AhoraLocal"], dt.datetime(2025, 3, 4, 15, 3))
        self.assertEqual(p["FechaInicioPlanes"], dt.date(2025, 2, 11))
        # hora local = UTC-3 -> 18:03 UTC; ventana GPS de 15 min
        self.assertEqual(p["DesdeUtc"], dt.datetime(2025, 3, 4, 17, 48))
        self.assertEqual(p["HastaUtc"], dt.datetime(2025, 3, 4, 19, 3))
        self.assertEqual(p["DesfaseMinutos"], -180)
        self.assertIsNone(p["DesdeUtc"].tzinfo)

    def test_parametros_turno_b_madrugada(self):
        ahora = tiempo.a_local(dt.datetime(2025, 3, 5, 3, 30))
        p = base.parametros_consulta(ahora)
        self.assertEqual(p["FechaOpHoy"], dt.date(2025, 3, 4))
        self.assertEqual(p["InicioTurnoActual"], dt.datetime(2025, 3, 4, 20, 0))
        self.assertEqual(p["InicioTurnoAnterior"], dt.datetime(2025, 3, 4, 8, 0))


class TestFuenteFija(unittest.TestCase):
    def test_devuelve_copias_y_registra_llamadas(self):
        f = base.FuenteFija({"equipos": [{"Equipo": "CAEX-01"}]})
        filas = f.obtener("equipos", {"x": 1})
        filas[0]["Equipo"] = "cambiado"
        self.assertEqual(f.obtener("equipos", {})[0]["Equipo"], "CAEX-01")
        self.assertEqual(f.obtener("no_existe", {}), [])
        self.assertEqual(len(f.llamadas), 3)
        self.assertEqual(f.estado()["tipo"], "fija")

    def test_cache_resumen(self):
        c = base.CacheDataset("gps")
        r = c.resumen()
        self.assertFalse(r["ok"])
        self.assertIsNone(r["actualizado"])


if __name__ == "__main__":
    unittest.main()
