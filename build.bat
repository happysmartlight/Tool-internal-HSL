@echo off
chcp 65001 >nul
echo =================================================
echo BẮT ĐẦU CÀI ĐẶT CÁC THƯ VIỆN CẦN THIẾT
echo =================================================
pip install -r requirements.txt
pip install pyinstaller

echo =================================================
echo DỌN DẸP DỮ LIỆU BUILD CŨ...
echo =================================================
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist HappySmartLightTool.spec del /q HappySmartLightTool.spec

echo =================================================
echo TIẾN HÀNH BUILD FILE THỰC THI (EXE)
echo =================================================
:: Chú ý: separator trên Windows cho --add-data là ";" thay vì ":"
pyinstaller --noconfirm --onedir --windowed --name "HappySmartLightTool" --icon "logo.png" --add-data "logo.png;." --add-data "config.json;." main.py

echo =================================================
echo HOÀN TẤT! Ứng dụng của bạn nằm trong thư mục "dist/HappySmartLightTool/"
echo =================================================
pause
