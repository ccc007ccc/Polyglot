# app/plugins/stt/funasr_local.py
import os
import re
import torch
import logging
import warnings
import tempfile
import numpy as np
import soundfile as sf
from app.core.interfaces import ISTTEngine
from app.services.lang_service import LanguageService

# [SILICON VALLEY OPTIMIZATION] 
# Import the local model class BEFORE initializing AutoModel.
# The @tables.register decorator in the imported file handles the registration.
from app.core.modeling.funasr_nano import FunASRNano 

# Mute Logger
warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.CRITICAL)
logging.getLogger("modelscope").setLevel(logging.CRITICAL)
logging.getLogger("funasr").setLevel(logging.CRITICAL)

class FunASRSTT(ISTTEngine):
    def __init__(self):
        self.model = None
        self._ready = False
        self.ls = LanguageService()
        self.lang_map = {
            "zh": "中文", "en": "英文", "ja": "日文", "yue": "粤语", "ko": "韩文",
            "vi": "越南语", "th": "泰语", "ms": "马来语", "id": "印尼语", "ru": "俄语", 
        }

    def initialize(self):
        print("Initializing FunASR Engine (Local Optimized)...")
        try:
            from modelscope import snapshot_download
            from funasr import AutoModel
        except ImportError:
            print("❌ Critical Error: Missing dependencies (funasr/modelscope).")
            self._ready = False
            return

        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Device: {device}")

            model_id = "FunAudioLLM/Fun-ASR-MLT-Nano-2512"
            
            # 1. Download/Cache model weights (only weights/config, not code)
            model_dir = snapshot_download(model_id)
            model_dir = os.path.abspath(model_dir)

            # 2. Initialize Model using LOCAL class
            # trust_remote_code=False ensures we use our app/core/modeling/funasr_nano.py
            # The registry knows 'FunASRNano' because we imported it above.
            self.model = AutoModel(
                model=model_dir,
                trust_remote_code=False,  # <--- SECURE MODE
                vad_model="fsmn-vad",
                vad_kwargs={"max_single_segment_time": 30000},
                punc_model="ct-punc-c",
                device=device,
                disable_update=True,
                log_level="ERROR"
            )
            
            self._ready = True
            print("✅ FunASR Ready (Local Execution)")
            
        except Exception as e:
            print(f"❌ FunASR Crash: {e}")
            self._ready = False

    def transcribe(self, audio_data, language: str = "zh") -> str:
        if not self._ready or not self.model:
            return ""
        
        temp_file = None
        try:
            target_lang = self.lang_map.get(language, "中文")
            input_data = audio_data

            if isinstance(audio_data, np.ndarray):
                # FunASR prefers file path for stability in some versions
                temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                sf.write(temp_file.name, audio_data, 16000)
                input_data = temp_file.name
                temp_file.close()

            generate_kwargs = {
                "input": input_data,
                "batch_size": 1, 
                "cache": {},
                "language": target_lang,
                "itn": True,
            }
            
            # The model wrapper will handle the VAD -> ASR -> PUNC pipeline
            res = self.model.generate(**generate_kwargs)
            
            if res and isinstance(res, list) and len(res) > 0:
                text = res[0].get('text', '')
                # Clean up repeated punctuation which sometimes happens with Nano models
                text = re.sub(r'([？?。，,！!])\1+', r'\1', text)
                return text.strip()
            return ""
        except Exception as e:
            print(f"FunASR Transcribe Error: {e}")
            return ""
        finally:
            if temp_file and os.path.exists(temp_file.name):
                try: os.remove(temp_file.name)
                except: pass

    def is_ready(self) -> bool:
        return self._ready