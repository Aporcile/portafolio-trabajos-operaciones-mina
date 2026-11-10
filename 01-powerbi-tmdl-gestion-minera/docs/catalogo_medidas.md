# Catálogo de medidas por familia

Proyecto de ejemplo de la empresa ficticia Minera Demo. El modelo reducido tiene **124 medidas** en **29 tablas**; esta página las agrupa por familia. Los nombres con prefijo `Rd` son las medidas de las tarjetas del informe; el resto son medidas de negocio. Las descripciones salen de los comentarios `///` del TMDL.

## Movimiento de mina (real)

Toneladas descargadas por los camiones y cargadas por las palas. `Movimiento` = extracción de mina + remanejo desde stock; las medidas de palas leen las cargas (van ligeramente adelantadas de las descargas).

| Medida | Tabla | Qué devuelve |
|---|---|---|
| `Extraccion Mina (Ex- Pit)` | `Produccion Mina` | Toneladas con origen en tronadura de mina (clase Mina). |
| `Movimiento` | `Produccion Mina` | Movimiento total de mina (extracción mina + remanejo), en t. |
| `Movimiento Palas` | `Produccion Palas Turno` | Toneladas cargadas por las palas y cargadores en los turnos del contexto de fecha. |
| `Movimiento Palas por hora` | `Produccion Palas Hora` | Toneladas cargadas por hora de mina; admite el filtro de pala y de destino. |
| `Movimiento PM` | `Produccion Mina` | Suma de toneladas descargadas, sin separar clase de material. |
| `Remanejo` | `Produccion Mina` | Toneladas con origen en stock (clase Stock). |

## Flota CAEX y carguío: tiempos y rendimiento

Indicadores de la flota a partir de las horas nominales, disponibles y efectivas: disponibilidad física (DF), utilización efectiva sobre base disponible (UEBD) y rendimiento en t por hora efectiva.

| Medida | Tabla | Qué devuelve |
|---|---|---|
| `Disponibilidad CAEX` | `Horas CAEX` | Disponibilidad física de CAEX: horas disponibles sobre horas nominales. |
| `Disponibilidad Palas turno` | `Horas Palas Turno` | DF de la flota de carguío: (nominal - mantención programada - mantención no programada) sobre nominal. |
| `Hr nominales` | `Horas CAEX` | Horas nominales de la flota CAEX. |
| `Hr_efectivo Turno Palas` | `Horas Palas Turno` | Horas efectivas de la flota de carguío. |
| `Hr_HD Turno Palas` | `Horas Palas Turno` | Horas disponibles de la flota de carguío: nominal menos mantención programada y no programada. |
| `TPH efectivo CAEX REV` | `Horas CAEX` | Rendimiento de la flota CAEX: toneladas movidas por hora efectiva. |
| `TPH efectivo Palas Por Turno Palas` | `Horas Palas Turno` | Rendimiento de carguío: toneladas cargadas por hora efectiva. |
| `UEBD CAEX` | `Horas CAEX` | Utilización efectiva sobre base disponible de CAEX: horas efectivas sobre horas disponibles. |
| `UEBD Palas turno` | `Horas Palas Turno` | UEBD de carguío: horas efectivas sobre horas disponibles (0 si no hay datos). |

## Plan mensual y semanal de mina

Se leen de `Planes_Mina` filtrando por `plan_type` y `property_name`. El plan de movimiento es el total que trae el propio plan; si falta, se reconstruye como extracción de mina más chancado desde stock. Las medidas CAEX distinguen dos formatos del plan (ver `generador/caex_plan_formato.py`).

