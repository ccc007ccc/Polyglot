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
from app.services.lang_service import LanguageService
from app.services.vr_service import VRService  # [新增] 导入 VR 服务

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
        
        # [新增] 初始化 VR 服务
        self.vr_service = VRService()
        
        self.window = MainWindow(self)
        
        self.ffmpeg.progress_signal.connect(self.window.log)
        self.ffmpeg.finished_signal.connect(self.on_ffmpeg_ready)
        self.ffmpeg.start()
        
        # 快捷键/热键连接
        self.hotkey.req_start_rec.connect(self.on_req_start)
        self.hotkey.req_stop_rec.connect(self.on_req_stop)
        self.hotkey.req_toggle_rec.connect(self.on_req_toggle)
        self.hotkey.req_send.connect(self.on_req_send)
        
        # [新增] VR 界面交互事件连接
        self.vr_service.req_toggle_rec.connect(self.on_req_toggle)
        self.vr_service.req_send.connect(self.on_req_send)
        
        # 音频服务信号连接
        self.audio.log_signal.connect(self.window.log)
        self.audio.status_signal.connect(self.window.set_status)
        self.audio.result_signal.connect(self.on_audio_result)
        
        # 翻译服务信号连接
        self.translator.finished_signal.connect(self.on_translation_done)
        self.translator.log_signal.connect(self.window.log)

        self.pending_osc = ""
        
        # [新增] 尝试启动 VR 服务 (内部会检查配置是否开启)
        self.vr_service.start()

    def on_ffmpeg_ready(self, success):
        if success:
            self.window.log(self.ls.tr("log_env_pass"))
            threading.Thread(target=self.audio.init_engine).start()
        else:
            self.window.log(self.ls.tr("log_env_fail"))

    def on_req_start(self): 
        if not self.audio.is_recording:
            msg = self.ls.tr("status_listening")
            self.window.overlay.update_content(msg)
            
            # [新增] 同步更新 VR 状态
            self.vr_service.update_content(msg, "REC", True)
            
            self.audio.start_record()

    def on_req_stop(self):
        if self.audio.is_recording: 
            self.audio.stop_record()
            # [新增] 同步更新 VR 状态
            self.vr_service.update_content("Processing...", "WAIT", False)

    def on_req_toggle(self):
        if not self.audio.is_recording:
            msg = self.ls.tr("status_listening")
            self.window.overlay.update_content(msg)
            # [新增] 开始录音状态
            self.vr_service.update_content(msg, "REC", True)
        else:
            # [新增] 停止录音状态
            self.vr_service.update_content("Processing...", "WAIT", False)
            
        self.audio.toggle_record()

    def on_req_send(self):
        if self.pending_osc:
            self.translator.send_osc(self.pending_osc)
            self.window.set_status(self.ls.tr("status_manual_sent"), "#2ecc71")
            
            formatted_osc = self.pending_osc.replace("\\n", "\n")
            self.window.overlay.update_content(formatted_osc)
            
            # [新增] 同步 VR 显示发送内容
            self.vr_service.update_content(formatted_osc, "SENT", False)

    def on_audio_result(self, text):
        self.window.log(self.ls.tr("log_trans_result").format(text))
        
        # 原文预览
        preview_text = f"{self.ls.tr('status_translating')}\n{text}"
        self.window.overlay.update_content(preview_text)
        
        # [新增] 同步 VR 显示识别原文
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
            
            # [新增] 自动发送时同步 VR
            self.vr_service.update_content(formatted_osc, "SENT", False)
        else:
            self.window.overlay.update_content(disp_msg)
            
            send_key = self.cfg.get('hotkey_send')
            self.window.set_status(self.ls.tr("status_wait_send").format(send_key), "#3498db")
            
            # [新增] 等待发送时同步 VR
            self.vr_service.update_content(disp_msg, "DONE", False)

    def run(self):
        self.window.show()
        ret = self.app.exec()
        self.hotkey.stop()
        # [新增] 停止 VR 服务
        self.vr_service.stop()
        sys.exit(ret)

if __name__ == "__main__":
    controller = AppController()
    controller.run()