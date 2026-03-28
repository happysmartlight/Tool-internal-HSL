"""
ui/domestic_price_tab.py
Domestic Product Price Calculator tab — pure VND, no exchange rates.

Palette mirrors import_cost_tab.py (dark neon cyberpunk).

Table layout: frozen panel (STT, Tên SP, ĐVT, SL) + scrollable panel
(all remaining columns). Both panels share vertical scroll and row heights.
"""
import json
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QEvent, QObject
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QSplitter, QStyledItemDelegate, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from database import db_handler
from models.domestic_product import (
    DomesticBreakdown, DomesticCostConfig, DomesticOrder, DomesticProduct,
)
from services import domestic_calculator_service
from utils import domestic_excel_exporter, domestic_doc_exporter
from utils.logger import get_logger

log = get_logger(__name__)

# ── Palette ───────────────────────────────────────────────────
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
_PURPLE = "#a855f7"

# ── Column indices (unified, 0-based) ─────────────────────────
COL_STT      = 0
COL_NAME     = 1
COL_UNIT     = 2
COL_QTY      = 3
# --- boundary: cols 0-3 go to tbl_frozen; 4-14 go to tbl_scroll ---
COL_PRICE    = 4
COL_SHIP     = 5
COL_OTHER    = 6
COL_DISC_PCT = 7
COL_DISC_VND = 8
COL_MARGIN   = 9
COL_COST     = 10  # read-only
COL_SELL_BV  = 11  # read-only
COL_SELL_AV  = 12  # read-only
COL_TOTAL    = 13  # read-only
COL_DEL      = 14

_FROZEN_NCOLS  = 4           # 0-3
_SCROLL_OFFSET = _FROZEN_NCOLS
_SCROLL_NCOLS  = 11          # 4-14 → local 0-10

_FROZEN_HEADERS = ["STT", "Tên sản phẩm", "ĐVT", "SL"]
_SCROLL_HEADERS = [
    "Giá mua (₫)", "Ship/đv (₫)", "CP khác/đv (₫)",
    "CK%", "CK (₫)", "Biên LN%",
    "Giá vốn/đv (₫)", "Bán (chưa VAT) ₫", "Bán (có VAT) ₫",
    "Tổng bán (₫)", "",
]

_READONLY_ORIG = (COL_COST, COL_SELL_BV, COL_SELL_AV, COL_TOTAL)


def _sc(orig_col: int) -> int:
    """Map original column index → local index in tbl_scroll."""
    return orig_col - _SCROLL_OFFSET


# ── Number parser ─────────────────────────────────────────────
def _parse_num(text: str, fallback: float = 0.0) -> float:
    """Parse a number string that may contain dot/comma thousands separators.

    Rules:
    - "1.000.000"  → 1000000  (all parts after dots are exactly 3 digits)
    - "1,000,000"  → 1000000  (all parts after commas are exactly 3 digits)
    - "40.5"       → 40.5     (last dot part is NOT 3 digits → decimal)
    - "1000000"    → 1000000  (plain integer)
    """
    s = text.strip().replace(" ", "")
    if not s:
        return fallback

    parts_dot = s.split(".")
    if len(parts_dot) > 1 and all(len(p) == 3 for p in parts_dot[1:]):
        s = s.replace(".", "")
    elif "," in s:
        parts_com = s.split(",")
        if len(parts_com) > 1 and all(len(p) == 3 for p in parts_com[1:]):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")

    try:
        return float(s) if s else fallback
    except ValueError:
        return fallback


# ── Numeric delegate: display with thousands separator ────────
class _MoneyDelegate(QStyledItemDelegate):
    def displayText(self, value, locale):          # noqa: N802
        try:
            n = float(str(value).replace(".", "").replace(",", "") or 0)
            return f"{int(n):,}".replace(",", ".")
        except (ValueError, TypeError):
            return str(value)

    def createEditor(self, parent, option, index):
        ed = QLineEdit(parent)
        ed.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        ed.setStyleSheet(
            f"background:{_ACCENT}; color:{_TEXT}; border:1px solid {_CYAN};"
            " border-radius:3px; padding:2px 6px; font-size:12px;"
        )
        return ed

    def setEditorData(self, editor, index):        # noqa: N802
        raw = index.data(Qt.ItemDataRole.DisplayRole) or "0"
        clean = str(raw).replace(".", "").replace(",", "")
        editor.setText(clean)
        editor.selectAll()

    def setModelData(self, editor, model, index):  # noqa: N802
        text = editor.text().strip().replace(".", "").replace(",", "")
        try:
            float(text or "0")
            model.setData(index, text or "0", Qt.ItemDataRole.EditRole)
        except ValueError:
            pass


