#!/bin/bash
# Happy Smart Light — Build Script cho Linux/macOS/Bash

echo "================================================="
echo "BẮT ĐẦU CÀI ĐẶT CÁC THƯ VIỆN CẦN THIẾT"
echo "================================================="
pip install -r requirements.txt
pip install pyinstaller

echo "================================================="
echo "DỌN DẸP DỮ LIỆU BUILD CŨ..."
echo "================================================="
rm -rf build/ dist/ HappySmartLightTool.spec

echo "================================================="
echo "TIẾN HÀNH BUILD FILE THỰC THI (EXE/APP)"
echo "================================================="
# Chú ý: separator trên Linux/macOS cho --add-data là ":" thay vì ";"
pyinstaller --noconfirm --onedir --windowed --name "HappySmartLightTool" --icon "logo.png" --add-data "logo.png;." --add-data "config.json;." main.py

echo "================================================="
echo "HOÀN TẤT! Ứng dụng của bạn nằm trong thư mục 'dist/'"
echo "================================================="
