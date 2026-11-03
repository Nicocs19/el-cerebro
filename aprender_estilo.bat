@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python aprender_estilo.py %*
pause
