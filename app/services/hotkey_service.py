import threading
import time
import keyboard
from PySide6.QtCore import QObject, Signal
from app.config import ConfigManager

class HotkeyService(QObject):
    req_start_rec = Signal()
    req_stop_rec = Signal()
    req_toggle_rec = Signal()
    req_send = Signal()

    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager()
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _poll_loop(self):
        last_rec_state = False
        last_send_state = False

        while self.running:
            try:
                time.sleep(0.05)
                rec_key = self.cfg.get("hotkey_rec")
                send_key = self.cfg.get("hotkey_send")
                mode = self.cfg.get("rec_mode")

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
