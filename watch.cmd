@echo off
rem Live, read-only progress view of the running experiment (Ctrl+C to quit).
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\watch.py" %*
