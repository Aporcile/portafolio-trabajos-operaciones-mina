# Decisiones de diseño (ADR cortos)

Cada entrada recoge el contexto, la decisión y sus consecuencias. Se actualizan en vez de duplicarse.
La tabla general de decisiones de arquitectura está en `ARQUITECTURA.md`; aquí van las de dominio.

ADR-001 a ADR-005 están implementadas y probadas en este repositorio. ADR-006 a ADR-008 describen el
comportamiento previsto del motor de KPI (hoja de ruta), que aún no forma parte del código.

## ADR-001: Turnos de 12 h y día operacional que empieza a las 08:00

- **Contexto**: la operación trabaja en dos turnos de 12 h. Un catálogo de turnos puede traer límites
  inconsistentes o solapados, y las horas de madrugada pertenecen al día operativo anterior.
- **Decisión**: turno A = 08:00–19:59, turno B = 20:00–07:59 del día calendario siguiente; día operacional =
  fecha de (hora − 8 h); `HoraTurno` 1..12 y `OrdenHoraDia` 1..24 desde las 08:00. Se implementa una sola vez en
  `tiempo.py` y los tests cubren los límites exactos.
- **Consecuencia**: ninguna consulta ni KPI reimplementa la regla; el motor clasifica cada instante con
  `turno_de()` en lugar de confiar en columnas de turno de las fuentes.

## ADR-002: Todo el código obtiene la hora de un reloj inyectable

- **Contexto**: un dashboard en tiempo real depende de la hora actual; probar cambios de turno o de día con el
  reloj del sistema es lento y no determinista.
- **Decisión**: `Reloj` (real) y `RelojSimulado` (factor de aceleración, congelado o con saltos). Ninguna función
  del dominio llama a `datetime.now()`.
- **Consecuencia**: los tests cruzan turnos a voluntad y la demo puede correr a velocidad acelerada.

## ADR-003: Zona horaria configurable con respaldo de desfase fijo

- **Contexto**: los instantes de GPS y auditoría vienen en UTC, mientras que los turnos son en hora local. La
  base de zonas horarias puede no existir en el equipo (p. ej. Windows sin el paquete `tzdata`).
- **Decisión**: `configurar_zona(nombre, desfase_respaldo_h)`: UTC directo, `zoneinfo` si existe y, si no, un
  desfase fijo configurable con advertencia en el log. Las consultas reciben `@DesfaseMinutos` calculado por el
  reloj en lugar de depender del reloj del servidor SQL.
- **Consecuencia**: el servidor siempre arranca; en zonas con horario de verano, el desfase fijo exige revisión
  manual y está documentado como limitación.

## ADR-004: Contrato de datos como única frontera entre fuentes y motor

- **Contexto**: un dashboard que se desarrolla con datos simulados y luego corre con datos reales corre el riesgo de
  que ambos caminos diverjan.
- **Decisión**: `contratos.py` declara columnas, tipos, parámetros y cadencia de cada dataset; fuentes SQL y simulador
  deben devolver exactamente esas columnas, y `validar_registros()` lo verifica. Los tests verifican que cada consulta
  incluida respeta el contrato de su dataset.
- **Consecuencia**: cambiar una columna exige tocar el contrato, la consulta y el generador sintético a la vez, y los
  tests lo detectan si alguno se olvida.

## ADR-005: Solo lectura con doble barrera

- **Contexto**: la aplicación se conecta a bases operacionales; un error o una inyección no debe poder escribir.
- **Decisión**: permiso de solo lectura en el login y, además, validación del texto de cada consulta (una sentencia,
  que empiece por `SELECT` o `WITH`, sin verbos de escritura ni DDL). El analizador ignora comentarios, cadenas e
  identificadores para no producir falsos positivos ni dejarse engañar.
- **Consecuencia**: ninguna consulta nueva entra sin pasar por la barrera; las consultas de referencia se validan en los tests.

## ADR-006: Tiempo de ciclo = suma de seis tiempos

- **Contexto**: los sistemas de despacho registran muchos tiempos por ciclo (viaje, espera, aculatamiento, carga,
  acarreo, cola, retroceso, descarga).
- **Decisión**: el tiempo de ciclo del dashboard es viaje vacío + espera + carga + acarreo + cola + descarga, sin
  aculatamiento ni retroceso. `HoraVacio − HoraSalida` solo se usa como respaldo si faltan los tiempos.
- **Consecuencia**: una definición única, comparable entre rutas y turnos; la norma de cada ruta es la mediana
  de los últimos 7 días, o `ciclos.norma_por_defecto_min` si no hay historia.

## ADR-007: Las tarjetas proyectan el día operacional, no el turno

- **Contexto**: comparar el acumulado de un turno contra el plan diario lleva a conclusiones erróneas.
- **Decisión**: el «real» de una tarjeta es el acumulado del día operacional y el cierre probable es del día (24 h);
  solo la curva gaviota se presenta por turno (actual vs anterior).
- **Consecuencia**: durante el turno B el real del día incluye el turno A.

## ADR-008: Los valores estimados se declaran como tales

- **Contexto**: parte de lo que muestra el tablero (cierre probable, normas, adherencia a la mezcla) no es un registro
  directo, sino un método propio.
- **Decisión**: cada bloque del snapshot lista en `estimado` los campos que no provienen de un registro y en `fuente`
  la consulta de la que derivan.
- **Consecuencia**: el operador puede distinguir dato medido de dato calculado; los métodos y sus parámetros viven en
  `config/dashboard.toml`.

## Preguntas abiertas

1. Ajustar el perfil horario del plan (`config/plan_horario.toml`) con la curva real observada.
2. Definir la fuente del estado vigente de cada equipo (`estado_equipos`) y, mientras tanto, derivarlo de horas por estado y GPS.
3. Validar la norma de ciclo con los parámetros de la plataforma de despacho (hoy, mediana histórica).
