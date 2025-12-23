import sys
import os
import threading
import qdarktheme
from PySide6.QtWidgets import QApplication

# 确保能找到 app 包
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.ui.main_window import MainWindow
from app.services.dep_installer import FFmpegInstaller
from app.services.audio_service import AudioService
from app.services.hotkey_service import HotkeyService
from app.services.trans_service import TranslationService
from app.config import ConfigManager

class AppController:
    def __init__(self):
        self.app = QApplication(sys.argv)
        qdarktheme.setup_theme("dark")
        self.cfg = ConfigManager()
        
        # 服务实例化
        self.ffmpeg = FFmpegInstaller()
        self.audio = AudioService()
        self.hotkey = HotkeyService()
        self.translator = TranslationService()
        
        # UI 实例化
        self.window = MainWindow(self)
        
        # === 信号连接 ===
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
            self.window.log("环境检查通过，启动 AI 引擎...")
            threading.Thread(target=self.audio.init_engine).start()
        else:
            self.window.log("关键组件缺失，请检查网络或日志。")

    def on_req_start(self): 
        if not self.audio.is_recording:
            # 开始录音时清空悬浮窗
            self.window.overlay.update_content("🎤 正在聆听...")
            self.audio.start_record()

    def on_req_stop(self):
        if self.audio.is_recording: self.audio.stop_record()

    def on_req_toggle(self):
        if not self.audio.is_recording:
            self.window.overlay.update_content("🎤 正在聆听...")
        self.audio.toggle_record()

    def on_req_send(self):
        # === 手动发送逻辑 ===
        if self.pending_osc:
            self.translator.send_osc(self.pending_osc)
            self.window.set_status("✅ 已手动发送", "#2ecc71")
            
            # 手动发送后，也将悬浮窗更新为 OSC 内容
            # 将字符串中的字面量 "\n" 转换为实际换行符
            formatted_osc = self.pending_osc.replace("\\n", "\n")
            self.window.overlay.update_content(formatted_osc)

    def on_audio_result(self, text):
        self.window.log(f"识别原文: {text}")
        self.window.overlay.update_content(f"正在翻译...\n原文: {text}")
        self.window.set_status("正在翻译...", "#f39c12")
        self.translator.process(text)

    def on_translation_done(self, osc_msg, disp_msg):
        self.pending_osc = osc_msg
        self.window.log("翻译完成")
        
        if self.cfg.get("auto_send"):
            # === 自动发送模式 ===
            self.translator.send_osc(osc_msg)
            self.window.set_status("✅ 已自动发送", "#2ecc71")
            
            # 发送后，直接显示 OSC 内容
            formatted_osc = osc_msg.replace("\\n", "\n")
            self.window.overlay.update_content(formatted_osc)
        else:
            # === 等待发送模式 ===
            # 先显示预览模板 (disp_msg)
            self.window.overlay.update_content(disp_msg)
            
            send_key = self.cfg.get('hotkey_send')
            self.window.set_status(f"等待发送 (按 {send_key})", "#3498db")

    def run(self):
        self.window.show()
        ret = self.app.exec()
        self.hotkey.stop()
        sys.exit(ret)

if __name__ == "__main__":
    controller = AppController()
    controller.run()