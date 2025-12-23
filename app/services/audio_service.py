import os
import wave
import threading
import pyaudio
import winsound
from PySide6.QtCore import QObject, Signal

from app.config import ConfigManager, TEMP_AUDIO
from app.plugins.stt import create_stt_engine
from app.services.lang_service import LanguageService # 导入

class AudioService(QObject):
    log_signal = Signal(str)
    status_signal = Signal(str, str)
    result_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager()
        self.ls = LanguageService() # 实例化
        self.audio = pyaudio.PyAudio()
        self.is_recording = False
        self.frames = []
        
        self.stt_engine = create_stt_engine(self.cfg.data)

    def get_input_devices(self):
        devices = []
        try:
            info = self.audio.get_host_api_info_by_index(0)
            numdevices = info.get('deviceCount')
            for i in range(0, numdevices):
                dev = self.audio.get_device_info_by_host_api_device_index(0, i)
                if dev.get('maxInputChannels') > 0:
                    name = dev.get('name')
                    try: name = name.encode('cp1252').decode('gbk')
                    except: pass
                    devices.append((i, name))
        except Exception as e:
            print(f"Get devices error: {e}")
        return devices

    def init_engine(self):
        # 使用 tr()
        self.log_signal.emit(self.ls.tr("log_init_engine"))
        try:
            self.stt_engine.initialize()
            if self.stt_engine.is_ready():
                self.log_signal.emit(self.ls.tr("log_engine_loaded"))
                hk = self.cfg.get('hotkey_rec')
                # 格式化字符串
                self.status_signal.emit(self.ls.tr("status_ready_hint").format(hk), "#27ae60")
            else:
                raise Exception("Init failed")
        except Exception as e:
            self.log_signal.emit(self.ls.tr("log_engine_fail").format(e))
            self.status_signal.emit(self.ls.tr("status_engine_error"), "#c0392b")

    def start_record(self):
        if not self.stt_engine.is_ready(): 
            return
        if self.is_recording: return

        self.is_recording = True
        self.frames = []
        # 使用 tr()
        self.status_signal.emit(self.ls.tr("status_listening"), "#e74c3c")
        
        if self.cfg.get("sound_cues"): winsound.Beep(800, 100)
        threading.Thread(target=self._record_loop, daemon=True).start()

    def stop_record(self):
        if not self.is_recording: return
        self.is_recording = False
        
        if self.cfg.get("sound_cues"): winsound.Beep(500, 100)
        # 使用 tr()
        self.status_signal.emit(self.ls.tr("status_processing"), "#f39c12")
        threading.Thread(target=self._process_audio, daemon=True).start()
    
    def toggle_record(self):
        if self.is_recording: self.stop_record()
        else: self.start_record()

    def _record_loop(self):
        stream = None
        try:
            mic_index = self.cfg.get("mic_index")
            stream = self.audio.open(
                format=pyaudio.paInt16, channels=1, rate=16000, 
                input=True, input_device_index=mic_index, frames_per_buffer=1024
            )
            while self.is_recording:
                data = stream.read(1024, exception_on_overflow=False)
                self.frames.append(data)
        except Exception as e:
            self.log_signal.emit(f"Mic Error: {e}")
        finally:
            if stream:
                stream.stop_stream()
                stream.close()

    def _process_audio(self):
        if not self.frames or len(self.frames) < 5: 
            self.status_signal.emit(self.ls.tr("status_too_short"), "#7f8c8d")
            return

        try:
            wf = wave.open(TEMP_AUDIO, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(16000)
            wf.writeframes(b''.join(self.frames))
            wf.close()
            
            text = self.stt_engine.transcribe(TEMP_AUDIO)
            
            if text:
                self.log_signal.emit(self.ls.tr("log_trans_result").format(text))
                self.result_signal.emit(text)
            else:
                self.log_signal.emit(self.ls.tr("status_no_speech"))
                self.status_signal.emit(self.ls.tr("status_no_speech"), "#7f8c8d")
                
        except Exception as e:
            self.log_signal.emit(f"Process Error: {e}")
            self.status_signal.emit(self.ls.tr("status_engine_error"), "#c0392b")
        finally:
            if os.path.exists(TEMP_AUDIO):
                try: os.remove(TEMP_AUDIO)
                except: pass