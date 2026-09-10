@echo off
REM Avvia PC Diagnostic Tool su Windows.
REM Fai doppio clic su questo file per installare le dipendenze (solo la prima volta)
REM e avviare il programma.

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERRORE] Python non risulta installato o non e' nel PATH.
    echo Scarica Python da https://www.python.org/downloads/
    echo IMPORTANTE: durante l'installazione spunta "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

echo Verifica/installazione delle dipendenze necessarie...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERRORE] Installazione delle dipendenze non riuscita.
    pause
    exit /b 1
)

echo Avvio di PC Diagnostic Tool...
python main.py

if errorlevel 1 (
    echo.
    echo Il programma si e' chiuso con un errore. Controlla il messaggio sopra.
    pause
)
