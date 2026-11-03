@echo off
title SAKA Overlay - Roblox Sambung Kata Assistant & Auto Solver
cd /d "%~dp0"

echo ===================================================
echo     SAKA Overlay - Roblox Sambung Kata Assistant
echo ===================================================
echo.

python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [X] Python belum terinstal atau belum terdaftar di PATH Windows!
    echo     Silakan unduh dan instal Python dari https://www.python.org/
    echo     CATATAN: Pastikan centang "Add Python to PATH" saat instalasi.
    echo.
    pause
    exit /b 1
)

echo [*] Menjalankan SAKA Overlay...
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Aplikasi membutuhkan modul Python tambahan.
    echo     Sedang menginstal modul dari requirements.txt...
    echo.
    pip install -r requirements.txt
    echo.
    echo [*] Mencoba menjalankan kembali aplikasi...
    python main.py
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo [X] Terjadi kendala saat menjalankan program. Silakan periksa pesan error di atas.
        pause
    )
)
