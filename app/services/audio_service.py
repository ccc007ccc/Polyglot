import pyaudio
import winsound
import numpy as np
import traceback
from PySide6.QtCore import QObject, Signal, QThread, QMutex

from app.plugins.stt import create_stt_engine

class AudioRecorder(QThread):
    def __init__(self, input_device_index):
        super().__init__()
        self.input_device_index = input_device_index
        self.running = True
        self.frames = []
        self.audio = pyaudio.PyAudio()

    def run(self):
        stream = None
        try:
            stream = self.audio.open(
                format=pyaudio.paInt16, 
                channels=1, 
                rate=16000, 
                input=True, 
                input_device_index=self.input_device_index, 
                frames_per_buffer=1024
            )
            while self.running:
                data = stream.read(1024, exception_on_overflow=False)
                self.frames.append(data)
        except Exception as e:
            print(f"Recorder Error: {e}")
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            self.audio.terminate()

    def stop(self):
        self.running = False
        self.wait()
    
    def get_audio_data(self):
        return b''.join(self.frames)

class AudioProcessor(QThread):
    result_ready = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, audio_bytes, engine):
        super().__init__()
        self.audio_bytes = audio_bytes
        self.engine = engine

    def run(self):
        try:
            if not self.audio_bytes or len(self.audio_bytes) < 16000 * 2 * 0.2: 
                self.error_occurred.emit("too_short")
                return

            audio_np = np.frombuffer(self.audio_bytes, dtype=np.int16).flatten().astype(np.float32) / 32768.0
            
            text = self.engine.transcribe(audio_np)
            if text:
                self.result_ready.emit(text)
            else:
                self.error_occurred.emit("no_speech")
        except Exception as e:
            traceback.print_exc()
            self.error_occurred.emit(str(e))

class AudioService(QObject):
    log_signal = Signal(str)
    status_signal = Signal(str, str)
    result_signal = Signal(str)

    def __init__(self, config_manager, lang_service):
        super().__init__()
        self.cfg = config_manager
        self.ls = lang_service
        self.stt_engine = create_stt_engine(self.cfg.data)
        
        self.recorder_thread = None
        self.processor_thread = None
        self.is_recording = False
        self._pa = pyaudio.PyAudio()

    def __del__(self):
        if self._pa: self._pa.terminate()

    def is_ready(self):
        """检查引擎是否完全加载完毕"""
        return self.stt_engine and self.stt_engine.is_ready()

    def init_engine(self):
        self.log_signal.emit(self.ls.tr("log_init_engine"))
        # 初始状态设为黄色，表示加载中
        self.status_signal.emit(self.ls.tr("status_init"), "#f39c12")
        try:
            self.stt_engine.initialize()
            if self.stt_engine.is_ready():
                self.log_signal.emit(self.ls.tr("log_engine_loaded"))
                hk = self.cfg.get('hotkey_rec')
                self.status_signal.emit(self.ls.tr("status_ready_hint").format(hk), "#27ae60")
            else:
                raise Exception("Init failed")
        except Exception as e:
            self.log_signal.emit(self.ls.tr("log_engine_fail").format(e))
            self.status_signal.emit(self.ls.tr("status_engine_error"), "#c0392b")

    def reload(self):
        """热重载引擎 (不重启程序)"""
        self.log_signal.emit(self.ls.tr("log_reloading"))
        self.status_signal.emit(self.ls.tr("status_init"), "#f39c12")
        
        # 1. 停止当前所有操作
        if self.is_recording:
            self.stop_record()
        
        # 2. 重新创建引擎实例 (读取最新配置)
        try:
            # 旧引擎垃圾回收
            self.stt_engine = None 
            self.stt_engine = create_stt_engine(self.cfg.data)
            
            # 3. 重新初始化
            self.init_engine()
        except Exception as e:
            self.log_signal.emit(f"Reload Error: {e}")

    def get_input_devices(self):
        devices = []
        try:
            info = self._pa.get_host_api_info_by_index(0)
            numdevices = info.get('deviceCount')
            for i in range(0, numdevices):
                dev = self._pa.get_device_info_by_host_api_device_index(0, i)
                if dev.get('maxInputChannels') > 0:
                    name = dev.get('name')
                    try: name = name.encode('cp1252').decode('gbk')
                    except: pass
                    devices.append((i, name))
        except Exception as e:
            print(f"Get devices error: {e}")
        return devices

    def start_record(self):
        if not self.is_ready(): return
        if self.is_recording: return

        self.is_recording = True
        self.status_signal.emit(self.ls.tr("status_listening"), "#e74c3c")
        
        if self.cfg.get("sound_cues"): winsound.Beep(800, 100)
        
        mic_index = self.cfg.get("mic_index")
        self.recorder_thread = AudioRecorder(mic_index)
        self.recorder_thread.start()

    def stop_record(self):
        if not self.is_recording or not self.recorder_thread: return
        self.is_recording = False
        
        if self.cfg.get("sound_cues"): winsound.Beep(500, 100)
        self.status_signal.emit(self.ls.tr("status_processing"), "#f39c12")
        
        self.recorder_thread.stop()
        audio_data = self.recorder_thread.get_audio_data()
        self.recorder_thread = None

        self.processor_thread = AudioProcessor(audio_data, self.stt_engine)
        self.processor_thread.result_ready.connect(self._on_transcription_success)
        self.processor_thread.error_occurred.connect(self._on_transcription_error)
        self.processor_thread.finished.connect(self._on_processor_finished)
        self.processor_thread.start()
    
    def toggle_record(self):
        if self.is_recording: self.stop_record()
        else: self.start_record()

    def _on_transcription_success(self, text):
        self.log_signal.emit(self.ls.tr("log_trans_result").format(text))
        self.result_signal.emit(text)

    def _on_transcription_error(self, err_code):
        if err_code == "too_short":
            self.status_signal.emit(self.ls.tr("status_too_short"), "#7f8c8d")
        elif err_code == "no_speech":
            self.log_signal.emit(self.ls.tr("status_no_speech"))
            self.status_signal.emit(self.ls.tr("status_no_speech"), "#7f8c8d")
        else:
            self.log_signal.emit(f"Process Error: {err_code}")
            self.status_signal.emit(self.ls.tr("status_engine_error"), "#c0392b")

    def _on_processor_finished(self):
        self.processor_thread = None