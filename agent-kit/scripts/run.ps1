param([Parameter(ValueFromRemainingArguments=$true)][string[]]$AgentArgs)
$ErrorActionPreference = 'Stop'
$kitRoot = Split-Path -Parent $PSScriptRoot
$bundledPython = 'C:\Users\Justike\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = "$kitRoot\src;$kitRoot\.deps;$oldPythonPath"
    & $bundledPython -m navowork_agent.cli @AgentArgs
    exit $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $oldPythonPath
}
