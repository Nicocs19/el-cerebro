@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python kick_auth.py
pause
