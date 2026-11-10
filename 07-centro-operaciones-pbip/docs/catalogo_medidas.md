# Catálogo de medidas

122 medidas agrupadas por familia. Definiciones comunes (horas del hecho `Fact_HorasEquipo`, por tipo de equipo):

- **DF (disponibilidad física)** = horas disponibles / horas nominales.
- **UEBD (utilización efectiva sobre la disponibilidad)** = horas efectivas / horas disponibles. `UE CAEX` es la misma razón con otro nombre.
- **Utilización** = horas operativas / horas disponibles.
- **Rendimiento** = toneladas (o metros en perforación) por hora efectiva.
- **Cumplimiento** = real / plan.
- **Semáforo**: verde `#00C853` si el real alcanza el plan, rojo `#FF5C5C` si no, gris si falta el plan o el real. Las filas «Plan» de las matrices van en gris pizarra.

Las medidas marcadas con (oculta) son auxiliares del modelo. Los tipos de equipo del dato son `Truck`, `Shovel`, `Loader` y `Drill`.

## 1. Flota y equipos en operación

| Medida | Tabla | Qué calcula |
|---|---|---|
| Flota CAEX Total | Dim_Equipo | Camiones distintos presentes en `Fact_HorasEquipo`. |
| Flota Palas Total, Flota Perforadoras Total, Flota Cargadores Total | Dim_Equipo | Equipos activos para KPI (`Activo_KPI = 1`) de cada tipo. |
| Flota CAEX Muro Total, Flota Pala Muro Total, Flota Cargador Muro Total | Dim_Equipo | Equipos de cada tipo con sufijo `_M`. |
| Camiones Operando, Palas Operando, Perforadoras Operando, Cargadores Operando | Fact_HorasEquipo | Equipos distintos con horas operativas > 0 en el contexto. |
| Camiones, Palas, Perforadoras, Cargadores | Fact_HorasEquipo | Texto «operando / total» para las tarjetas «Equipos en uso». |
| Camiones Operando Muro, Palas Operando Muro, Cargadores Operando Muro | Fact_HorasEquipo_Muro | Igual que arriba para Muro; devuelven 0 en vez de blanco. |
| Camiones Muro, Palas Muro, Cargadores Muro | Fact_HorasEquipo_Muro | Texto «operando / total» de Muro. |

## 2. Flota Mina: disponibilidad, uso y rendimiento (real)

| Medida | Tabla | Qué calcula |
|---|---|---|
| Disponibilidad CAEX, UEBD CAEX, UE CAEX, Utilizacion CAEX | Fact_HorasEquipo | DF, UEBD y utilización de los camiones. |
| Rendimiento CAEX | Fact_HorasEquipo | Movimiento total / horas efectivas de los camiones (t/h). |
| Disponibilidad Pala, UEBD Pala, Rendimiento Pala | Fact_HorasEquipo | Lo mismo para las palas (tonelaje cargado por hora efectiva). |
| Disponibilidad Carguio, UEBD Carguio, Utilizacion Carguio, Rendimiento Carguio t/h | Fact_HorasEquipo | Palas y cargadores juntos. |
| Disponibilidad Perforadoras, UEBD Perforadoras, Rendimiento Perforadoras | Fact_HorasEquipo | Perforadoras; el rendimiento es en metros por hora efectiva. |
| Tonelaje Total Turno | Fact_HorasEquipo | Toneladas descargadas por los camiones en el contexto (turno, hora o día). |

## 3. Plan

