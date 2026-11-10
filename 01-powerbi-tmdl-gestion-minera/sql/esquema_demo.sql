-- Esquema mínimo de una base ficticia (SQL Server) que respalda las consultas de esta carpeta.
-- Tres esquemas, uno por sistema de origen genérico:
--   despacho_demo : despacho de mina (descargas, cargas, ciclos de camiones, planes)
--   equipos_demo  : equipos y sus tiempos (horas nominales, mantención, efectivas)
--   planta_demo   : cierres diarios de planta (puntos, versiones)
-- Los CSV de datos_sinteticos/ tienen las mismas columnas que devuelven las consultas de esta carpeta.

CREATE SCHEMA despacho_demo;
GO
CREATE SCHEMA equipos_demo;
GO
CREATE SCHEMA planta_demo;
GO

-- Descargas de camiones por hora (día de mina: 08:00 a 08:00; turno A 08-20 h, turno B 20-08 h; hora 0..11 dentro del turno)
CREATE TABLE despacho_demo.descargas (
    fecha_mina   DATE          NOT NULL,
    turno        CHAR(1)       NOT NULL,
    hora         TINYINT       NOT NULL,
    camion       VARCHAR(12)   NOT NULL,   -- CAEX-01 .. CAEX-26
    tronadura    VARCHAR(20)   NULL,       -- F01_B101, STO_P01 (stock) ...
    destino      VARCHAR(20)   NULL,       -- CHA_PRIM, DL_PAD01, BOT_N01, STO_01
    toneladas    DECIMAL(12,1) NOT NULL,
    eliminado_en DATETIME2     NULL
);

-- Cargas de palas y cargadores por hora
CREATE TABLE despacho_demo.cargas (
    fecha_mina   DATE          NOT NULL,
    turno        CHAR(1)       NOT NULL,
    hora         TINYINT       NOT NULL,
    pala         VARCHAR(12)   NOT NULL,   -- PALA-01 .. PALA-04, CARG-01 .. CARG-02
    destino      VARCHAR(20)   NULL,       -- CHANCADO, DL_PAD01, BOT_N01, STO_01
    toneladas    DECIMAL(12,1) NOT NULL,
    eliminado_en DATETIME2     NULL
);

-- Ciclos de transporte: velocidades medias por camión y turno (CAEX 15 a 30 km/h)
CREATE TABLE despacho_demo.ciclos (
    fecha_mina            DATE         NOT NULL,
    turno                 CHAR(1)      NOT NULL,
    camion                VARCHAR(12)  NOT NULL,
    ciclos                INT          NOT NULL,
    velocidad_cargado_kmh DECIMAL(5,1) NOT NULL,
    velocidad_vacio_kmh   DECIMAL(5,1) NOT NULL
);

-- Plan por propiedad y día (mensual o semanal)
CREATE TABLE despacho_demo.planes (
    fecha_inicio DATE          NOT NULL,
    propiedad    VARCHAR(80)   NOT NULL,   -- 'Total Toneladas', 'Horas Nominales CAEX SEM', ...
    valor        DECIMAL(14,2) NOT NULL,
    tipo_plan    VARCHAR(10)   NOT NULL    -- 'Mensual' | 'Semanal'
);

CREATE TABLE equipos_demo.equipos (
    equipo VARCHAR(12) NOT NULL PRIMARY KEY,
    tipo   VARCHAR(12) NOT NULL,           -- CAEX | Pala | Cargador
    activo BIT         NOT NULL DEFAULT 1
);

-- Tiempos por equipo y turno, en horas
CREATE TABLE equipos_demo.horas_equipo (
    fecha_mina DATE         NOT NULL,
    turno      CHAR(1)      NOT NULL,
    equipo     VARCHAR(12)  NOT NULL REFERENCES equipos_demo.equipos (equipo),
    nominal    DECIMAL(6,2) NOT NULL,
    mant_prog  DECIMAL(6,2) NOT NULL,      -- mantención programada
    mant_noprog DECIMAL(6,2) NOT NULL,     -- mantención no programada
    efectivo   DECIMAL(6,2) NOT NULL
);

-- Disponibilidad física (DF) y utilización (UE) diarias por área
CREATE TABLE equipos_demo.disponibilidad_diaria (
    fecha  DATE         NOT NULL,
    area   VARCHAR(40)  NOT NULL,          -- 'Chancado Primario', 'Molienda', 'MB1', ...
    medicion VARCHAR(4) NOT NULL,          -- 'DF' | 'UE'
    valor  DECIMAL(5,1) NOT NULL
);

-- Cierre diario de planta: varias versiones por punto y día (1 = real, 7 = plan semanal)
CREATE TABLE planta_demo.cierre_diario (
    id            BIGINT IDENTITY PRIMARY KEY,
    punto         VARCHAR(60)   NOT NULL,  -- 'PLANTA.SAG.TON_DIA', 'PLANTA.P80.PLAN', ...
    fecha         DATE          NOT NULL,
    version       TINYINT       NOT NULL,
    valor         VARCHAR(40)   NULL,      -- texto: se convierte con TRY_CONVERT
    modificado_en DATETIME2     NOT NULL DEFAULT SYSDATETIME()
);
GO
