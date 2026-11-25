@echo off
title Trading Strategy Simulator & Replay Engine
cd /d "%~dp0"

echo ================================================================
echo   TRADING STRATEGY SIMULATOR - 3-TIMEFRAME VISUAL REPLAY & MT5
echo ================================================================
echo.

:: 1. Xac dinh trinh thuc thi Python
set PY_EXE=
if exist ".venv\Scripts\python.exe" (
    set PY_EXE=.venv\Scripts\python.exe
) else if exist "..\trading-copilot\.venv\Scripts\python.exe" (
    set PY_EXE=..\trading-copilot\.venv\Scripts\python.exe
) else if exist "..\mt5-tester\.venv\Scripts\python.exe" (
    set PY_EXE=..\mt5-tester\.venv\Scripts\python.exe
)

:: Neu chua co moi truong ao nao, tu dong goi setup_env de cai dat lan dau
if "%PY_EXE%"=="" (
    echo [*] Phat hien day la lan chay dau tien tren may tinh moi.
    echo [*] Dang tu dong thiet lap moi truong Python va thu vien MT5...
    echo.
    call setup_env.bat
    if exist ".venv\Scripts\python.exe" (
        set PY_EXE=.venv\Scripts\python.exe
    ) else (
        echo [X] Khong the thiet lap moi truong ao. Dang thu dung Python he thong...
        set PY_EXE=python
    )
)

echo [*] Python Runtime: %PY_EXE%
echo [*] Kiem tra phan mem MetaTrader 5...

:: 2. Nhac nho mo MT5 neu chua bat
tasklist /fi "imagename eq terminal64.exe" 2>NUL | find /i "terminal64.exe" >NUL
if %errorlevel% neq 0 (
    echo [i] LUU Y: Phan mem MT5 (terminal64.exe) chua duoc bat.
    echo     De gia duoc keo truc tiep tu san cua ban, hay bat san MT5 len nhe!
    echo     (Neu khong bat MT5, Simulator se tu dong dung du lieu nến co san trong data/).
) else (
    echo [OK] Phat hien MetaTrader 5 dang chay. Gia chuan se duoc keo truc tiep tu MT5!
)

echo.
echo [*] Dang khoi dong Web Server Simulator tren cong 8080...
echo [*] Dang mo trinh duyet tai dia chi: http://localhost:8080
echo.

:: 3. Mo trinh duyet va chay Server
start http://localhost:8080
%PY_EXE% -m src.server --port 8080

pause
