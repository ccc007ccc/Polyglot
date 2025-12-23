import os
import sys
import re
import torch
import logging
import requests
import importlib.util
import warnings

# === 核心修改：彻底静默日志 ===
# 1. 过滤 HuggingFace 的 Warning
warnings.filterwarnings("ignore")

# 2. 强制设置 Logger 级别为 CRITICAL (最高级别，只报崩溃错误)
# 这样 "Downloading..." 之类的信息就不会显示了
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
        # 仅在下载文件时保留 print，因为这个过程比较慢，用户需要知道进度
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
        # 将这里的 print 改为标准输出，或者根据需要去掉
        print("Initializing FunASR Engine...")
        
        try:
            import transformers
            import sentencepiece
            from modelscope import snapshot_download
            from funasr import AutoModel
        except ImportError:
            print("❌ Critical Error: Missing dependencies.")
            self._ready = False
            return

        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            # 只显示设备信息，其他下载日志已被 logging.CRITICAL 屏蔽
            print(f"Device: {device}")

            model_id = "FunAudioLLM/Fun-ASR-MLT-Nano-2512"
            
            # snapshot_download 的日志已被屏蔽，界面会很清爽
            model_dir = snapshot_download(model_id)
            model_dir = os.path.abspath(model_dir)

            model_py_path = os.path.join(model_dir, "model.py")
            if not os.path.exists(model_py_path):
                github_url = "https://raw.githubusercontent.com/FunAudioLLM/Fun-ASR/main/model.py"
                success = self._download_file(github_url, model_py_path)
                if not success:
                    print("❌ Failed to get model.py")
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
                log_level="ERROR" # 再次确保内部日志级别
            )
            
            self._ready = True
            print("✅ FunASR Ready")
            
        except Exception as e:
            print(f"❌ FunASR Crash: {e}")
            self._ready = False

    def transcribe(self, audio_path: str, language: str = "zh") -> str:
        if not self._ready or not self.model:
            return ""
        
        try:
            target_lang = self.lang_map.get(language, "中文")
            generate_kwargs = {
                "input": audio_path,
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
        except Exception:
            return ""

    def is_ready(self) -> bool:
        return self._ready