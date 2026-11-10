/*==============================================================================
  Fact_HorasEquipo (datos_sinteticos/fact_horas_equipo.csv)
  Horas y KPI por equipo y hora. Grano: día operacional + turno + hora del turno + equipo.

  Horas (en horas, desde segundos):
    Operativas   = tiempo efectivo registrado
    Efectivas    = operativas menos las pérdidas operacionales (espera y cola en camiones;
                   espera en palas y cargadores)
    Disponibles  = operativas + demora no programada + demora programada + reserva
    Nominales    = disponibles + mantención programada + no programada
  Tonelaje por tipo: camiones (descargas), palas y cargadores (cargas); metros solo en perforadoras.
  Se excluyen los equipos de Muro («_M») y el CAEX auxiliar (ver 01_dim_equipo.sql).

  @DiasHistoria: ventana móvil; Turno es una columna, no un filtro, para poder comparar turnos.
==============================================================================*/

DECLARE @DiasHistoria INT  = 90;
DECLARE @FechaInicio  DATE = DATEADD(DAY, -@DiasHistoria, CAST(GETDATE() AS DATE));
DECLARE @FechaFin     DATE = DATEADD(DAY, 1, CAST(GETDATE() AS DATE));

WITH Descarga AS (
    SELECT d.fecha_operacional AS Fecha, d.turno AS Turno, d.hora_turno AS Hora, d.camion AS Equipo,
           SUM(d.tonelaje) AS Tonelaje,
           SUM(CASE WHEN UPPER(ISNULL(d.tronadura, N'')) LIKE N'%STOCK%' THEN 0 ELSE d.tonelaje END) AS MaterialExtraido,
           SUM(CASE WHEN UPPER(ISNULL(d.tronadura, N'')) LIKE N'%STOCK%' THEN d.tonelaje ELSE 0 END) AS MaterialRemanejo
    FROM despacho_demo.descargas_hora AS d WITH (NOLOCK)
    WHERE d.fecha_operacional >= @FechaInicio AND d.fecha_operacional < @FechaFin AND d.eliminado_en IS NULL
      AND CHARINDEX(N'_M', despacho_demo.nombre_norm(d.camion)) = 0
      AND despacho_demo.nombre_norm(d.camion) NOT LIKE N'CAEX-90%'
    GROUP BY d.fecha_operacional, d.turno, d.hora_turno, d.camion
),
Carguio AS (
    SELECT c.fecha_operacional AS Fecha, c.turno AS Turno, c.hora_turno AS Hora, c.pala AS Equipo,
           SUM(c.tonelaje) AS Tonelaje
    FROM despacho_demo.cargas_hora AS c WITH (NOLOCK)
    WHERE c.fecha_operacional >= @FechaInicio AND c.fecha_operacional < @FechaFin AND c.eliminado_en IS NULL
      AND CHARINDEX(N'_M', despacho_demo.nombre_norm(c.pala)) = 0
    GROUP BY c.fecha_operacional, c.turno, c.hora_turno, c.pala
),
Perforacion AS (
    SELECT p.fecha_operacional AS Fecha, p.turno AS Turno, p.hora_turno AS Hora, p.perforadora AS Equipo,
           SUM(p.metros) AS Metros
    FROM despacho_demo.perforacion_hora AS p WITH (NOLOCK)
    WHERE p.fecha_operacional >= @FechaInicio AND p.fecha_operacional < @FechaFin AND p.eliminado_en IS NULL
    GROUP BY p.fecha_operacional, p.turno, p.hora_turno, p.perforadora
),
BaseHora AS (
    SELECT h.fecha_operacional AS Fecha, h.turno AS Turno, h.hora_turno AS Hora,
           h.tipo_equipo AS TipoEquipo, h.flota AS Flota, h.equipo AS Equipo,
           SUM(h.seg_operativo) / 3600.0 AS HorasOperativas,
           CASE h.tipo_equipo
                WHEN N'Truck' THEN (SUM(h.seg_operativo) - SUM(h.seg_espera) - SUM(h.seg_cola)) / 3600.0
                WHEN N'Shovel' THEN (SUM(h.seg_operativo) - SUM(h.seg_espera)) / 3600.0
                WHEN N'Loader' THEN (SUM(h.seg_operativo) - SUM(h.seg_espera)) / 3600.0
                ELSE SUM(h.seg_operativo) / 3600.0
           END AS HorasEfectivas,
           CASE WHEN h.tipo_equipo IN (N'Truck', N'Shovel', N'Loader') THEN SUM(h.seg_espera) / 3600.0 ELSE 0 END AS POEspera,
           CASE WHEN h.tipo_equipo = N'Truck' THEN SUM(h.seg_cola) / 3600.0 ELSE 0 END AS POCola,
           SUM(h.seg_demora_no_prog) / 3600.0 AS HorasDNP,
           SUM(h.seg_demora_prog) / 3600.0    AS HorasDP,
           SUM(h.seg_reserva) / 3600.0        AS HorasReserva,
           SUM(h.seg_mant_prog) / 3600.0      AS HorasMP,
           SUM(h.seg_mant_no_prog) / 3600.0   AS HorasMNP
    FROM despacho_demo.horas_equipo AS h WITH (NOLOCK)
    WHERE h.fecha_operacional >= @FechaInicio AND h.fecha_operacional < @FechaFin AND h.eliminado_en IS NULL
      AND h.tipo_equipo IN (N'Truck', N'Shovel', N'Drill', N'Loader')
      AND CHARINDEX(N'_M', despacho_demo.nombre_norm(h.equipo)) = 0
      AND despacho_demo.nombre_norm(h.equipo) NOT LIKE N'CAEX-90%'
    GROUP BY h.fecha_operacional, h.turno, h.hora_turno, h.tipo_equipo, h.flota, h.equipo
),
Kpi AS (
    SELECT b.*,
           b.HorasOperativas + b.HorasDNP + b.HorasDP + b.HorasReserva AS HorasDisponibles,
           b.HorasOperativas + b.HorasDNP + b.HorasDP + b.HorasReserva + b.HorasMP + b.HorasMNP AS HorasNominales,
           CASE b.TipoEquipo WHEN N'Truck' THEN ISNULL(d.Tonelaje, 0)
                             WHEN N'Shovel' THEN ISNULL(c.Tonelaje, 0)
                             WHEN N'Loader' THEN ISNULL(c.Tonelaje, 0) ELSE 0 END AS Tonelaje,
           CASE WHEN b.TipoEquipo = N'Truck' THEN ISNULL(d.MaterialExtraido, 0) ELSE 0 END AS MaterialExtraido,
           CASE WHEN b.TipoEquipo = N'Truck' THEN ISNULL(d.MaterialRemanejo, 0) ELSE 0 END AS MaterialRemanejo,
           CASE WHEN b.TipoEquipo = N'Drill' THEN ISNULL(p.Metros, 0) ELSE 0 END AS MetrosPerforados
    FROM BaseHora AS b
    LEFT JOIN Descarga   AS d ON d.Fecha = b.Fecha AND d.Turno = b.Turno AND d.Hora = b.Hora AND d.Equipo = b.Equipo
    LEFT JOIN Carguio    AS c ON c.Fecha = b.Fecha AND c.Turno = b.Turno AND c.Hora = b.Hora AND c.Equipo = b.Equipo
    LEFT JOIN Perforacion AS p ON p.Fecha = b.Fecha AND p.Turno = b.Turno AND p.Hora = b.Hora AND p.Equipo = b.Equipo
)
SELECT
    Fecha, Turno, Hora,
    TipoEquipo AS [Tipo Equipo], Equipo, Flota,
    HorasNominales          AS [Horas Nominales],
    HorasOperativas         AS [Horas Operativas],
    HorasEfectivas          AS [Horas Efectivas],
    POEspera                AS [Horas PO Espera],
    POCola                  AS [Horas PO Cola],
    POEspera + POCola       AS [Horas PO Totales],
    HorasDNP                AS [Horas Demora No Programada],
    HorasDP                 AS [Horas Demora Programada],
    HorasReserva            AS [Horas Reserva],
    HorasDisponibles        AS [Horas Disponibles],
    HorasMP                 AS [Horas Mantencion Programada],
    HorasMNP                AS [Horas Mantencion No Programada],
    Tonelaje, MaterialExtraido AS [Material Extraido], MaterialRemanejo AS [Material Remanejo],
    MaterialExtraido + MaterialRemanejo AS [Movimiento Total],
    MetrosPerforados        AS [Metros Perforados],
    CASE WHEN HorasNominales  <= 0 THEN 0 ELSE HorasDisponibles / HorasNominales * 100 END AS Disponibilidad,
    CASE WHEN HorasDisponibles <= 0 THEN 0 ELSE HorasOperativas / HorasDisponibles * 100 END AS Utilizacion,
    CASE WHEN HorasDisponibles <= 0 THEN 0 ELSE HorasEfectivas / HorasDisponibles * 100 END AS UE,
    CASE WHEN HorasNominales  <= 0 THEN 0 ELSE HorasEfectivas / HorasNominales * 100 END AS OEE_Horas,
    CASE WHEN HorasEfectivas <= 0 THEN 0
         WHEN TipoEquipo = N'Drill' THEN MetrosPerforados / HorasEfectivas
         ELSE Tonelaje / HorasEfectivas END AS Rendimiento
FROM Kpi
ORDER BY Fecha, Turno, Hora, Equipo;
