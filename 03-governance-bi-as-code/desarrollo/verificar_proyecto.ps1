# Verifica el proyecto Gobernanza_uso_reportes sin abrir Power BI Desktop.
#
#   1. El TMDL del modelo semántico se deserializa con la biblioteca de Power BI Desktop (TOM); estructura esperada,
#      origen de datos (solo CSV de RutaDatos) y usuarios excluidos.
#   2. Estructura de archivos y referencias cruzadas del .pbip (tema y logo incluidos).
#   3. Páginas y visuales: JSON legible, nombres únicos, dentro del lienzo.
#   4. Cada campo que usan los visuales, sus filtros y las páginas debe existir en el modelo.
#   5. Cada JSON del informe, tal como está EN DISCO, valida contra su esquema (validar_disco.py).
#
# Uso (desde la carpeta desarrollo\):
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File verificar_proyecto.ps1 [-Esquemas <carpeta>]
# Lo único que no se puede comprobar sin abrir Desktop: que los datos carguen y que las cifras cuadren
# (para eso está validacion_datos.dax).
param(
    [string]$Proyecto = (Split-Path -Parent $PSScriptRoot),
    [string]$Nombre = 'Gobernanza_uso_reportes',
    [string]$Esquemas
)
$ErrorActionPreference = 'Stop'
$fallos = 0
function Bien($m) { Write-Host "  OK      $m" }
function Mal($m) { Write-Host "  FALLA   $m" -ForegroundColor Red; $script:fallos++ }
function Aviso($m) { Write-Host "  AVISO   $m" -ForegroundColor Yellow }
# JSON siempre como UTF-8: Get-Content sin -Encoding usa ANSI en Windows PowerShell 5.1 y rompe las tildes
function Read-Json([string]$ruta) { [IO.File]::ReadAllText($ruta, [Text.Encoding]::UTF8) | ConvertFrom-Json }
function Relativa([string]$ruta) { if ($ruta.StartsWith($Proyecto)) { $ruta.Substring($Proyecto.Length).TrimStart('\') } else { $ruta } }

$dirSM = Join-Path $Proyecto "$Nombre.SemanticModel"
$dirRep = Join-Path $Proyecto "$Nombre.Report"
$dirDef = Join-Path $dirRep 'definition'
$logo = 'logo_minera_demo_blanco.png'

Write-Host "`n=== 1. Modelo semántico (TMDL) ==="
# Biblioteca TOM de Power BI Desktop: la de la instalación MSI si existe; si no, la de Microsoft Store.
$loc = Join-Path $env:ProgramFiles 'Microsoft Power BI Desktop'
if (-not [IO.File]::Exists("$loc\bin\Microsoft.PowerBI.Tabular.dll")) { $loc = (Get-AppxPackage -Name 'Microsoft.MicrosoftPowerBIDesktop').InstallLocation }
if (-not $loc) { Mal 'no se encontró Power BI Desktop instalado'; exit 1 }
[void][Reflection.Assembly]::LoadFrom("$loc\bin\Microsoft.PowerBI.Tabular.dll")
try {
    $db = [Microsoft.AnalysisServices.Tabular.TmdlSerializer]::DeserializeDatabaseFromFolder((Join-Path $dirSM 'definition'))
    Bien "TMDL válido (nivel de compatibilidad $($db.CompatibilityLevel))"
} catch {
    Mal "el TMDL no se pudo leer: $($_.Exception.Message)"
    exit 1
}
$m = $db.Model

# 7 tablas: las 5 del esquema en estrella (hecho + 4 dimensiones), _Medidas y Eje_Detalle (auxiliar, sin relaciones)
$esperado = @{ tablas = 7; relaciones = 4; medidas = 22 }
$nTablas = $m.Tables.Count
$nRel = $m.Relationships.Count
$nAct = @($m.Relationships | Where-Object { $_.IsActive }).Count
$nMed = $m.Tables['_Medidas'].Measures.Count
if ($nTablas -eq $esperado.tablas) { Bien "$nTablas tablas" } else { Mal "tablas: $nTablas (se esperaban $($esperado.tablas))" }
if ($nRel -eq $esperado.relaciones -and $nAct -eq $esperado.relaciones) { Bien "$nRel relaciones, todas activas" } else { Mal "relaciones: $nRel ($nAct activas), se esperaban $($esperado.relaciones)" }
if ($nMed -eq $esperado.medidas) { Bien "$nMed medidas en _Medidas" } else { Mal "medidas: $nMed (se esperaban $($esperado.medidas); si agregaste medidas a propósito, actualiza `$esperado en este script)" }

$malCard = @($m.Relationships | Where-Object { -not (($_.FromCardinality -eq 'Many' -and $_.ToCardinality -eq 'One') -or ($_.FromCardinality -eq 'One' -and $_.ToCardinality -eq 'Many')) })
if ($malCard.Count -eq 0) { Bien 'todas las relaciones son varios a uno' } else { Mal "$($malCard.Count) relación(es) no son varios a uno" }
$bidi = @($m.Relationships | Where-Object { $_.CrossFilteringBehavior -ne 'OneDirection' })
if ($bidi.Count -eq 0) { Bien 'todas las relaciones filtran en un solo sentido' } else { Mal "$($bidi.Count) relación(es) filtran en ambos sentidos" }

if ($m.Tables['Dim_Fecha'].DataCategory -eq 'Time') { Bien 'Dim_Fecha marcada como tabla de fechas' } else { Mal 'Dim_Fecha no está marcada como tabla de fechas' }
$sinCarpeta = @($m.Tables['_Medidas'].Measures | Where-Object { -not $_.DisplayFolder })
if ($sinCarpeta.Count -eq 0) { Bien 'todas las medidas tienen carpeta' } else { Mal "$($sinCarpeta.Count) medida(s) sin carpeta" }
$sinDesc = @($m.Tables['_Medidas'].Measures | Where-Object { -not $_.Description })
if ($sinDesc.Count -eq 0) { Bien 'todas las medidas tienen descripción' } else { Mal "$($sinDesc.Count) medida(s) sin descripción" }

# Origen de datos: el parámetro RutaDatos y consultas que leen solo CSV de esa carpeta (sin conexiones a servicios)
if (-not $m.Expressions['RutaDatos']) { Mal 'falta el parámetro RutaDatos' }
else {
    $ruta = ([regex]::Match($m.Expressions['RutaDatos'].Expression, '"([^"]+)"')).Groups[1].Value
    $csv = @{ Fact_Uso = 'fact_uso.csv'; Dim_Reporte = 'dim_reporte.csv'; Dim_Area = 'lecturas_area.csv' }
    foreach ($t in $csv.Keys) {
        $tb = $m.Tables[$t]
        $src = if ($tb) { [string]$tb.Partitions[0].Source.Expression } else { '' }
        if ($src.Contains("Csv.Document(File.Contents(RutaDatos & ""$($csv[$t])"")")) { Bien "$t lee $($csv[$t]) de RutaDatos" }
        else { Mal "$t no lee $($csv[$t]) con Csv.Document(File.Contents(RutaDatos & ...)): regenera con generar_modelo.ps1" }
    }
    $acceso = 'Web\.Contents|Folder\.(Files|Contents)|SharePoint\.|Sql\.Database|OData\.Feed|AnalysisServices|Excel\.Workbook'
    $conServicio = @($m.Tables | Where-Object { $_.Partitions.Count -and $_.Partitions[0].Source -is [Microsoft.AnalysisServices.Tabular.MPartitionSource] -and ([string]$_.Partitions[0].Source.Expression) -match $acceso } | ForEach-Object { $_.Name })
    if ($conServicio.Count -eq 0) { Bien 'ninguna consulta abre conexiones a servicios: solo CSV locales' } else { Mal "$($conServicio -join ', ') accede(n) a un servicio en vez de CSV" }

    # Usuarios excluidos: Fact_Uso trae escrita la lista usuarios_excluidos de config_datos.json
    $fact = [string]$m.Tables['Fact_Uso'].Partitions[0].Source.Expression
    $cfg = $null
    $cfgArch = Join-Path $PSScriptRoot 'config_datos.json'
    if ([IO.File]::Exists($cfgArch)) { try { $cfg = Read-Json $cfgArch } catch { $cfg = $null } }
    $esperados = @(@(if ($cfg -is [System.Management.Automation.PSCustomObject] -and $cfg.usuarios_excluidos) { $cfg.usuarios_excluidos }) |
        ForEach-Object { ([string]$_).Trim().ToLowerInvariant() } | Where-Object { $_ } | Select-Object -Unique)
    $mEx = [regex]::Match($fact, 'Excluidos = List\.Buffer\(\{([^}]*)\}\)')
    if ($fact.Contains('{{USUARIOS_EXCLUIDOS}}')) { Mal 'Fact_Uso trae {{USUARIOS_EXCLUIDOS}} sin reemplazar: regenera con generar_modelo.ps1' }
    elseif (-not $mEx.Success) { Mal 'Fact_Uso no trae la lista de usuarios excluidos (Excluidos = List.Buffer({...})): regenera con generar_modelo.ps1' }
    else {
        $enModelo = @([regex]::Matches($mEx.Groups[1].Value, '"([^"]*)"') | ForEach-Object { $_.Groups[1].Value })
        if ((@($enModelo | Sort-Object) -join '|') -eq (@($esperados | Sort-Object) -join '|')) {
            Bien "Fact_Uso no cuenta el uso de $($enModelo.Count) usuario(s) excluido(s) (usuarios_excluidos de config_datos.json)"
        } else { Mal "Fact_Uso excluye $($enModelo.Count) usuario(s) y config_datos.json pide $($esperados.Count) (o son otros): regenera con generar_modelo.ps1" }
    }

    # RutaDatos: con el marcador no se puede comprobar nada; con una ruta real, deben estar los tres CSV
    if ($ruta.StartsWith('RUTA_DEL_CLON')) {
        Aviso 'RutaDatos tiene el marcador RUTA_DEL_CLON: antes de abrir el informe, fija la ruta (generar_modelo.ps1 -Local, o en Desktop: Transformar datos > Administrar parámetros)'
    } elseif (-not [IO.Directory]::Exists($ruta)) {
        Mal "RutaDatos apunta a $ruta, que no existe"
    } else {
        $faltan = @($csv.Values | Where-Object { -not [IO.File]::Exists((Join-Path $ruta $_)) })
        if ($faltan.Count -eq 0) { Bien "RutaDatos apunta a una carpeta con los $($csv.Count) CSV ($ruta)" }
        else { Mal "en RutaDatos ($ruta) faltan: $($faltan -join ', ') (python datos_sinteticos\generar_datos.py)" }
    }
    # Con datos sintéticos, el informe debe llevar el aviso
    $aviso = Join-Path $dirDef 'pages\paginaResumen\visuals\txtResumenAviso\visual.json'
    if ([IO.File]::Exists($aviso) -and [IO.File]::ReadAllText($aviso, [Text.Encoding]::UTF8).Contains('DATOS SINTÉTICOS')) { Bien 'el informe lleva el aviso de datos sintéticos' }
    else { Mal 'el informe no lleva el aviso de datos sintéticos (generar_reporte.py, constante DATOS_SINTETICOS)' }
}

Write-Host "`n=== 2. Archivos del proyecto ==="
$requeridos = @(
    "$Nombre.pbip",
    "$Nombre.Report\.platform", "$Nombre.Report\definition.pbir",
    "$Nombre.Report\definition\report.json", "$Nombre.Report\definition\version.json",
    "$Nombre.Report\definition\pages\pages.json",
    "$Nombre.Report\StaticResources\RegisteredResources\$Nombre.json",
    "$Nombre.Report\StaticResources\RegisteredResources\$logo",
    "$Nombre.SemanticModel\.platform", "$Nombre.SemanticModel\definition.pbism"
)
foreach ($r in $requeridos) {
    if ([IO.File]::Exists((Join-Path $Proyecto $r))) { Bien $r } else { Mal "falta $r" }
}
# Recursos del informe: el tema propio y el logo deben existir, y el tema debe llamarse igual que su ruta (como lo
# nombra Desktop). Si no, Desktop abre el informe con el tema por defecto: fondo blanco y sin el diseño oscuro.
try {
    $rj = Read-Json (Join-Path $dirRep 'definition\report.json')
    $items = @($rj.resourcePackages | ForEach-Object { $_.items })
    $itemsTema = @($items | Where-Object { $_.type -eq 'CustomTheme' })
    $nombreTema = [string]$rj.themeCollection.customTheme.name
    if ($itemsTema.Count -ne 1) { Mal "report.json registra $($itemsTema.Count) temas propios (se espera 1): regenera con generar_reporte.py" }
    else {
        $it = $itemsTema[0]
        $archivoTema = Join-Path $dirRep "StaticResources\RegisteredResources\$($it.path)"
        if (-not [IO.File]::Exists($archivoTema)) { Mal "el tema de report.json apunta a '$($it.path)', que no existe: Desktop lo abrirá con fondo blanco" }
        elseif ($it.name -ne $it.path -or $nombreTema -ne $it.name) { Mal "el tema tiene nombre '$($it.name)' / '$nombreTema' y ruta '$($it.path)': al guardar, Desktop copia el nombre en la ruta y la rompe. Regenera con generar_reporte.py" }
        else { Bien "el tema propio ($($it.path)) existe y su nombre coincide con la ruta, como lo guarda Desktop" }
    }
    $itLogo = @($items | Where-Object { $_.type -eq 'Image' -and $_.path -eq $logo })
    if ($itLogo.Count -eq 1) { Bien "el logo ($logo) está registrado como imagen en report.json" } else { Mal "report.json no registra la imagen $logo" }
} catch { Mal "no se pudo revisar el tema en report.json ($($_.Exception.Message))" }
try {
    $pbir = Read-Json (Join-Path $dirRep 'definition.pbir')
    $apuntaA = Join-Path $dirRep $pbir.datasetReference.byPath.path
    if ([IO.File]::Exists((Join-Path $apuntaA 'definition.pbism'))) { Bien 'el informe apunta a su modelo semántico' } else { Mal "definition.pbir apunta a $($pbir.datasetReference.byPath.path), que no es un modelo válido" }
} catch { Mal "no se pudo leer definition.pbir ($($_.Exception.Message))" }
try {
    $pbip = Read-Json (Join-Path $Proyecto "$Nombre.pbip")
    if ([IO.Directory]::Exists((Join-Path $Proyecto $pbip.artifacts[0].report.path))) { Bien 'el .pbip apunta a su carpeta de informe' } else { Mal 'el .pbip no apunta a una carpeta de informe válida' }
} catch { Mal "no se pudo leer $Nombre.pbip ($($_.Exception.Message))" }
foreach ($t in @("$Nombre.Report\_gen_nuevo", "$Nombre.Report\_gen_anterior", "$Nombre.SemanticModel\_gen_nuevo", "$Nombre.SemanticModel\_gen_anterior")) {
    if ([IO.Directory]::Exists((Join-Path $Proyecto $t))) { Aviso "quedó la carpeta temporal $t de una corrida cortada: la próxima corrida del generador la limpia o repone" }
}

Write-Host "`n=== 3. Páginas y visuales ==="
# Se lee cada JSON una sola vez; uno ilegible (vacío, truncado, mal editado) es una falla, no un error del script
$jsonVisual = [ordered]@{}
$jsonOtros = New-Object System.Collections.ArrayList
$dirPages = Join-Path $dirDef 'pages'
if (-not [IO.Directory]::Exists($dirPages)) {
    Mal "falta la carpeta $(Relativa $dirPages): el informe no tiene páginas"
} else {
    try {
        $pages = Read-Json (Join-Path $dirPages 'pages.json')
        $dirsPagina = @([IO.Directory]::GetDirectories($dirPages) | ForEach-Object { Split-Path $_ -Leaf })
        $faltan = @($pages.pageOrder | Where-Object { $_ -notin $dirsPagina })
        $sobran = @($dirsPagina | Where-Object { $_ -notin $pages.pageOrder })
        if ($faltan.Count -eq 0 -and $sobran.Count -eq 0) { Bien "$($pages.pageOrder.Count) páginas, todas con definición y en orden" }
        else { Mal "pages.json no coincide con las carpetas (faltan: $($faltan -join ',') | sobran: $($sobran -join ','))" }
        if ($pages.activePageName -in $dirsPagina) { Bien "página activa: $($pages.activePageName)" } else { Mal 'la página activa no existe' }
    } catch { Mal "no se pudo leer pages.json ($($_.Exception.Message))" }
    # [IO.Directory]::GetFiles conserva el prefijo tal como se pasó (Get-ChildItem expande los nombres cortos 8.3)
    foreach ($v in ([IO.Directory]::GetFiles($dirPages, 'visual.json', [IO.SearchOption]::AllDirectories) | Sort-Object)) {
        try { $j = Read-Json $v } catch { Mal "JSON ilegible: $(Relativa $v) ($($_.Exception.Message))"; continue }
        if ($j -isnot [System.Management.Automation.PSCustomObject] -or -not $j.name) { Mal "visual vacío o sin 'name': $(Relativa $v)"; continue }
        $jsonVisual[$v] = $j
    }
    foreach ($f in @([IO.Directory]::GetFiles($dirPages, 'page.json', [IO.SearchOption]::AllDirectories)) + @(Join-Path $dirDef 'report.json')) {
        try { $j = Read-Json $f } catch { Mal "JSON ilegible: $(Relativa $f) ($($_.Exception.Message))"; continue }
        if ($j -is [System.Management.Automation.PSCustomObject]) { [void]$jsonOtros.Add($j) } else { Mal "JSON vacío o que no es un objeto: $(Relativa $f)" }
    }
}

$nombres = @{}
$dup = 0
foreach ($k in $jsonVisual.Keys) {
    $j = $jsonVisual[$k]
    if ($nombres.ContainsKey([string]$j.name)) { $dup++ } else { $nombres[[string]$j.name] = $true }
    $carpeta = Split-Path (Split-Path $k -Parent) -Leaf
    if ($j.name -ne $carpeta) { Mal "el visual $($j.name) no coincide con su carpeta $carpeta" }
}
if ($dup -eq 0) { Bien "$($jsonVisual.Count) visuales con nombre único" } else { Mal "$dup visual(es) con nombre repetido" }

# Cada visual contra el lienzo de su página (pages/<pagina>/visuals/<visual>/visual.json -> pages/<pagina>/page.json)
$fuera = 0
$lienzos = @{}
foreach ($k in $jsonVisual.Keys) {
    $dirPagina = Split-Path (Split-Path (Split-Path $k -Parent) -Parent) -Parent
    if (-not $lienzos.ContainsKey($dirPagina)) {
        $pj = $null
        try { $pj = Read-Json (Join-Path $dirPagina 'page.json') } catch { }
        $lienzos[$dirPagina] = if ($pj -and $pj.width -and $pj.height) { @([double]$pj.width, [double]$pj.height) } else { @(1280, 720) }
    }
    $anchoPag, $altoPag = $lienzos[$dirPagina]
    $p = $jsonVisual[$k].position
    if ($p.x -lt 0 -or $p.y -lt 0 -or ($p.x + $p.width) -gt $anchoPag -or ($p.y + $p.height) -gt $altoPag) { $fuera++ }
}
$tamanos = ($lienzos.Values | ForEach-Object { "$($_[0])x$($_[1])" } | Sort-Object -Unique) -join ', '
if ($fuera -eq 0) { Bien "todos los visuales caben en el lienzo de su página ($tamanos)" } else { Mal "$fuera visual(es) se salen del lienzo de su página" }

Write-Host "`n=== 4. Campos de los visuales contra el modelo ==="
# Índice de lo que existe en el modelo
$existe = @{}
foreach ($t in $m.Tables) {
    foreach ($c in $t.Columns) { $existe["$($t.Name)|$($c.Name)|col"] = $true }
    foreach ($x in $t.Measures) { $existe["$($t.Name)|$($x.Name)|med"] = $true }
}

# Recorre el JSON buscando referencias {Column|Measure: {Expression: {SourceRef}, Property}}.
# SourceRef trae la tabla (Entity) o un alias (Source) que declara el "From" de un filtro:
# Desktop usa alias como "m", "d" o "d1", así que se resuelven en vez de suponer uno fijo.
function Buscar-Campos($nodo, [hashtable]$alias, $acc) {
    if ($null -eq $nodo) { return }
    if ($nodo -is [System.Collections.IEnumerable] -and $nodo -isnot [string]) {
        foreach ($i in $nodo) { Buscar-Campos $i $alias $acc }
        return
    }
    if ($nodo -isnot [psobject]) { return }
    $from = $nodo.PSObject.Properties['From']
    if ($from -and $from.Value) {
        $alias = $alias.Clone()
        foreach ($f in @($from.Value)) { if ($f.Name -and $f.Entity) { $alias[[string]$f.Name] = [string]$f.Entity } }
    }
    foreach ($prop in $nodo.PSObject.Properties) {
        if ($prop.Name -in 'Column', 'Measure' -and $prop.Value.Property) {
            $src = $prop.Value.Expression.SourceRef
            $tabla = if ($src.Entity) { [string]$src.Entity }
                     elseif ($src.Source -and $alias.ContainsKey([string]$src.Source)) { $alias[[string]$src.Source] }
                     else { "(alias sin declarar: $($src.Source))" }
            [void]$acc.Add([pscustomobject]@{
                    tabla = $tabla
                    campo = $prop.Value.Property
                    tipo  = if ($prop.Name -eq 'Column') { 'col' } else { 'med' }
                })
        }
        Buscar-Campos $prop.Value $alias $acc
    }
}

$refs = New-Object System.Collections.ArrayList
foreach ($j in $jsonVisual.Values) { Buscar-Campos $j @{} $refs }
foreach ($j in $jsonOtros) { Buscar-Campos $j @{} $refs }   # filtros de página y de informe agregados en Desktop
$unicos = @($refs | Sort-Object tabla, campo, tipo -Unique)
$malas = @($unicos | Where-Object { -not $existe["$($_.tabla)|$($_.campo)|$($_.tipo)"] })
if ($malas.Count -eq 0) {
    Bien "$($unicos.Count) referencias distintas a campos (visuales, filtros y páginas), todas existen en el modelo"
} else {
    foreach ($b in $malas) { Mal "se usa $($b.tabla)[$($b.campo)] ($($b.tipo)), que no existe en el modelo" }
}

$usadas = @($unicos | Where-Object { $_.tipo -eq 'med' -and $_.tabla -eq '_Medidas' } | Select-Object -ExpandProperty campo)
$sinUsar = @($m.Tables['_Medidas'].Measures.Name | Where-Object { $_ -notin $usadas })
if ($sinUsar.Count -eq 0) { Bien "las $nMed medidas se usan en algún visual" } else { Aviso "medidas sin usar en ningún visual: $($sinUsar -join ', ')" }

Write-Host "`n=== 5. JSON del informe en disco contra sus esquemas ==="
$py = @('python', 'py') | Where-Object { Get-Command $_ -ErrorAction SilentlyContinue } | Select-Object -First 1
if ($py) {
    # Continue: en PowerShell 5.1, con 'Stop', una línea de Python en stderr cortaría el script
    $ErrorActionPreference = 'Continue'
    $argumentos = @((Join-Path $PSScriptRoot 'validar_disco.py'), $Proyecto)
    if ($Esquemas) { $argumentos += @('--esquemas', $Esquemas) }
    $sal = @(& $py @argumentos 2>&1 | ForEach-Object { "$_" })
    $rc = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($rc -eq 0) { Bien ($sal | Select-Object -Last 1) }
    elseif ($rc -eq 3) { Aviso "no se validaron los esquemas JSON: $($sal | Select-Object -Last 1)" }
    else {
        $lineas = @($sal | Where-Object { $_ -match '^FALLA' })
        if ($lineas.Count) { $lineas | Select-Object -First 15 | ForEach-Object { Mal ($_ -replace '^FALLA\s+', '') } }
        else { Mal "la validación de esquemas falló: $($sal | Select-Object -Last 3)" }
    }
} else { Aviso 'sin Python: no se validaron los esquemas JSON' }

Write-Host ''
if ($fallos -eq 0) {
    Write-Host 'TODO EN ORDEN. Falta lo único que no se puede comprobar sin abrir Desktop:' -ForegroundColor Green
    Write-Host 'que los datos carguen y que las cifras cuadren (para eso está validacion_datos.dax).'
} else {
    Write-Host "$fallos comprobación(es) fallaron." -ForegroundColor Red
}
exit [int]($fallos -gt 0)
