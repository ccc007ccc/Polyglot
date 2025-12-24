import sys
import os
import threading
import qdarktheme
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer # 导入 QTimer

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
        
        # 初始化 VR 服务对象，但暂时不启动 (Start later)
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
        
        self.audio.log_signal.connect(self.window.log)
        self.audio.status_signal.connect(self.window.set_status)
        self.audio.result_signal.connect(self.on_audio_result)
        
        self.translator.finished_signal.connect(self.on_translation_done)
        self.translator.log_signal.connect(self.window.log)

        self.pending_osc = ""
        
        # 注意：这里不再直接调用 self.vr_service.start()

    def on_ffmpeg_ready(self, success):
        if success:
            self.window.log(self.ls.tr("log_env_pass"))
            threading.Thread(target=self.audio.init_engine).start()
        else:
            self.window.log(self.ls.tr("log_env_fail"))

    # === VR 延迟启动逻辑 ===
    def start_services(self):
        """在主界面显示后调用，防止启动卡死"""
        if self.cfg.get("enable_steamvr"):
            self.window.log("正在尝试连接 SteamVR...")
            # 这里的 start 内部包含 openvr.init，可能会有短暂阻塞，
            # 但因为界面已经显示，用户体验会好很多
            self.vr_service.start()
            if self.vr_service.is_running:
                self.window.log("SteamVR Overlay 已启动")
            else:
                self.window.log("SteamVR 启动失败或未运行")

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
        preview_text = f"{self.ls.tr('status_translating')}\n{text}"
        self.window.overlay.update_content(preview_text)
        self.vr_service.update_content(text, "Transcribing...", False)
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
            send_key = self.cfg.get('hotkey_send')
            self.window.set_status(self.ls.tr("status_wait_send").format(send_key), "#3498db")
            self.vr_service.update_content(disp_msg, "DONE", False)

    def run(self):
        self.window.show()
        
        # [关键修改] 延迟 1 秒启动 VR 服务
        # 确保窗口已经渲染出来，避免 openvr.init 阻塞导致白屏
        QTimer.singleShot(1000, self.start_services)
        
        ret = self.app.exec()
        self.hotkey.stop()
        self.vr_service.stop()
        sys.exit(ret)

if __name__ == "__main__":
    controller = AppController()
    controller.run()