# Catálogo de indicadores y fórmulas

## Árbol de tiempos de un equipo
```
Horas nominales (HN)  = horas del turno × equipos en flota
 ├─ Mantención programada + no programada          → explica la disponibilidad
 └─ Horas disponibles (HD)
     ├─ Horas efectivas (HE)
     └─ Demora programada + demora no programada + reserva + PO espera + PO cola   → explica la UEBD
```

## Indicadores base
| Indicador | Fórmula | Unidad |
|---|---|---|
| **DF** (disponibilidad física) | `HD / HN` | % |
| **UEBD** (utilización efectiva de las horas disponibles) | `HE / HD` | % |
| **Rendimiento efectivo** | `Movimiento total / HE` | t/h |
| **Factor de carga** | promedio del payload de las cargas completas (entre 200 y 330 t) | t por carga |
| **CAEX en flota** | `HN / (24 × días)` | equipos |
| **OEE** | `DF × UEBD × (rendimiento real / rendimiento plan)` | % |

El plan sigue las mismas fórmulas con las horas y toneladas del plan (`DF plan = HD plan / HN plan`, etc.).
El OEE del plan es `DF plan × UEBD plan` (el rendimiento del plan es la base y vale 1).

## Cascada del plan al real
Se cambia **una palanca a la vez**; la suma de las cuatro pérdidas (o ganancias) cierra exactamente el real.

```
Plan            = HN plan × DF plan × UEBD plan × Rend plan         (= toneladas del plan)
Pérdida DF      = HN plan × (DF real − DF plan) × UEBD plan × Rend plan
Pérdida UEBD    = HN plan × DF real × (UEBD real − UEBD plan) × Rend plan
Pérdida Rend    = HN plan × DF real × UEBD real × (Rend real − Rend plan)
Pérdida HN      = (HN real − HN plan) × DF real × UEBD real × Rend real
Real            = Plan + Pérdida DF + Pérdida UEBD + Pérdida Rend + Pérdida HN
```
La medida oculta `Control cascada` calcula `Plan + pérdidas − Real` y debe dar 0 (`dax/validar_cascada.dax`). Una palanca cuya
pérdida supera el 0,1 % del plan de toneladas se marca en rojo y es el foco de la reunión; la minuta detalla solo esas.

## Semáforo (regla común de la app y del informe)
| Color | Condición |
|---|---|
| Verde | real ≥ plan (en el informe, desde el 99,9 % del plan para absorber decimales) |
| Naranjo | real ≥ 95 % del plan |
| Rojo | real bajo el 95 % del plan |
| Azul / gris | sin plan |

## Periodos
La reunión es los lunes y los periodos van hasta ayer (el día operacional va de 08:00 a 08:00).

| Periodo | Ventana | Plan |
|---|---|---|
| SEMANAL | de lunes a ayer; el lunes de la reunión, la semana completa | semanal (`Plan_CAEX`), día a día |
| JUE-DOM | último jueves a domingo, sin pasar de ayer | los mismos días del plan semanal |
| MENSUAL | del día 1 del mes a ayer; el primer lunes del mes, el mes anterior completo | mensual (`Planes_Mina`), día a día |

Si a algún día del periodo le falta el plan semanal, SEMANAL y JUE-DOM quedan «sin plan en n de m días» en vez de comparar un plan
incompleto con el real completo.

## Catálogo de la app (13 indicadores)
La app conserva un catálogo numerado (`RD_KPI`, JSON por semana con real, plan, semana anterior, mes y jueves a domingo). El modelo de
`pbip/` implementa los de la flota CAEX (1, 2, 3, 4 y 6); el resto queda como definición.

| N.º | Área | Indicador | Unidad | Definición | Rango de ejemplo |
|---|---|---|---|---|---|
| 1 | Mina | Extracción total mina | t | movimiento total de los CAEX contra el plan semanal | 150-260 kt/día |
| 2 | CAEX | DF | % | `HD / HN` | 82-94 % |
| 3 | CAEX | UEBD | % | `HE / HD` | 70-85 % |
| 4 | CAEX | Rendimiento | t/h | `Movimiento / HE` | ~480 t/h |
| 5 | CAEX | Velocidad prom. | km/h | promedio entre los turnos A y B; sin plan | 15-30 km/h |
| 6 | CAEX | Factor de carga | t/carga | payload promedio de cargas completas | ~270 t |
| 7-9 | Pala | DF, UEBD, Rendimiento | %, %, t/h | igual que CAEX | |
| 10-12 | Perforación | DF, UEBD, Rendimiento | %, %, m/h | igual que CAEX con metros | |
| 13 | Perforación | Metros perforados | m | suma de metros contra el plan semanal | |
