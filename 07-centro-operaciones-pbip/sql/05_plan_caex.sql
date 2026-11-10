/*==============================================================================
  Plan_CAEX (datos_sinteticos/plan_caex.csv)
  Plan diario de la flota CAEX tomado del plan semanal. Grano: un día.
  Las propiedades del plan vienen como filas (propiedad, valor) y se pivotean a columnas.
  Rendimiento plan en DAX = Toneladas Plan / Horas Efectivas Plan.

  Plan_Carguio y Plan_Perforadoras siguen el mismo patrón con el nombre del equipo en
  la propiedad (p. ej. «Horas Disponibles PALA-01 SEM»), y Plan_Semanal_Chancador usa
  «Total Toneladas Chancador SEM» y «Ley CUT Chancado SEM».
==============================================================================*/

DECLARE @DiasHistoria INT  = 90;
DECLARE @FechaInicio  DATE = DATEADD(DAY, -@DiasHistoria, CAST(GETDATE() AS DATE));

WITH Base AS (
    SELECT
        p.fecha_inicio AS Fecha,
        CASE
            WHEN i.propiedad LIKE N'Horas Disponibles CAEX%' THEN N'Disponibles'
            WHEN i.propiedad LIKE N'Horas Efectivas CAEX%'   THEN N'Efectivas'
            WHEN i.propiedad LIKE N'Horas Nominales CAEX%'   THEN N'Nominales'
            WHEN i.propiedad LIKE N'Horas Operativas CAEX%'  THEN N'Operativas'
            WHEN i.propiedad LIKE N'Total Toneladas CAEX%'   THEN N'Toneladas'
        END AS Metrica,
        i.valor AS Valor
    FROM despacho_demo.planes_items AS i WITH (NOLOCK)
    INNER JOIN despacho_demo.planes AS p WITH (NOLOCK) ON p.id = i.plan_id
    WHERE p.tipo = N'SEMANAL'
      AND p.fecha_inicio >= @FechaInicio
      AND i.propiedad LIKE N'%CAEX SEM'
)
SELECT
    Fecha,
    MAX(CASE WHEN Metrica = N'Disponibles' THEN Valor END) AS [Horas Disponibles Plan],
    MAX(CASE WHEN Metrica = N'Efectivas'   THEN Valor END) AS [Horas Efectivas Plan],
    MAX(CASE WHEN Metrica = N'Nominales'   THEN Valor END) AS [Horas Nominales Plan],
    MAX(CASE WHEN Metrica = N'Operativas'  THEN Valor END) AS [Horas Operativas Plan],
    MAX(CASE WHEN Metrica = N'Toneladas'   THEN Valor END) AS [Toneladas Plan]
FROM Base
WHERE Metrica IS NOT NULL
GROUP BY Fecha
ORDER BY Fecha;
