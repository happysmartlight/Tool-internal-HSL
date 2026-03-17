"""
ui/import_cost_tab.py
Import Cost Calculator tab — theme synced with hop_dong_tool.py (dark neon).

Palette mirrors hop_dong_tool.py:
  _BG     = #0a0a14   background
  _CARD   = #111120   card/panel
  _BORDER = #1e1e38
  _TEXT   = #e8e8ff
  _DIM    = #6868a0
  _ACCENT = #16162a
  _CYAN   = #00c8f0   primary accent
  _PINK   = #e020d0   secondary accent
  _GREEN  = #00e87a   profit/positive
"""
import json
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (QApplication, QComboBox, QDoubleSpinBox,
                             QFileDialog, QFormLayout, QFrame, QGroupBox,
                             QHBoxLayout, QHeaderView, QLabel, QListWidget,
                             QListWidgetItem, QMessageBox, QPushButton,
                             QSizePolicy, QSplitter, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

from database import db_handler
from models.cost_config import CostBreakdown, CostConfig, ExchangeRate
from models.product import ImportOrder, OrderLine, Product
from services import calculator_service, exchange_rate_service
from utils import excel_exporter
from utils.logger import get_logger

log = get_logger(__name__)

# ── Palette — mirrors hop_dong_tool.py ──────────────────────
_PINK   = "#e020d0"
_CYAN   = "#00c8f0"
_BG     = "#0a0a14"
_CARD   = "#111120"
_BORDER = "#1e1e38"
_TEXT   = "#e8e8ff"
_DIM    = "#6868a0"
_ACCENT = "#16162a"
_GREEN  = "#00e87a"
_WARN   = "#ffaa00"

SUPPORTED_CURRENCIES = ["USD", "JPY", "CNY", "EUR", "GBP", "KRW", "THB"]

# Column indices in product table
COL_NAME     = 0
COL_QTY      = 1
COL_PRICE    = 2
COL_SHIP     = 3   # optional shipping/other cost per unit (ngoại tệ)
COL_DISCOUNT = 4   # chiết khấu (ngoại tệ)
COL_TOTAL    = 5   # read-only computed: (qty * price) + ship - discount
COL_DEL      = 6


# ─────────────────────────────────────────────────────────────
# Worker — non-blocking rate fetch
# ─────────────────────────────────────────────────────────────
class _RateFetchWorker(QThread):
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, currencies: list, spread_pct: float):
        super().__init__()
        self.currencies = currencies
        self.spread_pct = spread_pct

    def run(self):
        try:
            rates = exchange_rate_service.refresh_all(self.currencies, self.spread_pct)
            self.done.emit(rates)
        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────────────────────────────────────────────
