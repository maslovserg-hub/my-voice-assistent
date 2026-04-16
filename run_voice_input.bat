@echo off
cd /d "%~dp0"
if exist "C:\Users\Сергей\AppData\Local\Programs\Python\Python311\python.exe" (
    "C:\Users\Сергей\AppData\Local\Programs\Python\Python311\python.exe" voice_input.py
) else (
    python voice_input.py
)
pause
