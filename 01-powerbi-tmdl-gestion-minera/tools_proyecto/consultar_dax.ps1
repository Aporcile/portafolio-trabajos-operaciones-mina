# Consultas DAX y DMV de SOLO LECTURA contra el modelo del proyecto abierto en Power BI Desktop.
# No modifica el modelo ni los archivos. Detecta el puerto del motor local en cada corrida.
#
# Uso:
#   powershell -NoProfile -File tools_proyecto\consultar_dax.ps1 -Dax "EVALUATE ROW(""Dia"", [Rd Día])"
#   powershell -NoProfile -File tools_proyecto\consultar_dax.ps1 -Archivo consulta.dax [-OutCsv salida.csv]
#   powershell -NoProfile -File tools_proyecto\consultar_dax.ps1 -Pbip "Informe Operaciones Demo.pbip" -Dax "..."
#
# Para probar una medida SVG: EVALUATE ROW("svg", [Rd SVG Movimiento]) y pegar el resultado en un navegador.
param(
    [string]$Dax,
    [string]$Archivo,
    [string]$OutCsv,
    [string]$Pbip = 'Informe Operaciones Demo.pbip',
    [int]$Preview = 80,
    [int]$Port = 0
)
$ErrorActionPreference = 'Stop'
if ($Archivo) { $Dax = [IO.File]::ReadAllText($Archivo) }
if (-not $Dax) { Write-Output 'ERROR: falta -Dax o -Archivo'; exit 1 }

if ($Port -eq 0) {
    $pbi = Get-CimInstance Win32_Process -Filter "Name='PBIDesktop.exe'" | Where-Object { $_.CommandLine -like "*$Pbip*" } | Select-Object -First 1
    if (-not $pbi) { Write-Output "ERROR: $Pbip no está abierto en Power BI Desktop"; exit 1 }
    $ms = Get-CimInstance Win32_Process -Filter "Name='msmdsrv.exe'" | Where-Object { $_.ParentProcessId -eq $pbi.ProcessId } | Select-Object -First 1
    $dataDir = ([regex]::Match($ms.CommandLine, '-s "([^"]+)"')).Groups[1].Value
    $Port = [int]((Get-Content (Join-Path $dataDir 'msmdsrv.port.txt') -Raw -Encoding Unicode).Trim())
}

# AdomdClient de Power BI Desktop: instalador MSI si existe; si no, la versión de la Microsoft Store
# (su carpeta cambia con cada actualización, por eso se resuelve con Get-AppxPackage).
$binPbi = Join-Path $env:ProgramFiles 'Microsoft Power BI Desktop\bin'
if (-not (Test-Path (Join-Path $binPbi 'Microsoft.PowerBI.AdomdClient.dll'))) {
    $pkg = Get-AppxPackage -Name 'Microsoft.MicrosoftPowerBIDesktop' | Sort-Object Version -Descending | Select-Object -First 1
    if (-not $pkg) { Write-Output 'ERROR: no encontré Power BI Desktop (ni MSI ni Microsoft Store)'; exit 1 }
    $binPbi = Join-Path $pkg.InstallLocation 'bin'
}
Add-Type -Path (Join-Path $binPbi 'Microsoft.PowerBI.AdomdClient.dll')
$cn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$Port")
try {
    $cn.Open()
    $cmd = $cn.CreateCommand()
    $cmd.CommandText = $Dax
    $da = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdDataAdapter($cmd)
    $dt = New-Object System.Data.DataTable
    $sw = [Diagnostics.Stopwatch]::StartNew()
    [void]$da.Fill($dt)
    $sw.Stop()
    # Nombres legibles: 'Tabla'[Col] -> Col ; [Medida] -> Medida (sin duplicados)
    $vistos = @{}
    foreach ($c in $dt.Columns) {
        $n = $c.ColumnName
        $m = [regex]::Match($n, '\[([^\]]+)\]$')
        if ($m.Success) { $n = $m.Groups[1].Value }
        $base = $n; $i = 2
        while ($vistos.ContainsKey($n)) { $n = "$base`_$i"; $i++ }
        $vistos[$n] = 1
        $c.ColumnName = $n
    }
    $cols = @($dt.Columns | ForEach-Object { $_.ColumnName })
    Write-Output ("OK: {0} filas en {1:N1} s (puerto {2})" -f $dt.Rows.Count, $sw.Elapsed.TotalSeconds, $Port)
    if ($dt.Rows.Count -gt 0) {
        $dt | Select-Object -First $Preview -Property $cols | Format-Table -AutoSize | Out-String -Width 400 | Write-Output
    }
    if ($OutCsv) { $dt | Select-Object -Property $cols | Export-Csv -Path $OutCsv -NoTypeInformation -Encoding UTF8 }
} catch {
    Write-Output "ERROR: $($_.Exception.Message)"
    exit 2
} finally {
    $cn.Close()
}
