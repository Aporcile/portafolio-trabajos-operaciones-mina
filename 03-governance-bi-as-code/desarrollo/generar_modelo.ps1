# Genera el MODELO SEMÁNTICO (TMDL) del proyecto Gobernanza_uso_reportes.
#
# Construye el modelo con TOM (la biblioteca que trae Power BI Desktop) a partir de las consultas M y de las
# 22 medidas definidas en este archivo, y lo escribe como TMDL en Gobernanza_uso_reportes.SemanticModel\definition.
# Las medidas viven aquí: es su fuente de verdad (también se escribe medidas_vista_TMDL.tmdl para pegarlas
# en la Vista TMDL de Desktop).
#
# La escritura es atómica: el modelo nuevo se genera en una carpeta aparte y solo al final reemplaza al anterior;
# si algo falla en el cambio, se repone el anterior.
#
# Uso (desde la carpeta desarrollo\):
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File generar_modelo.ps1 [-Local] [-RutaDatos <carpeta>]
#
#   -RutaDatos  carpeta con los CSV (fact_uso.csv, dim_reporte.csv, lecturas_area.csv). Se escribe en el parámetro
#               RutaDatos del modelo.
#   -Local      atajo: usa <proyecto>\datos_sinteticos\csv\ de este clon.
#   (sin ambos) deja el marcador RUTA_DEL_CLON, que es lo que se versiona: cada persona fija su ruta con -Local o
#               desde Desktop (Transformar datos > Administrar parámetros > RutaDatos).
#
# Usuarios excluidos: usuarios_excluidos de config_datos.json (correos completos). Su uso no cuenta en el informe;
# la lista queda escrita en la consulta Fact_Uso, así que cambiarla es editar el json y regenerar.
param(
    [string]$Proyecto = (Split-Path -Parent $PSScriptRoot),
    [string]$RutaDatos,
    [switch]$Local
)
$ErrorActionPreference = 'Stop'

# Biblioteca TOM de Power BI Desktop: la de la instalación MSI si existe; si no, la de Microsoft Store.
$loc = Join-Path $env:ProgramFiles 'Microsoft Power BI Desktop'
if (-not [IO.File]::Exists("$loc\bin\Microsoft.PowerBI.Tabular.dll")) { $loc = (Get-AppxPackage -Name 'Microsoft.MicrosoftPowerBIDesktop').InstallLocation }
if (-not $loc) { Write-Host 'ERROR: no se encontró Power BI Desktop instalado'; exit 1 }
[void][Reflection.Assembly]::LoadFrom("$loc\bin\Microsoft.PowerBI.Tabular.dll")
$NS = 'Microsoft.AnalysisServices.Tabular'
$NombreProyecto = 'Gobernanza_uso_reportes'
# Semilla de los lineageTag: fija, para que regenerar sin cambios produzca exactamente los mismos archivos
$SemillaGuid = 'gobernanza_uso_reportes_demo'
$MarcadorRuta = 'RUTA_DEL_CLON\03-governance-bi-as-code\datos_sinteticos\csv\'

# ---------------- Configuración ----------------
$cfgRuta = Join-Path $PSScriptRoot 'config_datos.json'
$Cfg = $null
if ([IO.File]::Exists($cfgRuta)) {
    try { $Cfg = [IO.File]::ReadAllText($cfgRuta, [Text.Encoding]::UTF8) | ConvertFrom-Json }
    catch { Write-Host "ERROR: config_datos.json ilegible: $($_.Exception.Message). No se escribió nada."; exit 1 }
    if (-not ($Cfg -is [System.Management.Automation.PSCustomObject])) { Write-Host 'ERROR: config_datos.json debe ser un objeto JSON ({...}). No se escribió nada.'; exit 1 }
}
if ($RutaDatos) { $RutaFinal = $RutaDatos }
elseif ($Local) { $RutaFinal = Join-Path $Proyecto 'datos_sinteticos\csv' }
else { $RutaFinal = $MarcadorRuta }
if ($RutaFinal -ne $MarcadorRuta -and -not [IO.Directory]::Exists($RutaFinal)) { Write-Host "ERROR: la carpeta de datos no existe: $RutaFinal"; exit 1 }

# Fact_Uso con la lista de usuarios excluidos escrita (en minúsculas, como llega usuario); sin la clave, lista vacía
function Get-FactUso {
    $lista = @(@(if ($Cfg -and $Cfg.usuarios_excluidos) { $Cfg.usuarios_excluidos }) | ForEach-Object { ([string]$_).Trim().ToLowerInvariant() } |
        Where-Object { $_ } | Select-Object -Unique)
    $malos = @($lista | Where-Object { $_ -notmatch '^[^@\s"{}]+@[^@\s"{}]+\.[^@\s"{}]+$' })
    if ($malos.Count) { throw "usuarios_excluidos de config_datos.json: $($malos -join ', ') no es un correo (nombre@dominio)" }
    $M_FACT_USO.Replace('{{USUARIOS_EXCLUIDOS}}', '{' + (@($lista | ForEach-Object { '"' + $_ + '"' }) -join ', ') + '}')
}
# GUID estable derivado de un texto
$md5 = [Security.Cryptography.MD5]::Create()
function GuidDe([string]$texto) { (New-Object Guid (, $md5.ComputeHash([Text.Encoding]::UTF8.GetBytes("$SemillaGuid|$texto")))).ToString() }

