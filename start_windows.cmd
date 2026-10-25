@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    set "RC_PY=.venv\Scripts\python.exe"
) else if exist "..\.venv\Scripts\python.exe" (
    set "RC_PY=..\.venv\Scripts\python.exe"
) else (
    echo No project Python environment found.
    echo Please follow README.md to install requirements.
    pause
    exit /b 1
)
"%RC_PY%" -m streamlit run app.py
pause
