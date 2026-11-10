# Valida la sintaxis TMDL del modelo con el serializador que trae Power BI Desktop (sin abrir el informe).
# Lee la carpeta definition/ y la deserializa como base de datos tabular: si hay un error de sintaxis o de metadatos
# (sangría, propiedades desconocidas, relaciones a columnas inexistentes...) lo informa con el archivo y la línea.
# No evalúa DAX ni refresca datos.
#
# Uso: powershell -NoProfile -File tools_proyecto\validar_tmdl.ps1 [-Carpeta pbip\<modelo>.SemanticModel\definition]
param([string]$Carpeta)
$ErrorActionPreference = 'Stop'
$raiz = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $Carpeta) {
    $sm = Get-ChildItem (Join-Path $raiz 'pbip') -Directory -Filter '*.SemanticModel' | Select-Object -First 1
    $Carpeta = Join-Path $sm.FullName 'definition'
}
$bin = Join-Path $env:ProgramFiles 'Microsoft Power BI Desktop\bin'
if (-not (Test-Path (Join-Path $bin 'Microsoft.PowerBI.Tabular.dll'))) {
    $pkg = Get-AppxPackage -Name 'Microsoft.MicrosoftPowerBIDesktop' | Sort-Object Version -Descending | Select-Object -First 1
    if (-not $pkg) { Write-Output 'ERROR: no encontré Power BI Desktop (ni MSI ni Microsoft Store)'; exit 1 }
    $bin = Join-Path $pkg.InstallLocation 'bin'
}
[Reflection.Assembly]::LoadFrom((Join-Path $bin 'Microsoft.PowerBI.Tabular.dll')) | Out-Null
try {
    $db = [Microsoft.AnalysisServices.Tabular.TmdlSerializer]::DeserializeDatabaseFromFolder($Carpeta)
    $medidas = 0
    foreach ($t in $db.Model.Tables) { $medidas += $t.Measures.Count }
    Write-Output ("TMDL VÁLIDO: {0} tablas, {1} medidas, {2} relaciones, {3} parámetros" -f `
        $db.Model.Tables.Count, $medidas, $db.Model.Relationships.Count, $db.Model.Expressions.Count)
} catch {
    Write-Output ("ERROR: " + $_.Exception.Message)
    if ($_.Exception.InnerException) { Write-Output ("DETALLE: " + $_.Exception.InnerException.Message) }
    exit 2
}
