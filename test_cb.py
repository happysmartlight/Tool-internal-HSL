import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QComboBox, QLineEdit, QLabel

app = QApplication(sys.argv)
app.setStyleSheet("""
QWidget { background: #0a0a14; color: white; font-size: 14px; }
QComboBox {
    background: #16162a; border:1px solid #00c8f0;
    padding: 6px; border-radius: 6px;
}
/* The FIX for Windows QComboBox dropdown transparency */
QComboBox QAbstractItemView {
    background: #0d0d1a;
    background-color: #0d0d1a;
    border: 1px solid #00c8f0;
    selection-background-color: #00c8f0;
    outline: none;
}
QComboBox QAbstractItemView::item {
    background: #0d0d1a;
    background-color: #0d0d1a;
    padding: 6px;
    min-height: 24px;
}
QComboBox QAbstractItemView::item:selected {
    background: #00c8f0;
    background-color: #00c8f0;
    color: black;
}
""")

w = QWidget()
l = QVBoxLayout(w)
cb = QComboBox()
cb.addItems(["50%", "70%", "100%"])
l.addWidget(cb)
l.addWidget(QLabel("17/03/2026 - This text should be hidden behind popup"))
w.show()

def run_and_capture():
    import time
    # show it, open combobox, screenshot
    cb.showPopup()
    time.sleep(1)
    # screenshot
    p = w.grab()
    p.save("test_screenshot2.png")
    app.quit()

import threading
threading.Timer(1.0, run_and_capture).start()
sys.exit(app.exec())
