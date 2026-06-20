@echo off
rem ============================================================
rem  TFT Scout - one-click launcher (Windows)
rem  First run: sets up a venv, installs deps, fetches data,
rem  trains the recognizer. Every later run: just launches.
rem ============================================================
setlocal enableextensions
pushd "%~dp0"

rem --- locate Python 3 ---
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python 3 was not found.
  echo Install it from https://www.python.org/downloads/ and tick
  echo "Add Python to PATH" during installation, then run this again.
  goto :fail
)

rem --- create virtual environment on first run ---
if not exist ".venv\Scripts\python.exe" (
  echo [setup] Creating virtual environment...
  %PY% -m venv .venv || goto :fail
)
set "VPY=.venv\Scripts\python.exe"

rem --- install dependencies on first run ---
if not exist ".venv\.deps_installed" (
  echo [setup] Installing dependencies. First run only - this can take a few minutes...
  "%VPY%" -m pip install --upgrade pip || goto :fail
  "%VPY%" -m pip install -r requirements.txt || goto :fail
  echo done> ".venv\.deps_installed"
)

rem --- fetch champion data + portraits on first run ---
if not exist "config\set_data.json" (
  echo [setup] Downloading champion data and portraits...
  "%VPY%" -m src.data.fetch_data --set 17 || goto :fail
)

rem --- train the recognizer on first run ---
if not exist "models\classifier.pt" (
  echo [setup] Training the recognizer. First run only - a few minutes...
  "%VPY%" -m src.model.train --epochs 8 || goto :fail
)

rem --- launch the app ---
echo [run] Starting TFT Scout...
"%VPY%" main.py
goto :end

:fail
echo.
echo Setup failed - see the messages above.
:end
popd
pause
