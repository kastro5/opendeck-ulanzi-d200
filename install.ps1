<#
.SYNOPSIS
    Install the Ulanzi D200X / D200H device plugin into OpenDeck on Windows.

.DESCRIPTION
    Builds the plugin into a standalone d200x_plugin.exe (PyInstaller, inside a
    local .venv) so OpenDeck can launch it without a Python install on PATH,
    then copies it into OpenDeck's plugins directory.

      .\install.ps1               build and install
      .\install.ps1 -Model d200h  pick the model (d200x or d200h); remembered
      .\install.ps1 -SkipBuild    reinstall the last build
      .\install.ps1 -Uninstall

    If scripts are blocked, run it as:
      powershell -ExecutionPolicy Bypass -File .\install.ps1
#>
param(
    [ValidateSet('d200x', 'd200h')]
    [string]$Model,
    [switch]$Uninstall,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'

$Plugin = 'com.ulanzi.d200x.sdPlugin'
$Here = $PSScriptRoot
$Src = Join-Path $Here $Plugin
$DestDir = Join-Path $env:APPDATA 'opendeck\plugins'
$Dest = Join-Path $DestDir $Plugin
$Venv = Join-Path $Here '.venv'
$VenvPython = Join-Path $Venv 'Scripts\python.exe'
$Exe = Join-Path $Here 'dist\d200x_plugin.exe'

# OpenDeck keeps the plugin running, and Windows won't overwrite a running exe.
function Stop-Plugin {
    Get-Process -Name 'd200x_plugin' -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "Stopping running plugin (pid $($_.Id))"
        $_ | Stop-Process -Force
        $_.WaitForExit(5000) | Out-Null
    }
}

if ($Uninstall) {
    Stop-Plugin
    if (Test-Path $Dest) {
        Remove-Item -Recurse -Force $Dest
        Write-Host "Removed $Dest"
    } else {
        Write-Host "Not installed: $Dest"
    }
    Write-Host 'Restart OpenDeck to finish.'
    exit 0
}

if (-not (Test-Path $DestDir)) {
    Write-Error ("Could not find OpenDeck's plugins directory ($DestDir).`n" +
        'Start OpenDeck once so it creates its config, then re-run this script.')
}

if (-not $SkipBuild) {
    if (-not (Test-Path $VenvPython)) {
        $py = Get-Command py -ErrorAction SilentlyContinue
        if ($py) {
            & py -3 -m venv $Venv
        } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            & python -m venv $Venv
        } else {
            Write-Error 'Python 3 is needed to build the plugin. Install it from python.org (or winget install Python.Python.3.13) and re-run.'
        }
        if ($LASTEXITCODE) { Write-Error 'Could not create the virtual environment.' }
    }

    Write-Host 'Installing build dependencies...'
    & $VenvPython -m pip install --quiet --disable-pip-version-check -r (Join-Path $Here 'requirements-build.txt')
    if ($LASTEXITCODE) { Write-Error 'pip install failed.' }

    Write-Host 'Building d200x_plugin.exe...'
    # Console subsystem on purpose: OpenDeck starts plugins with CREATE_NO_WINDOW
    # and sends stderr to its plugin log, which a windowed build would lose.
    & $VenvPython -m PyInstaller --noconfirm --clean --onefile --log-level WARN `
        --name d200x_plugin `
        --distpath (Join-Path $Here 'dist') `
        --workpath (Join-Path $Here 'build') `
        --specpath (Join-Path $Here 'build') `
        (Join-Path $Src 'd200x_plugin.py')
    if ($LASTEXITCODE) { Write-Error 'PyInstaller build failed.' }
}

if (-not (Test-Path $Exe)) {
    Write-Error "No build found at $Exe. Run without -SkipBuild."
}

# Device check, using the build environment's hidapi when there is one.
if (Test-Path $VenvPython) {
    $count = & $VenvPython -c 'import hid; print(len(hid.enumerate(0x2207, 0x0019)))'
    if ($count -gt 0) {
        Write-Host 'Device found.'
    } else {
        Write-Host 'Note: no D200X is plugged in right now, so the device could not be checked.'
    }
}

# Both models share one USB ID, so the plugin can't tell them apart: the model
# it assumes on first launch comes from defaults.json. Keep the previous choice
# across reinstalls unless -Model says otherwise.
$Defaults = Join-Path $Dest 'defaults.json'
if (-not $Model -and (Test-Path $Defaults)) {
    try { $Model = (Get-Content $Defaults -Raw | ConvertFrom-Json).model } catch { }
}
if (-not $Model) { $Model = 'd200x' }

Stop-Plugin
if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
Copy-Item -Recurse $Src $Dest
Get-ChildItem $Dest -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
Copy-Item $Exe $Dest
# No BOM: Windows PowerShell's -Encoding utf8 would add one.
[IO.File]::WriteAllText($Defaults, (@{ model = $Model } | ConvertTo-Json -Compress))
Write-Host "Installed to $Dest (model: $Model)"

# Anything else talking to the deck will fight this plugin over it.
$conflict = Join-Path $DestDir 'com.glmagalhaes.ulanzi.d200.sdPlugin'
if (Test-Path $conflict) {
    Write-Warning ("'com.glmagalhaes.ulanzi.d200.sdPlugin' is also installed and claims the same hardware. " +
        "Remove it (or disable it in OpenDeck's plugin manager) first.")
}
if (Get-Process | Where-Object { $_.Name -match 'ulanzi' -and $_.Name -ne 'd200x_plugin' }) {
    Write-Warning 'Ulanzi Studio appears to be running. Quit it (and stop it starting with Windows) so it does not fight OpenDeck over the deck.'
}

Write-Host ''
Write-Host 'Restart OpenDeck. The deck should appear in the device selector.'
Write-Host 'A model chosen in the Wide screen action''s settings overrides the installer''s.'
