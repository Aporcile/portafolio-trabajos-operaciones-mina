-- Tabla `Produccion Palas Hora`: cargas por hora y pala de los últimos 45 días.
-- Mismas columnas que datos_sinteticos/produccion_palas_hora.csv.
SELECT
    c.fecha_mina AS [time],
    c.turno      AS [shift],
    c.hora       AS [hour],
    c.pala       AS shovel,
    c.destino    AS dump,
    c.toneladas  AS material_tonnage
FROM despacho_demo.cargas AS c
WHERE c.fecha_mina >= DATEADD(day, -45, CAST(GETDATE() AS date))
  AND c.eliminado_en IS NULL;
