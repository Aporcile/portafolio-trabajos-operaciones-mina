"""Tests de despacho.tiempo: turnos, día operacional, zona horaria y reloj simulado."""
import datetime as dt
import unittest

from despacho import tiempo


def _loc(texto: str) -> dt.datetime:
    return tiempo.a_local(dt.datetime.fromisoformat(texto))


class _ConZonaUTC(unittest.TestCase):
    """Deja la zona en UTC antes y después de cada test (la zona es estado de módulo)."""

    def setUp(self):
        tiempo.configurar_zona("UTC")

    def tearDown(self):
        tiempo.configurar_zona("UTC")


class TestTurnos(_ConZonaUTC):
    def test_turno_a_en_la_tarde(self):
        t = tiempo.turno_de(_loc("2025-03-04T15:03:00"))
        self.assertEqual(t.turno, "A")
        self.assertEqual(t.fecha_operacional, dt.date(2025, 3, 4))
        self.assertEqual(t.hora_turno, 8)
        self.assertEqual(t.orden_hora_dia, 8)
        self.assertEqual(t.inicio.hour, 8)
        self.assertEqual(t.fin.hour, 20)

    def test_turno_b_empieza_a_las_20(self):
        t = tiempo.turno_de(_loc("2025-03-04T20:00:00"))
        self.assertEqual((t.turno, t.hora_turno, t.orden_hora_dia), ("B", 1, 13))
        self.assertEqual(t.fecha_operacional, dt.date(2025, 3, 4))

    def test_madrugada_pertenece_al_dia_operacional_anterior(self):
        t = tiempo.turno_de(_loc("2025-03-05T03:30:00"))
        self.assertEqual(t.turno, "B")
        self.assertEqual(t.fecha_operacional, dt.date(2025, 3, 4))
        self.assertEqual(t.hora_turno, 8)
        self.assertEqual(t.orden_hora_dia, 20)
        self.assertEqual(t.fin, _loc("2025-03-05T08:00:00"))

    def test_limites_exactos(self):
        self.assertEqual(tiempo.turno_de(_loc("2025-03-05T07:59:59")).turno, "B")
        self.assertEqual(tiempo.turno_de(_loc("2025-03-05T08:00:00")).turno, "A")
        self.assertEqual(tiempo.turno_de(_loc("2025-03-05T19:59:59")).turno, "A")

    def test_turno_anterior_y_siguiente(self):
        a = tiempo.turno_de(_loc("2025-03-04T15:03:00"))
        ant = tiempo.turno_anterior(a)
        self.assertEqual((ant.turno, ant.fecha_operacional), ("B", dt.date(2025, 3, 3)))
        sig = tiempo.turno_siguiente(a)
        self.assertEqual((sig.turno, sig.fecha_operacional), ("B", dt.date(2025, 3, 4)))
        self.assertEqual(tiempo.turno_anterior(sig).inicio, a.inicio)

    def test_horas_transcurridas_y_restantes(self):
        ahora = _loc("2025-03-04T15:03:00")
        t = tiempo.turno_de(ahora)
        self.assertAlmostEqual(t.horas_transcurridas(ahora), 7.05, places=2)
        self.assertAlmostEqual(t.horas_restantes(ahora), 4.95, places=2)

    def test_fraccion_dia_operacional(self):
        self.assertAlmostEqual(tiempo.fraccion_dia_operacional(_loc("2025-03-04T15:03:00")), 7.05 / 24, places=3)
        self.assertAlmostEqual(tiempo.fraccion_dia_operacional(_loc("2025-03-05T07:59:00")), 23.983 / 24, places=3)

    def test_hora_reloj_y_orden(self):
        self.assertEqual(tiempo.hora_reloj_de_hora_turno("A", 1), 8)
        self.assertEqual(tiempo.hora_reloj_de_hora_turno("B", 5), 0)
        self.assertEqual(tiempo.hora_reloj_de_hora_turno("B", 12), 7)
        self.assertEqual(tiempo.orden_hora_dia_de("B", 3), 15)

    def test_cada_hora_del_dia_tiene_un_orden_unico(self):
        base = dt.datetime(2025, 3, 4, 8, 0)
        ordenes = [tiempo.turno_de(tiempo.a_local(base + dt.timedelta(hours=h))).orden_hora_dia for h in range(24)]
        self.assertEqual(ordenes, list(range(1, 25)))


