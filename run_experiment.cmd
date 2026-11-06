@echo off
rem CAPE-Pins one-command runner for Windows (cmd / PowerShell).
rem   .\run_experiment.cmd --stage smoke
rem   .\run_experiment.cmd --stage pilot --data ".\data\real"
rem   .\run_experiment.cmd --stage all --manifest ".\data\manifests\benchmark.jsonl" --config ".\configs\benchmark.yaml" --resume
rem   .\run_experiment.cmd --stage report --latest
rem   .\run_experiment.cmd --stage recover --latest
setlocal
set "CAPE_ROOT=%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: the Python launcher "py" was not found. Install CPython 3.12 from https://www.python.org/downloads/windows/
  exit /b 2
)
py -3.12 -c "import sys" >nul 2>nul
if errorlevel 1 (
  echo ERROR: CPython 3.12 is not installed ^(py -3.12 failed^). Install it from https://www.python.org/downloads/windows/
  exit /b 2
)
py -3.12 "%CAPE_ROOT%run_all.py" %*
exit /b %ERRORLEVEL%
