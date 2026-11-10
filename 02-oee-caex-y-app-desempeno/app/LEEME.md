# app/ · RD Terreno (Power Apps de lienzo, código fuente)

Aplicación para la reunión semanal de desempeño de operaciones mina de «Minera Demo» (datos 100 % sintéticos).
Tiene un **editor** (se prepara la reunión) y un **visor** (se presenta); el YAML de ambos se genera con Python.

```
herramientas/   generadores y utilidades (Python 3, PyYAML; openpyxl solo para crear_excel_demo.py)
pantallas/      scrInicio.yaml (escrita a mano), scrEditor.yaml y scrVisor.yaml (generadas)
formulas/       App_Formulas.fx (fórmulas con nombre), App_OnStart.fx, App_OnError.fx
```

## Regenerar y validar
```
python herramientas/gen_editor.py      # escribe pantallas/scrEditor.yaml
python herramientas/gen_visor.py       # escribe pantallas/scrVisor.yaml
python herramientas/validar_pantallas.py   # controles duplicados y paréntesis desbalanceados
python herramientas/crear_excel_demo.py --salida ../salida_excel   # Excel de datos desde datos_sinteticos/app/*.csv
```
`diff_pantalla.py` compara una pantalla copiada de Studio con el YAML local; `fx_a_studio.py` y `una_linea.py`
convierten fórmulas/consultas DAX al formato de la barra de fórmulas de Studio y de un flujo.

## Uso en Power Apps Studio
1. Pantallas: «Ver código» de cada pantalla › pegar el YAML correspondiente. Fórmulas: App.Formulas, App.OnStart y App.OnError.
2. Orígenes de datos: una tabla de Excel por registro, con el nombre del origen de datos de la app
   (`RD_Compromisos`, `RD_RevisionCompromisos`, `RD_Sesiones`, `RD_Destacados`, `RD_KPI`, `RD_PlanSemanal`,
   `RD_Preparacion`, `RD_Participantes`, `RD_Asistencia`). Columnas y ejemplos: `datos_sinteticos/app/`.
3. Logo principal: subir `recursos/logo_minera_demo_blanco.png` a Multimedia con el nombre `logo_minera_demo_blanco`.
   El ícono secundario va incrustado (data URI) desde `recursos/icono_minera_demo.png`.
4. Conectores: Excel Online, Office 365 Outlook (minuta), Office 365 Users (directorio) y dos flujos de Power Automate:
   `RD-OEE-Minuta` (ejecuta `dax/OEE_minuta.dax` sobre el modelo del informe y devuelve una fila por periodo) y
   `RDSubirEvidencia` (guarda la foto o el archivo de evidencia en la biblioteca de documentos y devuelve su URL).
5. Página «Indicadores» del visor: embebe el informe OEE de `pbip/`. Los ids de tenant, informe y área de trabajo en
   `gen_visor.py` son marcadores (`0000…`): reemplazarlos por los del informe publicado y regenerar.

## Qué no se pudo probar
Los YAML y las fórmulas no se abrieron en Power Apps Studio ni se ejecutaron los flujos: la verificación fue estática
(YAML válido, nombres de control únicos y paréntesis balanceados con `validar_pantallas.py`).
