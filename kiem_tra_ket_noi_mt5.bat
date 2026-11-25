@echo off
title Kiem Tra Ket Noi MetaTrader 5 (MT5 Health Doctor)
cd /d "%~dp0"

echo ================================================================
echo   KIEM TRA KET NOI METATRADER 5 (MT5 HEALTH DOCTOR)
echo ================================================================
echo.

set PY_EXE=python
if exist ".venv\Scripts\python.exe" (
    set PY_EXE=.venv\Scripts\python.exe
) else if exist "..\trading-copilot\.venv\Scripts\python.exe" (
    set PY_EXE=..\trading-copilot\.venv\Scripts\python.exe
)

%PY_EXE% kiem_tra_ket_noi_mt5.py
echo.
pause