class _PctDelegate(QStyledItemDelegate):
    def displayText(self, value, locale):          # noqa: N802
        try:
            n = float(str(value).replace(",", ".") or 0)
            return f"{n:.1f}"
        except (ValueError, TypeError):
            return str(value)

    def createEditor(self, parent, option, index):
        ed = QLineEdit(parent)
        ed.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        ed.setStyleSheet(
            f"background:{_ACCENT}; color:{_TEXT}; border:1px solid {_CYAN};"
            " border-radius:3px; padding:2px 6px; font-size:12px;"
        )
        return ed

    def setEditorData(self, editor, index):        # noqa: N802
        raw = index.data(Qt.ItemDataRole.DisplayRole) or "0"
        editor.setText(str(raw).replace(",", "."))
        editor.selectAll()

    def setModelData(self, editor, model, index):  # noqa: N802
        text = editor.text().strip().replace(",", ".")
        try:
            float(text or "0")
            model.setData(index, text or "0", Qt.ItemDataRole.EditRole)
        except ValueError:
            pass


# ── Shift+Wheel → horizontal scroll ──────────────────────────
class _HWheelFilter(QObject):
    """Intercept Shift+Wheel on a table viewport → scroll horizontally."""

    def __init__(self, table, parent=None):
        super().__init__(parent)
        self._table = table

    def eventFilter(self, obj, event):        # noqa: N802
        if event.type() == QEvent.Type.Wheel:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                bar = self._table.horizontalScrollBar()
                bar.setValue(bar.value() - event.angleDelta().y() // 3)
                return True
        return False


# ── Reusable stat card ────────────────────────────────────────
class _StatCard(QFrame):
    def __init__(self, label: str, accent: str, parent=None):
        super().__init__(parent)
        self._accent = accent
        self.setFixedHeight(72)
        self.setStyleSheet(f"""
            QFrame {{
                background: {_CARD};
                border: 1px solid {accent};
                border-radius: 8px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(2)

        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(f"color:{_DIM}; font-size:10px; border:none;")
        lay.addWidget(self._lbl)

        self._val = QLabel("—")
        self._val.setStyleSheet(f"color:{accent}; font-size:15px; font-weight:bold; border:none;")
        lay.addWidget(self._val)

    def set_value(self, vnd: float):
        self._val.setText(f"{vnd:,.0f} ₫".replace(",", "."))

    def set_pct(self, pct: float):
        self._val.setText(f"{pct:.1f} %")

    def clear(self):
        self._val.setText("—")


# ── Main tab widget ───────────────────────────────────────────
class DomesticPriceTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        db_handler.init_domestic_db()
        self._blocking_signals = False
        self._syncing_scroll   = False     # prevent scroll signal loops
        self._breakdown: DomesticBreakdown | None = None
        self._history_ids: list[int] = []
        self._build_ui()
        self._apply_style()
        self._refresh_history()

    # ── UI construction ───────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(8)
        left_lay.addWidget(self._build_settings_panel())
        left_lay.addWidget(self._build_product_panel(), stretch=1)

        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(8)
        right_lay.addWidget(self._build_results_panel(), stretch=2)
        right_lay.addWidget(self._build_history_panel(), stretch=1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([720, 440])
        root.addWidget(splitter)

    def _build_settings_panel(self) -> QGroupBox:
        grp = self._group("⚙️  Cài đặt chi phí")
        form = QFormLayout()
        form.setSpacing(8)
        form.setContentsMargins(10, 14, 10, 10)

        def spin(mn, mx, dec, suffix, val) -> QDoubleSpinBox:
            s = QDoubleSpinBox()
            s.setRange(mn, mx)
            s.setDecimals(dec)
            s.setSuffix(suffix)
            s.setValue(val)
            s.setGroupSeparatorShown(True)
            return s

        self.spin_vat      = spin(0, 100, 1, " %", 10.0)
        self.spin_shipping = spin(0, 500_000_000, 0, " ₫", 0.0)
        self.spin_other    = spin(0, 500_000_000, 0, " ₫", 0.0)
        self.spin_margin   = spin(0, 99.9, 1, " %", 40.0)

        form.addRow("VAT bán ra:", self.spin_vat)
        form.addRow("Phí ship tổng:", self.spin_shipping)
        form.addRow("CP cố định khác:", self.spin_other)
        form.addRow("Biên LN mặc định:", self.spin_margin)

        btn_reset = QPushButton("Reset mặc định")
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.clicked.connect(self._reset_settings)
        form.addRow("", btn_reset)

        grp.setLayout(form)
        grp.setFixedHeight(220)

        for sp in (self.spin_vat, self.spin_shipping, self.spin_other, self.spin_margin):
            sp.valueChanged.connect(self._recalculate)

        return grp

    def _build_product_panel(self) -> QGroupBox:
        grp = self._group("📦  Danh sách sản phẩm")
        lay = QVBoxLayout()
        lay.setContentsMargins(8, 14, 8, 8)
        lay.setSpacing(6)

        # ── Top row: add button + hint ─────────────────────────
        btn_add = QPushButton("➕  Thêm sản phẩm")
        btn_add.setObjectName("primary")
        btn_add.setFixedHeight(32)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.clicked.connect(self._add_product_row)

        lbl_hint = QLabel("⌨  Shift + cuộn chuột để kéo bảng ngang")
        lbl_hint.setStyleSheet(
            f"color:{_DIM}; font-size:10px; font-style:italic; border:none; background:transparent;"
        )

        top_row = QHBoxLayout()
        top_row.setSpacing(0)
        top_row.addWidget(btn_add, alignment=Qt.AlignmentFlag.AlignVCenter)
        top_row.addStretch()
        top_row.addWidget(lbl_hint, alignment=Qt.AlignmentFlag.AlignVCenter)
        lay.addLayout(top_row)

        # ── Table area: frozen + scroll side by side ───────────
        tbl_area = QHBoxLayout()
        tbl_area.setContentsMargins(0, 0, 0, 0)
        tbl_area.setSpacing(0)

        # Frozen table (cols 0-3)
        self.tbl_frozen = QTableWidget(0, _FROZEN_NCOLS)
        self.tbl_frozen.setHorizontalHeaderLabels(_FROZEN_HEADERS)
        self._setup_table_common(self.tbl_frozen, frozen=True)

        fhdr = self.tbl_frozen.horizontalHeader()
        fhdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # STT
        fhdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)        # Name
        fhdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Unit
        fhdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Qty
        self.tbl_frozen.setColumnWidth(1, 160)
        self.tbl_frozen.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tbl_frozen.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Fixed width: will be computed after show; set a reasonable default
        self.tbl_frozen.setFixedWidth(310)

        # Scrollable table (cols 4-14 → local 0-10)
        self.tbl = QTableWidget(0, _SCROLL_NCOLS)
        self.tbl.setHorizontalHeaderLabels(_SCROLL_HEADERS)
        self._setup_table_common(self.tbl, frozen=False)

        shdr = self.tbl.horizontalHeader()
        shdr.setMinimumSectionSize(50)
        for c, w in {
            _sc(COL_PRICE):   115, _sc(COL_SHIP):   90, _sc(COL_OTHER):   90,
            _sc(COL_DISC_VND): 90, _sc(COL_COST):  115, _sc(COL_SELL_BV): 115,
            _sc(COL_SELL_AV): 115, _sc(COL_TOTAL): 120,
        }.items():
            shdr.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
            self.tbl.setColumnWidth(c, w)
        for c in (_sc(COL_DISC_PCT), _sc(COL_MARGIN)):
            shdr.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.tbl.setColumnWidth(c, 80)
        shdr.setSectionResizeMode(_sc(COL_DEL), QHeaderView.ResizeMode.Fixed)
        self.tbl.setColumnWidth(_sc(COL_DEL), 46)

        self.tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tbl.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)

        # Shift+Wheel → horizontal scroll
        self._h_wheel_filter = _HWheelFilter(self.tbl)
        self.tbl.viewport().installEventFilter(self._h_wheel_filter)

        # Money delegates on scroll table
        money_del = _MoneyDelegate(self.tbl)
        for c in (_sc(COL_PRICE), _sc(COL_SHIP), _sc(COL_OTHER), _sc(COL_DISC_VND),
                  _sc(COL_COST), _sc(COL_SELL_BV), _sc(COL_SELL_AV), _sc(COL_TOTAL)):
            self.tbl.setItemDelegateForColumn(c, money_del)

        # ── Sync vertical scroll ───────────────────────────────
        self.tbl_frozen.verticalScrollBar().valueChanged.connect(self._sync_from_frozen)
        self.tbl.verticalScrollBar().valueChanged.connect(self._sync_from_scroll)

        # ── Connect changed signals ────────────────────────────
        self.tbl_frozen.itemChanged.connect(self._on_frozen_changed)
        self.tbl.itemChanged.connect(self._on_scroll_changed)

        tbl_area.addWidget(self.tbl_frozen)
        tbl_area.addWidget(self.tbl, stretch=1)
        lay.addLayout(tbl_area)

        grp.setLayout(lay)
        return grp

    def _setup_table_common(self, tbl: QTableWidget, *, frozen: bool):
        tbl.setAlternatingRowColors(True)
        tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(
            QTableWidget.EditTrigger.CurrentChanged |
            QTableWidget.EditTrigger.AnyKeyPressed |
            QTableWidget.EditTrigger.DoubleClicked
        )
        if frozen:
            # Frozen table: no editing on STT (col 0), rest editable
            pass
        tbl.horizontalHeader().setMinimumSectionSize(50)

    def _build_results_panel(self) -> QGroupBox:
        grp = self._group("📊  Kết quả tổng hợp")
        lay = QVBoxLayout()
        lay.setContentsMargins(10, 14, 10, 10)
        lay.setSpacing(8)

        self.card_cost    = _StatCard("Tổng giá vốn",        _WARN)
        self.card_revenue = _StatCard("Doanh thu (có VAT)",  _CYAN)
        self.card_profit  = _StatCard("Lợi nhuận",           _GREEN)
        self.card_margin  = _StatCard("Biên LN trung bình",  _PURPLE)

        cards_row = QHBoxLayout()
        for c in (self.card_cost, self.card_revenue, self.card_profit, self.card_margin):
            cards_row.addWidget(c)
        lay.addLayout(cards_row)

        self.tbl_bd = QTableWidget(0, 2)
        self.tbl_bd.setHorizontalHeaderLabels(["Khoản mục", "Giá trị (₫)"])
        self.tbl_bd.verticalHeader().setVisible(False)
        self.tbl_bd.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_bd.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.tbl_bd.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.tbl_bd.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_bd.setFixedHeight(180)
        lay.addWidget(self.tbl_bd)

        btn_row = QHBoxLayout()
        btn_excel = QPushButton("📊  Xuất Excel")
        btn_word  = QPushButton("📄  Xuất Báo giá (Word)")
        btn_save  = QPushButton("💾  Lưu lịch sử")
        btn_excel.setObjectName("primary")
        btn_excel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_word.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_excel.clicked.connect(self._export_excel)
        btn_word.clicked.connect(self._export_word)
        btn_save.clicked.connect(self._save_to_history)
        for b in (btn_excel, btn_word, btn_save):
            btn_row.addWidget(b)
        lay.addLayout(btn_row)

        grp.setLayout(lay)
        return grp

    def _build_history_panel(self) -> QGroupBox:
        grp = self._group("🕘  Lịch sử tính toán")
        lay = QVBoxLayout()
        lay.setContentsMargins(8, 14, 8, 8)
        lay.setSpacing(6)

        self.lst_history = QListWidget()
        self.lst_history.setFixedHeight(110)
        self.lst_history.itemDoubleClicked.connect(self._load_history)
        lay.addWidget(self.lst_history)

        btn_row = QHBoxLayout()
        btn_refresh = QPushButton("🔄  Làm mới")
        btn_delete  = QPushButton("🗑  Xóa")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.clicked.connect(self._refresh_history)
        btn_delete.clicked.connect(self._delete_history)
        btn_row.addWidget(btn_refresh)
        btn_row.addWidget(btn_delete)
        lay.addLayout(btn_row)

        grp.setLayout(lay)
        return grp

    # ── Scroll sync ───────────────────────────────────────────
    def _sync_from_frozen(self, val: int):
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        self.tbl.verticalScrollBar().setValue(val)
        self._syncing_scroll = False

    def _sync_from_scroll(self, val: int):
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        self.tbl_frozen.verticalScrollBar().setValue(val)
        self._syncing_scroll = False

    def _sync_row_heights(self):
        """Copy row heights from scroll table to frozen table."""
        for r in range(self.tbl.rowCount()):
            h = self.tbl.rowHeight(r)
            self.tbl_frozen.setRowHeight(r, h)

    # ── Product table helpers ─────────────────────────────────
    def _make_pct_spin(self, value: float, row_ref: list) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(0.0, 99.9)
        sp.setDecimals(1)
        sp.setSuffix(" %")
        sp.setValue(value)
        sp.setFrame(False)
        sp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sp.setStyleSheet(f"""
            QDoubleSpinBox {{
                background: transparent;
                color: {_TEXT};
                border: none;
                font-size: 12px;
            }}
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                background: {_BORDER};
                border: none;
                width: 14px;
            }}
        """)
        sp.valueChanged.connect(lambda val: self._on_pct_spin_changed(row_ref))
        return sp

    def _on_pct_spin_changed(self, row_ref: list):
        if self._blocking_signals:
            return
        r = row_ref[0]
        self._update_row_computed(r)
        self._recalculate()

    def _add_product_row(self):
        self._blocking_signals = True
        r = self.tbl.rowCount()

        # --- frozen table ---
        self.tbl_frozen.insertRow(r)

        def _fitem(val="", readonly=False,
                   align=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter):
            it = QTableWidgetItem(str(val))
            it.setTextAlignment(align)
            if readonly:
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                it.setForeground(QColor(_DIM))
            return it

        self.tbl_frozen.setItem(r, 0, _fitem(r + 1, readonly=True))  # STT
        self.tbl_frozen.setItem(r, 1, _fitem(
            "Sản phẩm",
            align=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft))  # Name
        self.tbl_frozen.setItem(r, 2, _fitem("cái"))    # Unit
        self.tbl_frozen.setItem(r, 3, _fitem("1"))      # Qty

        # --- scroll table ---
        self.tbl.insertRow(r)

        def _sitem(val="", readonly=False,
                   align=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight):
            it = QTableWidgetItem(str(val))
            it.setTextAlignment(align)
            if readonly:
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                it.setForeground(QColor(_DIM))
            return it

        self.tbl.setItem(r, _sc(COL_PRICE),    _sitem("0"))
        self.tbl.setItem(r, _sc(COL_SHIP),     _sitem("0"))
        self.tbl.setItem(r, _sc(COL_OTHER),    _sitem("0"))
        self.tbl.setItem(r, _sc(COL_DISC_VND), _sitem("0"))
        for c in (_sc(COL_COST), _sc(COL_SELL_BV), _sc(COL_SELL_AV), _sc(COL_TOTAL)):
            self.tbl.setItem(r, c, _sitem("0", readonly=True))

        # CK% spinbox
        row_ref_ck = [r]
        sp_ck = self._make_pct_spin(0.0, row_ref_ck)
        ph_ck = QTableWidgetItem("")
        ph_ck.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.tbl.setItem(r, _sc(COL_DISC_PCT), ph_ck)
        self.tbl.setCellWidget(r, _sc(COL_DISC_PCT), sp_ck)

        # Biên LN% spinbox
        row_ref_mg = [r]
        sp_mg = self._make_pct_spin(self.spin_margin.value(), row_ref_mg)
        ph_mg = QTableWidgetItem("")
        ph_mg.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self.tbl.setItem(r, _sc(COL_MARGIN), ph_mg)
        self.tbl.setCellWidget(r, _sc(COL_MARGIN), sp_mg)

        # Delete button in centered container
        btn_del = QPushButton("🗑")
        btn_del.setFixedSize(32, 32)
        btn_del.setStyleSheet(
            f"color:{_PINK}; font-size:16px; font-weight:bold;"
            " border:none; background:transparent; padding:0;"
        )
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.clicked.connect(lambda _, row=r: self._remove_row(row))
        _ctn = QWidget()
        _ctn_lay = QHBoxLayout(_ctn)
        _ctn_lay.setContentsMargins(0, 0, 0, 0)
        _ctn_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _ctn_lay.addWidget(btn_del)
        self.tbl.setCellWidget(r, _sc(COL_DEL), _ctn)

        self._blocking_signals = False
        self._sync_row_heights()
        self._recalculate()

    def _remove_row(self, row: int):
        self.tbl_frozen.removeRow(row)
        self.tbl.removeRow(row)
        self._renumber_rows()
        self._rebind_delete_buttons()
        self._sync_row_heights()
        self._recalculate()

    def _renumber_rows(self):
        self._blocking_signals = True
        for r in range(self.tbl_frozen.rowCount()):
            item = self.tbl_frozen.item(r, 0)
            if item:
                item.setText(str(r + 1))
            else:
                it = QTableWidgetItem(str(r + 1))
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                it.setForeground(QColor(_DIM))
                self.tbl_frozen.setItem(r, 0, it)
        self._blocking_signals = False

    def _rebind_delete_buttons(self):
        for r in range(self.tbl.rowCount()):
            w_del = self.tbl.cellWidget(r, _sc(COL_DEL))
            if w_del:
                btn = (w_del if isinstance(w_del, QPushButton)
                       else w_del.findChild(QPushButton))
                if btn:
                    try:
                        btn.clicked.disconnect()
                    except Exception:
                        pass
                    btn.clicked.connect(lambda _, row=r: self._remove_row(row))

            for lc in (_sc(COL_DISC_PCT), _sc(COL_MARGIN)):
                w_sp = self.tbl.cellWidget(r, lc)
                if isinstance(w_sp, QDoubleSpinBox):
                    try:
                        w_sp.valueChanged.disconnect()
                    except Exception:
                        pass
                    row_ref = [r]
                    w_sp.valueChanged.connect(lambda val, ref=row_ref: self._on_pct_spin_changed(ref))

    def _on_frozen_changed(self, item):
        """Handle edits in the frozen table (Name/Unit/Qty)."""
        if self._blocking_signals:
            return
        # Only QTY changes affect computed values
        if item and item.column() == 3:  # COL_QTY → frozen local col 3
            self._update_row_computed(item.row())
        self._recalculate()

    def _on_scroll_changed(self, item):
        """Handle edits in the scroll table (Price, Ship, Other, …)."""
        if self._blocking_signals:
            return
        editable_local = {_sc(COL_PRICE), _sc(COL_SHIP), _sc(COL_OTHER), _sc(COL_DISC_VND)}
        if item and item.column() in editable_local:
            self._update_row_computed(item.row())
        self._recalculate()

    def _update_row_computed(self, r: int):
        """Instant per-row update of read-only computed cells in scroll table."""
        def _fval(local_col, fallback=0.0):
            it = self.tbl_frozen.item(r, local_col)
            return _parse_num(it.text(), fallback) if it else fallback

        def _sval(orig_col, fallback=0.0):
            lc = _sc(orig_col)
            w = self.tbl.cellWidget(r, lc)
            if isinstance(w, QDoubleSpinBox):
                return w.value()
            it = self.tbl.item(r, lc)
            return _parse_num(it.text(), fallback) if it else fallback

        qty      = max(_fval(3, 1), 0.001)   # frozen col 3 = QTY
        price    = _sval(COL_PRICE)
        ship     = _sval(COL_SHIP)
        other    = _sval(COL_OTHER)
        disc_pct = _sval(COL_DISC_PCT)
        disc_vnd = _sval(COL_DISC_VND)
        margin   = _sval(COL_MARGIN, 40.0)
        vat      = self.spin_vat.value()

        discount_per_unit = disc_vnd + (price * disc_pct / 100)
        unit_cost = max(price + ship + other - discount_per_unit, 0)

        if 0 < margin < 100:
            sell_bv = unit_cost / (1 - margin / 100)
        else:
            sell_bv = unit_cost * 2
        sell_av = sell_bv * (1 + vat / 100)
        total   = sell_av * qty

        self._blocking_signals = True
        for orig_col, val in (
            (COL_COST, unit_cost), (COL_SELL_BV, sell_bv),
            (COL_SELL_AV, sell_av), (COL_TOTAL, total),
        ):
            it = self.tbl.item(r, _sc(orig_col))
            if it:
                it.setText(str(int(round(val))))
        self._blocking_signals = False

    # ── Data extraction ───────────────────────────────────────
    def _get_order(self) -> DomesticOrder:
        products = []
        for r in range(self.tbl.rowCount()):
            def _ftxt(local_col, fb=""):
                it = self.tbl_frozen.item(r, local_col)
                return it.text().strip() if it else fb

            def _snum(orig_col, fb=0.0):
                lc = _sc(orig_col)
                w = self.tbl.cellWidget(r, lc)
                if isinstance(w, QDoubleSpinBox):
                    return w.value()
                it = self.tbl.item(r, lc)
                return _parse_num(it.text() if it else "0", fb)

            p = DomesticProduct(
                name=_ftxt(1, ""),
                unit=_ftxt(2, "cái"),
                qty=max(_parse_num(_ftxt(3, "1"), 1), 0.001),
                purchase_price_vnd=_snum(COL_PRICE),
                shipping_per_unit_vnd=_snum(COL_SHIP),
                other_cost_per_unit_vnd=_snum(COL_OTHER),
                discount_pct=_snum(COL_DISC_PCT),
                discount_vnd=_snum(COL_DISC_VND),
                margin_pct=_snum(COL_MARGIN, self.spin_margin.value()),
            )
            products.append(p)
        return DomesticOrder(products=products)

    def _get_config(self) -> DomesticCostConfig:
        return DomesticCostConfig(
            vat_on_sale_pct=self.spin_vat.value(),
            shipping_total_vnd=self.spin_shipping.value(),
            other_fixed_costs_vnd=self.spin_other.value(),
            default_margin_pct=self.spin_margin.value(),
        )

    # ── Calculation ───────────────────────────────────────────
    def _recalculate(self):
        order  = self._get_order()
        config = self._get_config()
        if not order.products or all(p.purchase_price_vnd == 0 for p in order.products):
            self._breakdown = None
            self._clear_results()
            return
        self._breakdown = domestic_calculator_service.calculate(order, config)
        self._update_results(self._breakdown)

    def _clear_results(self):
        for card in (self.card_cost, self.card_revenue, self.card_profit, self.card_margin):
            card.clear()
        self.tbl_bd.setRowCount(0)

    def _update_results(self, bd: DomesticBreakdown):
        self.card_cost.set_value(bd.total_cost_vnd)
        self.card_revenue.set_value(bd.total_revenue_with_vat)
        self.card_profit.set_value(bd.total_profit_vnd)
        self.card_margin.set_pct(bd.avg_margin_pct)

        rows = [
            ("Tổng giá mua vào", bd.total_cost_vnd - sum(
                l.allocated_ship_vnd * l.qty + l.allocated_other_vnd * l.qty
                for l in bd.lines
            ) + sum(l.discount_applied_vnd * l.qty for l in bd.lines),
             _TEXT, False),
            ("Phí vận chuyển phân bổ", sum(l.allocated_ship_vnd * l.qty for l in bd.lines), _DIM, False),
            ("Chi phí khác phân bổ",   sum(l.allocated_other_vnd * l.qty for l in bd.lines), _DIM, False),
            ("Chiết khấu",             -sum(l.discount_applied_vnd * l.qty for l in bd.lines), _DIM, False),
            ("─────────────────────",  None, _BORDER, False),
            ("GIÁ VỐN (Tổng)",         bd.total_cost_vnd,              _WARN,   True),
            ("Doanh thu (chưa VAT)",   bd.total_revenue_before_vat,    _CYAN,   False),
            (f"Thuế VAT ({self.spin_vat.value():.0f}%)", bd.vat_amount_vnd, _DIM, False),
            ("Doanh thu (có VAT)",     bd.total_revenue_with_vat,      _CYAN,   True),
            ("─────────────────────",  None, _BORDER, False),
            ("Lợi nhuận",              bd.total_profit_vnd,            _GREEN,  True),
            ("Biên LN trung bình",     None,                           _PURPLE, True),
        ]

        self.tbl_bd.setRowCount(len(rows))
        for i, (label, value, color, bold) in enumerate(rows):
            lbl_item = QTableWidgetItem(label)
            lbl_item.setForeground(QColor(color))
            if bold:
                f = QFont()
                f.setBold(True)
                lbl_item.setFont(f)
            self.tbl_bd.setItem(i, 0, lbl_item)

            if value is None and label.startswith("Biên"):
                val_item = QTableWidgetItem(f"{bd.avg_margin_pct:.1f} %")
            elif value is None:
                val_item = QTableWidgetItem("")
            else:
                val_item = QTableWidgetItem(f"{value:,.0f} ₫".replace(",", "."))

            val_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val_item.setForeground(QColor(color))
            if bold:
                f = QFont()
                f.setBold(True)
                val_item.setFont(f)
            self.tbl_bd.setItem(i, 1, val_item)

    # ── Export ────────────────────────────────────────────────
    def _export_excel(self):
        if not self._breakdown:
            QMessageBox.warning(self, "Chưa có dữ liệu", "Vui lòng nhập sản phẩm trước.")
            return
        default = f"baogianoidia_{datetime.now():%Y%m%d_%H%M}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu Excel", default, "Excel Files (*.xlsx)")
        if not path:
            return
        try:
            domestic_excel_exporter.export(
                self._breakdown, self._get_config(), Path(path))
            QMessageBox.information(self, "Thành công", f"Đã xuất Excel:\n{path}")
        except Exception as e:
            log.exception("Excel export error")
            QMessageBox.critical(self, "Lỗi", str(e))

    def _export_word(self):
        if not self._breakdown:
            QMessageBox.warning(self, "Chưa có dữ liệu", "Vui lòng nhập sản phẩm trước.")
            return
        customer, ok = QInputDialog.getText(
            self, "Tên khách hàng", "Nhập tên khách hàng:",
            text="Quý Khách Hàng")
        if not ok:
            return
        default = f"BaoGia_NoiDia_HappySmartLight_{datetime.now():%Y%m%d_%H%M}.docx"
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu Word", default, "Word Files (*.docx)")
        if not path:
            return
        try:
            domestic_doc_exporter.export_domestic_quotation(
                self._breakdown, Path(path), customer or "Quý Khách Hàng")
            QMessageBox.information(self, "Thành công", f"Đã xuất báo giá:\n{path}")
        except Exception as e:
            log.exception("Word export error")
            QMessageBox.critical(self, "Lỗi", str(e))

    # ── History ───────────────────────────────────────────────
    def _save_to_history(self):
        if not self._breakdown:
            QMessageBox.warning(self, "Chưa có dữ liệu", "Vui lòng nhập sản phẩm trước.")
            return
        order  = self._get_order()
        config = self._get_config()
        n = len(order.products)
        total = self._breakdown.total_revenue_with_vat
        label = (f"Nội địa — {n} SP — "
                 f"{total:,.0f}₫ — "
                 f"{datetime.now().strftime('%d/%m/%Y %H:%M')}")
        products_list = [
            {
                "name": p.name, "unit": p.unit, "qty": p.qty,
                "purchase_price_vnd": p.purchase_price_vnd,
                "shipping_per_unit_vnd": p.shipping_per_unit_vnd,
                "other_cost_per_unit_vnd": p.other_cost_per_unit_vnd,
                "discount_pct": p.discount_pct,
                "discount_vnd": p.discount_vnd,
                "margin_pct": p.margin_pct,
            }
            for p in order.products
        ]
        config_dict = {
            "vat_on_sale_pct": config.vat_on_sale_pct,
            "shipping_total_vnd": config.shipping_total_vnd,
            "other_fixed_costs_vnd": config.other_fixed_costs_vnd,
            "default_margin_pct": config.default_margin_pct,
        }
        result_dict = domestic_calculator_service.breakdown_to_dict(self._breakdown)
        try:
            db_handler.save_domestic_calculation(label, products_list, config_dict, result_dict)
            self._refresh_history()
            QMessageBox.information(self, "Đã lưu", "Đã lưu vào lịch sử.")
        except Exception as e:
            log.exception("Save history error")
            QMessageBox.critical(self, "Lỗi", str(e))

    def _refresh_history(self):
        self.lst_history.clear()
        self._history_ids = []
        rows = db_handler.list_domestic_calculations(limit=50)
        for row in rows:
            self.lst_history.addItem(QListWidgetItem(row.get("label", f"ID {row['id']}")))
            self._history_ids.append(row["id"])

    def _load_history(self, item: QListWidgetItem):
        idx = self.lst_history.row(item)
        if idx < 0 or idx >= len(self._history_ids):
            return
        calc_id = self._history_ids[idx]
        data = db_handler.get_domestic_calculation(calc_id)
        if not data:
            return
        products = data["products_list"]
        config   = data["config_dict"]

        self._blocking_signals = True
        self.tbl_frozen.setRowCount(0)
        self.tbl.setRowCount(0)

        self.spin_vat.setValue(config.get("vat_on_sale_pct", 10.0))
        self.spin_shipping.setValue(config.get("shipping_total_vnd", 0.0))
        self.spin_other.setValue(config.get("other_fixed_costs_vnd", 0.0))
        self.spin_margin.setValue(config.get("default_margin_pct", 40.0))
        self._blocking_signals = False

        for p in products:
            self._add_product_row()
            r = self.tbl.rowCount() - 1
            self._blocking_signals = True

            def _fset(local_col, val):
                it = self.tbl_frozen.item(r, local_col)
                if it:
                    it.setText(str(val))

            def _sset(orig_col, val):
                lc = _sc(orig_col)
                w = self.tbl.cellWidget(r, lc)
                if isinstance(w, QDoubleSpinBox):
                    w.setValue(float(val))
                    return
                it = self.tbl.item(r, lc)
                if it:
                    it.setText(str(val))

            _fset(1, p.get("name", ""))
            _fset(2, p.get("unit", "cái"))
            _fset(3, p.get("qty", 1))
            _sset(COL_PRICE,    p.get("purchase_price_vnd", 0))
            _sset(COL_SHIP,     p.get("shipping_per_unit_vnd", 0))
            _sset(COL_OTHER,    p.get("other_cost_per_unit_vnd", 0))
            _sset(COL_DISC_PCT, p.get("discount_pct", 0))
            _sset(COL_DISC_VND, p.get("discount_vnd", 0))
            _sset(COL_MARGIN,   p.get("margin_pct", 40.0))
            self._blocking_signals = False

        self._sync_row_heights()
        self._recalculate()

    def _delete_history(self):
        idx = self.lst_history.currentRow()
        if idx < 0 or idx >= len(self._history_ids):
            QMessageBox.warning(self, "Chưa chọn", "Vui lòng chọn mục cần xóa.")
            return
        calc_id = self._history_ids[idx]
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            "Bạn có chắc muốn xóa mục lịch sử này?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            db_handler.delete_domestic_calculation(calc_id)
            self._refresh_history()

    # ── Settings reset ────────────────────────────────────────
    def _reset_settings(self):
        self._blocking_signals = True
        self.spin_vat.setValue(10.0)
        self.spin_shipping.setValue(0.0)
        self.spin_other.setValue(0.0)
        self.spin_margin.setValue(40.0)
        self._blocking_signals = False
        self._recalculate()

    # ── Helpers ───────────────────────────────────────────────
    @staticmethod
    def _group(title: str) -> QGroupBox:
        return QGroupBox(title)

    # ── Style ─────────────────────────────────────────────────
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
            QDoubleSpinBox {{
                background: {_ACCENT};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                padding: 3px 6px;
                color: {_TEXT};
                selection-background-color: {_CYAN}44;
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
            QScrollBar:horizontal {{
                background: {_CARD};
                height: 7px;
                border-radius: 3px;
            }}
            QScrollBar::handle:horizontal {{
                background: {_CYAN}55;
                border-radius: 3px;
                min-width: 20px;
            }}
            QScrollBar::handle:horizontal:hover {{ background: {_CYAN}; }}
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{ width: 0; }}
            QSplitter::handle {{ background: {_BORDER}; }}
        """)