class TestZonaHoraria(_ConZonaUTC):
    def test_utc_por_defecto(self):
        self.assertEqual(tiempo.origen_zona_horaria(), "UTC")
        self.assertEqual(_loc("2025-03-04T12:00:00").utcoffset(), dt.timedelta(0))

    def test_respaldo_de_desfase_fijo_si_la_zona_no_existe(self):
        tiempo.configurar_zona("Region/Inexistente", desfase_respaldo_h=-4)
        self.assertIn("desfase fijo", tiempo.origen_zona_horaria())
        self.assertEqual(_loc("2025-03-04T12:00:00").utcoffset(), dt.timedelta(hours=-4))
        self.assertEqual(tiempo.desfase_minutos(_loc("2025-03-04T12:00:00")), -240)

    def test_conversion_desde_utc(self):
        tiempo.configurar_zona("Region/Inexistente", desfase_respaldo_h=-3)
        x = tiempo.a_local(dt.datetime(2025, 3, 4, 18, 3), origen_utc=True)
        self.assertEqual((x.hour, x.minute), (15, 3))

    def test_iso_sin_microsegundos(self):
        x = _loc("2025-03-04T15:03:10.123456")
        self.assertEqual(tiempo.iso(x)[:19], "2025-03-04T15:03:10")
        self.assertIsNone(tiempo.iso(None))

    def test_zona_con_horario_de_verano(self):
        try:
            import zoneinfo
            zoneinfo.ZoneInfo("America/New_York")
        except Exception:
            self.skipTest("no hay base de zonas horarias en este sistema")
        tiempo.configurar_zona("America/New_York")
        invierno = tiempo.desfase_minutos(dt.datetime(2025, 1, 15, 12, 0))
        verano = tiempo.desfase_minutos(dt.datetime(2025, 7, 15, 12, 0))
        self.assertEqual((invierno, verano), (-300, -240))
        # los turnos siguen empezando a las 08:00 de pared aunque cambie el desfase
        self.assertEqual(tiempo.turno_de(tiempo.a_local(dt.datetime(2025, 7, 15, 9, 0))).inicio.hour, 8)


class TestRelojSimulado(_ConZonaUTC):
    def test_congelado_y_avance(self):
        r = tiempo.RelojSimulado(dt.datetime(2025, 3, 4, 15, 3), factor=0)
        self.assertEqual(tiempo.iso(r.ahora())[:19], "2025-03-04T15:03:00")
        r.avanzar(3600)
        self.assertEqual(r.ahora().hour, 16)
        self.assertTrue(r.simulado)
        self.assertFalse(tiempo.Reloj().simulado)

    def test_factor_acelera_el_tiempo(self):
        r = tiempo.RelojSimulado(dt.datetime(2025, 3, 4, 15, 3), factor=3600)
        self.assertGreaterEqual((r.ahora() - r.inicio).total_seconds(), 0)


class TestTextos(unittest.TestCase):
    def test_fecha_texto(self):
        self.assertEqual(tiempo.fecha_texto(dt.date(2025, 3, 4)), "martes, 4 de marzo")

    def test_hora_12h(self):
        self.assertEqual(tiempo.hora_texto_12h(dt.datetime(2025, 3, 4, 15, 3)), "03:03 p.m.")
        self.assertEqual(tiempo.hora_texto_12h(dt.datetime(2025, 3, 4, 0, 7)), "12:07 a.m.")

    def test_duracion(self):
        self.assertEqual(tiempo.duracion_texto(325), "5 h 25")
        self.assertEqual(tiempo.duracion_texto(48), "48 min")
        self.assertEqual(tiempo.duracion_texto(60), "1 h 00")


if __name__ == "__main__":
    unittest.main()