| Medida | Tabla | Qué devuelve |
|---|---|---|
| `PlanMensual Ampliacion` | `Planes_Mina` | Plan mensual de extracción de mina: chancado desde mina + dump + estéril + stock de sulfuro. |
| `PlanMensual Movimiento mina` | `Planes_Mina` | Plan mensual de movimiento total (propiedad Total Toneladas); si falta, extracción más chancado desde stock. |
| `PlanMensual Total Toneladas Chancado` | `Planes_Mina` | Plan mensual de toneladas totales a chancado (mina más stock). |
| `PlanMensual Total Toneladas Chancado desde Mina` | `Planes_Mina` | Plan mensual de toneladas a chancado con origen en mina. |
| `PlanMensual Total Toneladas Chancado desde stock` | `Planes_Mina` | Plan mensual de toneladas a chancado desde stock (remanejo). |
| `PlanMensual Total Toneladas Dump` | `Planes_Mina` | Plan mensual de toneladas a dump leach. |
| `PlanMensual Total Toneladas Esteril` | `Planes_Mina` | Plan mensual de toneladas a botadero (estéril). |
| `PlanMensual Total Toneladas Stock Sulfuro` | `Planes_Mina` | Plan mensual de toneladas a stock de sulfuro. |
| `PlanSemanal - Disponibilidad CAEX` | `Planes_Mina` | DF del plan de CAEX: horas disponibles sobre horas nominales. |
| `PlanSemanal - Disponibilidad PALAS` | `Planes_Mina` | DF del plan de carguío: horas disponibles sobre horas nominales. |
| `PlanSemanal - Horas Disponible CAEX` | `Planes_Mina` | Horas disponibles del plan semanal de CAEX; lee el formato clásico y el alternativo del plan. |
| `PlanSemanal - Horas Disponible PALAS` | `Planes_Mina` | Suma de horas disponibles del plan semanal de los 5 equipos de carguío. |
| `PlanSemanal - Horas efectivas CAEX` | `Planes_Mina` | Horas efectivas del plan semanal de CAEX; en el formato alternativo = movimiento del plan / rendimiento. |
| `PlanSemanal - Horas Efectivas PALAS` | `Planes_Mina` | Suma de horas efectivas del plan semanal de los 5 equipos de carguío. |
| `PlanSemanal - Horas Nominales CAEX` | `Planes_Mina` | Horas nominales del plan semanal de CAEX; lee el formato clásico y el alternativo del plan. |
| `PlanSemanal - Horas Nominales PALAS` | `Planes_Mina` | Suma de horas nominales del plan semanal de los 5 equipos de carguío. |
| `PlanSemanal - movimiento calculado CAEX` | `Planes_Mina` | Movimiento del plan reconstruido: nominales x DF x UEBD x rendimiento. |
| `PlanSemanal - Rendimiento CAEX` | `Planes_Mina` | Rendimiento del plan de CAEX: movimiento del plan por hora efectiva. |
| `PlanSemanal - Rendimiento Palas` | `Planes_Mina` | Rendimiento del plan de carguío: movimiento del plan por hora efectiva de palas. |
| `PlanSemanal - UEBD CAEX` | `Planes_Mina` | UEBD del plan de CAEX: horas efectivas sobre horas disponibles. |
| `PlanSemanal - UEBD PALAS` | `Planes_Mina` | UEBD del plan de carguío: horas efectivas sobre horas disponibles. |
| `PlanSemanal Ampliacion` | `Planes_Mina` | Plan semanal de extracción de mina: chancado desde mina + dump + estéril + stock de sulfuro. |
| `PlanSemanal Movimiento mina CAEX` | `Planes_Mina` | Plan semanal de movimiento total de la flota CAEX (propiedad Total Toneladas SEM). |
| `PlanSemanal Remanejo` | `Planes_Mina` | Plan semanal de remanejo: toneladas a chancado desde stock. |
| `PlanSemanal Total Toneladas Chancado` | `Planes_Mina` | Plan semanal de toneladas totales a chancado (mina más stock). |
| `PlanSemanal Total Toneladas Chancado desde Mina` | `Planes_Mina` | Plan semanal de toneladas a chancado con origen en mina. |
| `PlanSemanal Total Toneladas Chancado desde stock` | `Planes_Mina` | Plan semanal de toneladas a chancado desde stock (remanejo). |
| `PlanSemanal Total Toneladas Dump` | `Planes_Mina` | Plan semanal de toneladas a dump leach. |
| `PlanSemanal Total Toneladas Esteril` | `Planes_Mina` | Plan semanal de toneladas a botadero (estéril). |
| `PlanSemanal Total Toneladas Stock Sulfuro` | `Planes_Mina` | Plan semanal de toneladas a stock de sulfuro. |

