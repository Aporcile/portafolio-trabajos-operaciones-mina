/*==============================================================================
  Dim_Equipo (datos_sinteticos/dim_equipo.csv)
  Una fila por equipo con la bandera Activo_KPI, que concentra en un solo lugar la regla de
  exclusión de los KPI:
    - equipos de la flota de Muro (nombre con «_M»);
    - el CAEX auxiliar CAEX-90 y sus variantes;
    - equipos marcados como «Testeo» en el nombre o en la flota.
  En DAX, filtrar por Dim_Equipo[Activo_KPI] = 1 reemplaza esa regla repetida en cada consulta.
==============================================================================*/

SELECT DISTINCT
    h.equipo       AS Equipo,
    h.tipo_equipo  AS TipoEquipo,
    h.flota        AS Flota,
    CASE
        WHEN CHARINDEX(N'_M', despacho_demo.nombre_norm(h.equipo)) > 0 THEN 0
        WHEN despacho_demo.nombre_norm(h.equipo) LIKE N'CAEX-90%'     THEN 0
        WHEN CHARINDEX(N'TESTEO', UPPER(h.equipo + N' ' + ISNULL(h.flota, N''))) > 0 THEN 0
        ELSE 1
    END            AS Activo_KPI
FROM despacho_demo.horas_equipo AS h WITH (NOLOCK)
WHERE h.equipo IS NOT NULL
  AND h.tipo_equipo IN (N'Truck', N'Shovel', N'Drill', N'Loader');
