@echo off
cd /d "%~dp0"
if exist "To-do list.exe" (
    start "" "%~dp0To-do list.exe"
    exit /b 0
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 app.py
    exit /b
)
if exist "%LocalAppData%\Programs\Python\Python314\python.exe" (
    "%LocalAppData%\Programs\Python\Python314\python.exe" app.py
    exit /b
)
echo Spustte soubor To-do list.exe, nebo nainstalujte Python 3.10 a novejsi.
pause
