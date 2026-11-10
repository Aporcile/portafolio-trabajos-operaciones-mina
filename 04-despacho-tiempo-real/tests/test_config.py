"""Tests de despacho.config: parser de .env, prioridad de variables, TOML y resumen sin secretos."""
import os
import tempfile
import unittest
from pathlib import Path

from despacho import config


class TestLeerEnv(unittest.TestCase):
    def test_parser_basico(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "archivo.env"
            ruta.write_text(
                "# comentario\nDATA_SOURCE=demo\nDESPACHO_PASSWORD='xxxx con espacios y #'\n"
                "WEB_PORT=9000 # puerto\nVACIA=\n\nSIN_IGUAL\n",
                encoding="utf-8",
            )
            valores = config.leer_env(ruta)
        self.assertEqual(valores["DATA_SOURCE"], "demo")
        self.assertEqual(valores["DESPACHO_PASSWORD"], "xxxx con espacios y #")
        self.assertEqual(valores["WEB_PORT"], "9000")
        self.assertEqual(valores["VACIA"], "")
        self.assertNotIn("SIN_IGUAL", valores)

    def test_archivo_inexistente(self):
        self.assertEqual(config.leer_env(Path("no_existe.env")), {})


class TestConfig(unittest.TestCase):
    def _raiz_temporal(self, env_texto: str = "", toml_texto: str = "") -> tempfile.TemporaryDirectory:
        d = tempfile.TemporaryDirectory()
        raiz = Path(d.name)
        (raiz / "config").mkdir()
        if env_texto:
            (raiz / ".env").write_text(env_texto, encoding="utf-8")
        (raiz / "config" / "dashboard.toml").write_text(toml_texto or "[refresco]\nsnapshot_s = 10\n", encoding="utf-8")
        return d

    def test_valores_por_defecto_son_genericos(self):
        with self._raiz_temporal("DATA_SOURCE=sql\nWEB_PORT=8800\n") as d:
            cfg = config.cargar_config(Path(d))
            self.assertEqual(cfg.modo_datos, "sql")
            self.assertEqual(cfg.env_int("WEB_PORT"), 8800)
            self.assertEqual(cfg.env("DESPACHO_SERVER"), "servidor-demo")
            self.assertEqual(cfg.env("DESPACHO_DATABASE"), "despacho_demo")
            self.assertEqual(cfg.env("PLANTA_DATABASE"), "planta_demo")
            self.assertEqual(cfg.env("DESPACHO_USER"), "")
            self.assertEqual(cfg.env("DESPACHO_PASSWORD"), "")
            self.assertEqual(config.obtener(cfg.dashboard, "refresco.snapshot_s"), 10)
            self.assertIsNone(config.obtener(cfg.dashboard, "no.existe"))

    def test_conexion_segura_por_defecto(self):
        with self._raiz_temporal() as d:
            cfg = config.cargar_config(Path(d))
            self.assertTrue(cfg.env_bool("SQL_ENCRYPT"))
            self.assertFalse(cfg.env_bool("SQL_TRUST_SERVER_CERTIFICATE"))
            self.assertEqual(cfg.env("WEB_HOST"), "127.0.0.1")

    def test_variable_de_proceso_tiene_prioridad(self):
        with self._raiz_temporal("DATA_SOURCE=sql\n") as d:
            os.environ["DATA_SOURCE"] = "demo"
            try:
                cfg = config.cargar_config(Path(d))
                self.assertEqual(cfg.modo_datos, "demo")
            finally:
                del os.environ["DATA_SOURCE"]

    def test_modo_invalido_cae_a_auto(self):
        with self._raiz_temporal("DATA_SOURCE=cualquiera\n") as d:
            self.assertEqual(config.cargar_config(Path(d)).modo_datos, "auto")

    def test_credenciales_completas(self):
        with self._raiz_temporal("DESPACHO_USER=usuario_demo\nDESPACHO_PASSWORD=xxxx\n") as d:
            cfg = config.cargar_config(Path(d))
            self.assertTrue(cfg.credenciales_completas("DESPACHO"))
            self.assertFalse(cfg.credenciales_completas("PLANTA"))
        with self._raiz_temporal("DESPACHO_AUTH=windows\n") as d:
            self.assertTrue(config.cargar_config(Path(d)).credenciales_completas("DESPACHO"))

    def test_resumen_enmascara_secretos(self):
        with self._raiz_temporal("DESPACHO_PASSWORD=xxxx-oculto\nIA_API_KEY=xxxx-clave\nWEB_TOKEN=xxxx-token\n") as d:
            resumen = config.cargar_config(Path(d)).resumen_sin_secretos()
        self.assertEqual(resumen["DESPACHO_PASSWORD"], "***")
        self.assertEqual(resumen["IA_API_KEY"], "***")
        self.assertEqual(resumen["WEB_TOKEN"], "***")
        self.assertEqual(resumen["PLANTA_PASSWORD"], "")
        self.assertNotIn("xxxx", str(resumen))

    def test_escenario_inexistente_cae_a_normal(self):
        with self._raiz_temporal() as d:
            esc = Path(d) / "config" / "escenarios"
            esc.mkdir()
            (esc / "turno_normal.toml").write_text("[general]\nritmo_factor = 1.0\n", encoding="utf-8")
            cfg = config.cargar_config(Path(d), env_extra={"DEMO_ESCENARIO": "no_existe"})
            datos = cfg.escenario()
            self.assertEqual(datos["general"]["ritmo_factor"], 1.0)
            self.assertEqual(cfg.escenarios_disponibles(), ["turno_normal"])


class TestConfigProyecto(unittest.TestCase):
    """Los TOML incluidos en config/ deben cargar y ser coherentes entre sí."""

    def test_los_toml_del_proyecto_cargan(self):
        cfg = config.cargar_config()
        self.assertIn("refresco", cfg.dashboard)
        self.assertIn("turno_A", cfg.plan_horario)
        self.assertAlmostEqual(sum(cfg.plan_horario["turno_A"]["pesos"]), 1.0, places=3)
        self.assertAlmostEqual(sum(cfg.plan_horario["turno_B"]["pesos"]), 1.0, places=3)
        self.assertEqual(len(cfg.plan_horario["turno_A"]["pesos"]), 12)
        self.assertIn("calibracion", cfg.mapa)
        mezcla = cfg.dashboard["chancado"]["mezcla_plan"]
        self.assertAlmostEqual(sum(mezcla.values()), 1.0, places=3)

    def test_planes_por_defecto_en_rangos_normales(self):
        planes = config.cargar_config().dashboard["planes_por_defecto"]
        self.assertTrue(150 <= planes["movimiento_mina_kt_dia"] <= 260)
        self.assertTrue(82 <= planes["df_caex_pct"] <= 94)
        self.assertTrue(70 <= planes["uebd_caex_pct"] <= 85)
        self.assertTrue(3200 <= planes["chancado_kt_dia"] * 1000 / 24 <= 4800)

    def test_mapa_es_coherente(self):
        mapa = config.cargar_config().mapa
        frentes = {f["nombre"] for f in mapa["frentes"]}
        destinos = {d["nombre"] for d in mapa["destinos"]}
        for ruta in mapa["rutas"]:
            self.assertIn(ruta["origen"], frentes)
            self.assertIn(ruta["destino"], destinos)
            self.assertTrue(all(0 <= x <= 1 and 0 <= y <= 1 for x, y in ruta["puntos"]))
        cal = mapa["calibracion"]
        self.assertLess(cal["lat_min"], cal["lat_max"])
        self.assertLess(cal["lon_min"], cal["lon_max"])

    def test_reglas_de_alerta(self):
        reglas = config.cargar_config().alertas["regla"]
        ids = [r["id"] for r in reglas]
        self.assertEqual(len(ids), len(set(ids)))
        for r in reglas:
            self.assertIn(r["severidad"], ("critica", "alta", "media", "informativa"))
            self.assertIsInstance(r["umbral"], (int, float))


if __name__ == "__main__":
    unittest.main()
