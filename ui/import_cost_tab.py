"""
ui/import_cost_tab.py
Main Import Cost Calculator tab widget.
Orchestrates product table, settings panel, results panel and history panel.
"""
import json
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QDate, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFrame,
                             QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                             QMessageBox, QPushButton, QScrollArea,
                             QSizePolicy, QSplitter, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

from database import db_handler
from models.cost_config import CostBreakdown, CostConfig, ExchangeRate
from models.product import ImportOrder, OrderLine, Product
from services import calculator_service, exchange_rate_service
from utils import excel_exporter
from utils.logger import get_logger

log = get_logger(__name__)

# ── Color palette ────────────────────────────────────────────
_DARK_BG    = "#1E1E2E"
_DARK_CARD  = "#2A2A3E"
_DARK_PANEL = "#252535"
_ACCENT     = "#7C83FD"
_RED        = "#FF5C7A"
_GREEN      = "#4CD964"
_BLUE       = "#5AC8FA"
_TEXT       = "#E0E0F0"
_MUTED      = "#888AAA"

SUPPORTED_CURRENCIES = ["USD", "JPY", "CNY", "EUR", "GBP", "KRW", "THB"]


# ─────────────────────────────────────────────────────────────
# Worker thread for non-blocking rate fetch
# ─────────────────────────────────────────────────────────────
class _RateFetchWorker(QThread):
    done = pyqtSignal(dict)   # {currency -> ExchangeRate}
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
# Stat card widget (Giá vốn / Giá bán / Lợi nhuận)
# ─────────────────────────────────────────────────────────────
class _StatCard(QFrame):
    def __init__(self, label: str, color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("StatCard")
        self.setStyleSheet(f"""
            #StatCard {{
                background: {_DARK_CARD};
                border-radius: 10px;
                border-left: 4px solid {color};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        self._label = QLabel(label)
        self._label.setStyleSheet(f"color: {_MUTED}; font-size: 11px;")
        self._value = QLabel("—")
        self._value.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: bold;")
        layout.addWidget(self._label)
        layout.addWidget(self._value)

    def set_value(self, vnd: float):
        self._value.setText(f"{vnd:,.0f} ₫")


# ─────────────────────────────────────────────────────────────
# Main Tab
# ─────────────────────────────────────────────────────────────
class ImportCostTab(QWidget):
    """Tab 2: Import Cost Calculator"""

    def __init__(self, parent=None):
        super().__init__(parent)
        db_handler.init_db()
        self._rates: dict[str, ExchangeRate] = {}
        self._config = CostConfig()
        self._breakdown: CostBreakdown | None = None
        self._worker: _RateFetchWorker | None = None

        self._build_ui()
        self._apply_dark_style()

        # Auto-refresh timer (5 min)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._fetch_rates)
        self._timer.start(5 * 60 * 1000)

        # Initial fetch
        self._fetch_rates()

    # ── UI Builder ─────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        # Left pane
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(self._build_currency_panel())
        left_layout.addWidget(self._build_product_panel(), 1)
        left_layout.addWidget(self._build_cost_settings_panel())

        # Right pane
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(self._build_results_panel())
        right_layout.addWidget(self._build_history_panel(), 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([620, 460])
        root.addWidget(splitter)

    # ── Currency Panel ──────────────────────────────────────
    def _build_currency_panel(self) -> QGroupBox:
        gb = QGroupBox("💱 Tỷ giá")
        layout = QHBoxLayout(gb)
        layout.setSpacing(10)

        # Currency selector
        self.combo_currency = QComboBox()
        self.combo_currency.addItems(SUPPORTED_CURRENCIES)
        self.combo_currency.currentTextChanged.connect(self._on_currency_changed)
        layout.addWidget(QLabel("Loại tiền:"))
        layout.addWidget(self.combo_currency)

        # Rate display
        self.lbl_market_rate = QLabel("Thị trường: —")
        self.lbl_bank_rate   = QLabel("Ngân hàng: —")
        self.lbl_market_rate.setObjectName("RateLbl")
        self.lbl_bank_rate.setObjectName("RateLbl")
        layout.addWidget(self.lbl_market_rate)
        layout.addWidget(self.lbl_bank_rate)

        layout.addStretch()

        # Use rate toggle
        self.combo_rate_type = QComboBox()
        self.combo_rate_type.addItems(["Tỷ giá ngân hàng", "Tỷ giá thị trường"])
        self.combo_rate_type.currentTextChanged.connect(self._recalculate)
        layout.addWidget(QLabel("Dùng:"))
        layout.addWidget(self.combo_rate_type)

        # Refresh
        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedWidth(34)
        btn_refresh.setToolTip("Cập nhật tỷ giá")
        btn_refresh.clicked.connect(self._fetch_rates)
        self.lbl_rate_status = QLabel("Đang tải…")
        self.lbl_rate_status.setStyleSheet(f"color:{_MUTED}; font-size:10px;")
        layout.addWidget(btn_refresh)
        layout.addWidget(self.lbl_rate_status)
        return gb

    # ── Product Table Panel ─────────────────────────────────
    def _build_product_panel(self) -> QGroupBox:
        gb = QGroupBox("📦 Danh sách sản phẩm")
        layout = QVBoxLayout(gb)

        # Table
        self.tbl_products = QTableWidget(0, 5)
        self.tbl_products.setHorizontalHeaderLabels(
            ["Tên sản phẩm", "Số lượng", "Đơn giá", "T.Tiền (ngoại tệ)", ""])
        self.tbl_products.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_products.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_products.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.tbl_products.setColumnWidth(4, 30)
        self.tbl_products.setColumnWidth(1, 80)
        self.tbl_products.setColumnWidth(2, 100)
        self.tbl_products.setAlternatingRowColors(True)
        self.tbl_products.itemChanged.connect(self._on_table_changed)
        self.tbl_products.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked |
                                          QTableWidget.EditTrigger.SelectedClicked)
        layout.addWidget(self.tbl_products)

        # Buttons
        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Thêm sản phẩm")
        btn_add.clicked.connect(self._add_product_row)
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Add a default row
        self._add_product_row()
        return gb

    # ── Cost Settings Panel ─────────────────────────────────
    def _build_cost_settings_panel(self) -> QGroupBox:
        gb = QGroupBox("⚙️ Thông số chi phí")
        from PyQt6.QtWidgets import QDoubleSpinBox, QFormLayout
        form = QFormLayout(gb)
        form.setSpacing(6)

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
        self.spin_margin     = spin(40.0, suffix=" %")

        form.addRow("Thuế nhập khẩu:", self.spin_import_tax)
        form.addRow("VAT:", self.spin_vat)
        form.addRow("Phí chuyển đổi ngoại tệ:", self.spin_fx_fee)
        form.addRow("Lệ phí hải quan:", self.spin_customs)
        form.addRow("VAT lệ phí HQ:", self.spin_customs_vat)
        form.addRow("Margin lợi nhuận:", self.spin_margin)
        return gb

    # ── Results Panel ───────────────────────────────────────
    def _build_results_panel(self) -> QGroupBox:
        gb = QGroupBox("📊 Kết quả")
        layout = QVBoxLayout(gb)

        # Stat cards
        cards_row = QHBoxLayout()
        self.card_cost   = _StatCard("Giá vốn",           _RED)
        self.card_sell   = _StatCard("Giá bán đề xuất",   _BLUE)
        self.card_profit = _StatCard("Lợi nhuận",          _GREEN)
        for c in (self.card_cost, self.card_sell, self.card_profit):
            cards_row.addWidget(c)
        layout.addLayout(cards_row)

        # Breakdown table (read-only)
        self.tbl_breakdown = QTableWidget(0, 2)
        self.tbl_breakdown.setHorizontalHeaderLabels(["Khoản mục", "Giá trị (VND)"])
        self.tbl_breakdown.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_breakdown.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_breakdown.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_breakdown.setMaximumHeight(200)
        layout.addWidget(self.tbl_breakdown)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_export  = QPushButton("📥 Export Excel")
        btn_save_hist = QPushButton("💾 Lưu lịch sử")
        btn_export.clicked.connect(self._export_excel)
        btn_save_hist.clicked.connect(self._save_to_history)
        btn_export.setObjectName("AccentBtn")
        btn_save_hist.setObjectName("AccentBtn")
        btn_row.addWidget(btn_export)
        btn_row.addWidget(btn_save_hist)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return gb

    # ── History Panel ───────────────────────────────────────
    def _build_history_panel(self) -> QGroupBox:
        from PyQt6.QtWidgets import QListWidget
        gb = QGroupBox("🕐 Lịch sử tính toán")
        layout = QVBoxLayout(gb)

        self.list_history = QListWidget()
        self.list_history.itemDoubleClicked.connect(self._load_history_item)
        layout.addWidget(self.list_history)

        btn_row = QHBoxLayout()
        btn_refresh_hist = QPushButton("🔄 Tải lại")
        btn_del = QPushButton("🗑 Xóa")
        btn_refresh_hist.clicked.connect(self._refresh_history)
        btn_del.clicked.connect(self._delete_history_item)
        btn_row.addWidget(btn_refresh_hist)
        btn_row.addWidget(btn_del)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._refresh_history()
        return gb

    # ── Logic: Rate Fetch ────────────────────────────────────
    def _fetch_rates(self):
        self.lbl_rate_status.setText("⏳ Đang tải…")
        currencies = SUPPORTED_CURRENCIES
        spread = 2.0
        self._worker = _RateFetchWorker(currencies, spread)
        self._worker.done.connect(self._on_rates_fetched)
        self._worker.error.connect(lambda e: self.lbl_rate_status.setText(f"⚠️ {e}"))
        self._worker.start()

    def _on_rates_fetched(self, rates: dict):
        self._rates = rates
        self._update_rate_display()
        now = datetime.now().strftime("%H:%M:%S")
        self.lbl_rate_status.setText(f"✅ Cập nhật lúc {now}")
        self._recalculate()

    def _on_currency_changed(self, _):
        self._update_rate_display()
        self._recalculate()

    def _update_rate_display(self):
        cur = self.combo_currency.currentText()
        rate = self._rates.get(cur)
        if rate:
            self.lbl_market_rate.setText(f"Thị trường: {rate.market_rate:,.0f} VND")
            self.lbl_bank_rate.setText(  f"Ngân hàng:  {rate.bank_rate:,.0f} VND")
        else:
            self.lbl_market_rate.setText("Thị trường: —")
            self.lbl_bank_rate.setText(  "Ngân hàng:  —")

    # ── Logic: Table ─────────────────────────────────────────
    def _add_product_row(self):
        self.tbl_products.itemChanged.disconnect(self._on_table_changed)
        r = self.tbl_products.rowCount()
        self.tbl_products.insertRow(r)
        self.tbl_products.setItem(r, 0, QTableWidgetItem("Sản phẩm mới"))
        self.tbl_products.setItem(r, 1, QTableWidgetItem("1"))
        self.tbl_products.setItem(r, 2, QTableWidgetItem("0"))
        self.tbl_products.setItem(r, 3, QTableWidgetItem("0"))
        # Delete button
        btn_del = QPushButton("✕")
        btn_del.setFixedWidth(28)
        btn_del.setStyleSheet(f"color:{_RED}; background:transparent; border:none; font-weight:bold;")
        btn_del.clicked.connect(lambda: self._remove_row(btn_del))
        self.tbl_products.setCellWidget(r, 4, btn_del)
        self.tbl_products.itemChanged.connect(self._on_table_changed)

    def _remove_row(self, btn):
        for r in range(self.tbl_products.rowCount()):
            if self.tbl_products.cellWidget(r, 4) == btn:
                self.tbl_products.removeRow(r)
                break
        self._recalculate()

    def _on_table_changed(self, item):
        if item.column() in (1, 2):
            # Update total column
            r = item.row()
            try:
                qty = float(self.tbl_products.item(r, 1).text() or 0)
                price = float(self.tbl_products.item(r, 2).text() or 0)
                total = qty * price
            except ValueError:
                total = 0.0
            self.tbl_products.blockSignals(True)
            self.tbl_products.setItem(r, 3, QTableWidgetItem(f"{total:,.2f}"))
            self.tbl_products.blockSignals(False)
        self._recalculate()

    def _get_order(self) -> ImportOrder:
        cur = self.combo_currency.currentText()
        rate = self._rates.get(cur)
        ex = rate.bank_rate if rate and self.combo_rate_type.currentIndex() == 0 else (
             rate.market_rate if rate else 0.0)
        lines = []
        for r in range(self.tbl_products.rowCount()):
            try:
                name  = (self.tbl_products.item(r, 0) or QTableWidgetItem("")).text()
                qty   = float((self.tbl_products.item(r, 1) or QTableWidgetItem("0")).text())
                price = float((self.tbl_products.item(r, 2) or QTableWidgetItem("0")).text())
            except ValueError:
                continue
            p = Product(name=name, qty=qty, unit_price_foreign=price, currency=cur)
            lines.append(OrderLine(product=p, exchange_rate=ex))
        return ImportOrder(lines=lines, currency=cur)

    def _get_config(self) -> CostConfig:
        return CostConfig(
            import_tax_pct    = self.spin_import_tax.value(),
            vat_pct           = self.spin_vat.value(),
            fx_conversion_pct = self.spin_fx_fee.value(),
            customs_fee_vnd   = self.spin_customs.value(),
            customs_fee_vat_pct = self.spin_customs_vat.value(),
            margin_pct        = self.spin_margin.value(),
        )

    # ── Logic: Calculate ─────────────────────────────────────
    def _recalculate(self):
        cur = self.combo_currency.currentText()
        rate = self._rates.get(cur)
        if not rate:
            return
        order  = self._get_order()
        config = self._get_config()
        use_bank = self.combo_rate_type.currentIndex() == 0
        self._breakdown = calculator_service.calculate(order, config, rate, use_bank)
        self._update_results(self._breakdown)

    def _update_results(self, bd: CostBreakdown):
        self.card_cost.set_value(bd.total_cost_vnd)
        self.card_sell.set_value(bd.selling_price_vnd)
        self.card_profit.set_value(bd.profit_vnd)

        rows = [
            ("Trị giá hàng hóa (FOB)", bd.total_vnd_base),
            ("Thuế nhập khẩu",          bd.import_tax_vnd),
            ("VAT",                      bd.vat_vnd),
            ("Phí chuyển đổi ngoại tệ", bd.fx_fee_vnd),
            ("Lệ phí hải quan",          bd.customs_fee_vnd),
            ("VAT lệ phí hải quan",      bd.customs_fee_vat_vnd),
        ]
        self.tbl_breakdown.setRowCount(len(rows))
        for i, (label, val) in enumerate(rows):
            self.tbl_breakdown.setItem(i, 0, QTableWidgetItem(label))
            item = QTableWidgetItem(f"{val:,.0f} ₫")
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl_breakdown.setItem(i, 1, item)

    # ── Logic: Export Excel ──────────────────────────────────
    def _export_excel(self):
        if not self._breakdown:
            QMessageBox.warning(self, "Chưa tính toán", "Vui lòng nhập sản phẩm trước.")
            return
        cur = self.combo_currency.currentText()
        rate = self._rates.get(cur)
        if not rate:
            QMessageBox.warning(self, "Chưa có tỷ giá", "Không tìm thấy tỷ giá.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu báo giá Excel", f"baogianhapmkau_{datetime.now():%Y%m%d_%H%M}.xlsx",
            "Excel (*.xlsx)")
        if not path:
            return
        try:
            order = self._get_order()
            config = self._get_config()
            use_bank = self.combo_rate_type.currentIndex() == 0
            excel_exporter.export(order, config, rate, self._breakdown, use_bank, Path(path))
            QMessageBox.information(self, "Thành công", f"Đã xuất file:\n{path}")
        except Exception as e:
            log.exception("Export Excel failed")
            QMessageBox.critical(self, "Lỗi", str(e))

    # ── Logic: History ───────────────────────────────────────
    def _save_to_history(self):
        if not self._breakdown:
            return
        cur = self.combo_currency.currentText()
        rate = self._rates.get(cur)
        order = self._get_order()
        products_list = [
            {"name": l.product.name, "qty": l.product.qty,
             "unit_price": l.product.unit_price_foreign, "currency": l.product.currency}
            for l in order.lines
        ]
        config = self._get_config()
        config_dict = {
            "import_tax_pct": config.import_tax_pct,
            "vat_pct": config.vat_pct,
            "fx_conversion_pct": config.fx_conversion_pct,
            "customs_fee_vnd": config.customs_fee_vnd,
            "customs_fee_vat_pct": config.customs_fee_vat_pct,
            "margin_pct": config.margin_pct,
        }
        rate_dict = {
            "currency": cur,
            "market_rate": rate.market_rate if rate else 0,
            "bank_rate":   rate.bank_rate   if rate else 0,
        }
        result_dict = calculator_service.breakdown_to_dict(self._breakdown)
        label = f"{cur} — {order.total_foreign:,.0f} — {datetime.now():%d/%m/%Y %H:%M}"
        db_handler.save_calculation(label, products_list, config_dict, rate_dict, result_dict)
        self._refresh_history()
        QMessageBox.information(self, "Đã lưu", "Đã lưu lịch sử tính toán.")

    def _refresh_history(self):
        self.list_history.clear()
        rows = db_handler.list_calculations(30)
        for row in rows:
            from PyQt6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(
                f"#{row['id']} | {row['created_at'][:16]} | {row['label']}")
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.list_history.addItem(item)

    def _load_history_item(self, item):
        calc_id = item.data(Qt.ItemDataRole.UserRole)
        row = db_handler.get_calculation(calc_id)
        if not row:
            return
        # Restore products
        self.tbl_products.setRowCount(0)
        for p in row["products_list"]:
            self.tbl_products.itemChanged.disconnect(self._on_table_changed)
            r = self.tbl_products.rowCount()
            self.tbl_products.insertRow(r)
            self.tbl_products.setItem(r, 0, QTableWidgetItem(p["name"]))
            self.tbl_products.setItem(r, 1, QTableWidgetItem(str(p["qty"])))
            self.tbl_products.setItem(r, 2, QTableWidgetItem(str(p["unit_price"])))
            self.tbl_products.setItem(r, 3, QTableWidgetItem(
                f"{p['qty'] * p['unit_price']:,.2f}"))
            btn_del = QPushButton("✕")
            btn_del.setFixedWidth(28)
            btn_del.setStyleSheet(f"color:{_RED}; background:transparent; border:none;")
            btn_del.clicked.connect(lambda: self._remove_row(btn_del))
            self.tbl_products.setCellWidget(r, 4, btn_del)
            self.tbl_products.itemChanged.connect(self._on_table_changed)
        # Restore config
        c = row["config_dict"]
        self.spin_import_tax.setValue(c.get("import_tax_pct", 15))
        self.spin_vat.setValue(c.get("vat_pct", 10))
        self.spin_fx_fee.setValue(c.get("fx_conversion_pct", 3.4))
        self.spin_customs.setValue(c.get("customs_fee_vnd", 1_500_000))
        self.spin_customs_vat.setValue(c.get("customs_fee_vat_pct", 10))
        self.spin_margin.setValue(c.get("margin_pct", 40))
        # Set currency
        rcur = row["rate_dict"].get("currency", "USD")
        idx = self.combo_currency.findText(rcur)
        if idx >= 0:
            self.combo_currency.setCurrentIndex(idx)
        self._recalculate()

    def _delete_history_item(self):
        item = self.list_history.currentItem()
        if not item:
            return
        calc_id = item.data(Qt.ItemDataRole.UserRole)
        db_handler.delete_calculation(calc_id)
        self._refresh_history()

    # ── Style ────────────────────────────────────────────────
    def _apply_dark_style(self):
        self.setStyleSheet(f"""
            QWidget {{
                background: {_DARK_BG};
                color: {_TEXT};
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
            }}
            QGroupBox {{
                background: {_DARK_PANEL};
                border: 1px solid #3A3A5A;
                border-radius: 8px;
                margin-top: 10px;
                font-weight: bold;
                font-size: 12px;
                padding: 4px;
                color: {_ACCENT};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }}
            QTableWidget {{
                background: {_DARK_CARD};
                alternate-background-color: #23233A;
                gridline-color: #3A3A5A;
                border: none;
                border-radius: 4px;
            }}
            QHeaderView::section {{
                background: #303050;
                color: {_ACCENT};
                font-weight: bold;
                padding: 4px;
                border: none;
                border-right: 1px solid #3A3A5A;
            }}
            QTableWidget::item:selected {{
                background: {_ACCENT}55;
            }}
            QComboBox, QDoubleSpinBox {{
                background: {_DARK_CARD};
                border: 1px solid #4A4A6A;
                border-radius: 4px;
                padding: 3px 6px;
                selection-background-color: {_ACCENT};
            }}
            QComboBox QAbstractItemView {{
                background: {_DARK_CARD};
                selection-background-color: {_ACCENT};
            }}
            QPushButton {{
                background: #303050;
                border: 1px solid #4A4A6A;
                border-radius: 5px;
                padding: 5px 12px;
                color: {_TEXT};
            }}
            QPushButton:hover {{
                background: {_ACCENT};
                color: white;
            }}
            #AccentBtn {{
                background: {_ACCENT};
                color: white;
                font-weight: bold;
                border: none;
            }}
            #AccentBtn:hover {{
                background: #9CA3FF;
            }}
            #RateLbl {{
                color: {_MUTED};
                font-size: 11px;
                padding: 0 8px;
            }}
            QListWidget {{
                background: {_DARK_CARD};
                border: 1px solid #3A3A5A;
                border-radius: 4px;
            }}
            QListWidget::item:selected {{
                background: {_ACCENT}55;
            }}
            QListWidget::item:hover {{
                background: #303050;
            }}
            QScrollBar:vertical {{
                background: {_DARK_CARD};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: #4A4A6A;
                border-radius: 4px;
            }}
        """)
