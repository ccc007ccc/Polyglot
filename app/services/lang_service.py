import os
import json
import locale
import sys
from app.config import ConfigManager

class LanguageService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.translations = {}
            cls._instance.current_lang = "en_US" 
            cls._instance.load_language()
        return cls._instance

    def load_language(self):
        # 1. 优先从配置中读取用户设定
        cfg = ConfigManager()
        user_pref = cfg.get("app_lang") # 'auto', 'zh_CN', 'en_US'
        
        target_file = "en_US.json" # 默认兜底
        
        # 2. 逻辑判断
        if user_pref and user_pref != "auto":
            # 用户手动强制指定
            target_file = f"{user_pref}.json"
            self.current_lang = user_pref
        else:
            # 自动跟随系统
            try:
                sys_lang, _ = locale.getdefaultlocale()
            except:
                sys_lang = "en_US"
            
            if not sys_lang: sys_lang = "en_US"

            if sys_lang.startswith("zh"):
                target_file = "zh_CN.json"
                self.current_lang = "zh_CN"
            else:
                target_file = "en_US.json"
                self.current_lang = "en_US"

        # 3. 读取文件
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        lang_path = os.path.join(base_dir, "assets", "lang", target_file)

        if os.path.exists(lang_path):
            try:
                with open(lang_path, 'r', encoding='utf-8') as f:
                    self.translations = json.load(f)
                print(f"Loaded Language: {target_file}")
            except Exception as e:
                print(f"Error loading language file: {e}")
                self.translations = {}
        else:
            print(f"Language file not found: {lang_path}, using keys.")

    def tr(self, key):
        return self.translations.get(key, key)