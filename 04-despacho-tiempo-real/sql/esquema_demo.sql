/*==============================================================================
  Esquema ficticio de referencia (SQL Server) para las consultas de sql/consultas/.

  Dos bases de datos de ejemplo:
    despacho_demo : sistema de despacho (equipos, ciclos, descargas, horas por estado, GPS, planes)
    planta_demo   : puntos y valores diarios de planta (planes de indicadores)

  Este archivo solo documenta la forma de los datos; el dashboard NUNCA lo ejecuta
  (la barrera de solo lectura rechaza CREATE). Los datos de ejemplo se generan en
  datos_sinteticos/generar_datos.py.
==============================================================================*/

-- ============================== despacho_demo ================================

CREATE TABLE despacho_demo.dbo.equipos (
    equipo_id    INT          NOT NULL PRIMARY KEY,
    nombre       VARCHAR(30)  NOT NULL UNIQUE,      -- CAEX-01, PALA-01, CARG-01, PERF-01
    tipo_equipo  VARCHAR(10)  NOT NULL,             -- Truck | Shovel | Loader | Drill
    flota        VARCHAR(40)  NULL,                 -- modelo o flota
    es_auxiliar  BIT          NOT NULL DEFAULT 0    -- 1 = flota auxiliar (sufijo _AUX)
);

-- Un registro por ciclo de acarreo
CREATE TABLE despacho_demo.dbo.ciclos (
    ciclo_id          BIGINT IDENTITY(1,1) PRIMARY KEY,
    dia_operativo     DATE          NOT NULL,
    turno             CHAR(1)       NOT NULL,        -- 'A' | 'B'
    camion_id         INT           NOT NULL REFERENCES despacho_demo.dbo.equipos (equipo_id),
    carguio_id        INT           NOT NULL REFERENCES despacho_demo.dbo.equipos (equipo_id),
    origen            VARCHAR(40)   NOT NULL,
    tipo_origen       VARCHAR(20)   NULL,
    destino           VARCHAR(40)   NOT NULL,
    tipo_destino      VARCHAR(20)   NULL,
    material          VARCHAR(30)   NULL,
    hora_salida       DATETIME      NOT NULL,        -- hora local
    hora_llegada      DATETIME      NULL,
    hora_lleno        DATETIME      NULL,
    hora_vacio        DATETIME      NULL,
    tonelaje          DECIMAL(10,2) NOT NULL,
    distancia_m       DECIMAL(10,1) NULL,
    t_viaje_s         DECIMAL(9,1)  NOT NULL DEFAULT 0,
    t_espera_s        DECIMAL(9,1)  NOT NULL DEFAULT 0,
    t_aculatamiento_s DECIMAL(9,1)  NOT NULL DEFAULT 0,
    t_carga_s         DECIMAL(9,1)  NOT NULL DEFAULT 0,
    t_acarreo_s       DECIMAL(9,1)  NOT NULL DEFAULT 0,
    t_cola_s          DECIMAL(9,1)  NOT NULL DEFAULT 0,
    t_retroceso_s     DECIMAL(9,1)  NOT NULL DEFAULT 0,
    t_descarga_s      DECIMAL(9,1)  NOT NULL DEFAULT 0,
    pala_esperando_s  DECIMAL(9,1)  NOT NULL DEFAULT 0,
    ciclos            INT           NOT NULL DEFAULT 1,
    cargas            INT           NOT NULL DEFAULT 1
);

-- Una descarga por viaje (la hora UTC permite agrupar por hora local)
CREATE TABLE despacho_demo.dbo.descargas (
    descarga_id    BIGINT IDENTITY(1,1) PRIMARY KEY,
    fecha          DATE          NOT NULL,           -- día operativo
    turno          CHAR(1)       NOT NULL,
    hora           TINYINT       NOT NULL,           -- 0..11 dentro del turno
    fecha_hora_utc DATETIME      NOT NULL,
    camion_id      INT           NOT NULL REFERENCES despacho_demo.dbo.equipos (equipo_id),
    carguio_id     INT           NOT NULL REFERENCES despacho_demo.dbo.equipos (equipo_id),
    origen         VARCHAR(10)   NOT NULL,           -- F01..F04 (fases) | STK (stock)
    destino        VARCHAR(40)   NOT NULL,
    material       VARCHAR(30)   NULL,
    tonelaje       DECIMAL(10,2) NOT NULL,
    ley_cut        DECIMAL(6,3)  NULL,
    eliminado_en   DATETIME      NULL                -- borrado lógico
);

