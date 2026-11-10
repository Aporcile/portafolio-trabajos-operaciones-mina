/* Dataset chancado_hora: tonelaje enviado a chancado por hora de reloj y por origen.
   Parámetros: @DesfaseMinutos (hora local menos UTC), @FechaOpAyer y @FechaOpHoy (días operativos).
   La hora de reloj sale de la marca UTC de la descarga convertida a hora local.
   HoraTurno: 1..12 dentro del turno (A: 08-19 h, B: 20-07 h); queda NULL si no cuadra con el turno. */
WITH Base AS (
    SELECT
        d.fecha    AS Fecha,
        DATEPART(HOUR, DATEADD(MINUTE, @DesfaseMinutos, d.fecha_hora_utc)) AS Hora,
        d.turno    AS Turno,
        d.origen   AS Origen,
        d.tonelaje AS Tonelaje
    FROM despacho_demo.dbo.descargas AS d WITH (NOLOCK)
    WHERE d.fecha BETWEEN @FechaOpAyer AND @FechaOpHoy
      AND d.eliminado_en IS NULL
      AND UPPER(d.destino) = 'CHANCADO PRIMARIO'
),
Agrupado AS (
    SELECT
        Fecha,
        Hora,
        CASE
            WHEN Turno = 'A' THEN Hora - 7
            WHEN Hora >= 20  THEN Hora - 19
            ELSE Hora + 5
        END AS HoraTurnoBruta,
        Turno,
        Origen,
        SUM(ISNULL(Tonelaje, 0)) AS Tonelaje
    FROM Base
    GROUP BY Fecha, Hora, Turno, Origen
)
SELECT
    Fecha,
    Hora,
    CASE WHEN HoraTurnoBruta BETWEEN 1 AND 12 THEN HoraTurnoBruta ELSE NULL END AS HoraTurno,
    Turno,
    Origen,
    Tonelaje
FROM Agrupado
ORDER BY Fecha, Hora, Turno, Origen;