## Cascada plan semanal a real

Cada paso es la diferencia de t entre dejar un factor en su valor real y en su valor del plan (DF, UEBD, rendimiento, horas nominales), en ese orden. Alimentan las cascadas SVG de la flota CAEX.

| Medida | Tabla | Qué devuelve |
|---|---|---|
| `Waterfall - Plansemanal dif Disponibilidad` | `Planes_Mina` | Paso de la cascada por disponibilidad: real menos plan con los demás factores en plan, en t. |
| `Waterfall - Plansemanal dif hrs nominales` | `Planes_Mina` | Paso de la cascada por horas nominales: horas reales contra horas del plan, en t. |
| `Waterfall - Plansemanal dif rendimiento` | `Planes_Mina` | Paso de la cascada por rendimiento (t por hora efectiva), en t. |
| `Waterfall - Plansemanal dif UEBD` | `Planes_Mina` | Paso de la cascada por UEBD: real menos plan con disponibilidad real y rendimiento en plan, en t. |

## Día de mina, proyección y selección de fecha

El día de mina va de 08:00 a 08:00. `Rd Día` es el día elegido en el segmentador o, sin selección, el día en curso; las horas transcurridas se miden con los datos cargados (no con el reloj) y alimentan la proyección lineal a 24 h.

| Medida | Tabla | Qué devuelve |
|---|---|---|
| `Rd Alim Hora` | `dax_kpi_tabla` | Toneladas cargadas por las palas con destino chancado, por hora del día de mina. |
| `Rd Día` | `dax_kpi_tabla` | Día de mina mostrado: el elegido en el segmentador o, sin selección, el día en curso (08:00 a 08:00). |
| `Rd Día En Curso` | `dax_kpi_tabla` | Verdadero si el día mostrado está en curso. |
| `Rd Factor Proyección` | `dax_kpi_tabla` | Factor de extrapolación lineal a 24 h; 1 en día cerrado. |
| `Rd Fecha Elegida` | `dax_kpi_tabla` | Fecha elegida en el segmentador de fecha; vacío equivale al día en curso. |
| `Rd Horas Transcurridas` | `dax_kpi_tabla` | Horas del día de mina cubiertas por los datos cargados (24 si el día está cerrado). |
| `Rd Ventana Mina` | `dax_kpi_tabla` | Leyenda de la ventana del día de mina (08:00 a 08:00). |

## Destinos y fases

Medidas de fila para las tablas de destinos (chancado, dump leach, botadero, stock) y de fases: real, proyección y plan del día.

| Medida | Tabla | Qué devuelve |
|---|---|---|
| `Rd Destino Plan` | `dax_kpi_tabla` | Plan semanal del día para el destino de la fila (chancado, dump, estéril o stock). |
| `Rd Destino Proyección` | `dax_kpi_tabla` | Real del destino por el factor de proyección a 24 h. |
| `Rd Destino Real` | `dax_kpi_tabla` | Toneladas del día del destino de la fila (0 si no hubo movimiento; vacío en el miembro en blanco). |
| `Rd Fase Máximo Día` | `dax_kpi_tabla` | Escala común de las barras de fase: el mayor entre plan y proyección de las fases. |
| `Rd Fase Plan` | `dax_kpi_tabla` | Plan del día de la fase en contexto de fila de la dimensión de fases. |
| `Rd Fase Proyección` | `dax_kpi_tabla` | Real de la fase por el factor de proyección a 24 h. |
| `Rd Fase Real` | `dax_kpi_tabla` | Toneladas del día de la fase de la fila (0 si no hubo movimiento; vacío en el miembro en blanco). |

## Tarjetas SVG de mina

