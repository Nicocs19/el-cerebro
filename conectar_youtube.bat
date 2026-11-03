@echo off
chcp 65001 >nul
cd /d "%~dp0"
title El Cerebro - conectar_youtube
".venv\Scripts\python.exe" youtube_auth.py
echo.
echo  Terminado. Ya podes cerrar esta ventana.
pause
