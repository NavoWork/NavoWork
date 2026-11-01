#Requires -Version 5.1
<#
.SYNOPSIS
    NavoWork launcher for Windows.

.DESCRIPTION
    Finds Python 3.12+ (preferring the py launcher), then hands control to
    dev.py. The first run creates backend/.venv, installs Python and npm
    dependencies, applies migrations and starts the API, worker and UI.

.EXAMPLE
    .\start.ps1

.EXAMPLE
    .\start.ps1 --setup-only
#>

$ErrorActionPreference = 'Stop'
$LauncherArgs = @($args)

try {
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
} catch {
    # Older hosts may not allow changing the console encoding; keep going.
}

$root = $PSScriptRoot
Set-Location -LiteralPath $root

function Test-PythonVersion {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [string[]]$Prefix = @()
    )

    try {
        & $Executable @Prefix -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

$python = $null
$pythonPrefix = @()

if (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($tag in @('-3', '-3.12', '-3.13')) {
        if (Test-PythonVersion -Executable 'py' -Prefix @($tag)) {
            $python = 'py'
            $pythonPrefix = @($tag)
            break
        }
    }
}

if (-not $python) {
    foreach ($candidate in @('python3.12', 'python3.13', 'python3', 'python')) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $command) {
            continue
        }
        if (Test-PythonVersion -Executable $command.Source) {
            $python = $command.Source
            $pythonPrefix = @()
            break
        }
    }
}

if (-not $python) {
    Write-Host ''
    Write-Host '[NavoWork] 未找到 Python 3.12+。' -ForegroundColor Red
    Write-Host '  winget install Python.Python.3.12'
    Write-Host '  或从 https://www.python.org/downloads/ 安装，并勾选 "Add python.exe to PATH"。'
    Write-Host '  安装完成后重新打开终端，再运行 start.bat 或 .\start.ps1。'
    exit 1
}

$launcher = Join-Path $root 'dev.py'
Write-Host "==> 使用 Python: $python $($pythonPrefix -join ' ')" -ForegroundColor DarkGray

if ($python -eq 'py') {
    & py @pythonPrefix $launcher @LauncherArgs
} else {
    & $python $launcher @LauncherArgs
}

exit $LASTEXITCODE
