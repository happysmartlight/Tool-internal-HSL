#!/bin/bash
# Happy Smart Light — Build Script (Windows via Git Bash / MSYS2)

echo "================================================="
echo "BẮT ĐẦU CÀI ĐẶT CÁC THƯ VIỆN CẦN THIẾT"
echo "================================================="
pip install -r requirements.txt
pip install pyinstaller

echo "================================================="
echo "DỌN DẸP DỮ LIỆU BUILD CŨ..."
echo "================================================="
rm -rf build/ dist/ HappySmartLightTool.spec
rm -rf Output/

echo "================================================="
echo "TIẾN HÀNH BUILD FILE THỰC THI (EXE)"
echo "================================================="
# Trên Windows (Git Bash), separator cho --add-data là ";"
pyinstaller --noconfirm --onedir --windowed \
    --name "HappySmartLightTool" \
    --icon "logo.png" \
    --add-data "logo.png;." \
    --add-data "config.json;." \
    main.py

if [ $? -ne 0 ]; then
    echo ""
    echo "[LỖI] PyInstaller build thất bại! Dừng lại."
    exit 1
fi

echo ""
echo "================================================="
echo "TIẾN HÀNH TẠO FILE INSTALLER WINDOWS (Inno Setup)"
echo "================================================="

# Tìm ISCC.exe — thử PATH trước, sau đó thử các đường dẫn phổ biến
ISCC_PATH=""
if command -v ISCC &>/dev/null; then
    ISCC_PATH="ISCC"
elif [ -f "/c/Users/$USERNAME/AppData/Local/Programs/Inno Setup 6/ISCC.exe" ]; then
    ISCC_PATH="/c/Users/$USERNAME/AppData/Local/Programs/Inno Setup 6/ISCC.exe"
elif [ -f "/c/Program Files (x86)/Inno Setup 6/ISCC.exe" ]; then
    ISCC_PATH="/c/Program Files (x86)/Inno Setup 6/ISCC.exe"
elif [ -f "/c/Program Files/Inno Setup 6/ISCC.exe" ]; then
    ISCC_PATH="/c/Program Files/Inno Setup 6/ISCC.exe"
fi

if [ -z "$ISCC_PATH" ]; then
    echo ""
    echo "[CẢNH BÁO] Không tìm thấy ISCC.exe (Inno Setup Compiler)."
    echo "  Vui lòng cài đặt Inno Setup 6 từ: https://jrsoftware.org/isdl.php"
    echo "  hoặc thêm thư mục cài đặt vào biến môi trường PATH."
    echo "  Bước tạo installer bị bỏ qua."
else
    "$ISCC_PATH" setup_script.iss
    if [ $? -eq 0 ]; then
        echo ""
        echo "================================================="
        echo "HOÀN TẤT! File installer nằm trong thư mục 'Output/'"
        echo "================================================="
    else
        echo ""
        echo "[LỖI] Inno Setup build thất bại!"
        exit 1
    fi
fi
