@echo off
chcp 65001 >nul
cd /d "%~dp0"
title El Cerebro - conectar Hogger y OBS
echo.
echo  Paso 1 de 2: conectar El Cerebro con Hogger y OBS
echo  ---------------------------------------------------
".venv\Scripts\python.exe" conectar_claves.py
echo.
echo  Paso 2 de 2: actualizar Hogger en el servidor (con copia de seguridad)
echo  ----------------------------------------------------------------------
".venv\Scripts\python.exe" actualizar_hogger.py
echo.
echo  Terminado. Ya podes cerrar esta ventana.
pause
