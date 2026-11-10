/* Dataset equipos: catálogo con la bandera ActivoKPI.
   Sin parámetros. ActivoKPI = 0 para la flota auxiliar y para equipos de test. */
SELECT
    e.nombre      AS Equipo,
    e.tipo_equipo AS TipoEquipo,
    e.flota       AS Flota,
    CASE
        WHEN e.es_auxiliar = 1 THEN 0
        WHEN UPPER(e.nombre) LIKE '%TEST%' THEN 0
        WHEN UPPER(ISNULL(e.flota, '')) LIKE '%TEST%' THEN 0
        ELSE 1
    END AS ActivoKPI
FROM despacho_demo.dbo.equipos AS e WITH (NOLOCK)
WHERE e.tipo_equipo IN ('Truck', 'Shovel', 'Loader', 'Drill')
ORDER BY e.nombre;
