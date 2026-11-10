-- Tablas `planta_cierre`, `planta_cierre_ejec` y `planta_plan_puntos`: valores diarios de cierre de planta por punto.
-- Mismas columnas que datos_sinteticos/planta_cierre.csv: Punto, Fecha, Valor.
-- El sistema guarda varias versiones de cada punto y día: se toma la última modificación de la versión que corresponde
-- (real = versión 1; plan semanal = versión 7, puntos que terminan en .PLAN). Para cada tabla del modelo se cambia la lista de puntos.
SELECT Punto, Fecha, Valor
FROM (
    SELECT
        c.punto AS Punto,
        c.fecha AS Fecha,
        TRY_CONVERT(float, c.valor) AS Valor,
        ROW_NUMBER() OVER (PARTITION BY c.punto, c.fecha, c.version
                           ORDER BY c.modificado_en DESC, c.id DESC) AS rn
    FROM planta_demo.cierre_diario AS c
    WHERE c.punto IN ('PLANTA.CIERRE.OFICIAL', 'PLANTA.SAG.TON_DIA')
      AND c.fecha >= DATEADD(day, -45, CAST(GETDATE() AS date))
      AND ((c.punto LIKE '%.PLAN' AND c.version = 7)
        OR (c.punto NOT LIKE '%.PLAN' AND c.version = 1))
) AS x
WHERE rn = 1;
