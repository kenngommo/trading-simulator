@echo off
title Cai Dat Moi Truong Trading Simulator
cd /d "%~dp0"

echo ================================================================
echo   CAI DAT MOI TRUONG PYTHON CHO TRADING SIMULATOR
echo ================================================================
echo.

:: 1. Kiem tra Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [X] LOI: Khong tim thay Python tren may tinh cua ban!
    echo.
    echo Vui long cai dat Python (khuyen dung Python 3.10, 3.11 hoac 3.12 64-bit)
    echo tu trang chu: https://www.python.org/downloads/
    echo [Luu y quan trong: Nho tich chon vao 'Add python.exe to PATH' khi cai dat]
    echo.
    pause
    exit /b 1
)

echo [*] Tim thay Python tren may tinh:
python --version
echo.

:: 2. Tao moi truong ao .venv neu chua co
if not exist ".venv\Scripts\python.exe" (
    echo [*] Dang khoi tao moi truong ao (.venv)...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [X] Khong the tao .venv. Vui long kiem tra quyen ghi thu muc.
        pause
        exit /b 1
    )
    echo [OK] Da tao .venv thanh cong.
) else (
    echo [*] Da co san moi truong ao .venv.
)
echo.

:: 3. Cai dat thu vien tu requirements.txt
echo [*] Dang cai dat va cap nhat cac thu vien can thiet (FastAPI, MetaTrader5, Pandas, NumPy)...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo [!] Co loi xay ra trong qua trinh cai dat thu vien.
    echo Vui long kiem tra ket noi mang va thu lai.
    pause
    exit /b 1
)

echo.
echo ================================================================
echo   [HOAN TAT] MOI TRUONG DA DUOC CAI DAT THANH CONG 100%!
echo   Ban co the chay 'run_simulator.bat' de mo ung dung ngay bay gio.
echo ================================================================
echo.
pause
