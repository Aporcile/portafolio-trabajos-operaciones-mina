/* Dataset plan_caex: plan diario agregado de la flota CAEX (sin detalle por equipo).
   Parámetro: @FechaInicioPlanes (inicio de la ventana de planes).
   Las propiedades del plan están en filas (plan_items); aquí se pivotan a columnas. */
WITH Base AS (
    SELECT
        p.fecha     AS Fecha,
        i.propiedad AS Propiedad,
        i.valor     AS Valor
    FROM despacho_demo.dbo.planes AS p WITH (NOLOCK)
    INNER JOIN despacho_demo.dbo.plan_items AS i WITH (NOLOCK) ON i.plan_id = p.plan_id
    WHERE p.tipo_plan = 'caex'
      AND p.fecha >= @FechaInicioPlanes
)
SELECT
    Fecha,
    MAX(CASE WHEN Propiedad = 'horas_disponibles' THEN Valor END) AS HorasDisponiblesPlan,
    MAX(CASE WHEN Propiedad = 'horas_efectivas'   THEN Valor END) AS HorasEfectivasPlan,
    MAX(CASE WHEN Propiedad = 'horas_nominales'   THEN Valor END) AS HorasNominalesPlan,
    MAX(CASE WHEN Propiedad = 'horas_operativas'  THEN Valor END) AS HorasOperativasPlan,
    MAX(CASE WHEN Propiedad = 'toneladas'         THEN Valor END) AS ToneladasPlan
FROM Base
GROUP BY Fecha
ORDER BY Fecha;
