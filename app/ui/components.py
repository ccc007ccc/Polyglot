from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QPushButton, QComboBox, 
    QSpinBox, QSlider, QHBoxLayout, QInputDialog, QMessageBox, QWidget,
    QSizePolicy  # [修复] 引入 QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QIcon
from app.ui.theme import Theme
from app.config import ConfigManager

class SettingCard(QFrame):
    """卡片容器：增加阴影和边框"""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingCard")
        self.setStyleSheet(f"""
            #SettingCard {{
                background-color: {Theme.COLOR_SURFACE};
                border-radius: 12px;
                border: 1px solid {Theme.COLOR_BORDER};
            }}
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(15)
        self.layout.setContentsMargins(24, 20, 24, 24)
        
        if title:
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet(f"font-size: 15px; font-weight: 600; color: {Theme.COLOR_PRIMARY}; letter-spacing: 0.5px;")
            self.layout.addWidget(lbl_title)
            
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet(f"background-color: {Theme.COLOR_BORDER}; max-height: 1px;")
            self.layout.addWidget(line)

    def add_widget(self, widget):
        self.layout.addWidget(widget)
        
    def add_layout(self, layout):
        self.layout.addLayout(layout)

class NavButton(QPushButton):
    """侧边栏按钮：优化选中态"""
    def __init__(self, text, icon_text, parent=None):
        super().__init__(parent)
        self.setText(f" {icon_text}  {text}")
        self.setCheckable(True)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(48)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 8px;
                color: {Theme.COLOR_TEXT_SUB};
                text-align: left;
                padding-left: 16px;
                font-size: 14px;
                font-weight: 500;
                margin: 0 10px;
            }}
            QPushButton:checked {{
                background-color: rgba(79, 154, 249, 0.15); /* Primary with alpha */
                color: {Theme.COLOR_PRIMARY};
            }}
            QPushButton:hover {{
                background-color: {Theme.COLOR_SURFACE_HOVER};
                color: {Theme.COLOR_TEXT_MAIN};
            }}
        """)

class StatusBadge(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedHeight(32)
        self.set_status("Ready", Theme.COLOR_TEXT_SUB)

    def set_status(self, text, color_hex):
        self.setText(text)
        self.setStyleSheet(f"""
            background-color: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 0 16px;
            font-weight: 600;
            font-size: 12px;
            color: {color_hex};
            border: 1px solid {color_hex};
        """)

# === 模版管理组件 ===
class TemplateWidget(QWidget):
    content_changed = Signal() # 通知外部内容变化

    def __init__(self, config_key, target_input, parent=None):
        super().__init__(parent)
        self.cfg = ConfigManager()
        self.key = config_key
        self.target = target_input # 绑定的 QTextEdit 或 QLineEdit
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)
        
        self.combo = NoScrollComboBox()
        self.combo.setPlaceholderText("Select Template...")
        # [修复] 使用 QSizePolicy.Expanding 而不是整数
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.btn_load = QPushButton("Load")
        self.btn_save = QPushButton("Save New")
        self.btn_del = QPushButton("Del")
        
        # 样式
        btn_style = f"""
            QPushButton {{
                background-color: #21262d; border: 1px solid {Theme.COLOR_BORDER}; 
                border-radius: 6px; padding: 5px 12px; color: {Theme.COLOR_TEXT_SUB};
            }}
            QPushButton:hover {{ border-color: {Theme.COLOR_TEXT_SUB}; color: {Theme.COLOR_TEXT_MAIN}; }}
        """
        self.btn_load.setStyleSheet(btn_style)
        self.btn_save.setStyleSheet(btn_style)
        self.btn_del.setStyleSheet(btn_style)
        
        self.layout.addWidget(self.combo, 1)
        self.layout.addWidget(self.btn_load)
        self.layout.addWidget(self.btn_save)
        self.layout.addWidget(self.btn_del)
        
        self.refresh_combo()
        
        self.btn_load.clicked.connect(self.load_template)
        self.btn_save.clicked.connect(self.save_template)
        self.btn_del.clicked.connect(self.delete_template)

    def refresh_combo(self):
        self.combo.clear()
        templates = self.cfg.get(self.key) or {}
        for name in templates.keys():
            self.combo.addItem(name)

    def load_template(self):
        name = self.combo.currentText()
        templates = self.cfg.get(self.key) or {}
        if name in templates:
            content = templates[name]
            if hasattr(self.target, 'setPlainText'):
                self.target.setPlainText(content)
            else:
                self.target.setText(content)
            self.content_changed.emit()

    def save_template(self):
        text = ""
        if hasattr(self.target, 'toPlainText'):
            text = self.target.toPlainText()
        else:
            text = self.target.text()
            
        if not text.strip(): return
        
        name, ok = QInputDialog.getText(self, "Save Template", "Template Name:")
        if ok and name:
            templates = self.cfg.get(self.key) or {}
            templates[name] = text
            self.cfg.set(self.key, templates)
            self.cfg.save()
            self.refresh_combo()
            self.combo.setCurrentText(name)

    def delete_template(self):
        name = self.combo.currentText()
        if not name: return
        
        ret = QMessageBox.question(self, "Confirm", f"Delete template '{name}'?")
        if ret == QMessageBox.Yes:
            templates = self.cfg.get(self.key) or {}
            if name in templates:
                del templates[name]
                self.cfg.set(self.key, templates)
                self.cfg.save()
                self.refresh_combo()

# === 防滚轮组件 ===
class NoScrollComboBox(QComboBox):
    def wheelEvent(self, event): event.ignore()

class NoScrollSpinBox(QSpinBox):
    def wheelEvent(self, event): event.ignore()

class NoScrollSlider(QSlider):
    def wheelEvent(self, event): event.ignore()