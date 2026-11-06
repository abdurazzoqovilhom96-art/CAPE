@echo off
rem CAPE-Pins v2.1 - one command (no new mechanism; measurements + preparation only):
rem   check v2 (Z=512 run finished) -> build -> tests -> SNEMI3D prepare (no compression on it)
rem   -> v1->v2 speed-up attribution -> scaling crops -> scaling runs -> audit
rem   -> analysis\v21_final\V21_HISOBOT_UZ.md
rem   .\run_v21.cmd               resume (steps already DONE are skipped)
rem   .\run_v21.cmd --restart     start the step list again (finished runs stay on disk)
rem   .\run_v21.cmd --only report rebuild only the report
setlocal
set "CAPE_ROOT=%~dp0"
if not exist "%CAPE_ROOT%.venv\Scripts\python.exe" (
  echo ERROR: .venv missing - run ".\run_experiment.cmd --stage smoke" once to bootstrap the environment.
  exit /b 2
)
"%CAPE_ROOT%.venv\Scripts\python.exe" "%CAPE_ROOT%scripts\run_v21.py" %*
