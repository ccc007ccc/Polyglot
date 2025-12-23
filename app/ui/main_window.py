import threading
import time
import keyboard
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QTextEdit, QLineEdit, QCheckBox, 
    QStackedWidget, QScrollArea, QFormLayout, QGridLayout,
    QRadioButton, QButtonGroup, QMessageBox,
    QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QFont, QIcon

from app.config import ConfigManager
from app.ui.theme import Theme
# 导入新的防滚轮组件
from app.ui.components import SettingCard, NavButton, StatusBadge, NoScrollComboBox, NoScrollSpinBox, NoScrollSlider
from app.services.lang_service import LanguageService

# === 快捷键按钮 ===
class HotkeyButton(QPushButton):
    key_changed = Signal(str)
    reset_signal = Signal()

    def __init__(self, default_key, placeholder_text="Press Key..."):
        super().__init__()
        self.current_key = default_key
        self.placeholder_text = placeholder_text
        self.setText(f"{self.current_key}")
        self.clicked.connect(self.start_recording)
        self.is_recording = False
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px 12px;
                color: {Theme.COLOR_PRIMARY};
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #3e3e3e; }}
        """)
        self.reset_signal.connect(self._reset_ui)

    def start_recording(self):
        if self.is_recording: return
        self.is_recording = True
        self.setText(self.placeholder_text)
        self.setStyleSheet(f"background-color: {Theme.COLOR_WARNING}; color: #000; border-radius: 4px;")
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def _listen_loop(self):
        try:
            time.sleep(0.4)
            new_key = keyboard.read_hotkey(suppress=False)
            if new_key and new_key.lower() != "esc":
                self.current_key = new_key
                self.key_changed.emit(self.current_key)
        except: pass
        finally:
            self.is_recording = False
            self.reset_signal.emit()

    def _reset_ui(self):
        self.setText(f"{self.current_key}")
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: #2d2d2d;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px 12px;
                color: {Theme.COLOR_PRIMARY};
                font-weight: bold;
            }}
        """)

