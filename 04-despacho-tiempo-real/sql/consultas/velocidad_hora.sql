/* Dataset velocidad_hora: lecturas GPS de CAEX agregadas por día operacional, turno, hora y equipo.
   Parámetros: @DesfaseMinutos (hora local menos UTC), @DesdeUtcHistoria y @HastaUtc (ventana UTC).
   Se devuelven sumas y conteos (no promedios) para que el motor combine horas y turnos sin sesgo:
   velocidad media en movimiento = SumaVelocidadMovimiento / LecturasMovimiento. */
WITH Lecturas AS (
    SELECT
        DATEADD(MINUTE, @DesfaseMinutos, g.fecha_hora_utc) AS HoraLocal,
        e.nombre                                          AS Equipo,
        CASE WHEN e.es_auxiliar = 1 THEN 'Auxiliar' ELSE 'Principal' END AS Flota,
        g.velocidad_kmh                                   AS Velocidad
    FROM despacho_demo.dbo.gps_lecturas AS g WITH (NOLOCK)
    INNER JOIN despacho_demo.dbo.equipos AS e WITH (NOLOCK) ON e.equipo_id = g.equipo_id
    WHERE g.fecha_hora_utc >= @DesdeUtcHistoria
      AND g.fecha_hora_utc <= @HastaUtc
      AND e.tipo_equipo = 'Truck'
      AND g.velocidad_kmh BETWEEN 0 AND 100
),
Base AS (
    SELECT
        /* día operacional: las horas 00:00-07:59 pertenecen al día anterior */
        CAST(DATEADD(HOUR, -8, HoraLocal) AS DATE) AS Fecha,
        CASE WHEN DATEPART(HOUR, HoraLocal) >= 8 AND DATEPART(HOUR, HoraLocal) < 20 THEN 'A' ELSE 'B' END AS Turno,
        /* 1 = 08:00 ... 12 = 19:00 (turno A), 13 = 20:00 ... 24 = 07:00 (turno B) */
        ((DATEPART(HOUR, HoraLocal) - 8 + 24) % 24) + 1 AS OrdenHoraDia,
        Equipo,
        Flota,
        Velocidad
    FROM Lecturas
)
SELECT
    Fecha,
    Turno,
    OrdenHoraDia,
    Equipo,
    Flota,
    COUNT(*)                                               AS Lecturas,
    SUM(Velocidad)                                         AS SumaVelocidad,
    SUM(CASE WHEN Velocidad > 0 THEN 1 ELSE 0 END)         AS LecturasMovimiento,
    SUM(CASE WHEN Velocidad > 0 THEN Velocidad ELSE 0 END) AS SumaVelocidadMovimiento
FROM Base
GROUP BY Fecha, Turno, OrdenHoraDia, Equipo, Flota
ORDER BY Fecha, OrdenHoraDia, Equipo;
