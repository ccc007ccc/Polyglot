import sys
import qdarktheme
from PySide6.QtWidgets import QApplication
from ui import MainWindow
from services import FFmpegWorker, AudioService, HotkeyService, TranslationService
from config import ConfigManager

class AppController:
    def __init__(self):
        self.app = QApplication(sys.argv)
        qdarktheme.setup_theme("dark")
        self.cfg = ConfigManager()
        
        # 初始化服务
        self.ffmpeg = FFmpegWorker()
        self.audio = AudioService()
        self.hotkey = HotkeyService()
        self.translator = TranslationService()
        
        # 初始化 UI
        self.window = MainWindow(self)
        
        # === 信号连接 ===
        
        # FFmpeg
        self.ffmpeg.progress_signal.connect(self.window.log)
        self.ffmpeg.finished_signal.connect(self.on_ffmpeg_ready)
        self.ffmpeg.start()
        
        # 快捷键 -> 音频
        self.hotkey.req_start_rec.connect(self.on_req_start)
        self.hotkey.req_stop_rec.connect(self.on_req_stop)
        self.hotkey.req_toggle_rec.connect(self.on_req_toggle)
        self.hotkey.req_send.connect(self.on_req_send)
        
        # 音频 -> UI & 翻译
        self.audio.log_signal.connect(self.window.log)
        self.audio.status_signal.connect(self.window.set_status)
        self.audio.result_signal.connect(self.on_audio_result)
        
        # 翻译 -> UI & OSC
        self.translator.finished_signal.connect(self.on_translation_done)
        self.translator.log_signal.connect(self.window.log)

        self.pending_osc = ""

    def on_ffmpeg_ready(self, success):
        if success:
            self.window.log("FFmpeg 检查通过，正在初始化 AI 模型...")
            import threading
            threading.Thread(target=self.audio.init_model).start()
        else:
            self.window.log("FFmpeg 缺失，程序无法工作。")

    # === 控制逻辑 ===
    def on_req_start(self):
        if not self.audio.is_recording: self.audio.start_record()

    def on_req_stop(self):
        if self.audio.is_recording: self.audio.stop_record()

    def on_req_toggle(self):
        self.audio.toggle_record()

    def on_audio_result(self, text):
        self.window.log(f"识别原文: {text}")
        
        # === 修复文字不刷新的 BUG ===
        # 在开始翻译之前，立刻把识别到的中文原文显示在悬浮窗上
        self.window.overlay.update_content(f"正在翻译...\n原文: {text}")
        self.window.set_status("正在翻译...", "#f39c12")
        
        # 开始翻译
        self.translator.process(text)

    def on_translation_done(self, osc_msg, disp_msg):
        self.pending_osc = osc_msg
        
        # 更新悬浮窗为最终翻译结果
        self.window.overlay.update_content(disp_msg)
        self.window.log("翻译完成")
        
        if self.cfg.get("auto_send"):
            self.translator.send_osc(osc_msg)
            self.window.set_status("✅ 已自动发送", "#2ecc71")
        else:
            self.window.set_status(f"等待发送 (按 {self.cfg.get('hotkey_send')})", "#3498db")

    def on_req_send(self):
        if self.pending_osc:
            self.translator.send_osc(self.pending_osc)
            self.window.set_status("✅ 已手动发送", "#2ecc71")

    def run(self):
        self.window.show()
        ret = self.app.exec()
        self.hotkey.stop() 
        sys.exit(ret)

if __name__ == "__main__":
    controller = AppController()
    controller.run()