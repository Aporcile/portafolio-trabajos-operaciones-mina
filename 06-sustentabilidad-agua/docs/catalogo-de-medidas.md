# Catálogo de medidas por familia

Todas las medidas viven en la tabla `Medidas` y se ordenan en carpetas (`displayFolder`). Convenciones: sufijo `cod` = estado
numérico, sin sufijo = texto para mostrar, `Color ...` = color hex para formato condicional, `KPI ...` = texto de tarjeta,
`Sem ...` = semáforo por sistema.

| Carpeta | Medidas | Qué resuelve | Medidas clave |
|---|---:|---|---|
| 0 Parámetros | 27 | Lee umbrales de `Config` (siempre de ejemplo) y el modo de datos. | `Ahora`, `Modo historiador`, `Cupo captacion`, `pH minimo`, `Horas para congelado` |
| 1 Base | 22 | Último valor, antigüedad del dato, deltas y series suavizadas para gráficos. | `Valor actual`, `Ultima marca`, `Delta 7 d`, `Serie 72 h` |
| 2 Recuperación | 37 | Pozos de agua recuperada: estado, caudal, corriente, horas detenidas y detención más larga. | `Estado pozo cod`, `Caudal Norte (L/s)`, `Horas detenidas 7 d`, `Caudal recuperada total` |
| 3 Estanques | 26 | Nivel frente a HI/HH, tendencia en %/h y tiempo estimado a HH. | `Estado estanque cod`, `Tasa estanque (%/h)`, `Horas a HH` |
| 4 Agua fresca | 30 | Captación, cupo mensual, volumen del mes y proyección al cierre; piezómetros. | `Caudal pozo`, `% cupo pozo`, `Proyeccion mes (m3)`, `Delta 7 d piezometro` |
| 5 Calidad | 27 | pH, conductividad y turbidez en línea; sólidos suspendidos de laboratorio. | `Estado calidad cod`, `Turbidez actual`, `Estado SST cod` |
| 6 Datos | 18 | Calidad del dato: señales con dato, congeladas o atrasadas, por fuente. | `Tag congelado`, `% tags con dato`, `Estado fuente cod` |
| 7 Alarmas | 14 | Motor único de alarmas por activo (severidad, condición, desde, duración). | `Alarma severidad`, `Alarma condicion`, `Alarma duracion` |
| 8 Tranques | 27 | Tranques y pozas: nivel, HI/HH, fuga, bombas y tiempo a HH. | `Estado tranque cod`, `Rebalse texto`, `Poza emergencia texto` |
| 9 Aguas abajo | 14 | Pozos de monitoreo: profundidad y subida del nivel freático en 7 días. | `Ascenso 7 d (m)`, `Estado aguas abajo cod` |
| 10 Energía y reporte | 40 | Comunicación por estación, posible corte de energía, UPS, baterías y envíos a portales. | `Estacion sin comunicacion`, `Posible corte energia`, `Estado UPS cod` |
| 11 Semáforos | 26 | Un semáforo por sistema (10 sistemas) con estado, color y detalle. | `Sem cod`, `Sem color`, `Sem detalle` |
| 12 Balance | 30 | Balance hídrico diario, ventanas de 7 y 30 días, recirculación y cierre. | `Vol agua total`, `Recirculacion %`, `Cierre balance %`, `Consumo 30 d (m3)` |

## Patrones DAX que se repiten

- **Último valor por señal**: `SUMX(VALUES(Tags[Tag]), CALCULATE(MAX(Mediciones[Valor]), Mediciones[FechaHora] = última))`.
- **Estado por activo**: `SWITCH(TRUE(), sin dato, 4, congelado, 5, sobre HH, 3, sobre HI, 2, 1)`; los números se traducen a
  texto y color con medidas gemelas.
- **Alarmas por tipo de activo**: `Alarma severidad` y `Alarma condicion` hacen `SWITCH` sobre `Activos[Tipo]` y reutilizan el
  estado de cada familia; si toda una estación pierde comunicación queda una sola alarma.
- **Ventanas del balance**: `CALCULATE([medida], FILTER(ALL(BalanceDiario[Fecha]), BalanceDiario[Fecha] > [Fecha corte balance] - n))`.
- **Semáforo**: verde normal, naranjo alerta, rojo crítico, gris sin dato; las reglas son genéricas (límites de ejemplo).
