@echo off
chcp 65001 >nul
cd /d "%~dp0"
title El Cerebro - conectar_voz
".venv\Scripts\python.exe" conectar_voz.py
echo.
echo  Terminado. Ya podes cerrar esta ventana.
pause
