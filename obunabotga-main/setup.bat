@echo off
REM Obunalar boti - Windows uchun bir martalik sozlash
chcp 65001 >nul

echo Kutubxonalar ornatilmoqda...
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

if not exist .env (
    copy .env.example .env >nul
    echo.
    echo .env fayl yaratildi.
    echo Endi uni Notepad'da oching va BOT_TOKEN ni toldiring:
    echo     notepad .env
    echo.
    echo Toldirgach setup.bat ni qayta ishga tushiring.
    pause
    exit /b 0
)

echo Namuna malumot qoshilmoqda...
python seed.py

echo.
echo Bot ishga tushmoqda... (toxtatish uchun Ctrl+C)
python bot.py
goto :eof

:error
echo.
echo Xatolik yuz berdi. Python ornatilganini tekshiring: python --version
pause
