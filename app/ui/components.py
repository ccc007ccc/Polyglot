from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QPushButton, QComboBox, QSpinBox, QSlider
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from app.ui.theme import Theme

class SettingCard(QFrame):
    """
    圆角卡片容器，用于分组设置项
    """
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingCard")
        self.setStyleSheet(f"""
            #SettingCard {{
                background-color: {Theme.COLOR_SURFACE};
                border-radius: 8px;
                border: 1px solid #333;
            }}
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(15)
        self.layout.setContentsMargins(20, 20, 20, 20)
        
        # 标题栏
        if title:
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {Theme.COLOR_PRIMARY};")
            self.layout.addWidget(lbl_title)
            
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet("background-color: #333;")
            self.layout.addWidget(line)

    def add_widget(self, widget):
        self.layout.addWidget(widget)
        
    def add_layout(self, layout):
        self.layout.addLayout(layout)

class NavButton(QPushButton):
    """
    侧边栏导航按钮
    """
    def __init__(self, text, icon_text, parent=None):
        super().__init__(parent)
        self.setText(f" {icon_text}  {text}")
        self.setCheckable(True)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(50)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {Theme.COLOR_TEXT_SUB};
                text-align: left;
                padding-left: 20px;
                font-size: 15px;
                border-left: 4px solid transparent;
            }}
            QPushButton:checked {{
                background-color: {Theme.COLOR_SURFACE_HOVER};
                color: {Theme.COLOR_TEXT_MAIN};
                border-left: 4px solid {Theme.COLOR_PRIMARY};
            }}
            QPushButton:hover {{
                background-color: #252526;
                color: {Theme.COLOR_TEXT_MAIN};
            }}
        """)

class StatusBadge(QLabel):
    """
    状态显示徽章
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(40)
        self.set_status("Ready", Theme.COLOR_TEXT_SUB)

    def set_status(self, text, color_hex):
        self.setText(text)
        self.setStyleSheet(f"""
            background-color: {Theme.COLOR_SURFACE};
            border-radius: 6px;
            font-weight: bold;
            color: {color_hex};
            border: 1px solid {color_hex};
        """)

# === 新增：防滚轮误触控件 ===
# 这些控件会忽略滚轮事件，使其自然冒泡到 ScrollArea，从而滚动页面而不是修改值

class NoScrollComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()

class NoScrollSpinBox(QSpinBox):
    def wheelEvent(self, event):
        event.ignore()

class NoScrollSlider(QSlider):
    def wheelEvent(self, event):
        event.ignore()