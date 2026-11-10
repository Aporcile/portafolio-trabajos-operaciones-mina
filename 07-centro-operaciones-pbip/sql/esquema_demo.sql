/*==============================================================================
  Esquema ficticio de ejemplo (T-SQL) para las consultas de esta carpeta.

  No corresponde a ningún sistema real: sirve para leer cada consulta con sus
  tablas y columnas a la vista. Los CSV de datos_sinteticos/ tienen la misma forma
  que el resultado de estas consultas.

  Dos esquemas:
    despacho_demo  sistema de despacho (equipos, horas por estado, descargas, GPS, planes)
    planta_demo    base de planificación de planta (puntos de plan y sus valores diarios)
==============================================================================*/

CREATE SCHEMA despacho_demo;
GO
CREATE SCHEMA planta_demo;
GO

/* ---- despacho_demo ------------------------------------------------------- */

CREATE TABLE despacho_demo.equipos (
    id      INT           NOT NULL PRIMARY KEY,
    nombre  NVARCHAR(40)  NOT NULL,           -- CAEX-01, PALA-01, CARG-01, PERF-01 ...
    tipo    NVARCHAR(20)  NOT NULL,           -- Truck | Shovel | Loader | Drill
    flota   NVARCHAR(40)  NULL
);

/* Una fila por equipo y hora; los estados vienen en segundos. */
CREATE TABLE despacho_demo.horas_equipo (
    fecha_operacional   DATE          NOT NULL,   -- día operacional (08:00 a 08:00)
    turno               CHAR(1)       NOT NULL,   -- A: 08:00-19:59, B: 20:00-07:59
    hora_turno          TINYINT       NOT NULL,   -- 0..11 dentro del turno
    equipo              NVARCHAR(40)  NOT NULL,
    tipo_equipo         NVARCHAR(20)  NOT NULL,
    flota               NVARCHAR(40)  NULL,
    seg_operativo       INT           NOT NULL DEFAULT 0,
    seg_espera          INT           NOT NULL DEFAULT 0,   -- espera de pala o de camión
    seg_cola            INT           NOT NULL DEFAULT 0,   -- cola en el punto de descarga
    seg_demora_no_prog  INT           NOT NULL DEFAULT 0,
    seg_demora_prog     INT           NOT NULL DEFAULT 0,
    seg_reserva         INT           NOT NULL DEFAULT 0,
    seg_mant_prog       INT           NOT NULL DEFAULT 0,
    seg_mant_no_prog    INT           NOT NULL DEFAULT 0,
    eliminado_en        DATETIME2     NULL
);

/* Toneladas por hora y camión. */
CREATE TABLE despacho_demo.descargas_hora (
    fecha_operacional DATE NOT NULL, turno CHAR(1) NOT NULL, hora_turno TINYINT NOT NULL,
    camion NVARCHAR(40) NOT NULL, tronadura NVARCHAR(60) NULL, tonelaje DECIMAL(12, 2) NOT NULL,
    eliminado_en DATETIME2 NULL
);

/* Toneladas por hora y equipo de carguío. */
CREATE TABLE despacho_demo.cargas_hora (
    fecha_operacional DATE NOT NULL, turno CHAR(1) NOT NULL, hora_turno TINYINT NOT NULL,
    pala NVARCHAR(40) NOT NULL, tonelaje DECIMAL(12, 2) NOT NULL, eliminado_en DATETIME2 NULL
);

/* Metros perforados por hora y perforadora. */
CREATE TABLE despacho_demo.perforacion_hora (
    fecha_operacional DATE NOT NULL, turno CHAR(1) NOT NULL, hora_turno TINYINT NOT NULL,
    perforadora NVARCHAR(40) NOT NULL, metros DECIMAL(10, 2) NOT NULL, eliminado_en DATETIME2 NULL
);

/* Una fila por grupo de descargas (pala, camión, tronadura, calidad). */
CREATE TABLE despacho_demo.descargas_detalle (
    fecha_operacional DATE NOT NULL, turno CHAR(1) NOT NULL, pala NVARCHAR(40) NOT NULL,
    camion NVARCHAR(40) NOT NULL, ley NVARCHAR(20) NULL, tronadura NVARCHAR(60) NULL,
    destino NVARCHAR(40) NOT NULL, material NVARCHAR(40) NULL, tonelaje DECIMAL(12, 2) NOT NULL,
    cargas INT NOT NULL, calidades NVARCHAR(MAX) NULL,   -- lista separada por comas; el primer valor es CuT
    registrado_utc DATETIME2 NOT NULL, eliminado_en DATETIME2 NULL
);

/* Lecturas GPS: listas separadas por comas; el primer valor es la lectura vigente. */
CREATE TABLE despacho_demo.gps_turno (
    instante_utc DATETIME2 NOT NULL, equipo_id INT NOT NULL,
    latitudes NVARCHAR(MAX) NULL, longitudes NVARCHAR(MAX) NULL, velocidades NVARCHAR(MAX) NULL
);

CREATE TABLE despacho_demo.planes (
    id INT NOT NULL PRIMARY KEY, tipo NVARCHAR(20) NOT NULL,   -- SEMANAL
    fecha_inicio DATE NOT NULL
);

CREATE TABLE despacho_demo.planes_items (
    plan_id INT NOT NULL, propiedad NVARCHAR(120) NOT NULL,    -- p. ej. 'Horas Disponibles CAEX SEM'
    valor DECIMAL(14, 4) NULL
);

/* ---- planta_demo --------------------------------------------------------- */

CREATE TABLE planta_demo.puntos_plan (
    id INT NOT NULL PRIMARY KEY, nombre NVARCHAR(80) NOT NULL    -- p. ej. 'PLAN_MURO_CAEX_DISP'
);

CREATE TABLE planta_demo.valores_plan (
    id BIGINT IDENTITY(1, 1) PRIMARY KEY, punto_id INT NOT NULL,
    version TINYINT NOT NULL,            -- 1 = plan mensual
    instante DATETIME2 NOT NULL, valor FLOAT NULL
);
GO

/* Normaliza un nombre de equipo: sin espacios, espacios duros ni tabulaciones, en mayúsculas. */
CREATE FUNCTION despacho_demo.nombre_norm (@x NVARCHAR(80))
RETURNS NVARCHAR(80)
AS
BEGIN
    RETURN UPPER(REPLACE(REPLACE(REPLACE(ISNULL(@x, N''), N' ', N''), NCHAR(160), N''), NCHAR(9), N''));
END;
GO
