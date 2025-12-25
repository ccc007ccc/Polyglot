# app/vr/ui/panel.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QLinearGradient
from app.ui.theme import Theme
from app.services.lang_service import LanguageService

class CursorLayer(QWidget):
    """专门用于绘制红点的透明层"""
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.cursor_pos = QPoint(-1, -1)
        self.setFixedSize(parent.size())

    def update_pos(self, x, y):
        self.cursor_pos = QPoint(x, y)
        self.update()

    def paintEvent(self, event):
        if self.cursor_pos.x() >= 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(Qt.red, 2))
            painter.setBrush(QBrush(QColor(255, 0, 0, 200)))
            painter.drawEllipse(self.cursor_pos, 8, 8)

class TitleBar(QLabel):
    """可拖动的标题栏"""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setObjectName("VRTitleBar")
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(80)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {Theme.COLOR_SURFACE_HOVER};
                color: {Theme.COLOR_PRIMARY};
                font-size: 28px;
                font-weight: bold;
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
                border-bottom: 2px solid #444;
            }}
            QLabel:hover {{
                background-color: #3d3d3d;
                color: white;
            }}
        """)

class ResizeHandle(QLabel):
    """右下角调整大小的手柄"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VRResizeHandle")
        self.setFixedSize(60, 60)
        self.setStyleSheet("""
            background-color: transparent;
        """)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(100, 100, 100), 4)
        painter.setPen(pen)
        # 画三条斜线
        w, h = self.width(), self.height()
        for i in range(3):
            offset = i * 10
            painter.drawLine(w - 5 - offset, h - 5, w - 5, h - 5 - offset)

class VRPanel(QWidget):
    req_toggle_rec = Signal()
    req_send = Signal()
    request_repaint = Signal()

    def __init__(self, width=800, height=800):
        super().__init__()
        self.ls = LanguageService()
        self.setFixedSize(width, height)
        
        self.setStyleSheet(f"""
            QWidget#VRPanelRoot {{
                background-color: #121212;
                border: 4px solid #444;
                border-radius: 24px;
            }}
            QPushButton {{
                background-color: #2c2c2c;
                border: 3px solid #555;
                border-radius: 16px;
                color: #eee;
                font-size: 32px;
                font-weight: bold;
                padding: 20px;
            }}
            QPushButton:hover {{
                border-color: {Theme.COLOR_PRIMARY};
                background-color: #3d3d3d;
            }}
            QPushButton:pressed {{
                background-color: {Theme.COLOR_PRIMARY};
            }}
        """)
        self.setObjectName("VRPanelRoot")

        # === 主布局 ===
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. 拖动标题栏
        self.title_bar = TitleBar(f"⚓ {self.ls.tr('vr_title')}")
        self.main_layout.addWidget(self.title_bar)

        # 内部容器
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(30, 20, 30, 30)
        content_layout.setSpacing(20)

        # 2. 状态栏
        self.lbl_status = QLabel("Standby")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("font-size: 24px; color: #888; font-weight: bold;")
        content_layout.addWidget(self.lbl_status)

        # 3. 文本内容区
        self.content_area = QLabel("Waiting...")
        self.content_area.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.content_area.setWordWrap(True)
        self.content_area.setStyleSheet("""
            font-size: 30px; 
            color: #eee; 
            padding: 20px; 
            background-color: #1e1e1e; 
            border-radius: 12px;
            border: 1px solid #333;
        """)
        content_layout.addWidget(self.content_area, 1)

        # 4. 按钮区
        btn_layout = QHBoxLayout()
        self.btn_rec = QPushButton("🎤 REC")
        self.btn_rec.setMinimumHeight(100)
        self.btn_rec.clicked.connect(self.on_rec_click)

        self.btn_send = QPushButton("📤 SEND")
        self.btn_send.setMinimumHeight(100)
        self.btn_send.clicked.connect(self.on_send_click)

        btn_layout.addWidget(self.btn_rec, 2)
        btn_layout.addWidget(self.btn_send, 1)
        content_layout.addLayout(btn_layout)
        
        self.main_layout.addWidget(content_container, 1)

        # 5. 提示栏
        hint_bar = QHBoxLayout()
        hint_bar.setContentsMargins(30, 0, 10, 10)
        self.lbl_hint = QLabel(self.ls.tr("vr_drag_hint"))
        self.lbl_hint.setStyleSheet("color: #666; font-size: 18px; font-style: italic;")
        hint_bar.addWidget(self.lbl_hint)
        hint_bar.addStretch()
        
        self.resize_handle = ResizeHandle(self)
        self.resize_handle.move(width - 60, height - 60)
        self.resize_handle.raise_()

        self.main_layout.addLayout(hint_bar)

        self.cursor_layer = CursorLayer(self)
        self.cursor_layer.setGeometry(0, 0, width, height)
        self.cursor_layer.raise_()

    def on_rec_click(self):
        self.req_toggle_rec.emit()
        self.request_repaint.emit()

    def on_send_click(self):
        self.req_send.emit()
        self.request_repaint.emit()

    def update_state(self, content_text, status_text, is_recording):
        need_repaint = False
        
        clean_text = content_text.strip()
        if self.content_area.text() != clean_text:
            if len(clean_text) > 300: clean_text = clean_text[:300] + "..."
            self.content_area.setText(clean_text)
            need_repaint = True
        
        if status_text not in self.lbl_status.text():
            need_repaint = True

        if is_recording:
            self.lbl_status.setText(f"● {status_text}")
            self.lbl_status.setStyleSheet(f"color: {Theme.COLOR_ERROR}; font-weight: bold; font-size: 24px;")
            self.btn_rec.setText("STOP")
            self.btn_rec.setStyleSheet(f"background-color: {Theme.COLOR_ERROR}; color: white; border-color: #c0392b;")
        else:
            # [Fix] 增加对 Init/Busy 等状态的颜色高亮
            self.lbl_status.setText(status_text)
            if "Init" in status_text or "Load" in status_text or "Wait" in status_text:
                self.lbl_status.setStyleSheet(f"color: {Theme.COLOR_WARNING}; font-size: 24px; font-weight: bold;")
            else:
                self.lbl_status.setStyleSheet("color: #888; font-size: 24px;")
                
            self.btn_rec.setText("🎤 REC")
            self.btn_rec.setStyleSheet("")
            
        if need_repaint:
            self.request_repaint.emit()

    def set_debug_cursor(self, x, y):
        self.cursor_layer.update_pos(x, y)
        self.request_repaint.emit()
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'resize_handle'):
            self.resize_handle.move(self.width() - 60, self.height() - 60)
        if hasattr(self, 'cursor_layer'):
            self.cursor_layer.setGeometry(0, 0, self.width(), self.height())