Cada medida devuelve un SVG como data URI (`dataCategory: ImageUrl`) que una visual de tabla pinta como imagen. Las tres tarjetas bullet salen de `generador/tarjetas_svg.py`.

| Medida | Tabla | Qué devuelve |
|---|---|---|
| `Rd Frag Tabla CAEX` | `dax_kpi_tabla` | Fragmento SVG con la tabla real y plan bajo la cascada de la flota CAEX. |
| `Rd Frag Tabla Carguío` | `dax_kpi_tabla` | Fragmento SVG con la tabla real y plan bajo la cascada de la flota de carguío. |
| `Rd SVG Bullet Fase` | `dax_kpi_tabla` | Barras bullet por fase: real, proyección y plan del día. |
| `Rd SVG Cascada CAEX` | `dax_kpi_tabla` | Cascada plan semanal a real de la flota CAEX: disponibilidad, UEBD, rendimiento y horas nominales. |
| `Rd SVG Cascada Carguío` | `dax_kpi_tabla` | Cascada plan semanal a real de la flota de carguío. |
| `Rd SVG Ampliacion` | `dax_kpi_tabla` | Tarjeta SVG (data URI) para una visual de tabla con imagen. |
| `Rd SVG Movimiento` | `dax_kpi_tabla` | Tarjeta SVG (data URI) para una visual de tabla con imagen. |
| `Rd SVG Plan Movimiento` | `dax_kpi_tabla` | Tarjeta SVG (data URI) para una visual de tabla con imagen. |
| `Rd SVG Remanejo` | `dax_kpi_tabla` | Tarjeta SVG (data URI) para una visual de tabla con imagen. |
| `Rd SVG Tarjeta Destino` | `dax_kpi_tabla` | Tarjeta por destino (chancado, dump leach, botadero, stock): real, proyección y plan. |

## Ventana del día de planta

El día de planta va de 07:00 a 07:00. Su inicio y fin se detectan por la caída del acumulador diario de alimentación al SAG; si hay cierre oficial publicado se usa, y si no, se calcula desde el historiador de proceso.

| Medida | Tabla | Qué devuelve |
|---|---|---|
| `Rd Planta Cierre Horas Efectivas` | `dax_planta_dia` | Horas efectivas del SAG en el día de planta: cierre publicado o, si falta, muestras con alimentación sobre 100 t/h. |
| `Rd Planta Cierre Oficial` | `dax_planta_dia` | Verdadero si el cierre diario oficial de planta ya está publicado para el día. |
| `Rd Planta Cierre Toneladas` | `dax_planta_dia` | Toneladas procesadas por el SAG en el día de planta: cierre publicado o, si falta, acumulado del historiador. |
| `Rd Planta Cierre TPH` | `dax_planta_dia` | Rendimiento (t/h) del cierre diario; si no está publicado, cálculo desde el historiador. |
| `Rd Planta Día` | `dax_planta_dia` | Día de planta (inicio a la hora de reinicio del acumulador diario) elegido o en curso. |
| `Rd Planta Fin` | `dax_planta_dia` | Fin de la ventana del día de planta. |
| `Rd Planta Hist Horas Efectivas` | `dax_planta_dia` | Horas efectivas del SAG desde el historiador: media hora por cada muestra sobre 100 t/h. |
| `Rd Planta Hist Procesado` | `dax_planta_dia` | Toneladas del acumulador diario del SAG en la última muestra de la ventana, desde el historiador. |
| `Rd Planta Hora Reset` | `dax_planta_dia` | Hora local en que se reinicia el acumulador diario (parámetro calculado; 6 si no se detecta). |
| `Rd Planta Horas` | `dax_planta_dia` | Horas de la ventana del día de planta (máximo 24). |
| `Rd Planta Inicio` | `dax_planta_dia` | Inicio de la ventana del día de planta, detectado por la caída del acumulador diario del SAG. |
| `Rd Planta Último TS` | `dax_planta_dia` | Marca de tiempo de la última muestra válida de alimentación al SAG. |

## Valores de planta por fecha

