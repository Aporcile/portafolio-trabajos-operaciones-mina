"""Tests de la barrera de solo lectura SQL y del enlace de parámetros."""
import unittest

from despacho.datos import consultas
from despacho.datos.solo_lectura import ConsultaNoPermitida, es_solo_lectura, limpiar, validar_solo_lectura


class TestSoloLectura(unittest.TestCase):
    def test_acepta_select_y_cte(self):
        self.assertTrue(es_solo_lectura("SELECT 1"))
        self.assertTrue(es_solo_lectura("select a, b from t with (nolock) where a > @X;"))
        self.assertTrue(es_solo_lectura("WITH c AS (SELECT 1 AS x) SELECT x FROM c ORDER BY x"))
        self.assertTrue(es_solo_lectura("SELECT * FROM t OPTION (RECOMPILE)"))

    def test_rechaza_escritura_y_ddl(self):
        for sql in (
            "INSERT INTO t VALUES (1)",
            "UPDATE t SET a = 1",
            "DELETE FROM t",
            "MERGE t USING s ON 1=1 WHEN MATCHED THEN DELETE;",
            "DROP TABLE t",
            "ALTER TABLE t ADD c INT",
            "CREATE TABLE t (a INT)",
            "TRUNCATE TABLE t",
            "EXEC procedimiento",
            "SELECT * INTO copia FROM t",
            "WITH c AS (SELECT 1 AS x) DELETE FROM t",
            "SELECT 1 FROM OPENROWSET('a', 'b', 'c')",
            "SELECT xp_cmdshell('x')",
            "DECLARE @a INT = 1; SELECT @a",
        ):
            with self.subTest(sql=sql):
                self.assertFalse(es_solo_lectura(sql))

    def test_rechaza_sentencias_apiladas(self):
        with self.assertRaises(ConsultaNoPermitida):
            validar_solo_lectura("SELECT 1; SELECT 2")
        with self.assertRaises(ConsultaNoPermitida):
            validar_solo_lectura("SELECT 1; -- comentario\nDROP TABLE t")

    def test_rechaza_vacia_o_con_inicio_invalido(self):
        for sql in ("", "   ", "-- solo comentario", "(SELECT 1)", "VALUES (1)"):
            with self.subTest(sql=sql):
                self.assertFalse(es_solo_lectura(sql))

    def test_ignora_comentarios_cadenas_e_identificadores(self):
        self.assertTrue(es_solo_lectura("SELECT 'DROP TABLE t; --' AS texto"))
        self.assertTrue(es_solo_lectura("SELECT 1 /* DELETE FROM t; */ AS x"))
        self.assertTrue(es_solo_lectura("SELECT 1 -- INSERT INTO t\n"))
        self.assertTrue(es_solo_lectura("SELECT [drop], \"update\" FROM t"))
        self.assertTrue(es_solo_lectura("SELECT 'it''s; DROP' AS x"))
        self.assertTrue(es_solo_lectura("SELECT 1 /* a /* anidado */ b */ AS x"))

    def test_comentario_no_puede_esconder_una_sentencia(self):
        self.assertFalse(es_solo_lectura("SELECT 1 /* x */; DROP TABLE t"))
        self.assertFalse(es_solo_lectura("SELECT 'abierta"))
        self.assertFalse(es_solo_lectura("SELECT 1 /* sin cerrar"))

    def test_palabras_parecidas_no_se_confunden(self):
        # 'updated_at', 'OFFSET' o 'settings' contienen verbos prohibidos como subcadena, no como palabra
        self.assertTrue(es_solo_lectura("SELECT updated_at, settings, inserted_by FROM t ORDER BY a OFFSET 0 ROWS"))

    def test_limpiar_neutraliza_texto(self):
        limpio = limpiar("SELECT 'a;b' /* c */ -- d\nFROM [t]")
        self.assertNotIn(";", limpio)
        self.assertNotIn("a;b", limpio)


class TestParametros(unittest.TestCase):
    def test_parametros_de_en_orden_y_sin_repetir(self):
        sql = "SELECT @B, @A FROM t WHERE x = @B AND y = @@ROWCOUNT AND z = '@Falso' -- @Otro"
        self.assertEqual(consultas.parametros_de(sql), ["B", "A"])

    def test_a_posicional_repite_valores_en_orden(self):
        sql = "SELECT * FROM t WHERE a = @A AND b = @B AND c = @A AND d = '@B'"
        texto, valores = consultas.a_posicional(sql, {"A": 1, "B": 2})
        self.assertEqual(texto.count("?"), 3)
        self.assertEqual(valores, [1, 2, 1])
        self.assertIn("'@B'", texto)

    def test_a_posicional_exige_todos_los_parametros(self):
        with self.assertRaises(KeyError):
            consultas.a_posicional("SELECT @Falta", {})


if __name__ == "__main__":
    unittest.main()
