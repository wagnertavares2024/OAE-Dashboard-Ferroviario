@echo off
chcp 65001 >nul
title Simulador OAE ^| Dashboard Estrutural Ferroviario
cd /d "%~dp0"

echo.
echo  =====================================================
echo   SIMULADOR OAE - GESTAO A VISTA ESTRUTURAL
echo  =====================================================
echo.
echo   Acesse no navegador: http://localhost:8501
echo.
echo   IMPORTANTE: Nao feche esta janela enquanto
echo   estiver usando o dashboard!
echo  =====================================================
echo.

echo   Encerrando sessoes anteriores na porta 8501...
taskkill /f /im streamlit.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:loop
.venv\Scripts\python.exe -m streamlit run app.py ^
    --server.port 8501 ^
    --server.headless false ^
    --server.enableCORS false ^
    --server.enableXsrfProtection false

echo.
echo  Servidor encerrado. Reiniciando em 3 segundos...
echo  (Feche esta janela para encerrar definitivamente)
echo.
timeout /t 3 /nobreak >nul
goto loop
