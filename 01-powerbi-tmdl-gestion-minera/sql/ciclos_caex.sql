-- Velocidades medias de CAEX por turno (rango habitual 15 a 30 km/h; cargado más lento que vacío).
-- Mismas columnas que datos_sinteticos/ciclos_caex.csv (archivo de ejemplo: el modelo reducido no lo usa).
SELECT
    c.fecha_mina AS fecha,
    c.turno      AS turno,
    c.camion     AS equipo,
    c.ciclos     AS ciclos,
    c.velocidad_cargado_kmh,
    c.velocidad_vacio_kmh
FROM despacho_demo.ciclos AS c
JOIN equipos_demo.equipos AS e ON e.equipo = c.camion
WHERE e.tipo = 'CAEX'
  AND c.fecha_mina >= DATEADD(day, -45, CAST(GETDATE() AS date))
  AND c.velocidad_cargado_kmh BETWEEN 15 AND 30;
