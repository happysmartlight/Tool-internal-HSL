"""
main.py
Application entry point — integrates 2 tabs:
  Tab 1: Hợp Đồng (from hop_dong_tool.py — unchanged layout/colors)
  Tab 2: Tính Giá Nhập Khẩu (new module)

Strategy for Tab 1:
- Import App and _QSS from hop_dong_tool — they are self-contained.
- Apply _QSS at QApplication level so ALL widgets inherit the same look.
- Build App() as a hidden QMainWindow, then reparent its centralWidget
  into the tab so the full layout and styling are 100% preserved.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QLabel

from ui.import_cost_tab import ImportCostTab
from utils.logger import get_logger

log = get_logger("main")


# ── Build Tab 1 from hop_dong_tool ────────────────────────────
def _build_contract_widget():
    """
    Import hop_dong_tool and return (contract_widget, _QSS).
    The App's centralWidget is extracted and reparented so the
    existing layout / styling / signals are preserved perfectly.
    """
    import hop_dong_tool as hdt

    # Create the App window (it builds the entire UI in __init__)
    app_win = hdt.App()

    # Extract and reparent the central widget.
    # The central widget owns all the child widgets + layouts.
    central = app_win.centralWidget()

    # Keep a reference so the original App window (and its signals,
    # threads, etc.) are not garbage-collected while the tab is alive.
    central._hop_dong_window = app_win

    return central, hdt._QSS


# ── Main Window ───────────────────────────────────────────────
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Happy Smart Light — Bộ công cụ v2.3.0")
        self.resize(1280, 900)
        self.setMinimumSize(900, 680)

        logo_path = Path(__file__).parent / "logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setTabPosition(QTabWidget.TabPosition.North)

        # ── Tab 1 ──────────────────────────────────────────
        try:
            contract_widget, _ = _build_contract_widget()
            tabs.addTab(contract_widget, "📄  Hợp Đồng")

            # ── Migrate menubar from hidden App window ──────
            hidden_win = contract_widget._hop_dong_window
            src_mb = hidden_win.menuBar()
            dst_mb = self.menuBar()
            dst_mb.setStyleSheet("""
                QMenuBar {
                    background: #0a0a14;
                    color: #e8e8ff;
                    font-size: 12px;
                    border-bottom: 1px solid #1e1e38;
                }
                QMenuBar::item { padding: 4px 12px; }
                QMenuBar::item:selected {
                    background: #00c8f022;
                    color: #00c8f0;
                    border-radius: 4px;
                }
                QMenu {
                    background: #111120;
                    color: #e8e8ff;
                    border: 1px solid #1e1e38;
                }
                QMenu::item { padding: 6px 24px; }
                QMenu::item:selected {
                    background: #00c8f022;
                    color: #00c8f0;
                }
                QMenu::separator { height: 1px; background: #1e1e38; margin: 2px 0; }
            """)
            for action in src_mb.actions():
                menu = action.menu()
                if menu:
                    new_menu = dst_mb.addMenu(action.text())
                    for a in menu.actions():
                        if a.isSeparator():
                            new_menu.addSeparator()
                        else:
                            new_action = new_menu.addAction(a.text())
                            # Re-bind logic for exit since it shouldn't close the hidden window
                            if "Thoát" in a.text():
                                new_action.triggered.connect(self.close)
                            else:
                                # Re-use the existing slot logic for About dialog
                                new_action.triggered.connect(a.trigger)
                else:
                    dst_mb.addAction(action)
            log.info("Contract Tool tab and menubar loaded OK")
        except Exception as e:
            log.exception("Failed to load Contract Tool: %s", e)
            err = QLabel(f"⚠️  Lỗi tải Hợp Đồng tab:\n{e}")
            err.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tabs.addTab(err, "📄  Hợp Đồng")

        # ── Tab 2 ──────────────────────────────────────────
        import_tab = ImportCostTab()
        tabs.addTab(import_tab, "🛒  Tính Giá Nhập Khẩu")

        # Tab bar style — matches hop_dong_tool's dark palette
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
            }
            QTabBar::tab {
                background: #18181F;
                color: #888899;
                border: none;
                border-bottom: 2px solid transparent;
                padding: 10px 28px;
                font-size: 13px;
                font-weight: 600;
                min-width: 180px;
            }
            QTabBar::tab:selected {
                color: #00D4FF;
                border-bottom: 2px solid #00D4FF;
                background: #0E0E14;
            }
            QTabBar::tab:hover:!selected {
                color: #CCCCFF;
                background: #1E1E28;
            }
        """)

        self.setCentralWidget(tabs)


# ── Entry point ───────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Happy Smart Light")
    app.setOrganizationName("HSL")
    app.setStyle("Fusion")

    # Apply hop_dong_tool's global stylesheet so Tab 1 looks identical
    try:
        import hop_dong_tool as hdt
        app.setStyleSheet(hdt._QSS)
    except Exception as e:
        log.warning("Could not load _QSS from hop_dong_tool: %s", e)

    win = MainWindow()
    win.show()
    log.info("Application started")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
