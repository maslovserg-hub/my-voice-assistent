@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo VoiceType запускается...
echo Нажми Right Ctrl для начала и остановки записи.
echo Для выхода нажми Ctrl+C в этом окне.
echo.
.venv\Scripts\python main.py
pause
