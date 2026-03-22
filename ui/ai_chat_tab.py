from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QComboBox, QLineEdit, QPushButton,
    QTextEdit, QListWidget, QListWidgetItem, QFrame,
    QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import uuid

from utils.security import get_api_key, save_api_key
from utils.database_chat import (
    init_chat_db, get_sessions, get_messages,
    save_session, save_message, update_session_title, delete_session
)
from services.ai_service import call_openai, call_gemini, call_anthropic

# -- Luồng gọi AI chạy ngầm không gây đơ GUI --
class AIWorker(QThread):
    finished = pyqtSignal(str)
    
    def __init__(self, provider, model, api_key, messages, system_context="", parent=None):
        super().__init__(parent)
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.messages = messages
        self.system_context = system_context
        
    def run(self):
        try:
            if self.provider == "OpenAI":
                res = call_openai(self.api_key, self.model, self.messages, self.system_context)
            elif self.provider == "Google Gemini":
                res = call_gemini(self.api_key, self.model, self.messages, self.system_context)
            elif self.provider == "Anthropic Claude":
                res = call_anthropic(self.api_key, self.model, self.messages, self.system_context)
            else:
                res = f"❌ Provider không hỗ trợ: {self.provider}"
            self.finished.emit(res)
        except Exception as e:
            self.finished.emit(f"❌ Lỗi: {str(e)}")

