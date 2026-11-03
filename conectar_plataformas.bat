@echo off
chcp 65001 >nul
cd /d "%~dp0"
title El Cerebro - conectar Kick y YouTube
if not exist "data\kick_tokens.json" (
  echo.
  echo  ===== KICK =====
  ".venv\Scripts\python.exe" kick_auth.py
) else (
  echo  Kick ya estaba conectado.
)
if not exist "data\youtube_token.json" (
  echo.
  echo  ===== YOUTUBE =====
  ".venv\Scripts\python.exe" youtube_auth.py
) else (
  echo  YouTube ya estaba conectado.
)
echo.
echo  Terminado. Ya podes cerrar esta ventana.
pause