| Medida | Tabla | Qué calcula |
|---|---|---|
| Disponibilidad CAEX Plan, UEBD CAEX Plan, Rendimiento CAEX Plan | Plan_CAEX | Razones del plan de camiones, con la misma definición que el real. |
| Plan Mov Total Dia | Plan_CAEX | Toneladas planificadas del día efectivo (`Fecha_Efectiva`). |
| Disponibilidad Carguio Plan, UEBD Carguio Plan, Utilizacion Carguio Plan, Rendimiento Carguio Plan | Plan_Carguio | Plan de carguío agregado solo para los equipos visibles (`TREATAS`). |
| Disponibilidad Pala Plan, UEBD Pala Plan, Rendimiento Pala Plan | Plan_Carguio | Plan de las palas (equipos cuyo nombre empieza con «P»). |
| Disponibilidad Perforadoras Plan, UEBD Perforadoras Plan, Rendimiento Perforadoras Plan | Plan_Perforadoras | Plan de perforación para los equipos visibles. |
| Plan Disponibilidad CAEX Muro, Plan UEBD CAEX Muro, Plan Rendimiento CAEX Muro | Plan_Muro | Promedio del valor diario de cada punto del plan de Muro (camiones). |
| Plan Disponibilidad Pala Muro, Plan UEBD Pala Muro, Plan Rendimiento Pala Muro | Plan_Muro | Ídem para la pala de Muro. |

## 4. Cumplimiento

| Medida | Tabla | Qué calcula |
|---|---|---|
| Disponibilidad CAEX Cumplimiento, UEBD CAEX Cumplimiento, Rendimiento CAEX Cumplimiento | Fact_HorasEquipo | Real / plan de los camiones. |

## 5. Selectores de matriz (real y plan en una sola medida)

| Medida | Tabla | Qué calcula |
|---|---|---|
| Valor Flota, Color Valor Flota | Dim_Flota_Tipo | Valor y color de la matriz «Resumen flota Mina»: elige la medida real o plan según flota (CAEX, PALA, PERFO), métrica y tipo. |
| Valor Flota Muro, Color Valor Flota Muro | Dim_Flota_Tipo | Lo mismo para Muro (CAEX y PALA). |
| Valor Carguio, Color Valor Carguio | Dim_Metrica_Carguio | Matriz «Equipo carguío Mina», una fila por pala o cargador. |
| Valor Carguio Muro, Color Valor Carguio Muro | Dim_Metrica_Carguio | Matriz «Carguío Muro»; en blanco si el equipo no tuvo horas ese día. El plan existe solo para la pala. |
| Valor Perforadoras, Color Valor Perforadoras | Dim_Metrica_Perforadoras | Matriz «Perforadoras». |

## 6. Semáforos y colores

| Medida | Tabla | Qué calcula |
|---|---|---|
| Color Disponibilidad CAEX, Color UEBD CAEX, Color Rendimiento CAEX | Fact_HorasEquipo | Verde si el real alcanza el plan; rojo si no. |
| Color Disponibilidad Carguio, Color UEBD Carguio, Color Utilizacion Carguio, Color Rendimiento Carguio | Fact_HorasEquipo | Verde o gris pizarra (sin rojo: el carguío depende del acarreo). |
| Color Disponibilidad Perforadoras, Color UEBD Perforadoras, Color Rendimiento Perforadoras | Fact_HorasEquipo | Verde o gris pizarra. |
| Color_Tonelaje_Turno, Color_Tonelaje_Chancado | Fact_HorasEquipo | Verde o rojo al comparar con el plan del día; gris claro si falta alguno. |
| Color_Disp_CAEX, Color_UE_CAEX, Color_Utilizacion_CAEX | Fact_HorasEquipo | Verde si el real supera un umbral fijo (85 %, 75 % y 85 %, valores de ejemplo). Ningún visual las usa hoy. |
| Color_Ley_Alimentacion | Fact_Chancado | Verde o rojo según la ley contra su plan. |

## 7. Chancado y ley

| Medida | Tabla | Qué calcula |
|---|---|---|
| Tonelaje Chancado | Fact_Chancado | Toneladas enviadas a chancado. |
| Ley Alimentacion | Fact_Chancado | Ley CuT ponderada por tonelaje. |
| Plan Ley Alimentacion | Fact_Chancado | Ley planificada del día efectivo. |
| Plan_Chancado_Dia, Plan_Chancado_Hora | Fact_ChancadoOrigen_Hora | Plan diario de chancado y su reparto por hora (día / 24; en blanco en las casillas de relleno). |
| Toneladas_Chancado_Hora | Fact_ChancadoOrigen_Hora | Toneladas de la hora del turno que muestra el eje (promedio entre los turnos visibles); sin hora en contexto, el total del día. |
| Ley Alimentacion Blast | Fact_LeyAlimentacion_Hora | Ley ponderada por tronadura y hora. |
| Ley Alimentacion Etiqueta (oculta) | Fact_LeyAlimentacion_Hora | Muestra la ley solo cuando cambia respecto de la hora anterior. |

