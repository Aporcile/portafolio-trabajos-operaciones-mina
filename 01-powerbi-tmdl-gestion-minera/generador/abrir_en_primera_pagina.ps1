# Abre el .pbip siempre en la primera página del informe.
#
# Power BI no tiene una opción de página de inicio: abre en la página que estaba activa al guardar (activePageName de
# pages.json). Este lanzador deja activePageName en la primera página visible de pageOrder y recién después abre el .pbip.
# Sirve, por ejemplo, para un acceso directo en el escritorio.
#
# Si el informe ya está abierto en Desktop no toca nada (Desktop revertiría el cambio al guardar).
# Uso: powershell -NoProfile -File generador\abrir_en_primera_pagina.ps1

$ErrorActionPreference = 'Stop'
$raiz  = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pbip  = (Get-ChildItem (Join-Path $raiz 'pbip') -Filter '*.pbip' | Select-Object -First 1).FullName
$dirPg = (Get-ChildItem (Join-Path $raiz 'pbip') -Directory -Filter '*.Report' | Select-Object -First 1).FullName
$dirPg = Join-Path $dirPg 'definition\pages'
$pgs   = Join-Path $dirPg 'pages.json'
$nombre = [IO.Path]::GetFileName($pbip)

$abierto = Get-CimInstance Win32_Process -Filter "Name='PBIDesktop.exe'" |
    Where-Object { $_.CommandLine -like "*$nombre*" }

if (-not $abierto) {
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $texto = [IO.File]::ReadAllText($pgs, $utf8)
    $meta = $texto | ConvertFrom-Json

    $primera = $null
    foreach ($id in $meta.pageOrder) {
        $pj = Join-Path $dirPg "$id\page.json"
        if (-not (Test-Path $pj)) { continue }
        $pagina = [IO.File]::ReadAllText($pj, $utf8) | ConvertFrom-Json
        if ($pagina.visibility -ne 'HiddenInViewMode') { $primera = $id; break }
    }

    if ($primera -and $meta.activePageName -ne $primera) {
        # Reemplazo de texto: conserva el formato del archivo (saltos de línea, sin BOM, sangría de 2).
        $nuevo = [regex]::Replace($texto, '("activePageName"\s*:\s*")[^"]*(")', "`${1}$primera`${2}")
        [IO.File]::WriteAllText($pgs, $nuevo, $utf8)
    }
}

Start-Process -FilePath $pbip
