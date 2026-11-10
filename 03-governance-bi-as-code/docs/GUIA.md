# Guía de trabajo: Gobernanza_uso_reportes

> Datos 100 % sintéticos de la empresa ficticia Minera Demo. Nada de lo que hay aquí viene de un sistema real.

## 1. Abrirlo y validarlo (10 minutos)

Requisitos: Windows, Power BI Desktop (con la Vista TMDL y el formato de proyecto PBIP activados), Python 3.10+ y,
opcionalmente, `pip install jsonschema` para validar los JSON del informe.

1. Generar los CSV (opcional, ya están versionados): `python datos_sinteticos/generar_datos.py`.
2. Fijar la ruta de los datos en el modelo. Dos formas:
   - `powershell -File desarrollo\generar_modelo.ps1 -Local` reescribe el modelo con la ruta de **este clon**
     (no la subas a git: el valor versionado es el marcador `RUTA_DEL_CLON`).
   - O en Desktop: Transformar datos > Administrar parámetros > `RutaDatos` = carpeta completa de
     `datos_sinteticos\csv\`, con `\` al final.
3. Abrir `Gobernanza_uso_reportes.pbip` y Actualizar.
4. En Desktop, Vista de consultas DAX: pegar `desarrollo/validacion_datos.dax`. Los 49 chequeos deben decir `OK`.
5. Sin abrir Desktop: `powershell -File desarrollo\verificar_proyecto.ps1`.

## 2. Qué contiene

| Capa | Archivos | Contenido |
|---|---|---|
| Datos | `datos_sinteticos/csv/` | `fact_uso`, `dim_reporte`, `lecturas_area` (generados con semilla fija) |
| Modelo | `*.SemanticModel/definition/` | TMDL: 7 tablas, 4 relaciones, 22 medidas |
| Informe | `*.Report/definition/` | PBIR: 6 páginas, 59 visuales, tema y logo como recursos |
| Generadores | `desarrollo/` | `generar_modelo.ps1`, `generar_reporte.py` (TMDL y PBIR salen de código) |
| Verificación | `desarrollo/` | `verificar_proyecto.ps1`, `validar_disco.py`, `validacion_datos.dax` |

Esquema en estrella: `Fact_Uso` (día x reporte x usuario) apunta a `Dim_Reporte`, `Dim_Fecha` y `Dim_Usuario`;
`Dim_Reporte` apunta a `Dim_Area`. `Eje_Detalle` (calculada, sin relaciones) y `_Medidas` son auxiliares.
Todas las relaciones son varios a uno y filtran en un solo sentido.

## 3. Contrato de datos (los tres CSV)

- `fact_uso.csv`: `fecha` (aaaa-mm-dd, obligatorio; otro formato detiene la actualización con un mensaje claro),
  `workspace_id`, `workspace_nombre`, `report_id`, `report_nombre`, `usuario` (correo), `aperturas`, `vistas_pagina`,
  `es_sintetico`.
- `dim_reporte.csv`: `report_id`, `report_nombre`, `workspace_id`, `workspace_nombre`, `url`.
- `lecturas_area.csv`: `workspace_id`, `ultima_lectura` (aaaa-mm-dd HH:mm): registro de la extracción por área.
- El modelo calcula el nombre corto del área (quita `WS-DEMO-` y `-PROD`) y una etiqueta única de reporte (si dos
  reportes se llaman igual, agrega el área). Las cuentas con prefijo `ext.` son externas; el resto, internas.
- Las cuentas de `desarrollo/config_datos.json` (`usuarios_excluidos`) no cuentan: son quienes mantienen el informe.

## 4. Cómo trabajarlo

Todo se regenera desde código; los archivos de `definition/` no se editan a mano.

- **Medidas**: editar la lista `$medidas` de `generar_modelo.ps1` y volver a correrlo. También deja
  `medidas_vista_TMDL.tmdl`, listo para pegar en la Vista TMDL de Desktop sin regenerar el modelo.
- **Visuales y páginas**: editar `generar_reporte.py` y correrlo (`python generar_reporte.py`). Reemplaza por completo
  `definition/` de forma atómica: si algo falla, repone la anterior.
- **Cambios hechos en Desktop**: los generadores no los detectan y los pisarían. O se pasan al generador, o no se
  regenera. Después de guardar desde Desktop conviene correr `validar_disco.py`.
- **Datos**: cambiar `generar_datos.py` y volver a correrlo; actualizar los esperados de `validacion_datos.dax`
  con los valores de `datos_sinteticos/esperados.json`.
- **Validación con esquemas**: `python desarrollo/extraer_esquemas.py` copia a `desarrollo/esquemas_pbir/` los esquemas
  que trae la instalación local de Desktop (no se versionan). Con ellos, `generar_reporte.py` y `validar_disco.py` validan
  cada JSON; sin ellos solo avisan.

## 5. Casos que el conjunto sintético incluye a propósito

| Caso | Dónde se ve |
|---|---|
| Reportes sin uso (solo los abre la cuenta de mantenimiento, excluida) | página Sin uso |
| Reportes con aperturas pero sin vistas de página (acceso automatizado) | Sin uso y Calidad |
| Un reporte abandonado (solo tuvo uso al inicio del periodo) | Vistas por semana y Detalle: el uso cae a cero |
| Dos reportes con el mismo nombre en áreas distintas | Calidad: nombres repetidos; etiqueta con el área |
| Un área cuya extracción se detuvo antes del final | Calidad: cobertura y última lectura |
| Cuentas externas frente a internas | Vistas, Detalle (tooltip) y Calidad |

## 6. Si algo falla

- *"No se encuentra la ruta"* al actualizar: `RutaDatos` sigue con el marcador o sin `\` final. Ver paso 2.
- *"La columna ... no se encontró"*: el CSV no trae el esquema del contrato (sección 3).
- *Fecha ilegible*: `fact_uso.csv` debe traer `aaaa-mm-dd`.
- `verificar_proyecto.ps1` dice FALLA en el TMDL: Power BI Desktop debe estar instalado (usa su biblioteca TOM).
- El informe abre con fondo blanco: el tema no quedó registrado; correr `generar_reporte.py` y revisar `report.json`.
- El logo no aparece: confirmar `StaticResources/RegisteredResources/logo_minera_demo_blanco.png`.

## 7. Qué está verificado y qué no

- Verificado por script: el TMDL se deserializa con TOM (7 tablas, 4 relaciones, 22 medidas); cada campo que usan los
  visuales existe en el modelo; los 69 JSON del informe validan contra los esquemas de Desktop.
- **No probado**: que las consultas M carguen los CSV en Desktop y que las cifras coincidan con
  `validacion_datos.dax`; tampoco la apariencia final ni el visual del logo. Esos pasos requieren abrir Desktop.

## 8. Pasar a datos reales (diseño, no incluido)

Los tres CSV son el contrato: cualquier extracción que los produzca con las mismas columnas sirve (por ejemplo, una
consulta DAX al modelo de métricas de uso de Power BI con un flujo programado que guarde el resultado). Al hacerlo:
poner `DATOS_SINTETICOS = False` en `generar_reporte.py`, regenerar y recordar que el servicio conserva unos 30 días de uso,
que las fechas están en UTC y que cada consulta tiene límites de filas.
