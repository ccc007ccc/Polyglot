import os
import sys
import re
import torch
import logging
import requests
import importlib.util
import warnings
import tempfile
import numpy as np
import soundfile as sf

# 日志静默处理
warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.CRITICAL)
logging.getLogger("modelscope").setLevel(logging.CRITICAL)
logging.getLogger("funasr").setLevel(logging.CRITICAL)

from app.core.interfaces import ISTTEngine

class FunASRSTT(ISTTEngine):
    def __init__(self):
        self.model = None
        self._ready = False
        self.lang_map = {
            "zh": "中文", "en": "英文", "ja": "日文", "yue": "粤语", "ko": "韩文",
            "vi": "越南语", "th": "泰语", "ms": "马来语", "id": "印尼语", "ru": "俄语", 
        }

    def _download_file(self, url, save_path):
        print(f"📥 Downloading: {os.path.basename(save_path)} ...")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(resp.content)
            print("✅ Download success")
            return True
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return False

    def initialize(self):
        print("Initializing FunASR Engine...")
        try:
            # 延迟导入
            from modelscope import snapshot_download
            from funasr import AutoModel
        except ImportError:
            print("❌ Critical Error: Missing dependencies.")
            self._ready = False
            return

        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Device: {device}")

            model_id = "FunAudioLLM/Fun-ASR-MLT-Nano-2512"
            model_dir = snapshot_download(model_id)
            model_dir = os.path.abspath(model_dir)

            # 动态加载 model.py 逻辑保持不变
            model_py_path = os.path.join(model_dir, "model.py")
            if not os.path.exists(model_py_path):
                github_url = "https://raw.githubusercontent.com/FunAudioLLM/Fun-ASR/main/model.py"
                if not self._download_file(github_url, model_py_path):
                    self._ready = False
                    return

            if os.path.exists(model_py_path):
                try:
                    if model_dir not in sys.path:
                        sys.path.insert(0, model_dir)
                    spec = importlib.util.spec_from_file_location("model", model_py_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules["model"] = module
                        spec.loader.exec_module(module)
                except Exception: pass

            self.model = AutoModel(
                model=model_dir,
                trust_remote_code=True,
                remote_code="model.py",
                vad_model="fsmn-vad",
                vad_kwargs={"max_single_segment_time": 30000},
                punc_model="ct-punc-c",
                device=device,
                disable_update=True,
                log_level="ERROR"
            )
            self._ready = True
            print("✅ FunASR Ready")
            
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

            # 兼容处理：如果传入的是 numpy 数组，先写入临时文件
            # FunASR AutoModel 对内存对象的支持取决于具体版本，文件是最稳妥的
            if isinstance(audio_data, np.ndarray):
                temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                sf.write(temp_file.name, audio_data, 16000)
                input_data = temp_file.name
                temp_file.close() # 关闭句柄，让模型去读

            generate_kwargs = {
                "input": input_data,
                "batch_size": 1, 
                "cache": {},
                "language": target_lang,
                "itn": True,
            }
            res = self.model.generate(**generate_kwargs)
            
            if res and isinstance(res, list) and len(res) > 0:
                text = res[0].get('text', '')
                text = re.sub(r'([？?。，,！!])\1+', r'\1', text)
                return text.strip()
            return ""
        except Exception as e:
            print(f"FunASR Transcribe Error: {e}")
            return ""
        finally:
            # 清理临时文件
            if temp_file and os.path.exists(temp_file.name):
                try: os.remove(temp_file.name)
                except: pass

    def is_ready(self) -> bool:
        return self._ready