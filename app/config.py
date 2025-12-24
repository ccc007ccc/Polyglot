# app/config.py
import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_DIR = os.path.join(BASE_DIR, "bin")
MODELS_DIR = os.path.join(BASE_DIR, "models")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
TEMP_AUDIO = os.path.join(BASE_DIR, "temp_recording.wav")

if not os.path.exists(MODELS_DIR):
    os.makedirs(MODELS_DIR)

os.environ["MODELSCOPE_CACHE"] = MODELS_DIR

if os.path.exists(BIN_DIR):
    os.environ["PATH"] += os.pathsep + BIN_DIR

DEFAULT_CONFIG = {
    "app_lang": "auto",
    "enable_steamvr": False,

    "api_base": "https://api.deepseek.com",
    "api_key": "",
    "model": "deepseek-chat",
    "stt_engine": "faster_whisper",
    
    "hotkey_rec": "ctrl+b",
    "hotkey_send": "ctrl+n",
    "rec_mode": "hold",
    "mic_index": 0,
    
    "auto_send": True,
    "sound_cues": True,
    
    # === PC 悬浮窗设置 ===
    "overlay_x": 100,
    "overlay_y": 100,
    "overlay_width": 500,
    "overlay_height": 200,
    "overlay_opacity": 0.8,
    "overlay_border_alpha": 0.8,
    "overlay_font_size": 14,
    "overlay_locked": False,
    
    # === VR 悬浮窗设置 ===
    "vr_width": 0.4,
    "vr_matrix": [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.25], 
        [0.0, 0.0, 1.0, -0.35],
        [0.0, 0.0, 0.0, 1.0]
    ],

    "tpl_osc": "{zh} | {en}",
    "tpl_display": "原文: {text}\n[CN] {zh}\n[EN] {en}\n[JA] {ja}\n[RU] {ru}",
    
    # === 新增：模版存储 ===
    "templates_osc": {
        "Default": "{zh} | {en}",
        "Simple CN": "{zh}",
        "Bilingual": "{zh} ({en})"
    },
    "templates_display": {
        "Default": "原文: {text}\n[CN] {zh}\n[EN] {en}\n[JA] {ja}\n[RU] {ru}",
        "Minimal": "{zh}\n{en}",
        "Debug": "RAW: {text}\nZH: {zh}"
    },

    "langs": {"zh": True, "en": True, "ja": True, "ru": True, "pinyin": True}
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
                    # 深度更新字典，防止新key丢失
                    self._deep_update(self.data, saved)
            except: pass
    
    def _deep_update(self, target, source):
        for k, v in source.items():
            if isinstance(v, dict) and k in target and isinstance(target[k], dict):
                self._deep_update(target[k], v)
            else:
                target[k] = v

    def save(self):
        try:
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Save config failed: {e}")

    def get(self, key): return self.data.get(key, DEFAULT_CONFIG.get(key))
    def set(self, key, val): self.data[key] = val