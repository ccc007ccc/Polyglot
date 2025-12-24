import threading
import json
import requests
import winsound
import re  # [New] 引入正则模块
from pythonosc import udp_client
from pypinyin import pinyin, Style
from PySide6.QtCore import QObject, Signal
from app.config import ConfigManager
from app.services.lang_service import LanguageService

class TranslationService(QObject):
    finished_signal = Signal(str, str) # osc_msg, display_msg
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.client = udp_client.SimpleUDPClient("127.0.0.1", 9000)
        self.cfg = ConfigManager()
        self.ls = LanguageService()

    def process(self, text):
        threading.Thread(target=self._do_process, args=(text,), daemon=True).start()

    def _get_pinyin(self, text):
        if not text: return ""
        pinyin_list = pinyin(text, style=Style.NORMAL)
        # 原始拼接
        raw = " ".join([item[0] for item in pinyin_list])
        # [Fix] 使用正则移除标点符号前的空格
        # \s+ 匹配一个或多个空格
        # ([^\w\s]) 捕获非单词且非空白的字符（即标点符号）
        # r'\1' 替换为捕获到的标点符号本身（即去掉了前面的空格）
        return re.sub(r'\s+([^\w\s])', r'\1', raw)

    def _do_process(self, text):
        try:
            langs = self.cfg.get("langs")
            pinyin_text = self._get_pinyin(text) if langs.get("pinyin") else ""
            
            data_map = {
                "text": text, "zh": text,
                "pinyin": pinyin_text,
                "en": "", "ja": "", "ru": "" 
            }

            json_fields = []
            if langs.get("zh"): json_fields.append('"zh": "Chinese Translation"')
            if langs.get("en"): json_fields.append('"en": "English Translation"')
            if langs.get("ja"): json_fields.append('"ja": "Japanese Translation"')
            if langs.get("ru"): json_fields.append('"ru": "Russian Translation"')
            
            if not json_fields: json_fields.append('"en": "English Translation"')

            system_prompt = (
                "You are a translation engine for VRChat. "
                "Translate the input strictly into JSON. No markdown. "
                "Format:\n{\n" + ",\n".join(json_fields) + "\n}"
            )

            api_key = self.cfg.get("api_key")
            api_base = self.cfg.get("api_base")
            model = self.cfg.get("model")

            if api_key:
                url = f"{api_base.rstrip('/')}/chat/completions"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3
                }
                
                resp = requests.post(url, headers=headers, json=payload, timeout=10)
                if resp.status_code == 200:
                    try:
                        content = resp.json()['choices'][0]['message']['content']
                        parsed = json.loads(content)
                        for k, v in parsed.items():
                            if v: data_map[k] = v
                    except: pass
                else:
                    self.log_signal.emit(self.ls.tr("err_api_code").format(resp.status_code))
            else:
                data_map["en"] = self.ls.tr("err_no_api_key")

            tpl_osc = self.cfg.get("tpl_osc")
            tpl_disp = self.cfg.get("tpl_display")
            
            # === OSC 消息处理 ===
            osc_msg = tpl_osc
            for k, v in data_map.items():
                osc_msg = osc_msg.replace(f"{{{k}}}", str(v))
            osc_msg = osc_msg.replace("\\n", "\n")

            # === 悬浮窗消息处理 ===
            final_lines = []
            raw_lines = tpl_disp.split('\n')
            
            for line in raw_lines:
                temp_line = line
                should_keep = True
                
                for k in data_map.keys():
                    placeholder = f"{{{k}}}"
                    if placeholder in line:
                        val = data_map[k]
                        if not val and k != "text":
                            should_keep = False
                            break
                        temp_line = temp_line.replace(placeholder, str(val))
                
                if should_keep:
                    final_lines.append(temp_line)

            disp_msg = "\n".join(final_lines)
            disp_msg = disp_msg.replace("\\n", "\n")
            
            self.finished_signal.emit(osc_msg, disp_msg)
            
        except Exception as e:
            self.log_signal.emit(self.ls.tr("err_trans_process").format(e))
            self.finished_signal.emit(text, self.ls.tr("err_general").format(e))

    def send_osc(self, text):
        if not text: return
        try:
            self.client.send_message("/chatbox/input", [text, True, True])
            if self.cfg.get("sound_cues"): winsound.Beep(1000, 100)
            self.log_signal.emit(self.ls.tr("log_osc_sent"))
        except Exception as e:
            self.log_signal.emit(self.ls.tr("err_osc_fail").format(e))