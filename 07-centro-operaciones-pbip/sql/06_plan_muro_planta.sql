/*==============================================================================
  Plan_Muro (datos_sinteticos/plan_muro.csv)
  Plan mensual de la flota de Muro (CAEX y pala) leído de la base de planificación de planta
  (esquema planta_demo). Grano: un valor por punto (tag) y día.

  Los puntos se leen por nombre. Si un punto se cargó más de una vez para el mismo día, se conserva
  la última carga (ROW_NUMBER por punto y día, orden descendente por id).
  DF y UEBD vienen como fracción (0,856 = 85,6 %); el rendimiento va en t por hora efectiva.
==============================================================================*/

DECLARE @DiasHistoria INT  = 90;
DECLARE @Desde        DATE = DATEADD(DAY, -@DiasHistoria, CAST(GETDATE() AS DATE));

WITH V AS (
    SELECT
        pt.nombre                         AS Tag,
        CAST(v.instante AS DATE)          AS Fecha,
        v.valor                           AS Valor,
        ROW_NUMBER() OVER (PARTITION BY pt.id, CAST(v.instante AS DATE) ORDER BY v.id DESC) AS rn
    FROM planta_demo.puntos_plan AS pt
    INNER JOIN planta_demo.valores_plan AS v
        ON v.punto_id = pt.id AND v.version = 1 AND v.instante >= @Desde
    WHERE pt.nombre IN (
        N'PLAN_MURO_CAEX_DISP', N'PLAN_MURO_CAEX_UEBD', N'PLAN_MURO_CAEX_REND',
        N'PLAN_MURO_PALA_DISP', N'PLAN_MURO_PALA_UEBD', N'PLAN_MURO_PALA_REND'
    )
)
SELECT Tag, Fecha, Valor
FROM V
WHERE rn = 1
ORDER BY Tag, Fecha;
