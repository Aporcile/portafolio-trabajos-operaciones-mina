/* Dataset plan_indicadores (base planta_demo): plan mensual de indicadores por tag y fecha.
   Parámetro: @FechaInicioPlanes. Los tags de plan empiezan con PLAN_ (p. ej. PLAN_DF_AUX). */
SELECT
    p.tag   AS Tag,
    v.fecha AS Fecha,
    v.valor AS Valor
FROM planta_demo.dbo.valores AS v WITH (NOLOCK)
INNER JOIN planta_demo.dbo.puntos AS p WITH (NOLOCK) ON p.punto_id = v.punto_id
WHERE v.fecha >= @FechaInicioPlanes
  AND p.tag LIKE 'PLAN[_]%'
ORDER BY p.tag, v.fecha;