Con la vista en línea devuelven el último dato del historiador; con un día de planta cerrado devuelven el cierre o el promedio de la ventana del día.

| Medida | Tabla | Qué devuelve |
|---|---|---|
| `Valor_Finos` | `dax_kpi_tabla` | Porcentaje de finos de la correa de alimentación al SAG; solo muestras con el SAG cargado (más de 1.000 t/h). |
| `Valor_Mantencion_Dia` | `equipos_df_ue` | DF o UE del día de planta (promedio por área), según el filtro de medición. |
| `Valor_P80` | `dax_kpi_tabla` | P80 de la molienda (µm): último valor en línea, promedio del día de planta si está cerrado. |
| `Valor_Pebble` | `dax_kpi_tabla` | Retorno de pebbles (t/h) en las muestras con el SAG operando. |
| `Valor_PlanMesProcesadoAcumulado` | `dax_kpi_tabla` | Valor de planta por fecha: en línea, el último dato del historiador; en día cerrado, el cierre del día de planta. |
| `Valor_ProcesadoSAGAcumulado` | `dax_kpi_tabla` | Valor de planta por fecha: en línea, el último dato del historiador; en día cerrado, el cierre del día de planta. |
| `Valor_SPI` | `dax_kpi_tabla` | Dureza SPI (minutos): último valor de la ventana en línea, promedio del día de planta si está cerrado. |
| `Valor_Stockpile` | `dax_kpi_tabla` | Nivel del stockpile de gruesos (%): último valor en línea, última muestra válida del día si está cerrado. |
| `Valor_TChancadoProyectado` | `dax_kpi_tabla` | Valor de planta por fecha: en línea, el último dato del historiador; en día cerrado, el cierre del día de planta. |
| `Valor_TPHChancado` | `dax_kpi_tabla` | Valor de planta por fecha: en línea, el último dato del historiador; en día cerrado, el cierre del día de planta. |
| `Valor_TPHChancadoAcumulado` | `dax_kpi_tabla` | Valor de planta por fecha: en línea, el último dato del historiador; en día cerrado, el cierre del día de planta. |
| `Valor_TPHSAG` | `dax_kpi_tabla` | Rendimiento del SAG (t/h): último dato en línea; en día cerrado, el cierre oficial o el promedio con el SAG operando. |
| `Valor_TPHSAGPMES` | `dax_kpi_tabla` | Valor de planta por fecha: en línea, el último dato del historiador; en día cerrado, el cierre del día de planta. |

## Estado de equipos y señales

`Rd Pl Estados` empaca el estado de 13 equipos on/off en un texto (1 operando, 0 detenido, 2 sin señal) y `Rd Pl Válvulas` las válvulas abiertas de las 4 baterías de ciclones; así una sola medida alimenta a todas las tarjetas.

| Medida | Tabla | Qué devuelve |
|---|---|---|
| `Rd Pl Estados` | `dax_kpi_tabla` | Estado de los 13 equipos on/off de planta, un carácter por equipo: 1 operando, 0 detenido, 2 sin señal. |
| `Rd Pl Vivo` | `dax_kpi_tabla` | Verdadero en vista en línea (sin fecha elegida o fecha en curso); falso para un día de planta cerrado. |
| `Rd Pl Válvulas` | `dax_kpi_tabla` | Válvulas abiertas de las 4 baterías de ciclones, como texto v1|v2|v3|v4. |

## Planes y calidad de planta

Planes de dureza, P80, nivel y pebbles; DF y UE de las baterías de ciclones; consumo específico del SAG.

