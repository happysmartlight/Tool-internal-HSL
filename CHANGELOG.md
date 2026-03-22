# Changelog

All notable changes to this project will be documented in this file.

## [2.7.0] - 2026-03-22

### Added
- Thêm tính năng **AI Chat** (`ui/ai_chat_tab.py`): Tích hợp trợ lý ảo AI hỗ trợ nhiều model (Google Gemini, OpenAI, Anthropic Claude) giúp tư vấn, phân tích file PDF/DOCX và tương tác với dữ liệu.
- Lưu trữ lịch sử trò chuyện AI cục bộ bằng SQLite (`utils/database_chat.py`) với tính năng mã hóa cấu hình API Key (`utils/security.py`).

### Changed
- Cập nhật và tinh chỉnh giao diện hộp thoại "Thông tin phiên bản": Tăng kích thước popup để không bị khuất nút "Đóng", thêm biểu tượng logo vào tiêu đề cửa sổ (`utils/hop_dong_tool.py`).
- Cập nhật cơ chế hiển thị danh mục tab.

## [2.6.1] - 2026-03-22

### Changed
- Refactor cấu trúc dự án: Dời file UI `hop_dong_tool.py` vào bên trong thư mục `utils/` và cập nhật đường dẫn `import` tại `main.py` nhằm giữ cho thư mục gốc luôn gọn gàng.

## [2.6.0] - 2026-03-22

### Added
- Thêm tính năng **Báo Giá Word** (`utils/doc_exporter.py`): Tự động tạo file Word báo giá chuyên nghiệp với logo in chìm (watermark), kèm điều khoản thanh toán, và thời hạn hiệu lực tự tính.
- Nút Báo Giá Word và tự động mở file sau khi xuất xong cho cả Word và Excel bên bảng "Tính giá nhập khẩu".
- **Tự động đồng bộ Ngày tháng Hợp Đồng**: Ngày ký tự điền ngày hiện tại. Ngày thanh toán đợt 2 liên kết động với số khoảng cách ngày (spinbox). Tự đồng bộ thay đổi giữa các đợt.
- Tự động sinh **Mã Báo Giá** dựa trên thời gian xuất và 4 số cuối của tổng tiền.

### Changed
- Refactor văn bản hợp đồng: Thêm diễn giải khoảng thời gian giao hàng sau đợt 1 ở điều khoản thanh toán.
- Thiết kế lại vùng Thông tin liên hệ ở Header (Hotline) và Footer (Website) và làm gọn hơn với các icon thân thiện.

## [2.5.0] - 2026-03-18

### Added
- Updated `build.sh` to automatically run PyInstaller and Inno Setup Compiler (`ISCC.exe`).
- Added automatic detection of Inno Setup path in various Windows locations.

### Changed
- Fixed entry point in `build.sh` to use `main.py` (which includes both Hợp Đồng and Tính Giá tabs).
- Improved UI in "Thông số chi phí" (Tab 2) to show thousand separators (e.g., 1,500,000 VND) in input fields for better readability.

## [2.4.0] - 2026-03-17

### Added
- Added `pyinstaller` to `requirements.txt`.
- Created PyInstaller build scripts (`build.bat` / `build.ps1`).

### Changed
- Improved Calculation History UI to parse and display up to 2 product names along with the total counts instead of just currency and total.
- Increased layout button size and changed unrendered Unicode icons to standard Emoji (`↻` and `🗑️`) for Windows compatibility without clipping.

## [2.3.0] - 2026-03-17

### Added
- New **Tab 2: Import Cost Calculator** with full clean architecture.
- `models/`, `services/`, `database/`, `utils/`, `ui/` module structure.
- Exchange rate fetch from open.er-api.com with SQLite cache + offline fallback.
- SQLite calculation history (save, load, delete).
- Export to Excel (.xlsx) with styled product list and cost breakdown sheets.
- Auto-refresh exchange rate every 5 minutes + manual refresh.
- Dark mode UI with highlighted stat cards (Giá vốn / Giá bán / Lợi nhuận).
- Realtime recalculation on any input change.
- `main.py` — new dual-tab entry point.
- `openpyxl` dependency for Excel export.

## [2.2.0] - 2026-03-17

### Added
- Implemented exclusive support for HTML draft invoices (specifically 1C template).
- Added `beautifulsoup4` and `lxml` as core dependencies for robust HTML parsing.
- Refined parsing logic to handle row-spanned totals and fragmented item tables.

### Changed
- Updated UI text and file dialog filter to restrict support to HTML format only.
- Enhanced address extraction with multiple field lookahead barriers.

### Fixed
- Fixed address parsing overflow issue where buyer address captured subsequent field labels.

## [2.1.0] - 2026-03-17

### Added
- Created `config.json` for centralized version management.
- Added `CHANGELOG.md` to track project history.

### Fixed
- Fixed `QComboBox` dropdown menu transparency issue on Windows by using explicit `QListView` and solid black background.
- Fixed `QCalendarWidget` month/year dropdown transparency by forcing opaque background-color in QSS.

## [2.0.0] - 2026-03-10

### Added
- Complete UI overhaul with Dark/Neon theme.
- Support for XML and PDF invoice parsing.
- Automated Tax Code (MST) lookup via API.
- Support for multiple seller bank accounts.
- Professional Word document generation with watermarks.
