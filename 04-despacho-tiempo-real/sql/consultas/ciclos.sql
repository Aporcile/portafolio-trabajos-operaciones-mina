/* Dataset ciclos: un registro por ciclo de acarreo desde el inicio del turno anterior.
   Parámetro: @InicioTurnoAnterior (hora local, lo calcula el programador con el reloj).
   Los tiempos vienen en segundos; el motor define el tiempo de ciclo como la suma de seis tiempos
   (viaje vacío + espera + carga + acarreo + cola + descarga). */
SELECT
    c.dia_operativo    AS DiaOperativo,
    c.turno            AS Turno,
    t.nombre           AS CAEX,
    t.flota            AS FlotaCAEX,
    p.nombre           AS EquipoCarguio,
    p.flota            AS FlotaCarguio,
    c.origen           AS Origen,
    c.tipo_origen      AS TipoOrigen,
    c.destino          AS Destino,
    c.tipo_destino     AS TipoDestino,
    c.material         AS Material,
    c.hora_salida      AS HoraSalida,
    c.hora_llegada     AS HoraLlegada,
    c.hora_lleno       AS HoraLleno,
    c.hora_vacio       AS HoraVacio,
    c.tonelaje         AS Tonelaje,
    c.distancia_m      AS Distancia,
    c.t_viaje_s        AS TiempoViajeS,
    c.t_espera_s       AS TiempoEsperaS,
    c.t_aculatamiento_s AS TiempoAculatamientoS,
    c.t_carga_s        AS TiempoCargaS,
    c.t_acarreo_s      AS TiempoAcarreoS,
    c.t_cola_s         AS TiempoColaS,
    c.t_retroceso_s    AS TiempoRetrocesoS,
    c.t_descarga_s     AS TiempoDescargaS,
    c.pala_esperando_s AS PalaEsperandoS,
    c.ciclos           AS Ciclos,
    c.cargas           AS Cargas
FROM despacho_demo.dbo.ciclos AS c WITH (NOLOCK)
INNER JOIN despacho_demo.dbo.equipos AS t WITH (NOLOCK) ON t.equipo_id = c.camion_id
INNER JOIN despacho_demo.dbo.equipos AS p WITH (NOLOCK) ON p.equipo_id = c.carguio_id
WHERE c.hora_salida >= @InicioTurnoAnterior
  AND t.es_auxiliar = 0
  AND p.es_auxiliar = 0
ORDER BY c.hora_salida;