# -- Khung giao diện chính --
class AIChatTab(QWidget):
    def __init__(self):
        super().__init__()
        init_chat_db()
        self.current_session_id = None
        self.messages_context = [] # List of {"role": "...", "content": "..."}
        
        self._build_ui()
        self._load_sessions()
        
    def _build_ui(self):
        main_lay = QHBoxLayout(self)
        main_lay.setContentsMargins(16, 16, 16, 16)
        main_lay.setSpacing(16)
        
        # -- Cột Trái: Sidebar cấu hình và Lịch sử --
        sidebar = QFrame()
        sidebar.setFixedWidth(280)
        sidebar.setObjectName("panel_bg")
        sidebar.setStyleSheet("#panel_bg { background: #161622; border-radius: 8px; }")
        
        slay = QVBoxLayout(sidebar)
        slay.setContentsMargins(12, 12, 12, 12)
        slay.setSpacing(12)
        
        # Cấu hình API
        slay.addWidget(self._lbl("🤖 Chọn Mô hình AI", title=True))
        
        self.cb_provider = QComboBox()
        self.cb_provider.addItems(["Google Gemini", "OpenAI", "Anthropic Claude"])
        self.cb_provider.currentTextChanged.connect(self._on_provider_changed)
        slay.addWidget(self.cb_provider)
        
        self.cb_model = QComboBox()
        # Mặc định Google Gemini
        self.cb_model.addItems(["gemini-1.5-pro", "gemini-1.5-flash", "gemini-pro"])
        slay.addWidget(self.cb_model)
        
        self.inp_api_key = QLineEdit()
        self.inp_api_key.setPlaceholderText("Nhập API Key ở đây...")
        self.inp_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        slay.addWidget(self.inp_api_key)
        
        btn_save_key = QPushButton("Lưu Key An Toàn")
        btn_save_key.clicked.connect(self._save_api_key)
        slay.addWidget(btn_save_key)
        
        # Load API Key cũ nếu có
        self._on_provider_changed(self.cb_provider.currentText())
        
        slay.addSpacing(16)
        
        # System Context (Poor Man's RAG)
        slay.addWidget(self._lbl("🏢 Hồ sơ Công ty (Tuỳ chọn)", title=True))
        self.inp_sys_context = QTextEdit()
        self.inp_sys_context.setPlaceholderText("Nhập thông tin công ty, bảng giá hoặc quy định để AI ghi nhớ làm gốc...")
        self.inp_sys_context.setFixedHeight(120)
        self.inp_sys_context.setStyleSheet("QTextEdit { font-size: 13px; background: #0c0c14; border: 1px solid #1e1e2c; border-radius: 4px; padding: 4px; }")
        slay.addWidget(self.inp_sys_context)
        
        slay.addSpacing(16)
        
        # Lịch sử hội thoại
        hs_row = QHBoxLayout()
        hs_row.addWidget(self._lbl("📝 Lịch sử chat", title=True))
        btn_new = QPushButton("+ Mới")
        btn_new.setFixedWidth(50)
        btn_new.clicked.connect(self._new_session)
        hs_row.addWidget(btn_new)
        slay.addLayout(hs_row)
        
        self.list_sessions = QListWidget()
        self.list_sessions.setStyleSheet("QListWidget { background: #11111a; border-radius: 6px; border: 1px solid #1e1e2c; padding: 4px; }")
        self.list_sessions.itemClicked.connect(self._load_selected_session)
        slay.addWidget(self.list_sessions)
        
        # -- Cột Phải: Chat View --
        chat_area = QFrame()
        chat_area.setObjectName("chat_bg")
        chat_area.setStyleSheet("#chat_bg { background: #11111A; border-radius: 8px; border: 1px solid #1e1e2c; }")
        
        clay = QVBoxLayout(chat_area)
        clay.setContentsMargins(16, 16, 16, 16)
        clay.setSpacing(12)
        
        self.chat_view = QTextEdit()
        self.chat_view.setReadOnly(True)
        self.chat_view.setStyleSheet("QTextEdit { background: transparent; border: none; font-size: 14px; line-height: 1.5; }")
        clay.addWidget(self.chat_view)
        
        # Input area
        inp_lay = QHBoxLayout()
        self.inp_msg = QTextEdit()
        self.inp_msg.setPlaceholderText("Nhập câu hỏi hoặc yêu cầu cho AI... (Shift+Enter để xuống dòng)")
        self.inp_msg.setFixedHeight(70)
        self.inp_msg.setStyleSheet("QTextEdit { font-size: 14px; }")
        inp_lay.addWidget(self.inp_msg)
        
        self.btn_send = QPushButton("Gửi")
        self.btn_send.setObjectName("primary")
        self.btn_send.setFixedSize(80, 70)
        self.btn_send.clicked.connect(self._send_message)
        inp_lay.addWidget(self.btn_send)
        
        clay.addLayout(inp_lay)
        
        main_lay.addWidget(sidebar)
        main_lay.addWidget(chat_area, 1)

    def _lbl(self, txt, title=False):
        lbl = QLabel(txt)
        if title:
            lbl.setStyleSheet("color: #00c8f0; font-weight: bold; font-size: 14px;")
        return lbl

    def _on_provider_changed(self, provider):
        self.cb_model.clear()
        if provider == "OpenAI":
            self.cb_model.addItems(["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"])
        elif provider == "Google Gemini":
            # Chỉ giữ lại gemini-2.5-flash theo yêu cầu
            self.cb_model.addItems(["gemini-2.5-flash"])
        elif provider == "Anthropic Claude":
            # Thêm bộ tam siêu việt của Claude
            self.cb_model.addItems(["claude-3-5-sonnet-20240620", "claude-3-opus-20240229", "claude-3-haiku-20240307"])
            
        # Nạp Key cũ từ DPAPI
        saved_key = get_api_key(provider)
        self.inp_api_key.setText(saved_key)
        
    def _save_api_key(self):
        provider = self.cb_provider.currentText()
        key = self.inp_api_key.text().strip()
        save_api_key(provider, key)
        QMessageBox.information(self, "Lưu thành công", f"Đã mã hoá DPAPI và lưu API Key cho {provider} an toàn cục bộ.")

    def _new_session(self):
        self.current_session_id = None
        self.messages_context = []
        self.chat_view.clear()
        self.chat_view.append("<b style='color:#00c8f0;'>Hệ thống:</b> Bắt đầu phiên trò chuyện mới. Nhập tin nhắn bên dưới.")
        
    def _load_sessions(self):
        self.list_sessions.clear()
        sessions = get_sessions()
        for s in sessions:
            title = s['title'] if s['title'] else "Hội thoại mới"
            item = QListWidgetItem(f"💬 {title.strip()[:20]}")
            item.setData(Qt.ItemDataRole.UserRole, s['id'])
            self.list_sessions.addItem(item)
            
    def _load_selected_session(self, item):
        session_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_session_id = session_id
        
        msgs = get_messages(session_id)
        self.chat_view.clear()
        self.messages_context = []
        
        for m in msgs:
            role = m['role']
            content = m['content']
            self.messages_context.append({"role": role, "content": content})
            self._append_chat(role, content)

    def _append_chat(self, role, content):
        if role == "user":
            html = f"<div style='margin-bottom: 10px;'><b style='color:#ff007f;'>Bạn:</b><br>{content.replace(chr(10), '<br>')}</div>"
        else:
            html = f"<div style='margin-bottom: 15px;'><b style='color:#00c8f0;'>AI Assistant:</b><br>{content.replace(chr(10), '<br>')}</div>"
        self.chat_view.append(html)
        
        # Scroll to bottom
        scrollbar = self.chat_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _send_message(self):
        msg = self.inp_msg.toPlainText().strip()
        if not msg:
            return
            
        provider = self.cb_provider.currentText()
        api_key = self.inp_api_key.text().strip()
        
        if not api_key:
            QMessageBox.warning(self, "Lỗi API Key", "Vui lòng nhập và Lưu API Key trước khi gửi!")
            self.inp_api_key.setFocus()
            return
            
        # Tạo session nếu chưa có
        if not self.current_session_id:
            self.current_session_id = str(uuid.uuid4())
            model = self.cb_model.currentText()
            title = msg[:30] + "..." if len(msg) > 30 else msg
            save_session(self.current_session_id, title, provider, model)
            self._load_sessions() # Refresh list
            
        # Record user message
        self.messages_context.append({"role": "user", "content": msg})
        save_message(self.current_session_id, "user", msg)
        self._append_chat("user", msg)
        
        self.inp_msg.clear()
        self.btn_send.setEnabled(False)
        self.btn_send.setText("Đang\nnghĩ...")
        self.cb_provider.setEnabled(False)
        
        # Call API on background thread
        model = self.cb_model.currentText()
        sys_ctx = self.inp_sys_context.toPlainText().strip()
        self.worker = AIWorker(provider, model, api_key, self.messages_context, sys_ctx)
        self.worker.finished.connect(self._on_ai_response)
        self.worker.start()

    def _on_ai_response(self, response_text):
        self.btn_send.setEnabled(True)
        self.btn_send.setText("Gửi")
        self.cb_provider.setEnabled(True)
        
        if response_text.startswith("❌"):
            # Lỗi
            self.chat_view.append(f"<div style='color:#ff6666;'>{response_text}</div>")
        else:
            self.messages_context.append({"role": "assistant", "content": response_text})
            save_message(self.current_session_id, "assistant", response_text)
            self._append_chat("assistant", response_text)
