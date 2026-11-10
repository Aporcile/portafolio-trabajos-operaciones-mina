-- Tabla `Produccion Mina`: descargas por hora, desde el día 1 del mes del primer día de la ventana de 45 días
-- (así el acumulado del mes tiene el mes completo). Mismas columnas que datos_sinteticos/produccion_mina.csv.
-- El modelo calcula HoraOp, BlastPrefix, BlastClass y DumpPrefix en Power Query a partir de estas columnas.
SELECT
    d.fecha_mina AS [time],
    d.turno      AS [shift],
    d.hora       AS [hour],
    d.camion     AS truck,
    d.tronadura  AS blast,
    d.destino    AS dump,
    d.toneladas  AS material_tonnage
FROM despacho_demo.descargas AS d
WHERE d.fecha_mina >= DATEADD(month, DATEDIFF(month, 0, DATEADD(day, -44, CAST(GETDATE() AS date))), 0)
  AND d.eliminado_en IS NULL;
