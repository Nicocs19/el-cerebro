@echo off
cd /d "%~dp0"
echo === Creando entorno de Python ===
if not exist .venv (py -3.12 -m venv .venv || py -3.11 -m venv .venv || python -m venv .venv)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
echo === Instalando dependencias (tarda unos minutos) ===
pip install -r requirements.txt
if not exist .env copy .env.example .env
if not exist data mkdir data
echo.
echo === Listo. Revisa .env y ejecuta diagnostico.bat ===
pause
