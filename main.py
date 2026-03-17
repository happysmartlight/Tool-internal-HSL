"""
main.py
Application entry point.
Wraps existing Contract Tool (Tab 1) and new Import Cost Calculator (Tab 2)
inside a QTabWidget.
"""
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from ui.import_cost_tab import ImportCostTab
from utils.logger import get_logger

log = get_logger("main")


def _load_app_widget():
    """Import and return the existing App widget from hop_dong_tool."""
    # We import App here to avoid circular imports during module load
    import importlib
    mod = importlib.import_module("hop_dong_tool")
    return mod.App


class MainWindow(QMainWindow):
    """Top-level window with two tabs."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Happy Smart Light — Bộ công cụ v2.3.0")
        self.resize(1280, 840)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                background: #252535;
                color: #888AAA;
                border: none;
                padding: 10px 24px;
                font-size: 13px;
                font-weight: bold;
                min-width: 180px;
            }
            QTabBar::tab:selected {
                color: #7C83FD;
                border-bottom: 3px solid #7C83FD;
                background: #1E1E2E;
            }
            QTabBar::tab:hover:!selected {
                color: #CCCCFF;
                background: #2A2A3E;
            }
            QTabWidget::pane {
                border: none;
                background: #1E1E2E;
            }
        """)

        # ── Tab 1: Contract Tool ──────────────────────────
        try:
            AppCls = _load_app_widget()
            # App is a QMainWindow; extract its central widget
            _dummy_app_win = AppCls()
            contract_widget = _dummy_app_win.centralWidget()
            if contract_widget is None:
                # Fallback: embed the full window as a widget
                contract_widget = _dummy_app_win
            self.tabs.addTab(contract_widget, "📄  Hợp Đồng")
            log.info("Contract Tool tab loaded OK")
        except Exception as e:
            log.exception("Failed to load Contract Tool tab: %s", e)
            from PyQt6.QtWidgets import QLabel
            err_lbl = QLabel(f"⚠️  Không thể tải tab Hợp Đồng:\n{e}")
            err_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabs.addTab(err_lbl, "📄  Hợp Đồng")

        # ── Tab 2: Import Cost Calculator ─────────────────
        import_tab = ImportCostTab()
        self.tabs.addTab(import_tab, "🛒  Tính Giá Nhập Khẩu")

        self.setCentralWidget(self.tabs)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Happy Smart Light")
    app.setOrganizationName("HSL")
    app.setStyle("Fusion")

    win = MainWindow()
    win.show()
    log.info("Application started")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
