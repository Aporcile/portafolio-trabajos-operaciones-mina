/* Dataset gps: última posición de cada equipo dentro de una ventana corta.
   Parámetros: @DesdeUtc y @HastaUtc (ventana en UTC) y @DesfaseMinutos (hora local menos UTC,
   lo calcula el programador). Latitud y longitud quedan en milisegundos de arco. */
WITH Ultimas AS (
    SELECT
        g.equipo_id,
        g.fecha_hora_utc,
        g.latitud_mas,
        g.longitud_mas,
        g.velocidad_kmh,
        ROW_NUMBER() OVER (PARTITION BY g.equipo_id ORDER BY g.fecha_hora_utc DESC) AS orden
    FROM despacho_demo.dbo.gps_lecturas AS g WITH (NOLOCK)
    WHERE g.fecha_hora_utc >= @DesdeUtc
      AND g.fecha_hora_utc <= @HastaUtc
      AND g.latitud_mas   IS NOT NULL
      AND g.longitud_mas  IS NOT NULL
      AND g.velocidad_kmh IS NOT NULL
)
SELECT
    e.nombre                                          AS Equipo,
    e.tipo_equipo                                     AS TipoEquipo,
    DATEADD(MINUTE, @DesfaseMinutos, u.fecha_hora_utc) AS FechaHora,
    u.latitud_mas                                     AS Latitud,
    u.longitud_mas                                    AS Longitud,
    u.velocidad_kmh                                   AS Velocidad
FROM Ultimas AS u
INNER JOIN despacho_demo.dbo.equipos AS e WITH (NOLOCK) ON e.equipo_id = u.equipo_id
WHERE u.orden = 1
ORDER BY e.nombre;
