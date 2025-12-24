# app/vr/ui/panel.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QColor, QPainter, QPen, QBrush
from app.ui.theme import Theme
from app.services.lang_service import LanguageService

class CursorLayer(QWidget):
    """
    专门用于绘制红点的透明层。
    设置了 WA_TransparentForMouseEvents，保证鼠标穿透，不影响按钮点击。
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.cursor_pos = QPoint(-1, -1)
        self.setFixedSize(parent.size()) # 跟随父窗口大小

    def update_pos(self, x, y):
        self.cursor_pos = QPoint(x, y)
        self.update() # 仅重绘光标层，开销极小

    def paintEvent(self, event):
        if self.cursor_pos.x() >= 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 绘制红点
            painter.setPen(QPen(Qt.red, 2))
            painter.setBrush(QBrush(QColor(255, 0, 0, 200)))
            painter.drawEllipse(self.cursor_pos, 8, 8)
            
            # 绘制十字准星辅助
            painter.setPen(QPen(QColor(255, 0, 0, 100), 1))
            cx, cy = self.cursor_pos.x(), self.cursor_pos.y()
            painter.drawLine(cx - 15, cy, cx + 15, cy)
            painter.drawLine(cx, cy - 15, cx, cy + 15)

class VRPanel(QWidget):
    req_toggle_rec = Signal()
    req_send = Signal()
    request_repaint = Signal()

    def __init__(self, width=800, height=800):
        super().__init__()
        self.ls = LanguageService()
        self.setFixedSize(width, height)
        
        # 样式：加粗边框，高对比度
        self.setStyleSheet(f"""
            QWidget {{
                background-color: #121212;
                color: #ffffff;
                font-family: "Microsoft YaHei", sans-serif;
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
                background-color: #3d3d3d;
                border-color: {Theme.COLOR_PRIMARY};
            }}
            QPushButton:pressed {{
                background-color: {Theme.COLOR_PRIMARY};
                color: #fff;
            }}
            QLabel {{ border: none; }}
        """)

        # === 布局 ===
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(40, 40, 40, 40)
        self.layout.setSpacing(25)

        # Header
        header = QHBoxLayout()
        self.lbl_title = QLabel("POLYGLOT VR")
        self.lbl_title.setStyleSheet(f"font-size: 36px; font-weight: 900; color: {Theme.COLOR_PRIMARY};")
        self.lbl_status = QLabel("Standby")
        self.lbl_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_status.setStyleSheet("font-size: 28px; color: #888; font-weight: bold;")
        
        header.addWidget(self.lbl_title)
        header.addStretch()
        header.addWidget(self.lbl_status)
        self.layout.addLayout(header)

        # Line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #444; border: none; min-height: 3px;")
        self.layout.addWidget(line)

        # Content
        self.content_area = QLabel("Waiting for input...")
        self.content_area.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.content_area.setWordWrap(True)
        self.content_area.setStyleSheet("""
            font-size: 32px; 
            color: #eee; 
            padding: 25px; 
            background-color: #1e1e1e; 
            border-radius: 16px;
        """)
        self.layout.addWidget(self.content_area, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(30)
        
        self.btn_rec = QPushButton("🎤 REC")
        self.btn_rec.setMinimumHeight(120)
        self.btn_rec.setCursor(Qt.PointingHandCursor)
        self.btn_rec.clicked.connect(self.on_rec_click)

        self.btn_send = QPushButton("📤 SEND")
        self.btn_send.setMinimumHeight(120)
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.clicked.connect(self.on_send_click)

        btn_layout.addWidget(self.btn_rec, 2)
        btn_layout.addWidget(self.btn_send, 1)
        self.layout.addLayout(btn_layout)
        
        # === 关键修复：添加独立的光标层 ===
        # 它必须作为 self 的子控件，并且最后创建，这样就在最上层
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
        if content_text and self.content_area.text() != content_text:
            if len(content_text) > 250: content_text = content_text[:250] + "..."
            self.content_area.setText(content_text)
            need_repaint = True
        
        if status_text not in self.lbl_status.text():
            need_repaint = True

        if is_recording:
            self.lbl_status.setText(f"● {status_text}")
            self.lbl_status.setStyleSheet(f"color: {Theme.COLOR_ERROR}; font-weight: bold; font-size: 28px;")
            self.btn_rec.setText("STOP")
            self.btn_rec.setStyleSheet(f"background-color: {Theme.COLOR_ERROR}; color: white; border-color: #c0392b;")
        else:
            self.lbl_status.setText(status_text)
            self.lbl_status.setStyleSheet("color: #888; font-size: 28px;")
            self.btn_rec.setText("🎤 REC")
            self.btn_rec.setStyleSheet("")
            
        if need_repaint:
            self.request_repaint.emit()

    def set_debug_cursor(self, x, y):
        # 更新光标层的位置
        self.cursor_layer.update_pos(x, y)
        # 触发整体重绘 (为了把光标层画到纹理上)
        self.request_repaint.emit()