## 8. Proyección

| Medida | Tabla | Qué calcula |
|---|---|---|
| Horas Dia Con Datos | Fact_HorasEquipo | Horas del día operacional con movimiento de camiones > 0. |
| Proyeccion Mov Mina | Fact_HorasEquipo | Movimiento acumulado / horas con datos × 24. |
| Proyeccion Ampliacion | Fact_HorasEquipo | Igual, solo con el material extraído (sin remanejo). |

## 9. Muro

| Medida | Tabla | Qué calcula |
|---|---|---|
| Disponibilidad CAEX Muro, UEBD CAEX Muro, Rendimiento CAEX Muro | Fact_HorasEquipo_Muro | Camiones de Muro. |
| Disponibilidad Pala Muro, UEBD Pala Muro, Rendimiento Pala Muro | Fact_HorasEquipo_Muro | Palas de Muro. |
| Disponibilidad Carguio Muro, UEBD Carguio Muro, Rendimiento Carguio Muro t/h | Fact_HorasEquipo_Muro | Palas y cargadores de Muro. |
| Material Muro | Fact_HorasEquipo_Muro | Movimiento total de Muro; alimenta el gráfico por hora. |

## 10. Ciclos de acarreo

| Medida | Tabla | Qué calcula |
|---|---|---|
| Tiempo Ciclo Promedio Min | Fact_Ciclos | Promedio de (viaje vacío + espera + carga + viaje cargado + cola + descarga) en minutos. |
| Tiempo Ciclo Ultima Hora | Fact_Ciclos | Mismo promedio, solo los ciclos de la última hora con datos. |
| Desviacion Ciclo Minutos | Fact_Ciclos | Última hora menos promedio (positivo = el ciclo se alargó). |
| Destino Actual | Fact_Ciclos | Destino del ciclo más reciente de cada pala o cargador. |

## 11. GPS y velocidad

| Medida | Tabla | Qué calcula |
|---|---|---|
| Mostrar Punto GPS (oculta) | Fact_GPS | 1 si el punto debe dibujarse: la hora elegida o, sin elección, la última hora con datos del día. |
| Velocidad CAEX en Contexto (oculta) | Fact_VelocidadCAEX_Hora | Velocidad promedio de las lecturas en movimiento (> 0 km/h). |
| Velocidad Promedio CAEX Turno | Fact_VelocidadCAEX_Hora | Lo anterior para el último turno con datos del día, o el turno u hora elegidos. |
| Velocidad CAEX Turno A, Velocidad CAEX Turno B | Fact_VelocidadCAEX_Hora | Texto con la velocidad de cada turno; un guion si aún no tiene datos. |

## 12. Tiempo y encabezado

| Medida | Tabla | Qué calcula |
|---|---|---|
| Fecha_Efectiva | Dim_Tiempo | Fecha del segmentador si hay una sola; si no, el día operacional en curso. |
| Fecha_Operacional_Actual | Dim_Tiempo | Mayor fecha marcada como día en curso. |
| Fecha_Con_Datos (oculta) | Dim_Tiempo | 1 si la fecha tiene datos de mina o de chancado; filtra el segmentador. |
| Fecha_Pantalla | Dim_Tiempo | Fecha en texto («sábado, 31 de mayo de 2025»). |
| Ultima_Actualizacion | Dim_Actualizacion | Hora del último refresco en HH:MM. |
| SVG_Ultima_Actualizacion | Dim_Actualizacion | Recuadro SVG del encabezado; antepone la fecha si el refresco no es de hoy. |

## Medidas que no usa ningún visual

20 medidas quedan disponibles para otros informes y no las usa la página actual (`python herramientas/verificar_modelo.py` las lista): cumplimientos, varios
semáforos de camiones y carguío, `Fecha_Pantalla` y `Ultima_Actualizacion`, entre otras.
