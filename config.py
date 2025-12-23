import os
import json
import sys

# 基础路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(BASE_DIR, "bin")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
TEMP_AUDIO = os.path.join(BASE_DIR, "temp_recording.wav")

if os.path.exists(BIN_DIR):
    os.environ["PATH"] += os.pathsep + BIN_DIR

# 默认配置
DEFAULT_CONFIG = {
    "api_base": "https://api.deepseek.com",
    "api_key": "",
    "model": "deepseek-chat",
    
    "hotkey_rec": "ctrl+b",
    "hotkey_send": "ctrl+n",
    "rec_mode": "hold",
    "mic_index": 0,
    
    "auto_send": True,
    "sound_cues": True,
    
    # === 悬浮窗配置 (已更新) ===
    "overlay_x": 100,
    "overlay_y": 100,
    "overlay_width": 500,       # 新增: 宽度
    "overlay_height": 200,      # 新增: 高度
    "overlay_opacity": 0.8,     # 背景不透明度
    "overlay_border_alpha": 0.8,# 新增: 未锁定边框不透明度
    "overlay_font_size": 14,    # 字体大小
    "overlay_locked": False,    # 是否锁定
    
    "tpl_osc": "{zh} | {en}",
    "tpl_display": "原文: {text}\n[CN] {zh}\n[EN] {en}\n[JA] {ja}",
    "langs": {"zh": True, "en": True, "ja": True, "pinyin": True}
}

class ConfigManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.data = DEFAULT_CONFIG.copy()
            cls._instance.load()
        return cls._instance

    def load(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    self.data.update(saved)
            except: pass
    
    def save(self):
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Save config failed: {e}")

    def get(self, key): return self.data.get(key, DEFAULT_CONFIG.get(key))
    def set(self, key, val): self.data[key] = val