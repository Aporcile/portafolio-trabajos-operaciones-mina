/*==============================================================================
  Fact_ChancadoOrigen_Hora (datos_sinteticos/fact_chancado_origen_hora.csv)
  Toneladas alimentadas a chancado por hora del reloj y origen. Grano: día operacional + hora + turno + origen.

  Origen: las dos primeras letras y el número de la tronadura identifican la fase (F01, F02 ...);
  los acopios se agrupan en Stock_1 y Stock_2.
  Hora_Orden: 0 a las 08:00 ... 23 a las 07:00. HoraTurno: 1 a 12 dentro del turno; queda nulo cuando
  el turno del registro no coincide con la hora del reloj (el modelo lo deja fuera del gráfico).
==============================================================================*/

DECLARE @ZonaLocal   SYSNAME = N'Central Standard Time';     -- zona horaria de la faena (ejemplo)
DECLARE @DiasHistoria INT    = 90;
DECLARE @FechaInicio DATE    = DATEADD(DAY, -@DiasHistoria, CAST(GETDATE() AS DATE));

WITH Base AS (
    SELECT
        d.fecha_operacional AS Fecha,
        DATEPART(HOUR, d.registrado_utc AT TIME ZONE N'UTC' AT TIME ZONE @ZonaLocal) AS Hora,
        d.turno AS Turno,
        CASE WHEN d.tronadura LIKE N'STOCK[_]1%' THEN N'Stock_1'
             WHEN d.tronadura LIKE N'STOCK[_]2%' THEN N'Stock_2'
             ELSE LEFT(d.tronadura, 3) END AS Origen,
        d.tonelaje AS Tonelaje
    FROM despacho_demo.descargas_detalle AS d WITH (NOLOCK)
    WHERE d.fecha_operacional >= @FechaInicio
      AND d.eliminado_en IS NULL
      AND UPPER(despacho_demo.nombre_norm(d.destino)) = N'CHANCADO'
      AND CHARINDEX(N'_M', despacho_demo.nombre_norm(d.pala))   = 0
      AND CHARINDEX(N'_M', despacho_demo.nombre_norm(d.camion)) = 0
      AND despacho_demo.nombre_norm(d.camion) NOT LIKE N'CAEX-90%'
),
Agrupado AS (
    SELECT Fecha, Hora, (Hora + 16) % 24 AS Hora_Orden,
           CASE WHEN Turno = N'A' THEN Hora - 7
                WHEN Hora >= 20   THEN Hora - 19
                ELSE Hora + 5 END AS HoraTurno_Cruda,
           Turno, Origen, SUM(ISNULL(Tonelaje, 0)) AS Tonelaje
    FROM Base
    GROUP BY Fecha, Hora, Turno, Origen
)
SELECT Fecha, Hora, Hora_Orden,
       CASE WHEN HoraTurno_Cruda BETWEEN 1 AND 12 THEN HoraTurno_Cruda END AS HoraTurno,
       Turno, Origen, Tonelaje
FROM Agrupado
ORDER BY Fecha, Hora, Turno, Origen;
