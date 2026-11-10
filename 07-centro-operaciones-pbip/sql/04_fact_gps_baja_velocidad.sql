/*==============================================================================
  Fact_GPS (datos_sinteticos/fact_gps.csv)
  Lecturas GPS de los CAEX en baja velocidad (0 a 5 km/h). Grano: una fila por lectura.
  Alimenta el mapa «CAEX en baja velocidad», navegable por fecha y hora.

  - El instante viene en UTC y se convierte a la hora de la faena con AT TIME ZONE (respeta el
    horario de verano).
  - Día operacional = hora local menos 8 horas; turno A de 08:00 a 19:59 y B de 20:00 a 07:59;
    Orden_Hora_Dia: 1 a las 08:00 ... 24 a las 07:00.
  - Latitud y longitud se guardan en milisegundos de arco; el modelo las divide por 3.600.000.
  - Solo CAEX de Mina (sin «_M») y dentro del rectángulo de la mina (parámetros de abajo).
==============================================================================*/

DECLARE @ZonaLocal    SYSNAME = N'Central Standard Time';          -- zona horaria de la faena (ejemplo)
DECLARE @DiasHistoria INT     = 7;
DECLARE @VelMax       FLOAT   = 5.0;                               -- umbral de baja velocidad (km/h)
DECLARE @LatMin       FLOAT   = 76000000,  @LatMax FLOAT = 78500000;    -- rectángulo de la mina (ms de arco)
DECLARE @LonMin       FLOAT   = 92000000,  @LonMax FLOAT = 94500000;
DECLARE @DesdeUtc     DATETIME2 = DATEADD(DAY, -@DiasHistoria, SYSUTCDATETIME());
DECLARE @HastaUtc     DATETIME2 = DATEADD(HOUR, 1, SYSUTCDATETIME());

WITH Lectura AS (
    SELECT
        CAST(g.instante_utc AT TIME ZONE N'UTC' AT TIME ZONE @ZonaLocal AS DATETIME) AS FechaHora,
        e.nombre AS Equipo,
        LTRIM(RTRIM(LEFT(g.latitudes,   CHARINDEX(',', g.latitudes   + ',') - 1))) AS LatitudTexto,
        LTRIM(RTRIM(LEFT(g.longitudes,  CHARINDEX(',', g.longitudes  + ',') - 1))) AS LongitudTexto,
        LTRIM(RTRIM(LEFT(g.velocidades, CHARINDEX(',', g.velocidades + ',') - 1))) AS VelocidadTexto
    FROM despacho_demo.gps_turno AS g WITH (NOLOCK)
    INNER JOIN despacho_demo.equipos AS e WITH (NOLOCK) ON e.id = g.equipo_id
    WHERE g.instante_utc >= @DesdeUtc AND g.instante_utc <= @HastaUtc
      AND e.nombre LIKE N'CAEX-%' AND e.nombre NOT LIKE N'%[_]M'
      AND g.latitudes IS NOT NULL AND g.longitudes IS NOT NULL AND g.velocidades IS NOT NULL
),
Valor AS (
    SELECT FechaHora, Equipo,
           TRY_CONVERT(FLOAT, LatitudTexto)   AS Latitud,
           TRY_CONVERT(FLOAT, LongitudTexto)  AS Longitud,
           TRY_CONVERT(FLOAT, VelocidadTexto) AS Velocidad
    FROM Lectura
)
SELECT
    CAST(DATEADD(HOUR, -8, FechaHora) AS DATE) AS Fecha,
    CASE WHEN CAST(FechaHora AS TIME) >= '08:00:00' AND CAST(FechaHora AS TIME) < '20:00:00' THEN 'A' ELSE 'B' END AS Turno,
    ((DATEPART(HOUR, FechaHora) - 8 + 24) % 24) + 1 AS Orden_Hora_Dia,
    Equipo, FechaHora, Latitud, Longitud,
    Velocidad AS [Velocidad km/h]
FROM Valor
WHERE Velocidad BETWEEN 0.0 AND @VelMax
  AND Latitud  BETWEEN @LatMin AND @LatMax
  AND Longitud BETWEEN @LonMin AND @LonMax
OPTION (RECOMPILE);
