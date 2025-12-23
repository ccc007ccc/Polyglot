import sys
import os
import threading
import qdarktheme
from PySide6.QtWidgets import QApplication

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.ui.main_window import MainWindow
from app.services.dep_installer import FFmpegInstaller
from app.services.audio_service import AudioService
from app.services.hotkey_service import HotkeyService
from app.services.trans_service import TranslationService
from app.config import ConfigManager
from app.services.lang_service import LanguageService # 导入

class AppController:
    def __init__(self):
        self.app = QApplication(sys.argv)
        qdarktheme.setup_theme("dark")
        self.cfg = ConfigManager()
        self.ls = LanguageService() # 实例化
        
        self.ffmpeg = FFmpegInstaller()
        self.audio = AudioService()
        self.hotkey = HotkeyService()
        self.translator = TranslationService()
        
        self.window = MainWindow(self)
        
        self.ffmpeg.progress_signal.connect(self.window.log)
        self.ffmpeg.finished_signal.connect(self.on_ffmpeg_ready)
        self.ffmpeg.start()
        
        self.hotkey.req_start_rec.connect(self.on_req_start)
        self.hotkey.req_stop_rec.connect(self.on_req_stop)
        self.hotkey.req_toggle_rec.connect(self.on_req_toggle)
        self.hotkey.req_send.connect(self.on_req_send)
        
        self.audio.log_signal.connect(self.window.log)
        self.audio.status_signal.connect(self.window.set_status)
        self.audio.result_signal.connect(self.on_audio_result)
        
        self.translator.finished_signal.connect(self.on_translation_done)
        self.translator.log_signal.connect(self.window.log)

        self.pending_osc = ""

    def on_ffmpeg_ready(self, success):
        if success:
            self.window.log(self.ls.tr("log_env_pass"))
            threading.Thread(target=self.audio.init_engine).start()
        else:
            self.window.log(self.ls.tr("log_env_fail"))

    def on_req_start(self): 
        if not self.audio.is_recording:
            # 使用 tr()
            self.window.overlay.update_content(self.ls.tr("status_listening"))
            self.audio.start_record()

    def on_req_stop(self):
        if self.audio.is_recording: self.audio.stop_record()

    def on_req_toggle(self):
        if not self.audio.is_recording:
            # 使用 tr()
            self.window.overlay.update_content(self.ls.tr("status_listening"))
        self.audio.toggle_record()

    def on_req_send(self):
        if self.pending_osc:
            self.translator.send_osc(self.pending_osc)
            self.window.set_status(self.ls.tr("status_manual_sent"), "#2ecc71")
            
            formatted_osc = self.pending_osc.replace("\\n", "\n")
            self.window.overlay.update_content(formatted_osc)

    def on_audio_result(self, text):
        self.window.log(self.ls.tr("log_trans_result").format(text))
        
        # 原文预览
        preview_text = f"{self.ls.tr('status_translating')}\n{text}"
        self.window.overlay.update_content(preview_text)
        
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
        else:
            self.window.overlay.update_content(disp_msg)
            
            send_key = self.cfg.get('hotkey_send')
            self.window.set_status(self.ls.tr("status_wait_send").format(send_key), "#3498db")

    def run(self):
        self.window.show()
        ret = self.app.exec()
        self.hotkey.stop()
        sys.exit(ret)

if __name__ == "__main__":
    controller = AppController()
    controller.run()