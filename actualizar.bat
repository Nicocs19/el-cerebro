@echo off
cd /d "%~dp0"
git pull
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
echo Actualizado.
pause
