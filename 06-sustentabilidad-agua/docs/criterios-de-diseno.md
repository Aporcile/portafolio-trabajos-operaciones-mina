# Criterios de diseño

## Estructura del tablero (11 páginas, 1920 x 1080)

| # | Página | Pregunta que responde |
|---|---|---|
| 1 | Vista general | ¿Qué requiere atención ahora? Tarjetas, alarmas por severidad, llegada de datos y resumen por sistema. |
| 2 | Semáforos | ¿Cómo está cada sistema? Un semáforo grande por sistema, pensado para una pantalla de sala. |
| 3 | Balance hídrico | ¿Cuánta agua entra, cuánta se recircula y cuánto consume cada área? Cierre del balance por día. |
| 4 | Recuperación de agua | ¿Qué pozos recuperan agua, cuáles están detenidos y desde cuándo? Matriz de bombeo de 24 h. |
| 5 | Aguas abajo | ¿Sube el nivel freático aguas abajo del Tranque Demo? |
| 6 | Estanques | ¿Qué estanque llega antes a su nivel HH? Medidores con línea objetivo. |
| 7 | Tranques y pozas | Vista completa de los ocho tranques y pozas, con tiempo estimado a HH. |
| 8 | Captación y agua fresca | Caudal captado, volumen del mes, proyección al cierre frente al cupo y piezómetros. |
| 9 | Calidad de agua | pH, conductividad y turbidez en línea; sólidos suspendidos de laboratorio. |
| 10 | Energía y reporte | Comunicación por estación, UPS, baterías y envíos a los portales A y B. |
| 11 | Señales y calidad del dato | Catálogo de señales con último valor y estado del dato. |

Todas las páginas llevan arriba a la derecha «DATOS AL dd-mm hh:mm». Si la última muestra supera `Horas datos atrasados`
el recuadro cambia de color y avisa cuántas horas lleva sin actualizar.

## Reglas visuales

- **Paleta Minera Demo**: azul medianoche `#1B2A41` para cabeceras, azul cielo `#4F9DDE` y violeta `#7B61C9` como acentos;
  rosa palo, verde salvia y azul acero solo cuando hay muchas series.
- **Color con significado**: verde, naranjo y rojo se reservan para estados (normal, alerta, crítico); gris para «sin dato».
  Verde = normal, naranjo = aviso o alerta, rojo = crítico.
- **Un patrón de estado**: todo activo se resume en un código 1 normal, 2 alto, 3 crítico, 4 sin dato, 5 congelado, con símbolo
  (● ▲ ■ ◌ ◇) además del color para no depender solo de él.
- **Tarjeta = cifra + contexto**: el título dice qué se mide y el subtítulo (medida `KPI ... detalle`) da el contexto o el peor caso.
- **Tablas de acción**: ordenadas por severidad, con estado coloreado y la columna «Ir a» que indica la página de detalle.
- **Gráficos**: líneas con las bandas HI/HH o los límites como líneas de referencia punteadas; ejes de 0 al máximo razonable.

## Reglas de negocio (genéricas)

- **Congelado**: señal analógica sin cambio durante `Horas para congelado` (no cuenta los valores en cero).
- **Sin dato**: sin muestra nueva en `Horas sin dato`; si toda una estación calla se emite **una sola alarma**.
- **Posible corte de energía**: todas las bombas de una estación se detienen dentro de `Minutos simultaneidad corte` y sin corriente.
- **Tiempo a HH**: `(HH - nivel) / subida de las últimas 3 h`, solo si el nivel sube.
- **Cupo mensual**: volumen del mes + ritmo de 24 h hasta fin de mes, frente al cupo de ejemplo; aviso sobre 90 %, alerta sobre 100 %.
- **Límites**: todos los umbrales de `Config`, `Activos` y `LabCalidad` son valores de ejemplo, no normas ni límites regulatorios.

## Decisiones de ingeniería

- **Modelo en formato largo** (`Tag, FechaHora, Valor`) para que un catálogo de señales gobierne qué se mide sin cambiar el modelo.
- **Un solo motor de alarmas** (`Alarma severidad`) sobre `Activos[Tipo]`: agregar un tipo de activo es agregar una rama.
- **Datos reproducibles**: el generador usa semilla fija, cubre 90 días desde 2025-03-03 y verifica que el balance horario suma el diario.
- **Verificador de coherencia** (`tools/verificar_coherencia.py`): valida referencias DAX, campos de los visuales, relaciones, CSV y
  literales sin abrir Power BI Desktop; es el control que corre antes de cada cambio.
- **Sin vínculos externos**: la rama `Historiador` usa una URL de ejemplo y solo documenta el contrato esperado del OData.
