-- Tabla `Horas Palas Turno`: tiempos de la flota de carguío por turno (horas) de los últimos 45 días.
-- Mismas columnas que datos_sinteticos/horas_palas_turno.csv.
--   Nominal  = horas del turno; MP / MNP = mantención programada / no programada;
--   Efectivo = horas con equipo cargando.
SELECT
    h.fecha_mina  AS [time],
    h.turno       AS [Shift],
    h.equipo      AS equipment,
    SUM(h.nominal)     AS Nominal,
    SUM(h.mant_prog)   AS MP,
    SUM(h.mant_noprog) AS MNP,
    SUM(h.efectivo)    AS Efectivo
FROM equipos_demo.horas_equipo AS h
JOIN equipos_demo.equipos      AS e ON e.equipo = h.equipo
WHERE h.fecha_mina >= DATEADD(day, -45, CAST(GETDATE() AS date))
  AND e.tipo IN ('Pala', 'Cargador')
GROUP BY h.fecha_mina, h.turno, h.equipo;
