@echo off
chcp 65001 >nul
title Seed Balance Scanner - Build EXE

echo =============================================
echo  Seed Balance Scanner - Windows Build
echo =============================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.13+ first.
    pause
    exit /b 1
)

:: Install dependencies
echo [1/4] Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [WARN] Some packages failed. Trying alternative install...
    pip install pyinstaller customtkinter mnemonic coincurve==18.0.0 pycryptodome PyNaCl base58 requests Pillow
)

:: Install PyInstaller if missing
echo [2/4] Checking PyInstaller...
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    pip install pyinstaller
)

:: Build the executable
echo [3/4] Building SeedBalanceScanner.exe...
pyinstaller ^
    --onefile ^
    --windowed ^
    --clean ^
    --noconfirm ^
    --name "SeedBalanceScanner" ^
    --add-data "README.md;." ^
    main.py
if %errorlevel% neq 0 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

:: Copy data.txt alongside the exe
echo [4/4] Copying data.txt to output...
if exist data.txt (
    copy /Y data.txt dist\data.txt >nul
    echo  - data.txt copied
) else (
    echo  [WARN] data.txt not found — place it next to the exe manually.
)

echo.
echo =============================================
echo  Build complete!
echo.
echo  Output: dist\SeedBalanceScanner.exe
echo.
echo  Run it directly — no Python required.
echo  Place your seed phrases in data.txt next to
echo  the exe before scanning.
echo =============================================
echo.
pause
