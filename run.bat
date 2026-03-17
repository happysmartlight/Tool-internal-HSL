@echo off
chcp 65001 >nul
title Happy Smart Light — Tao Hop Dong Mua Ban

:: Kiểm tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Chua cai Python! Tai tai: https://www.python.org/downloads/
    echo       Lua chon "Add Python to PATH" khi cai dat.
    pause
    exit /b 1
)

:: Cài dependencies nếu chưa có
echo [...] Kiem tra thu vien...
pip install -r "%~dp0requirements.txt" -q --disable-pip-version-check

:: Chạy ứng dụng
echo [OK ] Khoi dong ung dung...
python "%~dp0hop_dong_tool.py"

if errorlevel 1 (
    echo.
    echo [LOI] Ung dung thoat voi loi. Xem thong bao phia tren.
    pause
)