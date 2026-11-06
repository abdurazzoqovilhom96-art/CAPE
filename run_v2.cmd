@echo off
rem CAPE-Pins v2 - the whole experiment with one command:
rem   tests -> pilot (CREMI A) -> freeze -> frozen test (unseen CREMI B/C crops) -> width/scale
rem   -> archive ceiling -> independent audit -> analysis\v2_final\V2_YAKUNIY_HISOBOT_UZ.md
rem   .\run_v2.cmd               resume (steps already DONE are skipped)
rem   .\run_v2.cmd --restart     start the step list again (finished runs stay on disk)
rem   .\run_v2.cmd --only report rebuild only the final report
setlocal
set "CAPE_ROOT=%~dp0"
if not exist "%CAPE_ROOT%.venv\Scripts\python.exe" (
  echo ERROR: .venv missing - run ".\run_experiment.cmd --stage smoke" once to bootstrap the environment.
  exit /b 2
)
"%CAPE_ROOT%.venv\Scripts\python.exe" "%CAPE_ROOT%scripts\run_v2.py" %*
