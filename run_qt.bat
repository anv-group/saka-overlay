@echo off
title SAKA Overlay (PySide6 Edition)
cd /d "%~dp0"
python main_qt.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Terjadi kesalahan saat menjalankan SAKA Overlay PySide6.
    pause
)