# ---------------- Consultas M (todas leen CSV de la carpeta RutaDatos) ----------------
$M_FACT_USO = @'
// Consulta: Fact_Uso (una fila por día x reporte x usuario)
// Lee fact_uso.csv de la carpeta RutaDatos y descarta las cuentas de usuarios_excluidos (config_datos.json):
// el uso de quienes mantienen el informe no cuenta ni aparece como usuario.
let
    Origen = Csv.Document(File.Contents(RutaDatos & "fact_uso.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),
    Columnas = {"fecha", "workspace_id", "workspace_nombre", "report_id", "report_nombre", "usuario", "aperturas", "vistas_pagina", "es_sintetico"},
    // Esquema fijo: una columna extra del CSV no llega al modelo y una obligatoria que falte da error con su nombre
    Nombres = Table.TransformColumnNames(Encabezados, each Text.Lower(Text.Trim(_))),
    Seleccion = Table.SelectColumns(Nombres, Columnas),
    // fecha: SOLO aaaa-mm-dd (se acepta una hora detrás, que se descarta). Otro formato detiene la actualización con
    // un mensaje claro: no se adivina, así no quedan día y mes invertidos sin aviso.
    LeerFecha = (t) => if t = null or Text.Trim(t) = "" then null
        else Date.FromText(Text.Start(Text.Trim(t), 10), [Format = "yyyy-MM-dd", Culture = "en-US"]),
    Ilegibles = List.Count(List.Select(Seleccion[fecha], each (try LeerFecha(_))[HasError])),
    Fechas = if Ilegibles > 0
        then error Error.Record("DataFormat.Error",
            Text.From(Ilegibles) & " fila(s) de fact_uso.csv con la fecha ilegible: se espera aaaa-mm-dd (por ejemplo 2025-03-03)")
        else Table.TransformColumns(Seleccion, {{"fecha", LeerFecha, type date}}),
    // Claves sin espacios y en minúsculas: el motor del modelo compara texto sin distinguir mayúsculas y Power Query sí.
    // Sin usuario ("" o "?") queda como "(sin usuario)".
    Claves = Table.TransformColumns(Fechas, {
        {"workspace_id", each if _ = null then null else Text.Lower(Text.Trim(_)), type text},
        {"report_id", each if _ = null then null else Text.Lower(Text.Trim(_)), type text},
        {"usuario", each let u = Text.Lower(Text.Trim(_ ?? "")) in if u = "" or u = "?" then "(sin usuario)" else u, type text}
    }),
    Excluidos = List.Buffer({{USUARIOS_EXCLUIDOS}}),
    SinExcluidos = Table.SelectRows(Claves, each not List.Contains(Excluidos, [usuario])),
    // "en-US" fija el formato de lectura (True/False, punto decimal) sin depender de la configuración regional
    Tipos = Table.TransformColumnTypes(SinExcluidos, {
        {"workspace_nombre", type text}, {"report_nombre", type text}, {"aperturas", Int64.Type},
        {"vistas_pagina", Int64.Type}, {"es_sintetico", type logical}}, "en-US"),
    ConUso = Table.SelectRows(Tipos, each [aperturas] <> 0 or [vistas_pagina] <> 0)
in
    ConUso
'@

$M_DIM_REPORTE = @'
// Consulta: Dim_Reporte (una fila por reporte; report_id es la clave)
// Lee dim_reporte.csv y agrega dos columnas para los visuales:
//   Area     nombre corto del workspace ("WS-DEMO-Operaciones_Mina-PROD" -> "Operaciones Mina").
//   Reporte  nombre único para segmentaciones, tablas y matrices: si un nombre se repite, lleva el área y, si aun así
//            se repite, el inicio del report_id.
let
    Origen = Csv.Document(File.Contents(RutaDatos & "dim_reporte.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),
    Nombres = Table.TransformColumnNames(Encabezados, each Text.Lower(Text.Trim(_))),
    Inventario = Table.SelectColumns(Nombres, {"report_id", "report_nombre", "workspace_id", "workspace_nombre", "url"}),
    // Mismas claves normalizadas que en Fact_Uso
    Base = Table.TransformColumns(Inventario, {
        {"report_id", each if _ = null then null else Text.Lower(Text.Trim(_)), type text},
        {"workspace_id", each if _ = null then null else Text.Lower(Text.Trim(_)), type text},
        {"report_nombre", each if _ = null then null else Text.Trim(_), type text},
        {"workspace_nombre", each if _ = null then null else Text.Trim(_), type text},
        {"url", each _, type text}
    }),
    // La clave del lado "uno" de una relación no admite vacíos ni repetidos
    ConClave = Table.SelectRows(Base, each [report_id] <> null and [report_id] <> ""),
    SinDuplicados = Table.Distinct(ConClave, {"report_id"}),
    ConNombreCorto = Table.AddColumn(SinDuplicados, "AreaFila", each
        let
            n = if [workspace_nombre] = null then "" else [workspace_nombre],
            sinPrefijo = if Text.StartsWith(n, "WS-DEMO-", Comparer.OrdinalIgnoreCase) then Text.Range(n, 8) else n,
            sinSufijo = if Text.EndsWith(sinPrefijo, "-PROD", Comparer.OrdinalIgnoreCase) then Text.Start(sinPrefijo, Text.Length(sinPrefijo) - 5) else sinPrefijo
        in
            Text.Trim(Text.Replace(sinSufijo, "_", " ")), type text),
    // Un solo nombre de área por workspace: el de su última fila (un workspace renombrado no muestra dos nombres)
    PorWorkspace = Table.Group(Table.SelectRows(ConNombreCorto, each [workspace_id] <> null and [workspace_id] <> ""),
        {"workspace_id"}, {{"Area", each List.Last([AreaFila]), type text}}),
    AreaDe = Record.FromList(PorWorkspace[Area], PorWorkspace[workspace_id]),
    ConArea = Table.RemoveColumns(Table.AddColumn(ConNombreCorto, "Area", each
        if [workspace_id] = null or [workspace_id] = "" then [AreaFila] else Record.Field(AreaDe, [workspace_id]), type text), {"AreaFila"}),
    // Reporte: las comparaciones no distinguen mayúsculas, igual que el motor del modelo
    NombresRepetidos = List.Buffer(Table.SelectRows(
        Table.Group(ConArea, {"report_nombre"}, {{"n", each Table.RowCount(_), Int64.Type}}, GroupKind.Global, Comparer.OrdinalIgnoreCase),
        each [n] > 1)[report_nombre]),
    ConEtiqueta = Table.AddColumn(ConArea, "Etiqueta", each
        let nombre = if [report_nombre] = null or [report_nombre] = "" then "(sin nombre)" else [report_nombre]
        in if [report_nombre] <> null and List.Contains(NombresRepetidos, [report_nombre], Comparer.OrdinalIgnoreCase)
            then nombre & " · " & [Area] else nombre, type text),
    EtiquetasRepetidas = List.Buffer(Table.SelectRows(
        Table.Group(ConEtiqueta, {"Etiqueta"}, {{"n", each Table.RowCount(_), Int64.Type}}, GroupKind.Global, Comparer.OrdinalIgnoreCase),
        each [n] > 1)[Etiqueta]),
    ConReporte = Table.AddColumn(ConEtiqueta, "Reporte", each
        if List.Contains(EtiquetasRepetidas, [Etiqueta], Comparer.OrdinalIgnoreCase)
        then [Etiqueta] & " (" & Text.Start([report_id], 8) & ")" else [Etiqueta], type text),
    Tipos = Table.TransformColumnTypes(
        Table.RemoveColumns(ConReporte, {"Etiqueta"}),
        {
            {"report_id", type text},
            {"report_nombre", type text},
            {"workspace_id", type text},
            {"workspace_nombre", type text},
            {"url", type text},
            {"Area", type text},
            {"Reporte", type text}
        }
    )
in
    Tipos
'@

$M_DIM_FECHA = @'
// Consulta: Dim_Fecha (calendario del primer al último día con datos; Fecha es la clave)
// Es una consulta M y no una tabla calculada: el motor rechaza las relaciones hacia tablas calculadas al crear el modelo desde archivos.
let
    ColFecha = Table.SelectColumns(Fact_Uso, {"fecha"}),
    Ilegibles = Table.RowCount(Table.SelectRowsWithErrors(ColFecha)),
    Fechas = if Ilegibles > 0
        then error Error.Record("DataFormat.Error",
            Text.From(Ilegibles) & " fila(s) de fact_uso.csv con la fecha ilegible: se espera aaaa-mm-dd (por ejemplo 2025-03-03)")
        else List.Buffer(List.RemoveNulls(ColFecha[fecha])),
    Minimo = List.Min(Fechas),
    Maximo = List.Max(Fechas),
    // Sin datos: calendario vacío en vez de error
    Lista = if Minimo = null then {} else List.Dates(Minimo, Duration.Days(Maximo - Minimo) + 1, #duration(1, 0, 0, 0)),
    Tabla = Table.FromList(Lista, Splitter.SplitByNothing(), type table [Fecha = date], null, ExtraValues.Error),
    Anio = Table.AddColumn(Tabla, "Anio", each Date.Year([Fecha]), Int64.Type),
    Mes = Table.AddColumn(Anio, "Mes", each Date.Month([Fecha]), Int64.Type),
    NombreMes = Table.AddColumn(Mes, "NombreMes", each Date.MonthName([Fecha], "es-ES"), type text),
    Dia = Table.AddColumn(NombreMes, "Dia", each Date.Day([Fecha]), Int64.Type),
    DiaSemana = Table.AddColumn(Dia, "DiaSemana", each Date.DayOfWeekName([Fecha], "es-ES"), type text),
    // Orden de DiaSemana: lunes = 1 ... domingo = 7 (si no, se ordena alfabéticamente)
    DiaSemanaNum = Table.AddColumn(DiaSemana, "DiaSemanaNum", each Date.DayOfWeek([Fecha], Day.Monday) + 1, Int64.Type),
    // La semana parte el lunes
    NumSemana = Table.AddColumn(DiaSemanaNum, "NumSemana", each Date.WeekOfYear([Fecha], Day.Monday), Int64.Type),
    // Semana de lunes a domingo, para agrupar por semana; InicioSemana (su lunes) la ordena. La etiqueta lleva los días
    // que tienen datos: la primera y la última semana pueden quedar cortadas y llevan "(parcial)" para que su total
    // menor no se lea como una caída. El año hace única la etiqueta: Desktop exige un solo InicioSemana por Semana.
    InicioSemana = Table.AddColumn(NumSemana, "InicioSemana", each Date.StartOfWeek([Fecha], Day.Monday), type date),
    Semana = Table.AddColumn(InicioSemana, "Semana", each
        let
            Desde = List.Max({[InicioSemana], Minimo}),
            Hasta = List.Min({Date.AddDays([InicioSemana], 6), Maximo})
        in
            Date.ToText(Desde, "dd-MM") & " al " & Date.ToText(Hasta, "dd-MM-yyyy")
                & (if Duration.Days(Hasta - Desde) < 6 then " (parcial)" else ""),
        type text),
    // Los últimos 28 días cargados (4 semanas que terminan en el último día con datos), para la matriz diaria.
    // FechaCorta es "dd-MM" en esos días y la fecha completa en los demás: cada etiqueta es única y se ordena por Fecha.
    Ultimos28 = Table.AddColumn(Semana, "Ultimos28", each Duration.Days(Maximo - [Fecha]) < 28, type logical),
    FechaCorta = Table.AddColumn(Ultimos28, "FechaCorta", each
        Date.ToText([Fecha], if [Ultimos28] then "dd-MM" else "dd-MM-yyyy"), type text)
in
    FechaCorta
'@

$M_DIM_USUARIO = @'
// Consulta: Dim_Usuario (un usuario por fila; usuario es la clave)
// Es una consulta M y no una tabla calculada: el motor rechaza las relaciones hacia tablas calculadas al crear el modelo desde archivos.
// Las cuentas con prefijo "ext." son externas; el resto, internas.
let
    Usuarios = Table.Distinct(Table.SelectColumns(Fact_Uso, {"usuario"})),
    SinVacios = Table.SelectRows(Usuarios, each [usuario] <> null and [usuario] <> ""),
    Tipo = Table.AddColumn(SinVacios, "tipo_usuario", each if Text.StartsWith([usuario], "ext.", Comparer.OrdinalIgnoreCase) then "Externo" else "Interno", type text)
in
    Tipo
'@

$M_DIM_AREA = @'
// Consulta: Dim_Area (una fila por workspace; workspace_id es la clave)
// Es una consulta M y no una tabla calculada: el motor rechaza las relaciones hacia tablas calculadas al crear el modelo desde archivos.
// ultima_lectura sale de lecturas_area.csv (registro de la extracción, una fila por área): si se queda atrás, la
// extracción dejó de leer esa área. En blanco si el área no figura en el registro.
let
    ConClave = Table.SelectRows(Dim_Reporte, each [workspace_id] <> null and [workspace_id] <> ""),
    Areas = Table.Group(ConClave, {"workspace_id"}, {
        {"workspace_nombre", each List.Last([workspace_nombre]), type text},
        {"Area", each List.Last([Area]), type text}
    }),
    Origen = Csv.Document(File.Contents(RutaDatos & "lecturas_area.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true]),
    Nombres = Table.TransformColumnNames(Encabezados, each Text.Lower(Text.Trim(_))),
    Lecturas = Table.TransformColumns(Table.SelectColumns(Nombres, {"workspace_id", "ultima_lectura"}), {
        {"workspace_id", each Text.Lower(Text.Trim(_ ?? "")), type text},
        {"ultima_lectura", each try DateTime.FromText(Text.Trim(_), [Format = "yyyy-MM-dd HH:mm", Culture = "en-US"]) otherwise null, type nullable datetime}
    }),
    ConLectura = Table.ExpandTableColumn(
        Table.NestedJoin(Areas, {"workspace_id"}, Lecturas, {"workspace_id"}, "l", JoinKind.LeftOuter), "l", {"ultima_lectura"})
in
    Table.TransformColumnTypes(ConLectura, {{"ultima_lectura", type datetime}})
'@

function Add-TablaM($model, $nombre, $mCode, $cols) {
    $t = New-Object "$NS.Table"; $t.Name = $nombre
    foreach ($c in $cols) {
        $dc = New-Object "$NS.DataColumn"; $dc.Name = $c[0]; $dc.DataType = $c[1]; $dc.SourceColumn = $c[0]; $t.Columns.Add($dc)
    }
    $p = New-Object "$NS.Partition"; $p.Name = $nombre; $p.Mode = 'Import'
    $s = New-Object "$NS.MPartitionSource"; $s.Expression = $mCode; $p.Source = $s
    $t.Partitions.Add($p); $model.Tables.Add($t)
}
function Add-TablaCalc($model, $nombre, $dax, $cols) {
    $t = New-Object "$NS.Table"; $t.Name = $nombre
    foreach ($c in $cols) {
        $cc = New-Object "$NS.CalculatedTableColumn"; $cc.Name = $c[0]; $cc.DataType = $c[1]
        $cc.SourceColumn = "[$($c[0])]"; $cc.IsNameInferred = $true; $t.Columns.Add($cc)
    }
    $p = New-Object "$NS.Partition"; $p.Name = $nombre; $p.Mode = 'Import'
    $s = New-Object "$NS.CalculatedPartitionSource"; $s.Expression = $dax; $p.Source = $s
    $t.Partitions.Add($p); $model.Tables.Add($t)
}
function Add-Relacion($model, $tf, $cf, $tt, $ct) {
    $r = New-Object "$NS.SingleColumnRelationship"
    $r.Name = GuidDe "relacion|$tf.$cf|$tt.$ct"
    $r.FromColumn = $model.Tables[$tf].Columns[$cf]; $r.FromCardinality = 'Many'
    $r.ToColumn = $model.Tables[$tt].Columns[$ct]; $r.ToCardinality = 'One'
    $r.CrossFilteringBehavior = 'OneDirection'; $r.IsActive = $true
    $model.Relationships.Add($r)
}

# ---------------- Las 22 medidas (fuente de verdad de medidas_vista_TMDL.tmdl) ----------------
$medidas = @(
@{ n = 'Aperturas'; f = 'Uso'; fmt = '#,0'; d = 'Veces que se abrió un reporte (Report opens). Devuelve 0, no blanco, para que los reportes y días sin uso aparezcan.'; e = @'
// +0: 0 en vez de blanco, así los reportes y días sin uso aparecen en tablas y matrices.
// NOT ISEMPTY ( Dim_Reporte ): si un visual combina Área y Reporte, sin esta guarda el +0
// mostraría cada reporte repetido en todas las áreas (combinaciones que no existen).
IF ( NOT ISEMPTY ( Dim_Reporte ), SUM ( Fact_Uso[aperturas] ) + 0 )
'@ },
@{ n = 'Vistas de pagina'; f = 'Uso'; fmt = '#,0'; d = 'Páginas vistas dentro de los reportes (Report page views).'; e = @'
// Misma guarda y +0 que [Aperturas].
IF ( NOT ISEMPTY ( Dim_Reporte ), SUM ( Fact_Uso[vistas_pagina] ) + 0 )
'@ },
@{ n = 'Usuarios unicos'; f = 'Uso'; fmt = '#,0'; d = 'Usuarios distintos. No es sumable: el total de un período es el conteo distinto del período, no la suma de los días.'; e = @'
IF ( NOT ISEMPTY ( Dim_Reporte ), DISTINCTCOUNT ( Fact_Uso[usuario] ) + 0 )
'@ },
@{ n = 'Dias con actividad'; f = 'Uso'; fmt = '#,0'; d = 'Días distintos con al menos un registro de uso.'; e = @'
// NOBLANK: una fila con fecha vacía no cuenta como un día más
IF ( NOT ISEMPTY ( Dim_Reporte ), DISTINCTCOUNTNOBLANK ( Fact_Uso[fecha] ) + 0 )
'@ },
@{ n = 'Pags por apertura'; f = 'Uso'; fmt = '0.0'; d = 'Vistas de página por apertura (0 si no hubo aperturas). Muchas aperturas con pocas páginas puede indicar acceso automatizado o incrustado (hipótesis a verificar).'; e = @'
// 0 sin aperturas (no blanco), igual que las tarjetas de Aperturas y Vistas que la acompañan.
// Las tablas por usuario filtran a quien tuvo uso, así que esos ceros no encabezan un orden ascendente.
IF ( NOT ISEMPTY ( Dim_Reporte ), DIVIDE ( [Vistas de pagina], [Aperturas], 0 ) )
'@ },
@{ n = 'Aperturas sin vistas'; f = 'Uso'; fmt = '#,0'; d = 'Aperturas registradas en filas sin ninguna vista de página.'; e = @'
CALCULATE ( [Aperturas], Fact_Uso[vistas_pagina] = 0 )
'@ },
@{ n = 'Ultima actividad'; f = 'Fechas'; fmt = 'dd-MM-yyyy'; d = 'Fecha más reciente con uso. Blanco si nunca hubo uso.'; e = @'
MAX ( Fact_Uso[fecha] )
'@ },
@{ n = 'Datos desde'; f = 'Fechas'; fmt = 'dd-MM-yyyy'; d = 'Fecha más antigua con datos.'; e = @'
MIN ( Fact_Uso[fecha] )
'@ },
@{ n = 'Dias desde ultima actividad'; f = 'Fechas'; fmt = '#,0'; d = 'Días entre la última actividad y la última fecha con datos del histórico (no contra hoy). Blanco si nunca hubo uso.'; e = @'
// Se compara contra la última fecha del histórico y no contra HOY:
// si la carga de datos se atrasa, los días no se inflan.
VAR UltimaFechaHistorico = MAXX ( ALL ( Fact_Uso ), Fact_Uso[fecha] )
VAR UltimaActividad = [Ultima actividad]
RETURN
    IF (
        NOT ISBLANK ( UltimaActividad ),
        DATEDIFF ( UltimaActividad, UltimaFechaHistorico, DAY )
    )
'@ },
@{ n = 'Ultima lectura'; f = 'Fechas'; fmt = 'dd-MM-yyyy'; d = 'Fecha de la última lectura de la extracción en el área (lecturas_area.csv). Si un área se queda atrás, la extracción dejó de leerla. Blanco si el área no figura en el registro.'; e = @'
MAX ( Dim_Area[ultima_lectura] )
'@ },
@{ n = 'Profundidad historico dias'; f = 'Fechas'; fmt = '#,0'; d = 'Días cubiertos por el histórico completo (primera a última fecha), sin filtros.'; e = @'
// MIN/MAX no aceptan ALL(...) como argumento: se usa CALCULATE + REMOVEFILTERS.
VAR FechaMin = CALCULATE ( MIN ( Fact_Uso[fecha] ), REMOVEFILTERS () )
VAR FechaMax = CALCULATE ( MAX ( Fact_Uso[fecha] ), REMOVEFILTERS () )
RETURN
    DATEDIFF ( FechaMin, FechaMax, DAY ) + 1
'@ },
@{ n = 'Estado del reporte'; f = 'Estado'; fmt = ''; d = 'En uso: 1 o más vistas de página. Solo aperturas: aperturas sin vistas. Sin uso: ni aperturas ni vistas. Es el estado de UN reporte: en totales o con varios reportes queda en blanco.'; e = @'
VAR VistasPagina = [Vistas de pagina]
VAR TotalAperturas = [Aperturas]
RETURN
    SWITCH (
        TRUE (),
        NOT HASONEVALUE ( Dim_Reporte[report_id] ), BLANK (), // fila de total o varios reportes
        ISBLANK ( TotalAperturas ), BLANK (), // combinación Área/Reporte inexistente
        VistasPagina >= 1, "En uso",
        TotalAperturas > 0, "Solo aperturas",
        "Sin uso"
    )
'@ },
@{ n = 'Aperturas interno'; f = 'Tipo usuario'; fmt = '#,0'; d = 'Aperturas de cuentas internas (sin prefijo ext.).'; e = @'
CALCULATE ( [Aperturas], Dim_Usuario[tipo_usuario] = "Interno" )
'@ },
@{ n = 'Aperturas externo'; f = 'Tipo usuario'; fmt = '#,0'; d = 'Aperturas de cuentas externas (prefijo ext.).'; e = @'
CALCULATE ( [Aperturas], Dim_Usuario[tipo_usuario] = "Externo" )
'@ },
@{ n = 'Vistas pagina interno'; f = 'Tipo usuario'; fmt = '#,0'; d = 'Vistas de página de cuentas internas (sin prefijo ext.).'; e = @'
CALCULATE ( [Vistas de pagina], Dim_Usuario[tipo_usuario] = "Interno" )
'@ },
@{ n = 'Vistas pagina externo'; f = 'Tipo usuario'; fmt = '#,0'; d = 'Vistas de página de cuentas externas (prefijo ext.).'; e = @'
CALCULATE ( [Vistas de pagina], Dim_Usuario[tipo_usuario] = "Externo" )
'@ },
@{ n = 'Total reportes'; f = 'Conteos'; fmt = '#,0'; d = 'Reportes del inventario (Dim_Reporte).'; e = @'
// Sin +0 a propósito: solo queda en blanco cuando no hay reportes en el filtro,
// y así no genera combinaciones Área/Reporte inexistentes.
COUNTROWS ( Dim_Reporte )
'@ },
@{ n = 'Reportes en uso'; f = 'Conteos'; fmt = '#,0'; d = 'Reportes con 1 o más vistas de página.'; e = @'
IF (
    NOT ISEMPTY ( Dim_Reporte ),
    COUNTROWS ( FILTER ( Dim_Reporte, [Vistas de pagina] >= 1 ) ) + 0
)
'@ },
@{ n = 'Reportes solo aperturas'; f = 'Conteos'; fmt = '#,0'; d = 'Reportes con aperturas pero sin vistas de página.'; e = @'
IF (
    NOT ISEMPTY ( Dim_Reporte ),
    COUNTROWS ( FILTER ( Dim_Reporte, [Aperturas] > 0 && [Vistas de pagina] < 1 ) ) + 0
)
'@ },
@{ n = 'Reportes sin uso'; f = 'Conteos'; fmt = '#,0'; d = 'Reportes sin aperturas ni vistas de página.'; e = @'
IF (
    NOT ISEMPTY ( Dim_Reporte ),
    COUNTROWS ( FILTER ( Dim_Reporte, [Aperturas] = 0 && [Vistas de pagina] = 0 ) ) + 0
)
'@ },
@{ n = 'Aperturas por area o reporte'; f = 'Gráficos'; fmt = '#,0'; d = 'Barras del gráfico de la página Detalle (eje Eje_Detalle[Etiqueta]): con un área elegida en la segmentación, las aperturas de cada reporte de esa área; si no, las de cada área. En blanco sin aperturas, así esa barra no aparece.'; e = @'
// Eje_Detalle no tiene relaciones: cada fila trae su área o su reporte, que se aplica con TREATAS.
// Con UN área elegida, las barras son los reportes de esa área; con todas o varias, las áreas.
// KEEPFILTERS respeta lo elegido en las segmentaciones: un área no elegida queda en blanco.
// SUM sin +0: sin aperturas queda en blanco y esa barra no aparece.
VAR Nivel = IF ( HASONEVALUE ( Dim_Area[Area] ), "Reporte", "Area" )
RETURN
    SUMX (
        FILTER ( Eje_Detalle, Eje_Detalle[Nivel] = Nivel ),
        IF (
            Eje_Detalle[Nivel] = "Area",
            CALCULATE ( SUM ( Fact_Uso[aperturas] ), KEEPFILTERS ( TREATAS ( { Eje_Detalle[AreaEje] }, Dim_Area[Area] ) ) ),
            CALCULATE ( SUM ( Fact_Uso[aperturas] ), KEEPFILTERS ( TREATAS ( { Eje_Detalle[ClaveReporte] }, Dim_Reporte[report_id] ) ) )
        )
    )
'@ },
@{ n = 'Titulo grafico detalle'; f = 'Gráficos'; fmt = ''; d = 'Título del gráfico de la página Detalle: dice si las barras son las áreas o los reportes del área elegida.'; e = @'
IF (
    HASONEVALUE ( Dim_Area[Area] ),
    "APERTURAS POR REPORTE EN " & UPPER ( VALUES ( Dim_Area[Area] ) ) & " (DE MÁS A MENOS)",
    "APERTURAS POR ÁREA (DE MÁS A MENOS) · ELIJA UN ÁREA PARA VER SUS REPORTES"
)
'@ }
)

function Build-Modelo {
    $db = New-Object "$NS.Database"; $db.Name = $NombreProyecto; $db.ID = $db.Name; $db.CompatibilityLevel = 1600
    $m = New-Object "$NS.Model"; $m.Name = 'Model'; $m.Culture = 'es-ES'; $db.Model = $m
    try { $m.DefaultPowerBIDataSourceVersion = 'PowerBI_V3' } catch { }
    try { $m.SourceQueryCulture = 'es-ES' } catch { }
    $a = New-Object "$NS.Annotation"; $a.Name = '__PBI_TimeIntelligenceEnabled'; $a.Value = '0'; $m.Annotations.Add($a)

    # Parámetro RutaDatos: carpeta (con \ final) de los CSV
    $ex = New-Object "$NS.NamedExpression"; $ex.Name = 'RutaDatos'; $ex.Kind = 'M'
    $ruta = $RutaFinal.TrimEnd('\') + '\'
    $ex.Expression = '"' + $ruta.Replace('"', '""') + '" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]'
    $ex.LineageTag = GuidDe 'expresion|RutaDatos'
    $m.Expressions.Add($ex)

    Add-TablaM $m 'Fact_Uso' (Get-FactUso) @(
        @('fecha', 'DateTime'), @('workspace_id', 'String'), @('workspace_nombre', 'String'), @('report_id', 'String'),
        @('report_nombre', 'String'), @('usuario', 'String'), @('aperturas', 'Int64'), @('vistas_pagina', 'Int64'), @('es_sintetico', 'Boolean'))
    # Reporte (nombre único) y Area (nombre corto del workspace) son las columnas que usan los visuales
    Add-TablaM $m 'Dim_Reporte' $M_DIM_REPORTE @(
        @('report_id', 'String'), @('report_nombre', 'String'), @('workspace_id', 'String'), @('workspace_nombre', 'String'), @('url', 'String'),
        @('Area', 'String'), @('Reporte', 'String'))
    Add-TablaM $m 'Dim_Fecha' $M_DIM_FECHA @(
        @('Fecha', 'DateTime'), @('Anio', 'Int64'), @('Mes', 'Int64'), @('NombreMes', 'String'), @('Dia', 'Int64'), @('DiaSemana', 'String'),
        @('DiaSemanaNum', 'Int64'), @('NumSemana', 'Int64'), @('InicioSemana', 'DateTime'), @('Semana', 'String'),
        @('Ultimos28', 'Boolean'), @('FechaCorta', 'String'))
    Add-TablaM $m 'Dim_Usuario' $M_DIM_USUARIO @(@('usuario', 'String'), @('tipo_usuario', 'String'))
    Add-TablaM $m 'Dim_Area' $M_DIM_AREA @(@('workspace_id', 'String'), @('workspace_nombre', 'String'), @('Area', 'String'), @('ultima_lectura', 'DateTime'))
    Add-TablaCalc $m '_Medidas' 'ROW ( "x", 0 )' @(, @('x', 'Int64'))
    # Eje del gráfico de la página Detalle: las áreas y los reportes en una sola columna (Etiqueta), sin relaciones.
    # [Aperturas por area o reporte] muestra unas u otros según la segmentación de Área. Los nombres de columna no
    # coinciden con los de otras tablas: así Desktop no le detecta relaciones al cargar
    $daxEje = @'
UNION (
    SELECTCOLUMNS ( DISTINCT ( Dim_Area[Area] ), "Nivel", "Area", "Etiqueta", Dim_Area[Area], "AreaEje", Dim_Area[Area], "ClaveReporte", "" ),
    SELECTCOLUMNS ( Dim_Reporte, "Nivel", "Reporte", "Etiqueta", Dim_Reporte[Reporte], "AreaEje", Dim_Reporte[Area], "ClaveReporte", Dim_Reporte[report_id] )
)
'@
    Add-TablaCalc $m 'Eje_Detalle' $daxEje @(@('Nivel', 'String'), @('Etiqueta', 'String'), @('AreaEje', 'String'), @('ClaveReporte', 'String'))
    $m.Tables['_Medidas'].Columns['x'].IsHidden = $true
    $m.Tables['Dim_Fecha'].DataCategory = 'Time'
    $m.Tables['Dim_Fecha'].Columns['Fecha'].IsKey = $true

    Add-Relacion $m 'Fact_Uso' 'report_id' 'Dim_Reporte' 'report_id'
    Add-Relacion $m 'Fact_Uso' 'fecha' 'Dim_Fecha' 'Fecha'
    Add-Relacion $m 'Fact_Uso' 'usuario' 'Dim_Usuario' 'usuario'
    Add-Relacion $m 'Dim_Reporte' 'workspace_id' 'Dim_Area' 'workspace_id'

    foreach ($x in $medidas) {
        $ms = New-Object "$NS.Measure"; $ms.Name = $x.n; $ms.Expression = $x.e.Trim(); $ms.DisplayFolder = $x.f; $ms.Description = $x.d
        if ($x.fmt) { $ms.FormatString = $x.fmt }
        $m.Tables['_Medidas'].Measures.Add($ms)
    }
    $db
}

function Resumen($db, $etiqueta) {
    $m = $db.Model
    $med = $m.Tables['_Medidas'].Measures
    $carpetas = ($med | Group-Object DisplayFolder | ForEach-Object { "$($_.Name)=$($_.Count)" }) -join ', '
    $act = @($m.Relationships | Where-Object { $_.IsActive }).Count
    "[{0}] tablas={1} relaciones={2} (activas={3}) medidas={4} | carpetas: {5}" -f $etiqueta, $m.Tables.Count, $m.Relationships.Count, $act, $med.Count, $carpetas
}

# ======================= Acabado final y escritura al proyecto =======================
$db = Build-Modelo
$db.CompatibilityLevel = 1606
$m = $db.Model
$sinResumen = [Microsoft.AnalysisServices.Tabular.AggregateFunction]::None
# Sin medidas implícitas: arrastrar Fact_Uso[aperturas] a un visual sumaría sin el +0 ni la guarda de las medidas
try { $m.DiscourageImplicitMeasures = $true } catch { }

function Marcar($tabla, [string[]]$cols, [scriptblock]$accion) { foreach ($c in $cols) { & $accion $m.Tables[$tabla].Columns[$c] } }

# Columnas ocultas: claves técnicas, números y fecha de Fact_Uso (se usan las medidas y Dim_Fecha) y los nombres
# crudos que reemplazan Reporte y Area
Marcar 'Fact_Uso'    @('workspace_id','workspace_nombre','report_id','report_nombre','usuario','es_sintetico','fecha','aperturas','vistas_pagina') { param($c) $c.IsHidden = $true }
Marcar 'Dim_Reporte' @('report_id','report_nombre','workspace_id','workspace_nombre','url','Area') { param($c) $c.IsHidden = $true }
Marcar 'Dim_Area'    @('workspace_id','workspace_nombre','ultima_lectura') { param($c) $c.IsHidden = $true }
Marcar 'Dim_Fecha'   @('DiaSemanaNum','InicioSemana','Ultimos28') { param($c) $c.IsHidden = $true }
Marcar 'Eje_Detalle' @('Nivel','AreaEje','ClaveReporte') { param($c) $c.IsHidden = $true }
$m.Tables['Eje_Detalle'].Description = 'Eje del gráfico de aperturas de la página Detalle: áreas y reportes, sin relaciones (ver la medida Aperturas por area o reporte).'

# Claves
Marcar 'Dim_Reporte' @('report_id')    { param($c) $c.IsKey = $true }
Marcar 'Dim_Usuario' @('usuario')      { param($c) $c.IsKey = $true }
Marcar 'Dim_Area'    @('workspace_id') { param($c) $c.IsKey = $true }

# Formatos
Marcar 'Fact_Uso'  @('fecha')                        { param($c) $c.FormatString = 'dd-MM-yyyy' }
Marcar 'Dim_Fecha' @('Fecha','InicioSemana')         { param($c) $c.FormatString = 'dd-MM-yyyy' }
Marcar 'Dim_Area'  @('ultima_lectura')               { param($c) $c.FormatString = 'dd-MM-yyyy HH:mm' }
Marcar 'Fact_Uso'  @('aperturas','vistas_pagina')    { param($c) $c.FormatString = '#,0' }
Marcar 'Dim_Fecha' @('Anio','Mes','Dia','DiaSemanaNum','NumSemana') { param($c) $c.FormatString = '0'; $c.SummarizeBy = $sinResumen }
foreach ($par in @(@('Fact_Uso','fecha'), @('Dim_Fecha','Fecha'), @('Dim_Fecha','InicioSemana'))) {
    $a = New-Object "$NS.Annotation"; $a.Name = 'UnderlyingDateTimeDataType'; $a.Value = 'Date'
    $m.Tables[$par[0]].Columns[$par[1]].Annotations.Add($a)
}
# Los nombres de mes y de día se ordenan por su número, no alfabéticamente; la semana, por su lunes, y la fecha corta,
# por la fecha
$m.Tables['Dim_Fecha'].Columns['NombreMes'].SortByColumn = $m.Tables['Dim_Fecha'].Columns['Mes']
$m.Tables['Dim_Fecha'].Columns['DiaSemana'].SortByColumn = $m.Tables['Dim_Fecha'].Columns['DiaSemanaNum']
$m.Tables['Dim_Fecha'].Columns['Semana'].SortByColumn = $m.Tables['Dim_Fecha'].Columns['InicioSemana']
$m.Tables['Dim_Fecha'].Columns['FechaCorta'].SortByColumn = $m.Tables['Dim_Fecha'].Columns['Fecha']

# Anotaciones del modelo (las mismas que pone Desktop en un .pbip)
foreach ($kv in @(@('PBI_ProTooling','["DevMode"]'), @('PBI_QueryOrder','["RutaDatos","Fact_Uso","Dim_Reporte","Dim_Fecha","Dim_Usuario","Dim_Area"]'))) {
    $a = New-Object "$NS.Annotation"; $a.Name = $kv[0]; $a.Value = $kv[1]; $m.Annotations.Add($a)
}

# lineageTag en todo (los usa Desktop para identificar objetos); estables, para que regenerar sin cambios no cambie nada
foreach ($t in $m.Tables) {
    $t.LineageTag = GuidDe "tabla|$($t.Name)"
    foreach ($c in $t.Columns)  { $c.LineageTag = GuidDe "columna|$($t.Name)|$($c.Name)" }
    foreach ($x in $t.Measures) { $x.LineageTag = GuidDe "medida|$($t.Name)|$($x.Name)" }
}

$utf8 = New-Object Text.UTF8Encoding($false)
function Remove-Carpeta([string]$dir) {
    # Quita atributos de solo lectura antes de borrar. Devuelve $false si no pudo.
    if (-not [IO.Directory]::Exists($dir)) { return $true }
    try {
        Get-ChildItem -LiteralPath $dir -Recurse -Force | ForEach-Object { $_.Attributes = 'Normal' }
        [IO.Directory]::Delete($dir, $true)
        return $true
    } catch { Write-Host "AVISO: no se pudo borrar $dir ($($_.Exception.Message))." -ForegroundColor Yellow; return $false }
}

# ---------- Respaldo para la Vista TMDL de Desktop: las mismas 22 medidas, listas para pegar (createOrReplace) ----------
$sb = New-Object Text.StringBuilder
[void]$sb.Append("createOrReplace`r`n`r`n`tref table _Medidas`r`n")
foreach ($x in $medidas) {
    $nombre = if ($x.n -match '^[A-Za-z_][A-Za-z0-9_]*$') { $x.n } else { "'" + $x.n.Replace("'", "''") + "'" }
    [void]$sb.Append("`r`n`t`t/// $($x.d)`r`n`t`tmeasure $nombre =`r`n")
    foreach ($l in ($x.e.Trim() -split "`r?`n")) { [void]$sb.Append("`t`t`t`t$l`r`n") }
    if ($x.fmt) { [void]$sb.Append("`t`t`tformatString: $($x.fmt)`r`n") }
    [void]$sb.Append("`t`t`tdisplayFolder: $($x.f)`r`n")
}
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'medidas_vista_TMDL.tmdl'), $sb.ToString(), $utf8)

# ---------- Escritura: SemanticModel\definition (TMDL generado por la biblioteca oficial de Desktop) ----------
$dirSM    = Join-Path $Proyecto "$NombreProyecto.SemanticModel"
$dirDef   = Join-Path $dirSM 'definition'
# Carpetas temporales con nombres no más largos que "definition": no alargan las rutas (límite de 260)
$dirNuevo = Join-Path $dirSM '_gen_nuevo'
$dirViejo = Join-Path $dirSM '_gen_anterior'
if (Get-Process PBIDesktop -ErrorAction SilentlyContinue) {
    Write-Host 'AVISO: Power BI Desktop está abierto. Si tiene abierto este proyecto, ciérralo SIN guardar y ábrelo de nuevo al terminar: si guarda, pisará lo generado.' -ForegroundColor Yellow
}
[void][IO.Directory]::CreateDirectory($dirSM)
# Restos de una corrida cortada a mitad: si falta definition pero quedó la anterior, se repone primero
if (-not [IO.Directory]::Exists($dirDef) -and [IO.Directory]::Exists($dirViejo)) {
    [IO.Directory]::Move($dirViejo, $dirDef)
    Write-Host 'AVISO: una corrida anterior se cortó a mitad; se repuso el modelo anterior.' -ForegroundColor Yellow
}
foreach ($d in @($dirNuevo, $dirViejo)) {
    if (-not (Remove-Carpeta $d)) {
        Write-Host "NO SE REGENERÓ: no se pudo borrar la carpeta temporal $d (¿abierta en otro programa?). El modelo actual quedó intacto." -ForegroundColor Red
        exit 3
    }
}

# Escritura atómica: se serializa en una carpeta aparte y solo al final se cambia por la actual.
[void][IO.Directory]::CreateDirectory($dirNuevo)
try {
    [Microsoft.AnalysisServices.Tabular.TmdlSerializer]::SerializeDatabaseToFolder($db, $dirNuevo)
    # database.tmdl en el formato que escribe Desktop para .pbip
    [IO.File]::WriteAllText((Join-Path $dirNuevo 'database.tmdl'), "database`r`n`tcompatibilityLevel: 1606`r`n", $utf8)
} catch {
    [void](Remove-Carpeta $dirNuevo)
    Write-Host "NO SE REGENERÓ: error al escribir el modelo nuevo ($($_.Exception.Message)). El actual quedó intacto." -ForegroundColor Red
    exit 3
}
$habia = [IO.Directory]::Exists($dirDef)
if ($habia) {
    try { [IO.Directory]::Move($dirDef, $dirViejo) }
    catch {
        [void](Remove-Carpeta $dirNuevo)
        Write-Host "NO SE REGENERÓ: no se pudo reemplazar $dirDef ($($_.Exception.Message))." -ForegroundColor Red
        Write-Host 'Cierra Power BI Desktop (y espera a que termine cualquier sincronización) y vuelve a intentarlo. El modelo actual quedó intacto.'
        exit 3
    }
}
try { [IO.Directory]::Move($dirNuevo, $dirDef) }
catch {
    $motivo = $_.Exception.Message
    if ($habia) { try { [IO.Directory]::Move($dirViejo, $dirDef) } catch { } }
    [void](Remove-Carpeta $dirNuevo)
    Write-Host "NO SE REGENERÓ: no se pudo poner el modelo nuevo ($motivo). Se intentó reponer el anterior." -ForegroundColor Red
    exit 3
}
if ($habia) { [void](Remove-Carpeta $dirViejo) }

Resumen $db 'modelo escrito'
Write-Host "RutaDatos = $($RutaFinal.TrimEnd('\') + '\')"
Get-ChildItem -LiteralPath $dirDef -Recurse -File | ForEach-Object { '  ' + $_.FullName.Substring($Proyecto.Length).TrimStart('\') }
