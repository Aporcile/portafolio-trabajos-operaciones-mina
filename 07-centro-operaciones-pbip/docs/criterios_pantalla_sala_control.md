# Criterios de diseño para una pantalla de sala de control

El informe está pensado para una TV de 1920 × 1080 que se mira a varios metros de distancia, las 24 horas, sin que nadie la toque. Esos tres supuestos
(distancia, continuidad y cero interacción) explican casi todas las decisiones de diseño.

## Lienzo y composición

- **Página de 2740 × 1440 px** con `FitToPage`: Power BI la escala al televisor, y el área útil es mayor que la de una página estándar para caber el resumen
  de mina, el de Muro, el mapa y los gráficos horarios sin scroll.
- **Sin panel de filtros ni cabecera de visual.** El panel lateral está oculto (`outspacePane`) y el único control visible es el segmentador de día.
- **Lectura en Z**: arriba el encabezado (logo, título, última actualización, día); debajo una banda de tarjetas con lo que se mira primero (equipos en uso,
  velocidad, movimiento y chancado contra plan, ley); luego tres columnas: flota Mina a la izquierda, mapa y gráficos por hora al centro, ciclos y Muro a la derecha.
- **Una idea por bloque**, con título propio en mayúsculas dentro de una banda de color. Los bloques tienen el mismo borde redondeado y el mismo
  espaciado, así el ojo reconoce las tarjetas antes de leerlas.

## Tipografía y tamaños

- Cifras en **Segoe UI Semibold** (la fija el tema): 22 pt en las tarjetas principales (movimiento, chancado, proyecciones, ley) y 15 pt en las de
  equipos en uso; títulos de bloque en 14 pt en negrita.
- Valores y plan en la misma tarjeta: el real en grande y el plan debajo, en gris pizarra, para comparar sin buscar.
- Los textos largos se evitan: el título dice qué es («PROYECCIÓN MOV TOTAL MINA (kt)») y la unidad va en el título, no en cada valor.
- Las toneladas de las tarjetas se muestran en miles de t (`#,0.0," kt"`): menos dígitos, lectura más rápida.

## Color con significado

| Uso | Color | Contraste sobre el fondo |
|---|---|---|
| Fondo de página | `#0F1A2C` (azul medianoche más oscuro) | — |
| Tarjetas y bandas de título | `#1B2A41` (azul medianoche) | — |
| Cifras y texto principal | `#E6ECF2` | 14,6 : 1 sobre el fondo, 12,1 : 1 sobre la tarjeta |
| Títulos y acentos | `#8EC5F2` (tinte del azul cielo `#4F9DDE`) | 7,9 : 1 sobre la tarjeta |
| Plan, referencias, ejes | `#8FA3B8` (gris pizarra) | 6,7 : 1 sobre el fondo |
| Cumple el plan | `#00C853` (verde) | 7,8 : 1 sobre el fondo |
| No cumple | `#FF5C5C` (rojo) | 5,8 : 1 sobre el fondo |

- **Solo el semáforo usa verde y rojo.** Las series de los gráficos usan la paleta de marca (azul cielo, violeta, azul acero, rosa palo, verde salvia), de modo que
  un verde o un rojo en pantalla siempre quiere decir «cumple» o «no cumple».
- Todos los pares de texto cumplen un contraste de al menos 4,5 : 1 (los de lectura principal superan 7 : 1).
- **El color lo decide el modelo**: las medidas `Color_*` devuelven el color en texto y el visual solo lo aplica. Si cambia la regla del semáforo,
  cambia en un lugar.
- **Sin plan, sin juicio**: en varias medidas, si falta el plan o el real, la cifra se muestra en gris en vez de verde o rojo, para no afirmar lo que no se sabe.

## Cero interacción

- **Sin filtros cruzados entre bloques**: las interacciones entre las matrices de flota, las tarjetas y el mapa están en «sin filtro»; la única que filtra es el
  gráfico de movimiento por hora de Mina hacia el mapa (para ver la posición de los camiones de una hora). Un clic accidental no puede dejar la pantalla en un estado raro.
- **El día se mueve solo.** El segmentador guarda el texto «Dia actual» y el calendario marca el día operacional en curso, así que al refrescar tras las 08:00
  la pantalla pasa de día sin intervención.
- **«Última hora con datos» por defecto**: el mapa y la velocidad promedio muestran la última hora o el último turno con datos del día, sin que el operador
  elija nada.
- **Mismo estado inicial**: el segmentador viene predefinido en «Dia actual» y el panel de filtros está oculto, de modo que el informe abre siempre igual.

## Confianza en el dato

- **Última actualización visible.** Un recuadro en el encabezado muestra la hora del último refresco; si no es de hoy, antepone la fecha. Si el refresco se detiene,
  la hora queda congelada y se nota a simple vista. La marca se captura en Power Query (no con `NOW()` en DAX, que daría siempre la hora actual).
- **Proyección a 24 horas** junto al acumulado, para saber si el día va a cerrar sobre o bajo el plan antes de que termine.
- **Real y plan lado a lado** en todas las matrices; el plan nunca se muestra solo.
- **Horas vacías explícitas**: el eje de los gráficos horarios deja un hueco visible entre el turno A y el B, y las horas sin dato aparecen vacías, no interpoladas.

## Cadencia de actualización

Se recomienda refrescar el modelo cada 30 minutos (o conectar la fuente por DirectQuery y usar el refresco automático de página, que necesita una capacidad
dedicada). Con datos sintéticos fijos el informe no cambia entre refrescos: la hora de actualización y el «día actual» salen de los parámetros `FechaReferencia` y
`RutaDatos` (ver `docs/arquitectura_modelo.md`).

## Lista de comprobación antes de publicar una pantalla

1. Abrir el informe a 1920 × 1080 y mirarlo a 3 metros: ¿se lee el valor de cada tarjeta?
2. Cada color verde o rojo, ¿viene de un semáforo?
3. ¿Hay alguna interacción que deje la pantalla en un estado distinto al inicial?
4. ¿Se ve la hora de la última actualización y se nota que cambia (con fecha) cuando el dato es antiguo?
5. ¿El texto de cada título dice qué es y en qué unidad?
