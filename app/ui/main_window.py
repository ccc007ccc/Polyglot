import threading
import time
import keyboard
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QTextEdit, QLineEdit, QCheckBox, 
    QTabWidget, QGroupBox, QScrollArea, QFormLayout, QGridLayout,
    QComboBox, QRadioButton, QButtonGroup, QSlider, QSpinBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from app.config import ConfigManager

# === 快捷键按钮类 (保持不变) ===
class HotkeyButton(QPushButton):
    key_changed = Signal(str)
    reset_signal = Signal()

    def __init__(self, default_key):
        super().__init__()
        self.current_key = default_key
        self.setText(f"当前: {self.current_key}")
        self.clicked.connect(self.start_recording)
        self.is_recording = False
        self.setStyleSheet("text-align: left; padding: 5px;")
        self.reset_signal.connect(self._reset_ui)

    def start_recording(self):
        if self.is_recording: return
        self.is_recording = True
        self.setText("请按下按键... (Esc 取消)")
        self.setStyleSheet("background-color: #e74c3c; color: white; text-align: left; padding: 5px;")
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def _listen_loop(self):
        try:
            time.sleep(0.4)
            new_key = keyboard.read_hotkey(suppress=False)
            if new_key and new_key.lower() == "esc": pass
            else:
                self.current_key = new_key
                self.key_changed.emit(self.current_key)
        except Exception as e:
            print(f"Key Error: {e}")
        finally:
            self.is_recording = False
            self.reset_signal.emit()

    def _reset_ui(self):
        self.setText(f"当前: {self.current_key}")
        self.setStyleSheet("text-align: left; padding: 5px;")

