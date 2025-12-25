import sys
import os
import threading
import qdarktheme
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.ui.main_window import MainWindow
from app.services.dep_installer import FFmpegInstaller
from app.services.audio_service import AudioService
from app.services.hotkey_service import HotkeyService
from app.services.trans_service import TranslationService
from app.config import ConfigManager
from app.services.lang_service import LanguageService
from app.vr import SteamVRService 

class AppController:
    """
    App Controller (Composition Root)
    """
    def __init__(self):
        self.app = QApplication(sys.argv)
        qdarktheme.setup_theme("dark")
        
        self.cfg = ConfigManager()
        self.ls = LanguageService()
        
        self.ffmpeg = FFmpegInstaller()
        self.audio = AudioService(self.cfg, self.ls)
        self.hotkey = HotkeyService(self.cfg)
        self.translator = TranslationService(self.cfg, self.ls)
        self.vr_service = SteamVRService()
        
        self.window = MainWindow(self, self.cfg, self.ls)
        
        self._bind_signals()

        self.pending_osc = ""
        self.ffmpeg.start()

    def _bind_signals(self):
        self.ffmpeg.progress_signal.connect(self.window.log)
        self.ffmpeg.finished_signal.connect(self.on_ffmpeg_ready)
        
        self.hotkey.req_start_rec.connect(self.on_req_start)
        self.hotkey.req_stop_rec.connect(self.on_req_stop)
        self.hotkey.req_toggle_rec.connect(self.on_req_toggle)
        self.hotkey.req_send.connect(self.on_req_send)
        
        self.vr_service.req_toggle_rec.connect(self.on_req_toggle)
        self.vr_service.req_send.connect(self.on_req_send)
        self.vr_service.sig_connection_status.connect(self.on_vr_status)
        
        self.audio.log_signal.connect(self.window.log)
        
        # [Fix] 更改绑定：不再直接连 window.set_status，而是连到控制器逻辑，
        # 以便同时分发给 Window 和 VR
        self.audio.status_signal.connect(self.on_status_changed)
        
        self.audio.result_signal.connect(self.on_audio_result)
        
        self.translator.finished_signal.connect(self.on_translation_done)
        self.translator.log_signal.connect(self.window.log)

    def on_ffmpeg_ready(self, success):
        if success:
            self.window.log(self.ls.tr("log_env_pass"))
            threading.Thread(target=self.audio.init_engine, daemon=True).start()
        else:
            self.window.log(self.ls.tr("log_env_fail"))

    # [New] 统一的状态分发中心
    def on_status_changed(self, text, color):
        # 1. 更新 PC 界面
        self.window.set_status(text, color)
        
        # 2. 更新 VR 界面 (显示在顶部的状态栏)
        # 传入 (MainText, StatusText, isRecording)
        # 这里 MainText 传空字符串表示不改变当前主文本，只更新状态
        # 但 VRPanel.update_state 逻辑里如果 content_text 变了会重绘
        # 我们这里取巧一下：
        # 如果是 "Initializing..." 这种大状态，我们可能希望主文本也显示这个
        
        is_busy_state = "Init" in text or "Load" in text or "Wait" in text
        if is_busy_state:
            self.vr_service.update_content(text, "BUSY", False)
        else:
            # 对于普通状态更新（如 Ready），只更新右上角 Status，不改变主文本
            # 这里的实现取决于 VRPanel 的逻辑，暂时我们可以只更新 status_text
            # 为了不覆盖主文本，我们需要 VR Service 支持“保留原文本”
            # 现有的 update_content 是全覆盖。
            # 鉴于 init/reload 是重要状态，直接覆盖主文本是合理的。
            # 而 Ready 状态通常不需要特别显示在主文本区。
            pass

    def start_services(self):
        if self.cfg.get("enable_steamvr"):
            self.window.log(self.ls.tr("log_vr_connecting"))
            self.vr_service.start()

    def on_vr_status(self, success, msg):
        if success:
            self.window.log(self.ls.tr("log_vr_success"))
        else:
            self.window.log(self.ls.tr("log_vr_fail").format(msg))

    def on_req_start(self): 
        if not self.audio.is_ready(): 
            return

        if not self.audio.is_recording:
            msg = self.ls.tr("status_listening")
            self.window.overlay.update_content(msg)
            self.vr_service.update_content(msg, "REC", True)
            self.audio.start_record()

    def on_req_stop(self):
        if self.audio.is_recording: 
            self.audio.stop_record()
            self.vr_service.update_content("Processing...", "WAIT", False)

    def on_req_toggle(self):
        if not self.audio.is_ready():
            return
            
        if not self.audio.is_recording:
            self.on_req_start()
        else:
            self.on_req_stop()

    def on_req_send(self):
        if self.pending_osc:
            self.translator.send_osc(self.pending_osc)
            self.window.set_status(self.ls.tr("status_manual_sent"), "#2ecc71")
            formatted_osc = self.pending_osc.replace("\\n", "\n")
            self.window.overlay.update_content(formatted_osc)
            self.vr_service.update_content(formatted_osc, "SENT", False)

    def on_audio_result(self, text):
        preview_text = f"{self.ls.tr('status_translating')}\n{text}"
        
        self.window.log(self.ls.tr("log_trans_result").format(text))
        self.window.overlay.update_content(preview_text)
        self.vr_service.update_content(preview_text, "Transcribing...", False)
        
        self.window.set_status(self.ls.tr("status_translating"), "#f39c12")
        self.translator.process(text)

    def on_translation_done(self, osc_msg, disp_msg):
        self.pending_osc = osc_msg
        self.window.log(self.ls.tr("log_trans_complete"))
        
        if self.cfg.get("auto_send"):
            self.translator.send_osc(osc_msg)
            self.window.set_status(self.ls.tr("status_auto_sent"), "#2ecc71")
            
            formatted_osc = osc_msg.replace("\\n", "\n")
            self.window.overlay.update_content(formatted_osc)
            self.vr_service.update_content(formatted_osc, "SENT", False)
        else:
            self.window.overlay.update_content(disp_msg)
            self.vr_service.update_content(disp_msg, "DONE", False)
            
            send_key = self.cfg.get('hotkey_send')
            self.window.set_status(self.ls.tr("status_wait_send").format(send_key), "#3498db")

    def on_settings_saved(self):
        threading.Thread(target=self.audio.reload, daemon=True).start()

    def run(self):
        self.window.show()
        QTimer.singleShot(1000, self.start_services)
        ret = self.app.exec()
        
        self.hotkey.stop()
        self.vr_service.stop()
        sys.exit(ret)

if __name__ == "__main__":
    controller = AppController()
    controller.run()