-- Horas por estado y por equipo-hora
CREATE TABLE despacho_demo.dbo.horas_equipo (
    fecha            DATE         NOT NULL,           -- día operativo
    turno            CHAR(1)      NOT NULL,
    hora             TINYINT      NOT NULL,           -- 0..11 dentro del turno
    equipo_id        INT          NOT NULL REFERENCES despacho_demo.dbo.equipos (equipo_id),
    horas_nominales  DECIMAL(6,3) NOT NULL,
    horas_operativas DECIMAL(6,3) NOT NULL,
    horas_espera     DECIMAL(6,3) NOT NULL DEFAULT 0,
    horas_cola       DECIMAL(6,3) NOT NULL DEFAULT 0,
    horas_dnp        DECIMAL(6,3) NOT NULL DEFAULT 0, -- demora no programada
    horas_dp         DECIMAL(6,3) NOT NULL DEFAULT 0, -- demora programada
    horas_reserva    DECIMAL(6,3) NOT NULL DEFAULT 0,
    horas_mp         DECIMAL(6,3) NOT NULL DEFAULT 0, -- mantención programada
    horas_mnp        DECIMAL(6,3) NOT NULL DEFAULT 0, -- mantención no programada
    metros_perforados DECIMAL(9,2) NOT NULL DEFAULT 0,
    PRIMARY KEY (fecha, turno, hora, equipo_id)
);

-- Lecturas GPS (latitud y longitud en milisegundos de arco; hora en UTC)
CREATE TABLE despacho_demo.dbo.gps_lecturas (
    lectura_id     BIGINT IDENTITY(1,1) PRIMARY KEY,
    equipo_id      INT          NOT NULL REFERENCES despacho_demo.dbo.equipos (equipo_id),
    fecha_hora_utc DATETIME     NOT NULL,
    latitud_mas    FLOAT        NULL,
    longitud_mas   FLOAT        NULL,
    velocidad_kmh  DECIMAL(5,1) NULL
);
CREATE INDEX ix_gps_fecha ON despacho_demo.dbo.gps_lecturas (fecha_hora_utc);

-- Planes: cabecera por tipo y fecha, y propiedades en filas
CREATE TABLE despacho_demo.dbo.planes (
    plan_id   INT         NOT NULL PRIMARY KEY,
    tipo_plan VARCHAR(20) NOT NULL,                   -- caex | carguio | perforadora | chancador
    fecha     DATE        NOT NULL,
    equipo_id INT         NULL REFERENCES despacho_demo.dbo.equipos (equipo_id)
);
CREATE TABLE despacho_demo.dbo.plan_items (
    plan_id   INT           NOT NULL REFERENCES despacho_demo.dbo.planes (plan_id),
    propiedad VARCHAR(40)   NOT NULL,                 -- horas_disponibles | horas_efectivas | horas_nominales
                                                      -- horas_operativas | toneladas | metros | ley_cut
    valor     DECIMAL(14,3) NOT NULL,
    PRIMARY KEY (plan_id, propiedad)
);

-- Estado vigente de cada equipo (opcional)
CREATE TABLE despacho_demo.dbo.estados_equipo (
    equipo_id INT          NOT NULL REFERENCES despacho_demo.dbo.equipos (equipo_id),
    categoria VARCHAR(30)  NOT NULL,
    motivo    VARCHAR(80)  NULL,
    desde     DATETIME     NOT NULL,                  -- hora local
    hasta     DATETIME     NULL                       -- NULL = estado vigente
);

-- ============================== planta_demo ==================================

CREATE TABLE planta_demo.dbo.puntos (
    punto_id INT          NOT NULL PRIMARY KEY,
    tag      VARCHAR(60)  NOT NULL UNIQUE             -- p. ej. PLAN_DF_AUX, PLAN_UEBD_AUX
);
CREATE TABLE planta_demo.dbo.valores (
    punto_id INT           NOT NULL REFERENCES planta_demo.dbo.puntos (punto_id),
    fecha    DATE          NOT NULL,
    valor    DECIMAL(14,4) NOT NULL,
    PRIMARY KEY (punto_id, fecha)
);
