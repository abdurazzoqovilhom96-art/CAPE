# CAPE-Pins one-command runner (Windows PowerShell). Same arguments as run_experiment.cmd.
#   .\run_experiment.ps1 --stage smoke
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host 'ERROR: the Python launcher "py" was not found. Install CPython 3.12 from https://www.python.org/downloads/windows/'
    exit 2
}
& py -3.12 -c "import sys" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'ERROR: CPython 3.12 is not installed (py -3.12 failed).'
    exit 2
}
& py -3.12 (Join-Path $root 'run_all.py') @args
exit $LASTEXITCODE
