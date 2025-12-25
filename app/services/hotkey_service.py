import time
import keyboard
from PySide6.QtCore import QObject, Signal, QThread

class HotkeyWorker(QThread):
    """
    独立的按键监听线程，防止阻塞 UI
    """
    req_start_rec = Signal()
    req_stop_rec = Signal()
    req_toggle_rec = Signal()
    req_send = Signal()

    def __init__(self, config_manager):
        super().__init__()
        self.cfg = config_manager
        self.running = True

    def run(self):
        last_rec_state = False
        last_send_state = False

        while self.running:
            try:
                time.sleep(0.05)
                rec_key = self.cfg.get("hotkey_rec")
                send_key = self.cfg.get("hotkey_send")
                mode = self.cfg.get("rec_mode")

                # 检测录音键
                is_rec_pressed = False
                try:
                    if rec_key and keyboard.is_pressed(rec_key):
                        is_rec_pressed = True
                except: pass

                if mode == "hold":
                    if is_rec_pressed and not last_rec_state:
                        self.req_start_rec.emit()
                    elif not is_rec_pressed and last_rec_state:
                        self.req_stop_rec.emit()
                else:
                    if is_rec_pressed and not last_rec_state:
                        self.req_toggle_rec.emit()
                
                last_rec_state = is_rec_pressed

                # 检测发送键
                is_send_pressed = False
                try:
                    if send_key and keyboard.is_pressed(send_key):
                        is_send_pressed = True
                except: pass

                if is_send_pressed and not last_send_state:
                    self.req_send.emit()
                
                last_send_state = is_send_pressed

            except Exception as e:
                print(f"Hotkey Poll Error: {e}")
                time.sleep(1)

    def stop(self):
        self.running = False
        self.wait()

class HotkeyService(QObject):
    # 转发 Worker 信号
    req_start_rec = Signal()
    req_stop_rec = Signal()
    req_toggle_rec = Signal()
    req_send = Signal()

    def __init__(self, config_manager):
        super().__init__()
        self.worker = HotkeyWorker(config_manager)
        
        # 信号连接
        self.worker.req_start_rec.connect(self.req_start_rec)
        self.worker.req_stop_rec.connect(self.req_stop_rec)
        self.worker.req_toggle_rec.connect(self.req_toggle_rec)
        self.worker.req_send.connect(self.req_send)
        
        self.worker.start()

    def stop(self):
        self.worker.stop()