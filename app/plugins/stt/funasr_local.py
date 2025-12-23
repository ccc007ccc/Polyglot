import os
import sys
import re  # 新增：用于正则处理
import torch
import logging
import requests
import importlib.util

# 抑制 ModelScope 的下载进度条和繁琐日志
logging.getLogger("modelscope").setLevel(logging.ERROR)

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
        """下载单个文件的辅助函数"""
        print(f"📥 正在下载缺失文件: {os.path.basename(save_path)} ...")
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(resp.content)
            print("✅ 下载成功")
            return True
        except Exception as e:
            print(f"❌ 下载失败: {e}")
            return False

    def initialize(self):
        print("正在初始化 FunASR 引擎 (Fun-ASR-MLT-Nano-2512)...")
        
        try:
            import transformers
            import sentencepiece
            from modelscope import snapshot_download
            from funasr import AutoModel
        except ImportError:
            print("❌ 严重错误: 缺少必要依赖。请运行: pip install transformers sentencepiece modelscope funasr")
            self._ready = False
            return

        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"FunASR 推理设备: {device}")

            model_id = "FunAudioLLM/Fun-ASR-MLT-Nano-2512"
            
            print(f"正在检查/下载模型权重: {model_id}")
            model_dir = snapshot_download(model_id)
            model_dir = os.path.abspath(model_dir)

            # === 自动下载 model.py ===
            model_py_path = os.path.join(model_dir, "model.py")
            if not os.path.exists(model_py_path):
                print("⚠️ 检测到 model.py 缺失，尝试从官方 GitHub 获取...")
                github_url = "https://raw.githubusercontent.com/FunAudioLLM/Fun-ASR/main/model.py"
                success = self._download_file(github_url, model_py_path)
                if not success:
                    print("❌ 下载失败，请手动下载 model.py 到模型目录。")
                    self._ready = False
                    return

            # === 手动加载 model.py ===
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

            print("正在加载模型 (AutoModel)...")
            self.model = AutoModel(
                model=model_dir,
                trust_remote_code=True,
                remote_code="model.py",
                vad_model="fsmn-vad",
                vad_kwargs={"max_single_segment_time": 30000},
                punc_model="ct-punc-c",
                device=device,
                disable_update=True
            )
            
            self._ready = True
            print("✅ FunASR 引擎加载完毕")
            
        except Exception as e:
            print(f"❌ FunASR 加载崩溃: {e}")
            import traceback
            traceback.print_exc()
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
                "itn": True
            }

            res = self.model.generate(**generate_kwargs)
            
            if res and isinstance(res, list) and len(res) > 0:
                text = res[0].get('text', '')
                
                # === 修复：去除重复标点 ===
                # 将 "？？" 替换为 "？"，"。。" 替换为 "。" 等
                # 正则解释：([符号集合])\1+ 表示匹配该集合中连续出现2次以上的字符
                text = re.sub(r'([？?。，,！!])\1+', r'\1', text)
                
                return text.strip()
            return ""
        except Exception as e:
            print(f"FunASR 识别错误: {e}")
            return ""

    def is_ready(self) -> bool:
        return self._ready