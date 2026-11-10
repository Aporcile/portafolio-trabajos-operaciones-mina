/* Dataset horas_equipo: horas por estado y producción por equipo-hora de la flota principal.
   Parámetros: @FechaOpAyer y @FechaOpHoy (días operativos).
   Grano: Fecha + Turno + Hora (0..11 dentro del turno) + Equipo.
   La producción se separa por tipo de equipo: los CAEX aportan Tonelaje, MaterialExtraido y
   MaterialRemanejo; palas y cargadores, Tonelaje cargado; las perforadoras, MetrosPerforados. */
WITH ProduccionCamion AS (
    SELECT
        d.fecha, d.turno, d.hora, d.camion_id AS equipo_id,
        SUM(d.tonelaje) AS tonelaje,
        SUM(CASE WHEN d.origen = 'STK' THEN 0 ELSE d.tonelaje END) AS extraido,
        SUM(CASE WHEN d.origen = 'STK' THEN d.tonelaje ELSE 0 END) AS remanejo
    FROM despacho_demo.dbo.descargas AS d WITH (NOLOCK)
    WHERE d.fecha BETWEEN @FechaOpAyer AND @FechaOpHoy
      AND d.eliminado_en IS NULL
    GROUP BY d.fecha, d.turno, d.hora, d.camion_id
),
ProduccionCarguio AS (
    SELECT
        d.fecha, d.turno, d.hora, d.carguio_id AS equipo_id,
        SUM(d.tonelaje) AS tonelaje
    FROM despacho_demo.dbo.descargas AS d WITH (NOLOCK)
    WHERE d.fecha BETWEEN @FechaOpAyer AND @FechaOpHoy
      AND d.eliminado_en IS NULL
    GROUP BY d.fecha, d.turno, d.hora, d.carguio_id
)
SELECT
    h.fecha                  AS Fecha,
    h.turno                  AS Turno,
    h.hora                   AS Hora,
    e.tipo_equipo            AS TipoEquipo,
    e.nombre                 AS Equipo,
    e.flota                  AS Flota,
    h.horas_nominales        AS HorasNominales,
    h.horas_operativas       AS HorasOperativas,
    h.horas_operativas - h.horas_espera
        - CASE WHEN e.tipo_equipo = 'Truck' THEN h.horas_cola ELSE 0 END AS HorasEfectivas,
    h.horas_espera           AS HorasPOEspera,
    h.horas_cola             AS HorasPOCola,
    h.horas_dnp              AS HorasDNP,
    h.horas_dp               AS HorasDP,
    h.horas_reserva          AS HorasReserva,
    h.horas_operativas + h.horas_dnp + h.horas_dp + h.horas_reserva AS HorasDisponibles,
    h.horas_mp               AS HorasMP,
    h.horas_mnp              AS HorasMNP,
    CASE e.tipo_equipo
        WHEN 'Truck'  THEN COALESCE(pc.tonelaje, 0)
        WHEN 'Shovel' THEN COALESCE(pl.tonelaje, 0)
        WHEN 'Loader' THEN COALESCE(pl.tonelaje, 0)
        ELSE 0
    END                      AS Tonelaje,
    CASE WHEN e.tipo_equipo = 'Truck' THEN COALESCE(pc.extraido, 0) ELSE 0 END AS MaterialExtraido,
    CASE WHEN e.tipo_equipo = 'Truck' THEN COALESCE(pc.remanejo, 0) ELSE 0 END AS MaterialRemanejo,
    CASE WHEN e.tipo_equipo = 'Truck' THEN COALESCE(pc.extraido, 0) + COALESCE(pc.remanejo, 0) ELSE 0 END AS MovimientoTotal,
    CASE WHEN e.tipo_equipo = 'Drill' THEN h.metros_perforados ELSE 0 END AS MetrosPerforados
FROM despacho_demo.dbo.horas_equipo AS h WITH (NOLOCK)
INNER JOIN despacho_demo.dbo.equipos AS e WITH (NOLOCK) ON e.equipo_id = h.equipo_id
LEFT JOIN ProduccionCamion  AS pc ON pc.fecha = h.fecha AND pc.turno = h.turno AND pc.hora = h.hora AND pc.equipo_id = h.equipo_id
LEFT JOIN ProduccionCarguio AS pl ON pl.fecha = h.fecha AND pl.turno = h.turno AND pl.hora = h.hora AND pl.equipo_id = h.equipo_id
WHERE h.fecha BETWEEN @FechaOpAyer AND @FechaOpHoy
  AND e.es_auxiliar = 0
ORDER BY h.fecha, h.turno, h.hora, e.nombre;
