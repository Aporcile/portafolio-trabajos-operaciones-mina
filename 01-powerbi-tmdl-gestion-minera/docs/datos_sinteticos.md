# Datos sintéticos

Todos los datos del proyecto son inventados y salen de `datos_sinteticos/generar_datos.py`, que usa `tools/sinteticos.py` (semilla fija: dos ejecuciones
dan archivos idénticos). No hay registros reales, ni equipos, ni personas, ni fechas de operación real.

```text
python datos_sinteticos/generar_datos.py     # regenera los 21 CSV (unos 5 MB en total, ninguno sobre 2 MB)
```

## Periodo y hora de actualización

- 90 días de mina desde **2025-03-03** (hasta 2025-05-31).
- La hora simulada de la última actualización es **2025-05-31 14:30** (`actualizacion.csv`): el último día de mina (08:00 a 08:00) y el último día de planta
  (07:00 a 07:00) están **en curso**, así que las tarjetas muestran proyección a 24 h y vista en línea.
- Las series del historiador (`hist_*`) cubren solo los últimos 46 días, como los 45 días que muestran los segmentadores.

## Rangos

| Magnitud | Rango |
|---|---|
| Movimiento de mina | 150 a 260 miles de t por día |
| Velocidad de CAEX | 15 a 30 km/h (cargado 15-24, vacío 22-30), solo en `ciclos_caex.csv` |
| DF (disponibilidad física) | 82 a 94 % |
| UEBD / UE (utilización) | 70 a 85 % |
| Alimentación a chancado | 3.200 a 4.800 t/h |
| Alimentación al SAG | alrededor de 3.500 a 4.100 t/h por día, con paradas esporádicas |
| Finos de la correa de alimentación | fracción fina ~60 % (granulometría 60/20/20 en tres fracciones) |
| Flota | `CAEX-01` a `CAEX-26`; palas y cargadores `PALA-01` a `PALA-03`, `CARG-01` y `CARG-02` (carguío del informe) |

## Archivos

| CSV | Tabla del modelo | Filas | Contenido |
|---|---|---|---|
| `produccion_mina.csv` | `Produccion Mina` | 21.430 | descargas por hora, tronadura y destino (el modelo deriva clase, prefijos y hora operativa) |
| `produccion_palas_hora.csv` | `Produccion Palas Hora` | 21.430 | cargas por hora y pala, con destino |
| `produccion_palas_turno.csv` | `Produccion Palas Turno` | 179 | cargas por turno |
| `calendario_turno.csv`, `calendario_turno_hora.csv` | `Calendario Turno Pala`, `... Hora` | 179 / 2.143 | puentes fecha-turno-hora |
| `horas_caex.csv` | `Horas CAEX` | 90 | horas nominales, disponibles y efectivas por día |
| `horas_palas_turno.csv` | `Horas Palas Turno` | 895 | horas por equipo y turno (nominal, mantención programada y no programada, efectivo) |
| `planes_mina.csv` | `Planes_Mina` | 2.944 | planes mensual y semanal por propiedad y día |
| `hist_kpi.csv` | `hist_kpi` | 24.090 | 11 señales de proceso cada 30 min |
| `hist_senales.csv` | `hist_senales` | 18.613 | 13 estados on/off y 4 contadores de válvulas cada hora |
| `hist_potencia.csv` | `hist_potencia` | 6.570 | potencia (kW) del motor SAG y de 2 molinos de bolas cada 30 min |
| `planta_cierre.csv`, `planta_cierre_ejec.csv` | `planta_cierre`, `planta_cierre_ejec` | 86 / 86 | cierre diario de planta (toneladas, horas efectivas, t/h) |
| `planta_plan_spi.csv`, `planta_plan_puntos.csv`, `planta_plan_fase.csv` | `planta_plan_*` | 90 / 90 / 270 | planes diarios de dureza, P80 y movimiento por fase |
| `equipos_df_ue.csv`, `equipos_ciclones.csv` | `equipos_df_ue`, `equipos_ciclones` | 1.246 / 712 | DF y UE diarios por área y por batería de ciclones |
| `actualizacion.csv`, `pulso.csv` | `Rd Actualizacion`, `Rd Pulso` | 1 / 1 | hora simulada de la última actualización |
| `ciclos_caex.csv` | (ninguna) | 4.680 | extra: velocidades por camión y turno, para `sql/ciclos_caex.sql` |

## Situaciones incluidas a propósito

Los datos no son uniformes: contienen los casos que las medidas deben resolver.

- **Día en curso**: último día de mina con 6,5 h de datos (proyección a 24 h) y último día de planta a mitad de turno (vista en línea).
- **Cierre de planta sin publicar**: el cierre oficial del último día cerrado no existe todavía; las medidas calculan desde el historiador. Los días anteriores sí
  traen cierre.
- **Equipo sin señal**: una señal on/off deja de reportar a las 12:00; el estado del equipo sale «sin señal» (2).
- **Equipo detenido**: otro equipo queda en 0 desde las 10:00.
- **Paradas del SAG**: algunos días el SAG se detiene entre 1,5 y 3 h; el acumulador diario y las horas efectivas lo reflejan.
- **DF y UE del día en curso**: no se publican hasta el día siguiente, así que el último día no tiene dato.
- **Reinicio del acumulador diario**: la señal `SAG.ALIM.ACUM_DIA` se reinicia en la muestra siguiente a las 07:00 y de ahí salen el inicio y el fin del día de planta.

## Sustituir los CSV por una base de datos

`sql/esquema_demo.sql` crea un esquema ficticio mínimo y las consultas de `sql/` devuelven las columnas de cada CSV. Para usarlas, reemplaza en
cada partición M el paso `Csv.Document(...)` por una consulta nativa (`Value.NativeQuery`) con el SQL correspondiente; el resto de pasos
(tipos, columnas derivadas) sigue igual.