# === 悬浮窗类 ===
class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager()
        self.base_flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        self.setWindowFlags(self.base_flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        self.bg = QWidget(self)
        self.bg_layout = QVBoxLayout(self.bg)
        
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setAlignment(Qt.AlignLeft)
        
        self.lbl_text = QLabel("...")
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        self.bg_layout.addWidget(self.lbl_status)
        self.bg_layout.addWidget(self.lbl_text)
        self.bg_layout.addStretch()
        self.layout.addWidget(self.bg)
        
        self.old_pos = None
        self.apply_style()
        
        x = self.cfg.get("overlay_x")
        y = self.cfg.get("overlay_y")
        if x and y: self.move(x, y)

    def apply_style(self):
        w = self.cfg.get("overlay_width")
        h = self.cfg.get("overlay_height")
        self.setFixedWidth(w)
        self.setMinimumHeight(h)
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
        
        self.adjustSize()
        self.move(current_pos)
        self.show()

    def update_status(self, text, color):
        self.lbl_status.setText(text)
        self.lbl_status.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.repaint()

    def update_content(self, text):
        self.lbl_text.setText(text)
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

# === 主窗口 ===
class MainWindow(QMainWindow):
    def __init__(self, logic_controller):
        super().__init__()
        self.logic = logic_controller
        self.cfg = ConfigManager()
        self.ls = LanguageService()
        
        self.setWindowTitle(self.ls.tr("app_title"))
        self.resize(1000, 750)
        
        self.setStyleSheet(Theme.GLOBAL_STYLES)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # === 1. 左侧导航 ===
        nav_bar = QWidget()
        nav_bar.setFixedWidth(200)
        nav_bar.setStyleSheet(f"background-color: {Theme.COLOR_SURFACE};")
        nav_layout = QVBoxLayout(nav_bar)
        nav_layout.setContentsMargins(0, 20, 0, 20)
        nav_layout.setSpacing(10)

        lbl_logo = QLabel("POLYGLOT")
        lbl_logo.setAlignment(Qt.AlignCenter)
        lbl_logo.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {Theme.COLOR_PRIMARY}; letter-spacing: 2px;")
        nav_layout.addWidget(lbl_logo)
        nav_layout.addSpacing(20)

        self.btn_home = NavButton(self.ls.tr("nav_dashboard"), "📊")
        self.btn_settings = NavButton(self.ls.tr("nav_settings"), "⚙️")
        self.btn_logs = NavButton(self.ls.tr("nav_logs"), "📝")
        
        self.btn_home.clicked.connect(lambda: self.switch_page(0))
        self.btn_settings.clicked.connect(lambda: self.switch_page(1))
        self.btn_logs.clicked.connect(lambda: self.switch_page(2))

        nav_layout.addWidget(self.btn_home)
        nav_layout.addWidget(self.btn_settings)
        nav_layout.addWidget(self.btn_logs)
        nav_layout.addStretch()
        
        lbl_ver = QLabel("v2.4 Anti-Scroll")
        lbl_ver.setAlignment(Qt.AlignCenter)
        lbl_ver.setStyleSheet("color: #555; font-size: 12px;")
        nav_layout.addWidget(lbl_ver)

        main_layout.addWidget(nav_bar)

        # === 2. 内容区 ===
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(20)

        header_layout = QHBoxLayout()
        self.status_badge = StatusBadge()
        self.status_badge.set_status(self.ls.tr("status_ready"), Theme.COLOR_TEXT_SUB)
        header_layout.addWidget(self.status_badge)
        header_layout.addStretch()
        content_layout.addLayout(header_layout)

        self.pages = QStackedWidget()
        self.page_home = self.init_home_page()
        self.page_settings = self.init_settings_page()
        self.page_logs = self.init_log_page()
        
        self.pages.addWidget(self.page_home)
        self.pages.addWidget(self.page_settings)
        self.pages.addWidget(self.page_logs)
        
        content_layout.addWidget(self.pages)
        main_layout.addWidget(content_area)

        self.btn_home.setChecked(True)
        self.pages.setCurrentIndex(0)
        
        self.overlay = OverlayWindow()
        self.overlay.show()

    def switch_page(self, index):
        self.pages.setCurrentIndex(index)
        self.btn_home.setChecked(index == 0)
        self.btn_settings.setChecked(index == 1)
        self.btn_logs.setChecked(index == 2)

    # --- 仪表盘 ---
    def init_home_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        monitor_card = SettingCard(self.ls.tr("card_monitor"))
        
        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setPlaceholderText(self.ls.tr("placeholder_monitor"))
        self.txt_preview.setStyleSheet(f"""
            border: none; 
            background-color: transparent; 
            font-size: 16px; 
            color: {Theme.COLOR_TEXT_MAIN};
        """)
        monitor_card.add_widget(self.txt_preview)
        
        layout.addWidget(monitor_card, 2)
        
        control_card = SettingCard(self.ls.tr("card_quick_actions"))
        h_layout = QHBoxLayout()
        
        self.btn_toggle_mic = QPushButton(self.ls.tr("btn_toggle_rec"))
        self.btn_toggle_mic.clicked.connect(lambda: self.logic.hotkey.req_toggle_rec.emit())
        self.btn_toggle_mic.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.COLOR_PRIMARY}; color: white; border: none; border-radius: 6px; padding: 10px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #2980b9; }}
        """)
        
        self.btn_force_send = QPushButton(self.ls.tr("btn_force_send"))
        self.btn_force_send.clicked.connect(lambda: self.logic.hotkey.req_send.emit())
        self.btn_force_send.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.COLOR_SURFACE_HOVER}; color: white; border: 1px solid #444; border-radius: 6px; padding: 10px;
            }}
            QPushButton:hover {{ background-color: #3e3e3e; }}
        """)

        h_layout.addWidget(self.btn_toggle_mic)
        h_layout.addWidget(self.btn_force_send)
        control_card.add_layout(h_layout)
        
        layout.addWidget(control_card, 1)
        return page

    # --- 设置页 ---
    def init_settings_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(20)

        # 0. 通用/语言
        card_gen = SettingCard(self.ls.tr("card_general"))
        f_gen = QFormLayout()
        
        # 使用 NoScrollComboBox
        self.combo_lang = NoScrollComboBox()
        self.combo_lang.addItem(self.ls.tr("opt_lang_auto"), "auto")
        self.combo_lang.addItem("English", "en_US")
        self.combo_lang.addItem("简体中文", "zh_CN")
        
        curr_lang = self.cfg.get("app_lang")
        idx_lang = self.combo_lang.findData(curr_lang)
        self.combo_lang.setCurrentIndex(max(0, idx_lang))
        
        f_gen.addRow(self.ls.tr("lbl_interface_lang"), self.combo_lang)
        f_gen.addRow("", QLabel(f"<font color='gray'>{self.ls.tr('tip_lang_restart')}</font>"))
        card_gen.add_layout(f_gen)
        layout.addWidget(card_gen)

        # 1. 核心模型
        card_core = SettingCard(self.ls.tr("card_core"))
        f_core = QFormLayout()
        
        # 使用 NoScrollComboBox
        self.combo_stt = NoScrollComboBox()
        self.combo_stt.addItem("Faster-Whisper (Offline/Stable)", "faster_whisper")
        self.combo_stt.addItem("FunASR (FunAudioLLM/High-Acc)", "funasr")
        idx = self.combo_stt.findData(self.cfg.get("stt_engine"))
        self.combo_stt.setCurrentIndex(max(0, idx))
        
        f_core.addRow(self.ls.tr("lbl_stt_engine"), self.combo_stt)
        f_core.addRow("", QLabel(f"<font color='gray'>{self.ls.tr('tip_restart')}</font>"))
        card_core.add_layout(f_core)
        layout.addWidget(card_core)

        # 2. 音频
        card_audio = SettingCard(self.ls.tr("card_audio"))
        f_audio = QFormLayout()
        # 使用 NoScrollComboBox
        self.combo_mic = NoScrollComboBox()
        devices = self.logic.audio.get_input_devices()
        cur_mic = self.cfg.get("mic_index")
        self.combo_mic.addItem("Default Device", 0)
        sel_idx = 0
        for i, (idx, name) in enumerate(devices):
            self.combo_mic.addItem(f"{idx}: {name}", idx)
            if idx == cur_mic: sel_idx = i + 1
        self.combo_mic.setCurrentIndex(sel_idx)
        f_audio.addRow(self.ls.tr("lbl_mic"), self.combo_mic)
        card_audio.add_layout(f_audio)
        layout.addWidget(card_audio)

        # 3. 悬浮窗
        card_overlay = SettingCard(self.ls.tr("card_overlay"))
        g_overlay = QGridLayout()
        
        self.chk_lock = QCheckBox(self.ls.tr("chk_lock_overlay"))
        self.chk_lock.setChecked(self.cfg.get("overlay_locked"))
        self.chk_lock.toggled.connect(self.update_overlay_style)
        
        # 使用 NoScrollSpinBox 和 NoScrollSlider
        self.spin_w = NoScrollSpinBox(); self.spin_w.setRange(200, 1920); self.spin_w.setValue(self.cfg.get("overlay_width"))
        self.spin_h = NoScrollSpinBox(); self.spin_h.setRange(50, 1080); self.spin_h.setValue(self.cfg.get("overlay_height"))
        self.spin_w.valueChanged.connect(self.update_overlay_style)
        self.spin_h.valueChanged.connect(self.update_overlay_style)
        
        self.slider_opacity = NoScrollSlider(Qt.Horizontal); self.slider_opacity.setRange(10, 100); self.slider_opacity.setValue(int(self.cfg.get("overlay_opacity") * 100))
        self.slider_opacity.valueChanged.connect(self.update_overlay_style)
        
        self.slider_border = NoScrollSlider(Qt.Horizontal); self.slider_border.setRange(0, 100); self.slider_border.setValue(int(self.cfg.get("overlay_border_alpha") * 100))
        self.slider_border.valueChanged.connect(self.update_overlay_style)
        
        self.spin_font = NoScrollSpinBox(); self.spin_font.setRange(10, 60); self.spin_font.setValue(self.cfg.get("overlay_font_size"))
        self.spin_font.valueChanged.connect(self.update_overlay_style)

        g_overlay.addWidget(self.chk_lock, 0, 0)
        g_overlay.addWidget(QLabel(self.ls.tr("lbl_width")), 1, 0); g_overlay.addWidget(self.spin_w, 1, 1)
        g_overlay.addWidget(QLabel(self.ls.tr("lbl_min_height")), 2, 0); g_overlay.addWidget(self.spin_h, 2, 1)
        g_overlay.addWidget(QLabel(self.ls.tr("lbl_opacity")), 3, 0); g_overlay.addWidget(self.slider_opacity, 3, 1)
        g_overlay.addWidget(QLabel(self.ls.tr("lbl_border")), 4, 0); g_overlay.addWidget(self.slider_border, 4, 1)
        g_overlay.addWidget(QLabel(self.ls.tr("lbl_font_size")), 5, 0); g_overlay.addWidget(self.spin_font, 5, 1)
        
        card_overlay.add_layout(g_overlay)
        layout.addWidget(card_overlay)

        # 4. API
        card_api = SettingCard(self.ls.tr("card_api"))
        f_api = QFormLayout()
        self.input_api_base = QLineEdit(self.cfg.get("api_base"))
        self.input_api_key = QLineEdit(self.cfg.get("api_key")); self.input_api_key.setEchoMode(QLineEdit.Password)
        self.input_model = QLineEdit(self.cfg.get("model"))
        
        f_api.addRow("API Base:", self.input_api_base)
        f_api.addRow("API Key:", self.input_api_key)
        f_api.addRow("Model:", self.input_model)
        
        l_box = QHBoxLayout()
        langs = self.cfg.get("langs") or {}
        self.chk_zh = QCheckBox("CN"); self.chk_zh.setChecked(langs.get("zh", True))
        self.chk_en = QCheckBox("EN"); self.chk_en.setChecked(langs.get("en", True))
        self.chk_ja = QCheckBox("JA"); self.chk_ja.setChecked(langs.get("ja", False))
        self.chk_ru = QCheckBox("RU"); self.chk_ru.setChecked(langs.get("ru", False))
        l_box.addWidget(self.chk_zh); l_box.addWidget(self.chk_en); l_box.addWidget(self.chk_ja); l_box.addWidget(self.chk_ru)
        l_box.addStretch()
        f_api.addRow(self.ls.tr("lbl_target_lang"), l_box)
        
        self.txt_tpl_display = QTextEdit()
        self.txt_tpl_display.setPlainText(self.cfg.get("tpl_display"))
        self.txt_tpl_display.setMaximumHeight(60)
        self.input_tpl_osc = QLineEdit(self.cfg.get("tpl_osc"))
        
        f_api.addRow(self.ls.tr("lbl_tpl_overlay"), self.txt_tpl_display)
        f_api.addRow(self.ls.tr("lbl_tpl_osc"), self.input_tpl_osc)
        
        card_api.add_layout(f_api)
        layout.addWidget(card_api)
        
        # 5. 快捷键
        card_key = SettingCard(self.ls.tr("card_hotkey"))
        f_key = QFormLayout()
        self.btn_hk_rec = HotkeyButton(self.cfg.get("hotkey_rec"), self.ls.tr("btn_set_hotkey"))
        self.btn_hk_send = HotkeyButton(self.cfg.get("hotkey_send"), self.ls.tr("btn_set_hotkey"))
        
        self.btn_hk_rec.key_changed.connect(lambda k: self.cfg.set("hotkey_rec", k))
        self.btn_hk_send.key_changed.connect(lambda k: self.cfg.set("hotkey_send", k))
        
        self.rb_hold = QRadioButton(self.ls.tr("opt_hold"))
        self.rb_toggle = QRadioButton(self.ls.tr("opt_toggle"))
        bg = QButtonGroup(self); bg.addButton(self.rb_hold); bg.addButton(self.rb_toggle)
        if self.cfg.get("rec_mode") == "hold": self.rb_hold.setChecked(True)
        else: self.rb_toggle.setChecked(True)
        
        self.chk_auto_send = QCheckBox(self.ls.tr("chk_auto_send"))
        self.chk_auto_send.setChecked(self.cfg.get("auto_send"))
        
        f_key.addRow(self.ls.tr("lbl_rec_hotkey"), self.btn_hk_rec)
        f_key.addRow(self.ls.tr("lbl_send_hotkey"), self.btn_hk_send)
        f_key.addRow(self.ls.tr("lbl_trigger_mode"), self.rb_hold)
        f_key.addRow("", self.rb_toggle)
        f_key.addRow("", self.chk_auto_send)
        
        card_key.add_layout(f_key)
        layout.addWidget(card_key)

        btn_save = QPushButton(self.ls.tr("btn_save"))
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {Theme.COLOR_SUCCESS}; color: white; border: none; border-radius: 6px; padding: 12px; font-size: 16px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #27ae60; }}
        """)
        btn_save.clicked.connect(self.save_settings)
        layout.addWidget(btn_save)
        layout.addStretch()

        scroll.setWidget(content)
        return scroll

    # --- 日志 ---
    def init_log_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        card = SettingCard(self.ls.tr("nav_logs"))
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet(f"""
            background-color: #000; color: #0f0; font-family: Consolas, monospace; font-size: 13px; border: none;
        """)
        card.add_widget(self.txt_log)
        
        layout.addWidget(card)
        return page

    # === 逻辑 ===
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
        
        # === 保存语言设置 ===
        old_lang = self.cfg.get("app_lang")
        new_lang = self.combo_lang.currentData()
        self.cfg.set("app_lang", new_lang)
        
        self.cfg.set("api_base", self.input_api_base.text().strip())
        self.cfg.set("api_key", self.input_api_key.text().strip())
        self.cfg.set("model", self.input_model.text().strip())
        self.cfg.set("auto_send", self.chk_auto_send.isChecked())
        self.cfg.set("mic_index", self.combo_mic.currentData())
        self.cfg.set("rec_mode", "hold" if self.rb_hold.isChecked() else "toggle")
        
        old_stt = self.cfg.get("stt_engine")
        new_stt = self.combo_stt.currentData()
        self.cfg.set("stt_engine", new_stt)
        
        langs = {
            "zh": self.chk_zh.isChecked(), "en": self.chk_en.isChecked(),
            "ja": self.chk_ja.isChecked(), "ru": self.chk_ru.isChecked(),
            "pinyin": True
        }
        self.cfg.set("langs", langs)
        self.cfg.set("tpl_display", self.txt_tpl_display.toPlainText())
        self.cfg.set("tpl_osc", self.input_tpl_osc.text())
        
        self.cfg.save()
        
        # 检查是否需要提示重启
        if old_stt != new_stt or old_lang != new_lang:
            QMessageBox.information(self, "Info", self.ls.tr("msg_restart_needed"))
        else:
            self.set_status(self.ls.tr("msg_save_success"), Theme.COLOR_SUCCESS)

    def log(self, text):
        self.txt_log.append(text)
        if self.pages.currentIndex() == 0:
            self.txt_preview.append(text)
            self.txt_preview.verticalScrollBar().setValue(self.txt_preview.verticalScrollBar().maximum())
        sb = self.txt_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_status(self, text, color):
        self.status_badge.set_status(text, color)
        ov_color = Theme.COLOR_SUCCESS
        if "Record" in text or "录音" in text: ov_color = Theme.COLOR_ERROR
        elif "Trans" in text or "翻译" in text or "识别" in text: ov_color = Theme.COLOR_WARNING
        elif "Error" in text or "错误" in text: ov_color = Theme.COLOR_ERROR
        self.overlay.update_status(text, ov_color)