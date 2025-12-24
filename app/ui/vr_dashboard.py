from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from app.ui.theme import Theme

class VRDashboard(QWidget):
    """
    专为 SteamVR Overlay 渲染优化的无边框界面。
    高对比度，大按钮，便于 VR 激光指针操作。
    """
    req_toggle_rec = Signal()
    req_send = Signal()

    def __init__(self, width=600, height=400):
        super().__init__()
        self.setFixedSize(width, height)
        # 深色背景，确保在 VR 中不刺眼
        self.setStyleSheet(f"""
            QWidget {{
                background-color: #1a1a1a;
                border: 2px solid {Theme.COLOR_PRIMARY};
                border-radius: 15px;
                color: white;
                font-family: "Microsoft YaHei", sans-serif;
            }}
            QPushButton {{
                background-color: #333;
                border: 2px solid #555;
                border-radius: 8px;
                padding: 10px;
                font-size: 20px;
                font-weight: bold;
                color: #ddd;
            }}
            QPushButton:hover {{
                background-color: #444;
                border-color: {Theme.COLOR_PRIMARY};
                color: white;
            }}
            QPushButton:pressed {{
                background-color: {Theme.COLOR_PRIMARY};
                color: black;
            }}
            QLabel {{
                font-size: 18px;
            }}
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        # === 顶部状态栏 ===
        header = QHBoxLayout()
        self.lbl_title = QLabel("POLYGLOT VR")
        self.lbl_title.setStyleSheet(f"color: {Theme.COLOR_PRIMARY}; font-weight: bold; font-size: 24px;")
        
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_status.setStyleSheet("color: #aaa; font-size: 18px;")
        
        header.addWidget(self.lbl_title)
        header.addStretch()
        header.addWidget(self.lbl_status)
        self.layout.addLayout(header)
        
        # === 分隔线 ===
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #444;")
        self.layout.addWidget(line)

        # === 内容显示区 (类似于 HUD) ===
        self.lbl_content = QLabel("Waiting for input...")
        self.lbl_content.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.lbl_content.setWordWrap(True)
        # 增加行高，提升可读性
        self.lbl_content.setStyleSheet("font-size: 22px; color: white; padding: 10px;")
        self.layout.addWidget(self.lbl_content, 1) # 占用主要空间

        # === 底部操作栏 ===
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)
        
        self.btn_rec = QPushButton("🎤 REC")
        self.btn_rec.setMinimumHeight(60)
        self.btn_rec.setCursor(Qt.PointingHandCursor)
        self.btn_rec.clicked.connect(self.req_toggle_rec.emit)
        
        self.btn_send = QPushButton("📤 SEND")
        self.btn_send.setMinimumHeight(60)
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.clicked.connect(self.req_send.emit)
        
        btn_layout.addWidget(self.btn_rec, 2)
        btn_layout.addWidget(self.btn_send, 1)
        self.layout.addLayout(btn_layout)

    def update_status(self, text, is_recording=False):
        color = Theme.COLOR_ERROR if is_recording else Theme.COLOR_SUCCESS
        if is_recording:
            self.lbl_status.setText(f"🎤 {text}")
            self.lbl_status.setStyleSheet(f"color: {Theme.COLOR_ERROR}; font-weight: bold;")
            self.btn_rec.setStyleSheet(f"background-color: {Theme.COLOR_ERROR}; color: white; border: none;")
            self.btn_rec.setText("STOP")
        else:
            self.lbl_status.setText(text)
            self.lbl_status.setStyleSheet("color: #aaa;")
            self.btn_rec.setStyleSheet("") # 恢复默认
            self.btn_rec.setText("🎤 REC")

    def update_content(self, text):
        # 截断过长文本防止 UI 爆炸
        if len(text) > 200: text = text[:200] + "..."
        self.lbl_content.setText(text)