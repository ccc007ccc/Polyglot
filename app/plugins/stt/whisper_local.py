import numpy as np
from faster_whisper import WhisperModel
from app.core.interfaces import ISTTEngine

class FasterWhisperSTT(ISTTEngine):
    def __init__(self, model_size="base", device="cpu", compute_type="int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        self._ready = False

    def initialize(self):
        print(f"Loading Faster-Whisper ({self.model_size})...")
        try:
            self.model = WhisperModel(
                self.model_size, 
                device=self.device, 
                compute_type=self.compute_type, 
                cpu_threads=4
            )
            self._ready = True
            print("Faster-Whisper Loaded.")
        except Exception as e:
            print(f"Error loading model: {e}")
            self._ready = False

    def transcribe(self, audio_data, language: str = "zh") -> str:
        if not self._ready or not self.model:
            return ""
        
        try:
            # Faster-Whisper 原生支持 numpy float32 数组
            # 如果传入的是路径，它也能处理
            segments, _ = self.model.transcribe(
                audio_data, 
                beam_size=5, 
                language=language, 
                vad_filter=True
            )
            text = " ".join([s.text for s in segments]).strip()
            return text
        except Exception as e:
            print(f"Transcribe error: {e}")
            return ""

    def is_ready(self) -> bool:
        return self._ready