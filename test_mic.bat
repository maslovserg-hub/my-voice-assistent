@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Запускаю тест микрофона...
echo.
.venv\Scripts\python test_gigaam.py
echo.
pause