| Medida | Tabla | Qué devuelve |
|---|---|---|
| `Rd Ciclones DF Día` | `dax_kpi_tabla` | Disponibilidad física del día de planta, promedio de las 4 baterías de hidrociclones. |
| `Rd Ciclones Plan P80` | `dax_kpi_tabla` | Plan de P80 (µm) del día de planta; vacío si no hay plan. |
| `Rd Ciclones UE Día` | `dax_kpi_tabla` | Utilización efectiva del día de planta, promedio de las 4 baterías de hidrociclones. |
| `Rd Pebbles Plan TPH` | `dax_kpi_tabla` | Plan de pebbles (t/h): plan semanal del SAG por la carga circulante objetivo (20 %). |
| `Rd SAG kWh t` | `dax_kpi_tabla` | Consumo específico del SAG del día de planta: kWh por tonelada alimentada (muestras con SAG cargado). |
| `Rd SAG Plan SPI` | `dax_kpi_tabla` | Plan de dureza SPI (minutos) del día de planta. |
| `Rd Stockpile Plan Nivel` | `dax_kpi_tabla` | Meta de nivel del stockpile (%): constante del modelo. |
| `Rd Stockpile Tendencia` | `dax_kpi_tabla` | Variación del nivel del stockpile: %/h en línea (medianas de muestras recientes), puntos del día si está cerrado. |

## Sinópticos y tarjetas SVG de planta

Un sinóptico (diagrama del circuito con el estado de cada equipo) y una tarjeta de indicadores por etapa: chancado, stockpile, SAG, pebbles, bolas y ciclones.

| Medida | Tabla | Qué devuelve |
|---|---|---|
| `Rd SVG Sinóptico Bolas` | `dax_kpi_tabla` | Sinóptico SVG de Bolas: equipo coloreado según su estado y valor real contra plan. |
| `Rd SVG Sinóptico Chancado` | `dax_kpi_tabla` | Sinóptico SVG de Chancado: equipo coloreado según su estado y valor real contra plan. |
| `Rd SVG Sinóptico Ciclones` | `dax_kpi_tabla` | Sinóptico SVG de Ciclones: equipo coloreado según su estado y valor real contra plan. |
| `Rd SVG Sinóptico Pebbles` | `dax_kpi_tabla` | Sinóptico SVG de Pebbles: equipo coloreado según su estado y valor real contra plan. |
| `Rd SVG Sinóptico SAG` | `dax_kpi_tabla` | Sinóptico SVG de SAG: equipo coloreado según su estado y valor real contra plan. |
| `Rd SVG Sinóptico Stockpile` | `dax_kpi_tabla` | Sinóptico SVG de Stockpile: equipo coloreado según su estado y valor real contra plan. |
| `Rd SVG Tarjeta Bolas` | `dax_kpi_tabla` | Tarjeta SVG de Bolas: estado del equipo, DF y UE del día y valor real contra plan. |
| `Rd SVG Tarjeta Chancado` | `dax_kpi_tabla` | Tarjeta SVG de Chancado: estado del equipo, DF y UE del día y valor real contra plan. |
| `Rd SVG Tarjeta Ciclones` | `dax_kpi_tabla` | Tarjeta SVG de Ciclones: estado del equipo, DF y UE del día y valor real contra plan. |
| `Rd SVG Tarjeta Pebbles` | `dax_kpi_tabla` | Tarjeta SVG de Pebbles: estado del equipo, DF y UE del día y valor real contra plan. |
| `Rd SVG Tarjeta SAG` | `dax_kpi_tabla` | Tarjeta SVG de SAG: estado del equipo, DF y UE del día y valor real contra plan. |
| `Rd SVG Tarjeta Stockpile` | `dax_kpi_tabla` | Tarjeta SVG de Stockpile: estado del equipo, DF y UE del día y valor real contra plan. |

## Encabezado y pulso

Recuadro de última actualización, leyenda de la ventana de planta y la medida del pulso para el refresco automático de página.

| Medida | Tabla | Qué devuelve |
|---|---|---|
| `Rd Pulso Ahora` | `Rd Pulso` | Hora de servidor de la fuente de pulso; permite el refresco automático de página con DirectQuery. |
| `Rd SVG Última Actualización` | `dax_kpi_tabla` | Recuadro de encabezado con la hora de la última actualización del modelo. |
| `Rd Ventana Planta` | `dax_kpi_tabla` | Leyenda de la ventana del día de planta (07:00 a 07:00). |
