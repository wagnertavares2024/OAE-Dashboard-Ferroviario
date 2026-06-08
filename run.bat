@echo off
cd /d "%~dp0"
echo Iniciando Dashboard OAE...
.venv\Scripts\streamlit.exe run app.py --server.port 8501
pause
