@echo off
title VN30F1M Realtime Trading Engine
cd /d "%~dp0"
echo ======================================================================
echo   KHOI DONG PYTHON LIVE TRADING SERVER (AMIBROKER <-> AMIX BRIDGE)
echo ======================================================================
.\.venv\Scripts\python.exe run_live_trading.py %*
pause
