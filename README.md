# Happy Smart Light — Bộ Công Cụ Quản Lý Kinh Doanh

Ứng dụng desktop PyQt6 tích hợp 4 công cụ: tạo hợp đồng mua bán từ hóa đơn điện tử, tính giá nhập khẩu, tính giá nội địa, và trợ lý AI.

---

## Tính năng

| Tab | Tên | Chức năng |
|-----|-----|-----------|
| 📄 | Hợp Đồng | Tạo hợp đồng mua bán từ hóa đơn điện tử (XML/PDF/HTML) |
| 🛒 | Tính Giá Nhập Khẩu | Tính giá vốn + giá bán cho hàng nhập khẩu (ngoại tệ → VND) |
| 💰 | Tính Giá Nội Địa | Tính giá vốn + giá bán cho hàng nội địa (thuần VND) |
| 🤖 | Trợ lý AI | Chat AI (Google Gemini / OpenAI / Claude) hỗ trợ phân tích tài liệu |

---

## Cấu trúc dự án

```
GEN-HOP-DONG/
├── main.py                          # Entry point — dựng 4-tab window
├── config.json                      # Version & thông tin ứng dụng
├── requirements.txt                 # Phụ thuộc Python
├── run.bat                          # Launcher Windows (tự cài deps)
├── build.sh                         # Build EXE bằng PyInstaller + Inno Setup
├── HappySmartLightTool.spec         # Cấu hình PyInstaller
├── logo.png                         # Icon ứng dụng
│
├── models/                          # Dataclass thuần — không import PyQt6
│   ├── product.py                   # Product, OrderLine, ImportOrder
│   ├── cost_config.py               # CostConfig, ExchangeRate, CostBreakdown
│   └── domestic_product.py          # DomesticProduct, DomesticBreakdown
│
├── services/                        # Business logic — không import PyQt6
│   ├── calculator_service.py        # Tính giá nhập khẩu
│   ├── domestic_calculator_service.py  # Tính giá nội địa
│   ├── exchange_rate_service.py     # Lấy & cache tỷ giá (open.er-api.com)
│   └── ai_service.py                # Tích hợp Gemini / OpenAI / Claude
│
├── ui/                              # Giao diện PyQt6
│   ├── import_cost_tab.py           # Tab Tính Giá Nhập Khẩu
│   ├── domestic_price_tab.py        # Tab Tính Giá Nội Địa
│   └── ai_chat_tab.py               # Tab Trợ lý AI
│
├── utils/
│   ├── hop_dong_tool.py             # Tab Hợp Đồng (core feature)
│   ├── doc_exporter.py              # Xuất Word báo giá nhập khẩu
│   ├── domestic_doc_exporter.py     # Xuất Word báo giá nội địa
│   ├── excel_exporter.py            # Xuất Excel nhập khẩu
│   ├── domestic_excel_exporter.py   # Xuất Excel nội địa
│   ├── logger.py                    # Logging tập trung
│   ├── paths.py                     # Resolve đường dẫn (dev + PyInstaller)
│   ├── security.py                  # Mã hóa API key
│   └── database_chat.py             # SQLite cho chat AI
│
└── database/
    └── db_handler.py                # SQLite: lịch sử tính toán + cache tỷ giá
```

---

## Cài đặt & Chạy

### Yêu cầu

- Python 3.10+
- Windows 10/11 (đã test), macOS/Linux có thể chạy nhưng chưa test chính thức

### Cài đặt nhanh (Windows)

```bat
run.bat
```

Script tự `pip install -r requirements.txt` rồi khởi động ứng dụng.

### Cài đặt thủ công

```bash
pip install -r requirements.txt
python main.py
```

### Phụ thuộc chính

| Thư viện | Mục đích |
|----------|----------|
| `PyQt6 >= 6.6` | Framework giao diện |
| `python-docx >= 1.1` | Xuất file Word (.docx) |
| `openpyxl >= 3.1` | Xuất file Excel (.xlsx) |
| `pdfplumber >= 0.10` | Đọc hóa đơn PDF |
| `beautifulsoup4 >= 4.12` | Parse hóa đơn XML/HTML |
| `requests >= 2.31` | Gọi API tỷ giá |
| `num2words >= 0.5` | Đọc số tiền bằng chữ (tiếng Việt) |

---

## Tab 1 — Hợp Đồng

Tạo hợp đồng mua bán chuyên nghiệp từ hóa đơn điện tử.

**Quy trình:**
1. Tải lên hóa đơn đầu vào (định dạng XML của 1C eInvoice, PDF, hoặc HTML)
2. Ứng dụng tự tra MST bên bán, điền thông tin bên mua
3. Chọn ngân hàng thanh toán, giới tính đại diện (Ông/Bà), ngày hợp đồng
4. Nhấn **Tạo Hợp Đồng** → xuất file Word

**Mã hợp đồng tự sinh:** `HSL_{mã_người_mua}{YY}{MM}{DD}{4_số_cuối_tổng_tiền}`

