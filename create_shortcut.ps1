$ErrorActionPreference = 'Stop'
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcut = Join-Path $desktop 'Fast Convert.lnk'
$target = Join-Path $PSScriptRoot 'dist\Fast Convert.exe'
$workDir = Join-Path $PSScriptRoot 'dist'
$icon = Join-Path $PSScriptRoot 'assets\app.ico'

if (-not (Test-Path -LiteralPath $target)) {
    Write-Warning "Cannot create shortcut because target exe is missing: $target"
    exit 1
}

$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcut)
$link.TargetPath = $target
$link.WorkingDirectory = $workDir
if (Test-Path -LiteralPath $icon) {
    $link.IconLocation = "$icon,0"
}
$link.Description = 'Fast Convert / 闪电转换'
$link.Save()

$refresh = Join-Path $env:SystemRoot 'System32\ie4uinit.exe'
if (Test-Path -LiteralPath $refresh) {
    Start-Process -FilePath $refresh -ArgumentList '-show' -WindowStyle Hidden -Wait
}

Write-Host "Desktop shortcut created successfully: $shortcut"
