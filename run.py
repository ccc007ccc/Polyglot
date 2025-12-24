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
    def __init__(self):
        self.app = QApplication(sys.argv)
        qdarktheme.setup_theme("dark")
        self.cfg = ConfigManager()
        self.ls = LanguageService()
        
        self.ffmpeg = FFmpegInstaller()
        self.audio = AudioService()
        self.hotkey = HotkeyService()
        self.translator = TranslationService()
        
        self.vr_service = SteamVRService()
        
        self.window = MainWindow(self)
        
        self.ffmpeg.progress_signal.connect(self.window.log)
        self.ffmpeg.finished_signal.connect(self.on_ffmpeg_ready)
        self.ffmpeg.start()
        
        self.hotkey.req_start_rec.connect(self.on_req_start)
        self.hotkey.req_stop_rec.connect(self.on_req_stop)
        self.hotkey.req_toggle_rec.connect(self.on_req_toggle)
        self.hotkey.req_send.connect(self.on_req_send)
        
        self.vr_service.req_toggle_rec.connect(self.on_req_toggle)
        self.vr_service.req_send.connect(self.on_req_send)
        # [Fix 1] 连接 VR 状态信号，而非轮询
        self.vr_service.sig_connection_status.connect(self.on_vr_status)
        
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

    # [Fix 1] 移除 start_services 中的判断，改为只负责启动
    def start_services(self):
        if self.cfg.get("enable_steamvr"):
            self.window.log(self.ls.tr("log_vr_connecting"))
            self.vr_service.start()

    # [Fix 1] 新增回调处理真实的连接结果
    def on_vr_status(self, success, msg):
        if success:
            self.window.log(self.ls.tr("log_vr_success"))
        else:
            self.window.log(self.ls.tr("log_vr_fail").format(msg))

    def on_req_start(self): 
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
        if not self.audio.is_recording:
            msg = self.ls.tr("status_listening")
            self.window.overlay.update_content(msg)
            self.vr_service.update_content(msg, "REC", True)
        else:
            self.vr_service.update_content("Processing...", "WAIT", False)
        self.audio.toggle_record()

    def on_req_send(self):
        if self.pending_osc:
            self.translator.send_osc(self.pending_osc)
            self.window.set_status(self.ls.tr("status_manual_sent"), "#2ecc71")
            formatted_osc = self.pending_osc.replace("\\n", "\n")
            self.window.overlay.update_content(formatted_osc)
            self.vr_service.update_content(formatted_osc, "SENT", False)

    def on_audio_result(self, text):
        self.window.log(self.ls.tr("log_trans_result").format(text))
        
        # [Fix 2] 统一格式，确保 PC 和 VR 看到的内容一致
        preview_text = f"{self.ls.tr('status_translating')}\n{text}"
        
        self.window.overlay.update_content(preview_text)
        # 以前是 update_content(text)，现在统一为 preview_text
        self.vr_service.update_content(preview_text, "Transcribing...", False)
        
        self.window.set_status(self.ls.tr("status_translating"), "#f39c12")
        self.translator.process(text)

    def on_translation_done(self, osc_msg, disp_msg):
        self.pending_osc = osc_msg
        self.window.log(self.ls.tr("log_trans_complete"))
        
        # [Fix 2] 统一使用 disp_msg (清洗过的显示文本)
        if self.cfg.get("auto_send"):
            self.translator.send_osc(osc_msg)
            self.window.set_status(self.ls.tr("status_auto_sent"), "#2ecc71")
            
            formatted_osc = osc_msg.replace("\\n", "\n")
            self.window.overlay.update_content(formatted_osc)
            self.vr_service.update_content(formatted_osc, "SENT", False)
        else:
            self.window.overlay.update_content(disp_msg)
            # 确保 VR 也显示完整的翻译结果
            self.vr_service.update_content(disp_msg, "DONE", False)
            
            send_key = self.cfg.get('hotkey_send')
            self.window.set_status(self.ls.tr("status_wait_send").format(send_key), "#3498db")

    def run(self):
        self.window.show()
        # 延迟启动服务，防止 UI 未渲染导致的卡顿
        QTimer.singleShot(1000, self.start_services)
        
        ret = self.app.exec()
        self.hotkey.stop()
        self.vr_service.stop()
        sys.exit(ret)

if __name__ == "__main__":
    controller = AppController()
    controller.run()