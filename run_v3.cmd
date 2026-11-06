@echo off
rem CAPE v3 - one command over the existing pipeline (plan CAPE v3, sections 3.2 / 16):
rem   audit -> build -> tests -> develop (4 panels) -> select (pre-registered gates) -> freeze
rem   -> confirm (SNEMI3D, frozen batch) -> analyze -> package
rem   .\run_v3.cmd --stage all --resume     every stage; DONE stages are skipped
rem   .\run_v3.cmd --stage develop          one stage
rem   .\run_v3.cmd --stage report-status    stage table
rem   .\run_v3.cmd --help
setlocal
set "CAPE_ROOT=%~dp0"
if not exist "%CAPE_ROOT%.venv\Scripts\python.exe" (
  echo ERROR: .venv missing - run ".\run_experiment.cmd --stage smoke" once to bootstrap the environment.
  exit /b 2
)
"%CAPE_ROOT%.venv\Scripts\python.exe" "%CAPE_ROOT%scripts\run_v3.py" %*