# Stat card (Giá vốn / Giá bán / Lợi nhuận)
# ─────────────────────────────────────────────────────────────
class _StatCard(QFrame):
    def __init__(self, label: str, accent: str, parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setStyleSheet(f"""
            QFrame#StatCard {{
                background: {_CARD};
                border: 1px solid {_BORDER};
                border-top: 3px solid {accent};
                border-radius: 8px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)
        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(f"color:{_DIM}; font-size:11px;")
        self._val = QLabel("—")
        self._val.setStyleSheet(f"color:{accent}; font-size:17px; font-weight:bold;")
        lay.addWidget(self._lbl)
        lay.addWidget(self._val)

    def set_value(self, vnd: float):
        self._val.setText(f"{vnd:,.0f} ₫")


# ─────────────────────────────────────────────────────────────
# Main Tab Widget
# ─────────────────────────────────────────────────────────────
class ImportCostTab(QWidget):
    """Tab 2: Import Cost Calculator — theme synced with Tab 1."""

    def __init__(self, parent=None):
        super().__init__(parent)
        db_handler.init_db()
        self._rates: dict[str, ExchangeRate] = {}
        self._config = CostConfig()
        self._breakdown: CostBreakdown | None = None
        self._worker: _RateFetchWorker | None = None
        self._blocking_signals = False   # guard for programmatic table edits

        self._build_ui()
        self._apply_style()

        # Auto-refresh every 5 min
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._fetch_rates)
        self._timer.start(5 * 60 * 1000)

        self._fetch_rates()

    # ── UI ────────────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background:{_BORDER}; }}")

        # Left pane
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)
        ll.addWidget(self._build_currency_panel())
        ll.addWidget(self._build_product_panel(), 2)
        ll.addWidget(self._build_cost_settings_panel())

        # Right pane
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)
        rl.addWidget(self._build_results_panel(), 2)
        rl.addWidget(self._build_history_panel(), 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([640, 480])
        root.addWidget(splitter)

    # ── Currency Panel ────────────────────────────────────────
    def _build_currency_panel(self) -> QGroupBox:
        gb = self._group("💱  Tỷ giá")
        main_lay = QVBoxLayout(gb)
        main_lay.setSpacing(6)
        main_lay.setContentsMargins(8, 6, 8, 6)

        # Row 1: Loại tiền / Dùng tỷ giá / Refresh
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        lbl_cur = QLabel("Loại tiền:")
        lbl_cur.setStyleSheet(f"color:{_DIM}; font-size:11px;")
        self.combo_currency = QComboBox()
        self.combo_currency.addItems(SUPPORTED_CURRENCIES)
        self.combo_currency.setFixedWidth(90)
        self.combo_currency.currentTextChanged.connect(self._on_currency_changed)

        lbl_use = QLabel("Áp dụng:")
        lbl_use.setStyleSheet(f"color:{_DIM}; font-size:11px;")
        self.combo_rate_type = QComboBox()
        self.combo_rate_type.addItems(["Tỷ giá ngân hàng", "Tỷ giá thị trường"])
        self.combo_rate_type.currentTextChanged.connect(self._recalculate)

        btn_refresh = QPushButton("↻")
        btn_refresh.setFixedWidth(40)
        btn_refresh.setFixedHeight(32)
        btn_refresh.setToolTip("Cập nhật tỷ giá")
        font = btn_refresh.font()
        font.setBold(True)
        font.setPointSize(14)
        btn_refresh.setFont(font)
        btn_refresh.clicked.connect(self._fetch_rates)

        self.lbl_rate_status = QLabel("Đang tải…")
        self.lbl_rate_status.setStyleSheet(f"color:{_WARN}; font-size:10px;")

        row1.addWidget(lbl_cur)
        row1.addWidget(self.combo_currency)
        row1.addSpacing(12)
        row1.addWidget(lbl_use)
        row1.addWidget(self.combo_rate_type)
        row1.addStretch()
        row1.addWidget(self.lbl_rate_status)
        row1.addWidget(btn_refresh)

        # Row 2: Rate display (highlighted)
        row2 = QHBoxLayout()
        row2.setSpacing(16)

        self.lbl_market = QLabel("Thị trường: —")
        self.lbl_bank   = QLabel("Ngân hàng:  —")

        # Prominent green badges
        rate_style = f"""
            color: {_GREEN};
            font-size: 12px;
            font-weight: bold;
            background: {_GREEN}18;
            border: 1px solid {_GREEN}44;
            border-radius: 4px;
            padding: 2px 10px;
        """
        self.lbl_market.setStyleSheet(rate_style)
        self.lbl_bank.setStyleSheet(rate_style)

        row2.addWidget(self.lbl_market)
        row2.addWidget(self.lbl_bank)
        row2.addStretch()

        main_lay.addLayout(row1)
        main_lay.addLayout(row2)
        return gb

    # ── Product Table Panel ───────────────────────────────────
    def _build_product_panel(self) -> QGroupBox:
        gb = self._group("📦  Danh sách sản phẩm")
        lay = QVBoxLayout(gb)
        lay.setSpacing(6)

        # Table: 7 cols
        self.tbl = QTableWidget(0, 7)
        self.tbl.setHorizontalHeaderLabels([
            "Tên sản phẩm",
            "Số lượng",
            "Đơn giá theo ngoại tệ",
            "Chi phí ship / khác",
            "Chiết khấu (ngoại tệ)",
            "Thành tiền (ngoại tệ)",
            "",
        ])
        hdr = self.tbl.horizontalHeader()
        hdr.setSectionResizeMode(COL_NAME,     QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(COL_QTY,      QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(COL_PRICE,    QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(COL_SHIP,     QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(COL_DISCOUNT, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(COL_TOTAL,    QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(COL_DEL,      QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(COL_DEL, 42)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.itemChanged.connect(self._on_table_changed)
        lay.addWidget(self.tbl)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Thêm sản phẩm")
        btn_add.clicked.connect(self._add_product_row)
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self._add_product_row()
        return gb

    # ── Cost Settings ─────────────────────────────────────────
    def _build_cost_settings_panel(self) -> QGroupBox:
        gb = self._group("⚙️  Thông số chi phí")
        form = QFormLayout(gb)
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def spin(val, mn=0, mx=100, decs=1, suffix="") -> QDoubleSpinBox:
            s = QDoubleSpinBox()
            s.setRange(mn, mx)
            s.setDecimals(decs)
            s.setValue(val)
            s.setSuffix(suffix)
            s.valueChanged.connect(self._recalculate)
            return s

        self.spin_import_tax = spin(15.0, suffix=" %")
        self.spin_vat        = spin(10.0, suffix=" %")
        self.spin_fx_fee     = spin(3.4, decs=2, suffix=" %")
        self.spin_customs    = spin(1_500_000, mn=0, mx=100_000_000, decs=0, suffix=" VND")
        self.spin_customs_vat= spin(10.0, suffix=" %")
        self.spin_other      = spin(0, mn=0, mx=500_000_000, decs=0, suffix=" VND")
        self.spin_margin     = spin(40.0, suffix=" %")

        form.addRow("Thuế nhập khẩu:",          self.spin_import_tax)
        form.addRow("VAT:",                      self.spin_vat)
        form.addRow("Phí chuyển đổi ngoại tệ:", self.spin_fx_fee)
        form.addRow("Lệ phí hải quan:",          self.spin_customs)
        form.addRow("VAT lệ phí hải quan:",      self.spin_customs_vat)
        form.addRow("Chi phí phát sinh khác:",    self.spin_other)
        form.addRow("Margin lợi nhuận:",         self.spin_margin)
        return gb

    # ── Results Panel ─────────────────────────────────────────
    def _build_results_panel(self) -> QGroupBox:
        gb = self._group("📊  Kết quả")
        lay = QVBoxLayout(gb)
        lay.setSpacing(8)

        # Stat cards
        cards = QHBoxLayout()
        self.card_cost   = _StatCard("Giá vốn",          _PINK)
        self.card_sell   = _StatCard("Giá bán đề xuất",  _CYAN)
        self.card_profit = _StatCard("Lợi nhuận",         _GREEN)
        for c in (self.card_cost, self.card_sell, self.card_profit):
            cards.addWidget(c)
        lay.addLayout(cards)

        # Breakdown table — NO maxHeight so it shows all rows
        self.tbl_bd = QTableWidget(0, 2)
        self.tbl_bd.setHorizontalHeaderLabels(["Khoản mục", "Giá trị (VND)"])
        self.tbl_bd.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.tbl_bd.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_bd.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_bd.verticalHeader().setVisible(False)
        self.tbl_bd.setAlternatingRowColors(True)
        # Allow the table to expand — setSizePolicy Expanding
        self.tbl_bd.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(self.tbl_bd, 1)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_export = QPushButton("📥  Export Excel")
        btn_save   = QPushButton("💾  Lưu lịch sử")
        btn_export.setObjectName("primary")
        btn_save.setObjectName("primary")
        btn_export.clicked.connect(self._export_excel)
        btn_save.clicked.connect(self._save_to_history)
        btn_row.addWidget(btn_export)
        btn_row.addWidget(btn_save)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        return gb

    # ── History Panel ─────────────────────────────────────────
    def _build_history_panel(self) -> QGroupBox:
        gb = self._group("🕐  Lịch sử tính toán")
        lay = QVBoxLayout(gb)

        self.list_hist = QListWidget()
        self.list_hist.itemDoubleClicked.connect(self._load_history)
        lay.addWidget(self.list_hist)

        btn_row = QHBoxLayout()
        b_ref = QPushButton("🔄  Tải lại")
        b_del = QPushButton("🗑  Xóa")
        b_ref.clicked.connect(self._refresh_history)
        b_del.clicked.connect(self._delete_history)
        btn_row.addWidget(b_ref)
        btn_row.addWidget(b_del)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self._refresh_history()
        return gb

    # ── Helper widgets ────────────────────────────────────────
    @staticmethod
    def _group(title: str) -> QGroupBox:
        gb = QGroupBox(title)
        return gb

    @staticmethod
    def _lbl(text: str) -> QLabel:
        l = QLabel(text)
        return l

    # ── Logic: Rate fetch ─────────────────────────────────────
    def _fetch_rates(self):
        self.lbl_rate_status.setText("⏳  Đang tải…")
        self.lbl_rate_status.setStyleSheet(f"color:{_WARN}; font-size:10px;")
        self._worker = _RateFetchWorker(SUPPORTED_CURRENCIES, 2.0)
        self._worker.done.connect(self._on_rates_ok)
        self._worker.error.connect(self._on_rates_err)
        self._worker.start()

    def _on_rates_ok(self, rates: dict):
        self._rates = rates
        self._update_rate_display()
        now = datetime.now().strftime("%H:%M:%S")
        self.lbl_rate_status.setText(f"✅  {now}")
        self.lbl_rate_status.setStyleSheet(f"color:{_GREEN}; font-size:10px;")
        self._recalculate()

    def _on_rates_err(self, msg: str):
        self.lbl_rate_status.setText(f"⚠️  {msg[:40]}")
        self.lbl_rate_status.setStyleSheet(f"color:{_PINK}; font-size:10px;")

    def _on_currency_changed(self, _):
        self._update_rate_display()
        self._recalculate()

    def _update_rate_display(self):
        cur  = self.combo_currency.currentText()
        rate = self._rates.get(cur)
        if rate:
            self.lbl_market.setText(f"Thị trường: {rate.market_rate:,.0f} VND")
            self.lbl_bank.setText(  f"Ngân hàng:  {rate.bank_rate:,.0f} VND")
        else:
            self.lbl_market.setText("Thị trường: —")
            self.lbl_bank.setText(  "Ngân hàng:  —")

    # ── Logic: Product table ──────────────────────────────────
    def _add_product_row(self):
        self._blocking_signals = True
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)

        # Editable cells
        for col, text in [(COL_NAME,     "Sản phẩm mới"),
                          (COL_QTY,      "1"),
                          (COL_PRICE,    "0"),
                          (COL_SHIP,     "0"),
                          (COL_DISCOUNT, "0")]:
            self.tbl.setItem(r, col, QTableWidgetItem(text))

        # Read-only total
        total_item = QTableWidgetItem("0.00")
        total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        total_item.setForeground(QColor(_CYAN))
        total_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.tbl.setItem(r, COL_TOTAL, total_item)

        # Delete button
        btn_del = QPushButton("🗑️")
        btn_del.setFixedWidth(36)
        btn_del.setFixedHeight(30)
        btn_del.setStyleSheet(
            f"color:{_PINK}; background:transparent; border:none; font-size:14px;")
        btn_del.clicked.connect(lambda: self._remove_row(btn_del))
        self.tbl.setCellWidget(r, COL_DEL, btn_del)

        self._blocking_signals = False

    def _remove_row(self, btn):
        for r in range(self.tbl.rowCount()):
            if self.tbl.cellWidget(r, COL_DEL) == btn:
                self.tbl.removeRow(r)
                break
        self._recalculate()

    def _on_table_changed(self, item):
        if self._blocking_signals:
            return
        r = item.row()
        if item.column() in (COL_QTY, COL_PRICE, COL_SHIP, COL_DISCOUNT):
            self._update_row_total(r)
        self._recalculate()

    def _update_row_total(self, r: int):
        """Recalculate and display the read-only total for row r."""
        def _val(col) -> float:
            it = self.tbl.item(r, col)
            try:
                return float(it.text().replace(",", "") if it else "0")
            except ValueError:
                return 0.0

        total = _val(COL_QTY) * _val(COL_PRICE) + _val(COL_SHIP) - _val(COL_DISCOUNT)
        self._blocking_signals = True
        total_item = self.tbl.item(r, COL_TOTAL)
        if total_item is None:
            total_item = QTableWidgetItem()
            total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl.setItem(r, COL_TOTAL, total_item)
        total_item.setText(f"{total:,.2f}")
        total_item.setForeground(QColor(_CYAN))
        total_item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._blocking_signals = False

    def _get_order(self) -> ImportOrder:
        cur  = self.combo_currency.currentText()
        rate = self._rates.get(cur)
        use_bank = self.combo_rate_type.currentIndex() == 0
        ex   = (rate.bank_rate if use_bank else rate.market_rate) if rate else 0.0
        lines = []
        for r in range(self.tbl.rowCount()):
            def cell(col) -> str:
                it = self.tbl.item(r, col)
                return it.text() if it else "0"
            try:
                name  = cell(COL_NAME)
                qty   = float(cell(COL_QTY).replace(",", ""))
                price = float(cell(COL_PRICE).replace(",", ""))
                ship  = float(cell(COL_SHIP).replace(",", ""))
                disc  = float(cell(COL_DISCOUNT).replace(",", ""))
                # Effective unit price includes ship cost
                effective_price = price + (ship / qty if qty else 0)
            except (ValueError, ZeroDivisionError):
                continue
            p = Product(name=name, qty=qty,
                        unit_price_foreign=effective_price,
                        discount_foreign=disc,
                        currency=cur)
            lines.append(OrderLine(product=p, exchange_rate=ex))
        return ImportOrder(lines=lines, currency=cur)

    def _get_config(self) -> CostConfig:
        return CostConfig(
            import_tax_pct     = self.spin_import_tax.value(),
            vat_pct            = self.spin_vat.value(),
            fx_conversion_pct  = self.spin_fx_fee.value(),
            customs_fee_vnd    = self.spin_customs.value(),
            customs_fee_vat_pct= self.spin_customs_vat.value(),
            other_costs_vnd    = self.spin_other.value(),
            margin_pct         = self.spin_margin.value(),
        )

    # ── Logic: Calculate ──────────────────────────────────────
    def _recalculate(self):
        cur  = self.combo_currency.currentText()
        rate = self._rates.get(cur)
        if not rate:
            return
        order  = self._get_order()
        config = self._get_config()

        # Guard: no products / zero FOB -> clear results
        if order.total_foreign == 0:
            self._breakdown = None
            self._clear_results()
            return

        use_bank = self.combo_rate_type.currentIndex() == 0
        self._breakdown = calculator_service.calculate(order, config, rate, use_bank)
        self._update_results(self._breakdown)

    def _clear_results(self):
        """Reset stat cards and breakdown table when no products are entered."""
        for card in (self.card_cost, self.card_sell, self.card_profit):
            card._val.setText("—")
        self.tbl_bd.setRowCount(0)

    def _update_results(self, bd: CostBreakdown):
        self.card_cost.set_value(bd.total_cost_vnd)
        self.card_sell.set_value(bd.selling_price_vnd)
        self.card_profit.set_value(bd.profit_vnd)

        breakdown_rows = [
            ("Trị giá hàng hóa (FOB)",         bd.total_vnd_base),
            ("Chiết khấu (Discount)",         -bd.total_discount_vnd if bd.total_discount_vnd else 0),
            ("Thuế nhập khẩu",                  bd.import_tax_vnd),
            ("VAT",                              bd.vat_vnd),
            ("Phí chuyển đổi ngoại tệ",         bd.fx_fee_vnd),
            ("Lệ phí hải quan",                  bd.customs_fee_vnd),
            ("VAT lệ phí hải quan",              bd.customs_fee_vat_vnd),
            ("Chi phí phát sinh khác",            bd.other_costs_vnd),
            ("─────────────────────────────────",""),
            ("GIÁ VỐN (Tổng chi phí)",          bd.total_cost_vnd),
            ("Giá bán đề xuất",                  bd.selling_price_vnd),
            ("Lợi nhuận",                        bd.profit_vnd),
        ]

        self.tbl_bd.setRowCount(len(breakdown_rows))

        # Accent colors for special rows
        highlights = {
            "GIÁ VỐN (Tổng chi phí)": _PINK,
            "Giá bán đề xuất":         _CYAN,
            "Lợi nhuận":               _GREEN,
        }

        for i, (label, val) in enumerate(breakdown_rows):
            lbl_item = QTableWidgetItem(label)
            lbl_item.setFlags(lbl_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            val_item = QTableWidgetItem(
                f"{val:,.0f} ₫" if isinstance(val, (int, float)) else "")
            val_item.setFlags(val_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            val_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            if label in highlights:
                color = QColor(highlights[label])
                lbl_item.setForeground(color)
                val_item.setForeground(color)
                font = QFont(); font.setBold(True)
                lbl_item.setFont(font)
                val_item.setFont(font)
            elif label.startswith("───"):
                lbl_item.setForeground(QColor(_BORDER))

            self.tbl_bd.setItem(i, 0, lbl_item)
            self.tbl_bd.setItem(i, 1, val_item)

        self.tbl_bd.resizeRowsToContents()

    # ── Logic: Export ─────────────────────────────────────────
    def _export_excel(self):
        if not self._breakdown:
            QMessageBox.warning(self, "Chưa tính toán", "Vui lòng nhập sản phẩm trước.")
            return
        cur  = self.combo_currency.currentText()
        rate = self._rates.get(cur)
        if not rate:
            QMessageBox.warning(self, "Chưa có tỷ giá", "Không tìm thấy tỷ giá.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu báo giá Excel",
            f"baogianhapmkau_{datetime.now():%Y%m%d_%H%M}.xlsx",
            "Excel (*.xlsx)")
        if not path:
            return
        try:
            order  = self._get_order()
            config = self._get_config()
            use_bank = self.combo_rate_type.currentIndex() == 0
            excel_exporter.export(
                order, config, rate, self._breakdown, use_bank, Path(path))
            QMessageBox.information(self, "Thành công",
                                    f"Đã xuất file:\n{path}")
        except Exception as e:
            log.exception("Export Excel failed")
            QMessageBox.critical(self, "Lỗi", str(e))

    # ── Logic: History ────────────────────────────────────────
    def _save_to_history(self):
        if not self._breakdown:
            return
        cur   = self.combo_currency.currentText()
        rate  = self._rates.get(cur)
        order = self._get_order()
        products_list = [
            {"name": l.product.name,
             "qty": l.product.qty,
             "unit_price": l.product.unit_price_foreign,
             "discount_foreign": l.product.discount_foreign,
             "currency": l.product.currency}
            for l in order.lines
        ]
        cfg = self._get_config()
        config_dict = {
            "import_tax_pct":    cfg.import_tax_pct,
            "vat_pct":           cfg.vat_pct,
            "fx_conversion_pct": cfg.fx_conversion_pct,
            "customs_fee_vnd":   cfg.customs_fee_vnd,
            "customs_fee_vat_pct": cfg.customs_fee_vat_pct,
            "other_costs_vnd":   cfg.other_costs_vnd,
            "margin_pct":        cfg.margin_pct,
        }
        rate_dict = {
            "currency":    cur,
            "market_rate": rate.market_rate if rate else 0,
            "bank_rate":   rate.bank_rate   if rate else 0,
        }
        result_dict = calculator_service.breakdown_to_dict(self._breakdown)
        label = (f"{cur} — {order.total_foreign:,.0f}"
                 f" — {datetime.now():%d/%m/%Y %H:%M}")
        db_handler.save_calculation(
            label, products_list, config_dict, rate_dict, result_dict)
        self._refresh_history()
        QMessageBox.information(self, "Đã lưu", "Đã lưu lịch sử tính toán.")

    def _refresh_history(self):
        self.list_hist.clear()
        for row in db_handler.list_calculations(30):
            item = QListWidgetItem(
                f"#{row['id']} | {row['created_at'][:16]} | {row['label']}")
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.list_hist.addItem(item)

    def _load_history(self, item):
        calc_id = item.data(Qt.ItemDataRole.UserRole)
        row = db_handler.get_calculation(calc_id)
        if not row:
            return
        # Restore products
        self._blocking_signals = True
        self.tbl.setRowCount(0)
        self._blocking_signals = False
        for p in row["products_list"]:
            self._blocking_signals = True
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            self.tbl.setItem(r, COL_NAME,  QTableWidgetItem(p["name"]))
            self.tbl.setItem(r, COL_QTY,   QTableWidgetItem(str(p["qty"])))
            self.tbl.setItem(r, COL_PRICE, QTableWidgetItem(str(p["unit_price"])))
            self.tbl.setItem(r, COL_SHIP,  QTableWidgetItem("0"))
            
            # Khôi phục discount nếu có, tương thích với lịch sử cũ không có trường này
            disc = p.get("discount_foreign", 0.0)
            self.tbl.setItem(r, COL_DISCOUNT, QTableWidgetItem(str(disc)))

            total_val = (p['qty'] * p['unit_price']) - disc
            total_item = QTableWidgetItem(f"{total_val:,.2f}")
            total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            total_item.setForeground(QColor(_CYAN))
            total_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl.setItem(r, COL_TOTAL, total_item)
            btn_del = QPushButton("✕")
            btn_del.setFixedWidth(28)
            btn_del.setStyleSheet(
                f"color:{_PINK}; background:transparent; border:none; font-weight:bold;")
            btn_del.clicked.connect(lambda: self._remove_row(btn_del))
            self.tbl.setCellWidget(r, COL_DEL, btn_del)
            self._blocking_signals = False

        # Restore config
        c = row["config_dict"]
        self.spin_import_tax.setValue(c.get("import_tax_pct", 15))
        self.spin_vat.setValue(c.get("vat_pct", 10))
        self.spin_fx_fee.setValue(c.get("fx_conversion_pct", 3.4))
        self.spin_customs.setValue(c.get("customs_fee_vnd", 1_500_000))
        self.spin_customs_vat.setValue(c.get("customs_fee_vat_pct", 10))
        self.spin_other.setValue(c.get("other_costs_vnd", 0))
        self.spin_margin.setValue(c.get("margin_pct", 40))

        rcur = row["rate_dict"].get("currency", "USD")
        idx  = self.combo_currency.findText(rcur)
        if idx >= 0:
            self.combo_currency.setCurrentIndex(idx)
        self._recalculate()

    def _delete_history(self):
        item = self.list_hist.currentItem()
        if not item:
            return
        db_handler.delete_calculation(item.data(Qt.ItemDataRole.UserRole))
        self._refresh_history()

    # ── Stylesheet ────────────────────────────────────────────
    def _apply_style(self):
        self.setStyleSheet(f"""
            QWidget {{
                background: {_BG};
                color: {_TEXT};
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }}
            QGroupBox {{
                background: {_CARD};
                border: 1px solid {_BORDER};
                border-radius: 10px;
                margin-top: 10px;
                font-weight: bold;
                font-size: 12px;
                color: {_CYAN};
                padding: 4px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }}
            QTableWidget {{
                background: {_CARD};
                alternate-background-color: {_ACCENT};
                gridline-color: {_BORDER};
                border: 1px solid {_BORDER};
                border-radius: 6px;
            }}
            QHeaderView::section {{
                background: {_ACCENT};
                color: {_CYAN};
                font-weight: bold;
                padding: 5px;
                border: none;
                border-right: 1px solid {_BORDER};
                border-bottom: 1px solid {_BORDER};
            }}
            QTableWidget::item:selected {{
                background: {_CYAN}22;
                color: {_TEXT};
            }}
            QComboBox, QDoubleSpinBox {{
                background: {_ACCENT};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                padding: 3px 6px;
                color: {_TEXT};
                selection-background-color: {_CYAN}44;
            }}
            QComboBox QAbstractItemView {{
                background: {_CARD};
                selection-background-color: {_CYAN}44;
                border: 1px solid {_BORDER};
            }}
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                background: {_BORDER};
                border: none;
                border-radius: 2px;
            }}
            QPushButton {{
                background: {_ACCENT};
                border: 1px solid {_BORDER};
                border-radius: 6px;
                padding: 6px 14px;
                color: {_TEXT};
            }}
            QPushButton:hover {{
                background: {_CYAN}1a;
                border: 1px solid {_CYAN};
                color: {_CYAN};
            }}
            QPushButton#primary {{
                background: qlineargradient(
                    x1:0,y1:0,x2:1,y2:0,
                    stop:0 {_CYAN}, stop:1 {_PINK});
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }}
            QPushButton#primary:hover {{
                opacity: 0.85;
            }}
            QListWidget {{
                background: {_CARD};
                border: 1px solid {_BORDER};
                border-radius: 6px;
            }}
            QListWidget::item:selected {{
                background: {_CYAN}22;
            }}
            QListWidget::item:hover {{
                background: {_ACCENT};
            }}
            QScrollBar:vertical {{
                background: {_CARD};
                width: 7px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: {_CYAN}55;
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {_CYAN}; }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{ height: 0; }}
            QSplitter::handle {{ background: {_BORDER}; }}
        """)