**Tính năng:**
- Đọc tự động thông tin từ hóa đơn XML/PDF/HTML
- Tra cứu tên doanh nghiệp qua MST (API công khai)
- Số tiền bằng chữ tiếng Việt
- Watermark logo công ty trên file Word
- Hỗ trợ 2 tài khoản ngân hàng (MB Bank, Techcombank)

---

## Tab 2 — Tính Giá Nhập Khẩu

Tính giá vốn và giá bán cho hàng nhập từ nước ngoài.

**Công thức:**
```
Giá FOB (VND)     = Số lượng × Đơn giá × Tỷ giá
Thuế nhập khẩu    = FOB × % thuế NK (mặc định 15%)
Thuế VAT          = (FOB + Thuế NK) × 10%
Phí đổi ngoại tệ  = FOB × 3.4% (mặc định)
Phí hải quan      = 1.500.000 ₫ (cố định)
Giá vốn           = FOB + tất cả thuế & phí
Giá bán (chưa VAT) = Giá vốn / (1 − Biên LN%)
Giá bán (có VAT)   = Giá bán × (1 + VAT%)
```

**Tỷ giá:** Cập nhật tự động từ `open.er-api.com`, cache SQLite, tự động làm mới mỗi 5 phút.

**Tiền tệ hỗ trợ:** USD · JPY · CNY · EUR · GBP · KRW · THB

**Xuất:** Excel (2 sheet: nội bộ + báo giá khách hàng) · Word (báo giá)

---

## Tab 3 — Tính Giá Nội Địa

Tính giá vốn và giá bán cho hàng mua trong nước (thuần VND, không tỷ giá).

**Công thức Biên LN (Gross Margin):**
```
Giá vốn/đv  = Giá mua + Ship/đv + CP khác/đv − Chiết khấu/đv
               + Phân bổ ship tổng + Phân bổ CP cố định
Giá bán (chưa VAT) = Giá vốn / (1 − Biên LN%)
Giá bán (có VAT)   = Giá bán × (1 + VAT%)
```

> **Biên LN% là Gross Margin** (% lợi nhuận trên doanh thu).
> Ví dụ: Biên 50% + Giá vốn 100.000 → Giá bán 200.000 → Lời 100.000 (= 50% × 200.000).

**Chi phí cố định** (ship tổng, CP khác) được phân bổ theo tỷ lệ `(giá mua × số lượng) / tổng đơn hàng`.

**Giao diện bảng:**
- 4 cột đầu (STT, Tên SP, ĐVT, SL) cố định — không cuộn khuất
- Các cột còn lại cuộn ngang: `Shift + cuộn chuột`
- CK% và Biên LN%: dùng con lăn chuột để tăng/giảm

**Xuất:** Excel (2 sheet: nội bộ đầy đủ + báo giá khách hàng sạch) · Word (báo giá)

---

## Tab 4 — Trợ lý AI

Chat AI hỗ trợ tư vấn kinh doanh, phân tích tài liệu.

**Nhà cung cấp hỗ trợ:** Google Gemini · OpenAI · Anthropic Claude

**Tính năng:**
- Đính kèm file PDF, DOCX để AI phân tích
- Lưu lịch sử hội thoại (SQLite)
- API key được mã hóa cục bộ (`security.py`)

**Cài đặt:** Vào tab AI → nhập API key → chọn nhà cung cấp → bắt đầu chat.

---

## Xuất tài liệu

### Excel (.xlsx)
| Sheet | Nội dung |
|-------|----------|
| Nội bộ doanh nghiệp | Giá mua, ship, chi phí, giá vốn, biên LN, lợi nhuận từng dòng |
| Báo giá khách hàng | Tên sản phẩm, ĐVT, số lượng, đơn giá (có VAT), thành tiền — **không tiết lộ chi phí** |

### Word (.docx)
- Header công ty, watermark logo
- Bảng sản phẩm, điều khoản thanh toán (hiệu lực 15 ngày)
- Khung ký tên: đại diện khách hàng + đại diện công ty
- Mã báo giá tự sinh

---

## Build EXE (Windows)

```bash
bash build.sh
```

Yêu cầu: PyInstaller (`pip install pyinstaller`) + [Inno Setup](https://jrsoftware.org/isinfo.php) cài trên máy.

Output:
- `dist/HappySmartLightTool/HappySmartLightTool.exe` — file chạy standalone
- `Output/HappySmartLightTool_Setup.exe` — bộ cài đặt Windows

---

## Thông tin công ty

```
CÔNG TY TNHH THƯƠNG MẠI VÀ CÔNG NGHỆ HAPPY SMART LIGHT
Địa chỉ : 42 Hà Đức Trọng, Phường Bà Rịa, TP. Hồ Chí Minh
MST      : 3502535621
Điện thoại: 0784140494
Email    : happysmartlight@outlook.com
Website  : https://happysmartlight.com/
MB Bank  : 7294949999
Techcombank: 72949488
```

---

## Phiên bản

Xem [CHANGELOG.md](CHANGELOG.md) để biết lịch sử thay đổi.

Phiên bản hiện tại: **v2.8.0** — quản lý qua `config.json`.

---

## License

Phần mềm nội bộ — Happy Smart Light © 2026.