# === 悬浮窗类 (关键修复) ===
class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager()
        self.base_flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        self.setWindowFlags(self.base_flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # === 修复点 1: 初始化时不锁死固定尺寸，只设置初始位置 ===
        # self.setFixedSize(...) # 删除了这一行
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        self.bg = QWidget(self)
        self.bg_layout = QVBoxLayout(self.bg)
        
        self.lbl_status = QLabel("Polyglot Ready")
        self.lbl_status.setAlignment(Qt.AlignLeft)
        
        self.lbl_text = QLabel("...")
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        self.bg_layout.addWidget(self.lbl_status)
        self.bg_layout.addWidget(self.lbl_text)
        self.bg_layout.addStretch() # 让内容靠上
        self.layout.addWidget(self.bg)
        
        self.old_pos = None
        self.apply_style()
        
        x = self.cfg.get("overlay_x")
        y = self.cfg.get("overlay_y")
        if x and y: self.move(x, y)

    def apply_style(self):
        w = self.cfg.get("overlay_width")
        h = self.cfg.get("overlay_height")
        
        # === 修复点 2: 使用固定宽度 + 最小高度 ===
        # 允许高度自动根据内容撑大，解决 Geometry 冲突问题
        self.setFixedWidth(w)
        self.setMinimumHeight(h)
        # 解除最大高度限制，防止内容截断
        self.setMaximumHeight(1080) 

        opacity = self.cfg.get("overlay_opacity")
        border_alpha = self.cfg.get("overlay_border_alpha")
        font_size = self.cfg.get("overlay_font_size")
        is_locked = self.cfg.get("overlay_locked")
        
        current_pos = self.pos()
        
        if is_locked:
            self.setWindowFlags(self.base_flags | Qt.WindowTransparentForInput)
            bg_color = f"rgba(0, 0, 0, {int(opacity * 200)})"
            border = "border: none;"
        else:
            self.setWindowFlags(self.base_flags)
            bg_color = f"rgba(20, 20, 20, {int(opacity * 255)})"
            border_color = f"rgba(243, 156, 18, {border_alpha})"
            border = f"border: 2px dashed {border_color};"

        self.bg.setStyleSheet(f"""
            background-color: {bg_color}; 
            border-radius: 10px; 
            {border}
        """)
        
        font = QFont("Microsoft YaHei", font_size)
        font.setBold(True)
        self.lbl_status.setFont(font)
        
        font_content = QFont("Microsoft YaHei", font_size)
        self.lbl_text.setFont(font_content)
        self.lbl_text.setStyleSheet(f"color: white;")
        
        # 强制更新一次几何尺寸
        self.adjustSize()
        self.move(current_pos)
        self.show()

    def update_status(self, text, color):
        self.lbl_status.setText(text)
        self.lbl_status.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.repaint() # 强制重绘

    def update_content(self, text):
        self.lbl_text.setText(text)
        # === 修复点 3: 每次更新内容后，允许窗口调整大小并强制重绘 ===
        self.adjustSize() 
        self.repaint() 

    def mousePressEvent(self, event):
        if not self.cfg.get("overlay_locked") and event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()
            
    def mouseMoveEvent(self, event):
        if not self.cfg.get("overlay_locked") and self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPos()
            
    def mouseReleaseEvent(self, event):
        if not self.cfg.get("overlay_locked"):
            self.old_pos = None
            self.cfg.set("overlay_x", self.pos().x())
            self.cfg.set("overlay_y", self.pos().y())
            self.cfg.save()

# === 主窗口类 ===
class MainWindow(QMainWindow):
    def __init__(self, logic_controller):
        super().__init__()
        self.logic = logic_controller
        self.cfg = ConfigManager()
        self.setWindowTitle("Polyglot Pro (Modular)")
        self.resize(600, 950)
        
        container = QWidget()
        self.setCentralWidget(container)
        layout = QVBoxLayout(container)
        
        self.lbl_main_status = QLabel("正在初始化...")
        self.lbl_main_status.setAlignment(Qt.AlignCenter)
        self.lbl_main_status.setStyleSheet("background-color: #2c3e50; color: white; padding: 12px; border-radius: 6px; font-weight: bold;")
        layout.addWidget(self.lbl_main_status)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        self.init_log_tab()
        self.init_settings_tab()
        
        self.overlay = OverlayWindow()
        self.overlay.show()

    def init_log_tab(self):
        tab = QWidget()
        l = QVBoxLayout(tab)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("background-color: #1e1e1e; color: #ccc; font-family: Consolas;")
        l.addWidget(self.txt_log)
        self.tabs.addTab(tab, "运行日志")

    def init_settings_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        
        # 1. STT
        grp_stt = QGroupBox("🧠 语音识别核心")
        form_stt = QFormLayout(grp_stt)
        self.combo_stt = QComboBox()
        self.combo_stt.addItem("Faster-Whisper (推荐, 离线)", "faster_whisper")
        self.combo_stt.addItem("FunASR (阿里, 高精度中文)", "funasr")
        current_stt = self.cfg.get("stt_engine")
        idx = self.combo_stt.findData(current_stt)
        self.combo_stt.setCurrentIndex(max(0, idx))
        form_stt.addRow("识别模型:", self.combo_stt)
        form_stt.addRow(QLabel("<font color='gray'>切换后需重启。</font>"))
        layout.addWidget(grp_stt)

        # 2. 悬浮窗
        grp_overlay = QGroupBox("🖥️ 悬浮窗样式")
        form_overlay = QFormLayout(grp_overlay)
        
        self.chk_lock = QCheckBox("锁定位置 (穿透)"); self.chk_lock.setChecked(self.cfg.get("overlay_locked"))
        self.chk_lock.toggled.connect(self.update_overlay_style)
        
        size_layout = QHBoxLayout()
        self.spin_w = QSpinBox(); self.spin_w.setRange(200, 1920); self.spin_w.setValue(self.cfg.get("overlay_width"))
        self.spin_h = QSpinBox(); self.spin_h.setRange(50, 1080); self.spin_h.setValue(self.cfg.get("overlay_height"))
        self.spin_w.valueChanged.connect(self.update_overlay_style)
        self.spin_h.valueChanged.connect(self.update_overlay_style)
        size_layout.addWidget(self.spin_w); size_layout.addWidget(self.spin_h)
        
        self.slider_opacity = QSlider(Qt.Horizontal); self.slider_opacity.setRange(10, 100); self.slider_opacity.setValue(int(self.cfg.get("overlay_opacity") * 100))
        self.slider_opacity.valueChanged.connect(self.update_overlay_style)
        
        self.slider_border = QSlider(Qt.Horizontal); self.slider_border.setRange(0, 100); self.slider_border.setValue(int(self.cfg.get("overlay_border_alpha") * 100))
        self.slider_border.valueChanged.connect(self.update_overlay_style)
        
        self.spin_font = QSpinBox(); self.spin_font.setRange(10, 60); self.spin_font.setValue(self.cfg.get("overlay_font_size"))
        self.spin_font.valueChanged.connect(self.update_overlay_style)
        
        form_overlay.addRow(self.chk_lock)
        form_overlay.addRow("尺寸(宽x最小高):", size_layout)
        form_overlay.addRow("背景浓度:", self.slider_opacity)
        form_overlay.addRow("边框浓度:", self.slider_border)
        form_overlay.addRow("字体大小:", self.spin_font)
        layout.addWidget(grp_overlay)

        # 3. 音频
        grp_audio = QGroupBox("🎤 音频硬件")
        form_audio = QFormLayout(grp_audio)
        self.combo_mic = QComboBox()
        devices = self.logic.audio.get_input_devices()
        current_mic = self.cfg.get("mic_index")
        self.combo_mic.addItem("默认设备", 0)
        idx_to_select = 0
        for i, (idx, name) in enumerate(devices):
            self.combo_mic.addItem(f"{idx}: {name}", idx)
            if idx == current_mic: idx_to_select = i + 1
        self.combo_mic.setCurrentIndex(idx_to_select)
        form_audio.addRow("输入设备:", self.combo_mic)
        layout.addWidget(grp_audio)

        # 4. 控制
        grp_keys = QGroupBox("⌨️ 控制")
        form_keys = QFormLayout(grp_keys)
        self.rb_hold = QRadioButton("按住"); self.rb_toggle = QRadioButton("切换")
        self.bg_mode = QButtonGroup(); self.bg_mode.addButton(self.rb_hold); self.bg_mode.addButton(self.rb_toggle)
        if self.cfg.get("rec_mode") == "hold": self.rb_hold.setChecked(True)
        else: self.rb_toggle.setChecked(True)
        
        self.chk_auto_send = QCheckBox("自动发送"); self.chk_auto_send.setChecked(self.cfg.get("auto_send"))
        self.chk_sound = QCheckBox("提示音"); self.chk_sound.setChecked(self.cfg.get("sound_cues"))
        
        self.btn_hk_rec = HotkeyButton(self.cfg.get("hotkey_rec"))
        self.btn_hk_send = HotkeyButton(self.cfg.get("hotkey_send"))
        self.btn_hk_rec.key_changed.connect(lambda k: self.cfg.set("hotkey_rec", k))
        self.btn_hk_send.key_changed.connect(lambda k: self.cfg.set("hotkey_send", k))
        
        form_keys.addRow("模式:", self.rb_hold)
        form_keys.addRow("", self.rb_toggle)
        form_keys.addRow(self.chk_auto_send, self.chk_sound)
        form_keys.addRow("录音:", self.btn_hk_rec)
        form_keys.addRow("发送:", self.btn_hk_send)
        layout.addWidget(grp_keys)

        # 5. API
        grp_api = QGroupBox("🤖 API & 翻译")
        form_api = QFormLayout(grp_api)
        self.input_api_base = QLineEdit(self.cfg.get("api_base"))
        self.input_api_key = QLineEdit(self.cfg.get("api_key")); self.input_api_key.setEchoMode(QLineEdit.Password)
        self.input_model = QLineEdit(self.cfg.get("model"))
        form_api.addRow("Base:", self.input_api_base)
        form_api.addRow("Key:", self.input_api_key)
        form_api.addRow("Model:", self.input_model)
        layout.addWidget(grp_api)
        
        # 6. 语言
        grp_langs = QGroupBox("🌐 目标语言与模板")
        l_tpl = QVBoxLayout(grp_langs)
        grid = QGridLayout()
        langs = self.cfg.get("langs") or {}
        self.chk_zh = QCheckBox("CN"); self.chk_zh.setChecked(langs.get("zh", True))
        self.chk_en = QCheckBox("EN"); self.chk_en.setChecked(langs.get("en", True))
        self.chk_ja = QCheckBox("JA"); self.chk_ja.setChecked(langs.get("ja", False))
        self.chk_ru = QCheckBox("RU"); self.chk_ru.setChecked(langs.get("ru", False))
        self.chk_pinyin = QCheckBox("PY"); self.chk_pinyin.setChecked(langs.get("pinyin", True))
        grid.addWidget(self.chk_zh, 0, 0); grid.addWidget(self.chk_en, 0, 1)
        grid.addWidget(self.chk_ja, 0, 2); grid.addWidget(self.chk_ru, 0, 3)
        grid.addWidget(self.chk_pinyin, 0, 4)
        l_tpl.addLayout(grid)
        
        self.txt_tpl_display = QTextEdit()
        self.txt_tpl_display.setPlainText(self.cfg.get("tpl_display"))
        self.txt_tpl_display.setMaximumHeight(60)
        self.txt_tpl_display.setPlaceholderText("悬浮窗显示格式...")
        
        self.input_tpl_osc = QLineEdit(self.cfg.get("tpl_osc"))
        
        l_tpl.addWidget(QLabel("悬浮窗模板 (空行自动隐藏):"))
        l_tpl.addWidget(self.txt_tpl_display)
        l_tpl.addWidget(QLabel("OSC 发送模板:"))
        l_tpl.addWidget(self.input_tpl_osc)
        layout.addWidget(grp_langs)

        # 保存
        btn_save = QPushButton("💾 保存配置")
        btn_save.setStyleSheet("background-color: #27ae60; color: white; padding: 10px; font-weight: bold;")
        btn_save.clicked.connect(self.save_settings)
        layout.addWidget(btn_save)
        
        scroll.setWidget(content)
        self.tabs.addTab(scroll, "设置")

    def update_overlay_style(self):
        self.cfg.set("overlay_opacity", self.slider_opacity.value() / 100.0)
        self.cfg.set("overlay_border_alpha", self.slider_border.value() / 100.0)
        self.cfg.set("overlay_font_size", self.spin_font.value())
        self.cfg.set("overlay_width", self.spin_w.value())
        self.cfg.set("overlay_height", self.spin_h.value())
        self.cfg.set("overlay_locked", self.chk_lock.isChecked())
        self.overlay.apply_style()

    def save_settings(self):
        self.update_overlay_style()
        self.cfg.set("api_base", self.input_api_base.text().strip())
        self.cfg.set("api_key", self.input_api_key.text().strip())
        self.cfg.set("model", self.input_model.text().strip())
        self.cfg.set("auto_send", self.chk_auto_send.isChecked())
        self.cfg.set("sound_cues", self.chk_sound.isChecked())
        self.cfg.set("mic_index", self.combo_mic.currentData())
        self.cfg.set("rec_mode", "hold" if self.rb_hold.isChecked() else "toggle")
        
        old_stt = self.cfg.get("stt_engine")
        new_stt = self.combo_stt.currentData()
        self.cfg.set("stt_engine", new_stt)
        
        langs = {
            "zh": self.chk_zh.isChecked(), "en": self.chk_en.isChecked(),
            "ja": self.chk_ja.isChecked(), "ru": self.chk_ru.isChecked(),
            "pinyin": self.chk_pinyin.isChecked()
        }
        self.cfg.set("langs", langs)
        self.cfg.set("tpl_display", self.txt_tpl_display.toPlainText())
        self.cfg.set("tpl_osc", self.input_tpl_osc.text())
        
        self.cfg.save()
        
        if old_stt != new_stt:
            QMessageBox.information(self, "提示", "语音模型已切换，请重启程序以生效。")
            self.log("⚠️ 配置已保存，请重启程序应用新模型。")
        else:
            self.log("✅ 配置已保存")
        
        self.set_status("配置已保存", "#2ecc71")

    def log(self, text):
        self.txt_log.append(text)
        sb = self.txt_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_status(self, text, color):
        self.lbl_main_status.setText(text)
        self.lbl_main_status.setStyleSheet(f"background-color: {color}; color: white; padding: 10px; border-radius: 5px; font-weight: bold;")
        ov_color = "#2ecc71"
        if "录音" in text: ov_color = "#e74c3c"
        elif "识别" in text or "翻译" in text: ov_color = "#f39c12"
        elif "错误" in text: ov_color = "#e74c3c"
        self.overlay.update_status(text, ov_color)