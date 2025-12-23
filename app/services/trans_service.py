import threading
import json
import requests
import winsound
from pythonosc import udp_client
from pypinyin import pinyin, Style
from PySide6.QtCore import QObject, Signal
from app.config import ConfigManager

class TranslationService(QObject):
    finished_signal = Signal(str, str) # osc_msg, display_msg
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.client = udp_client.SimpleUDPClient("127.0.0.1", 9000)
        self.cfg = ConfigManager()

    def process(self, text):
        threading.Thread(target=self._do_process, args=(text,), daemon=True).start()

    def _get_pinyin(self, text):
        if not text: return ""
        pinyin_list = pinyin(text, style=Style.NORMAL)
        return " ".join([item[0] for item in pinyin_list])

    def _do_process(self, text):
        try:
            langs = self.cfg.get("langs")
            pinyin_text = self._get_pinyin(text) if langs.get("pinyin") else ""
            
            # 初始化所有支持的键，避免模板报错
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
            
            # 兜底：如果都没选，至少翻个英文
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
                        # 更新字典，只更新返回了内容的字段
                        for k, v in parsed.items():
                            if v: data_map[k] = v
                    except: pass
                else:
                    self.log_signal.emit(f"API 错误: {resp.status_code}")
            else:
                data_map["en"] = "[未配置 API Key]"

            tpl_osc = self.cfg.get("tpl_osc")
            tpl_disp = self.cfg.get("tpl_display")
            
            # === OSC 消息处理 (保持简单替换) ===
            osc_msg = tpl_osc
            for k, v in data_map.items():
                osc_msg = osc_msg.replace(f"{{{k}}}", str(v))
            osc_msg = osc_msg.replace("\\n", "\n")

            # === 悬浮窗消息处理 (智能隐藏空行) ===
            final_lines = []
            raw_lines = tpl_disp.split('\n')
            
            for line in raw_lines:
                # 临时替换该行，看看是否有空值
                temp_line = line
                should_keep = True
                
                # 检查该行引用的所有 key
                for k in data_map.keys():
                    placeholder = f"{{{k}}}"
                    if placeholder in line:
                        val = data_map[k]
                        # 如果该行包含这个 key，且这个 key 对应的值为空/False，则丢弃整行
                        # (特例：如果 key 是 'text' 原文，即使为空通常也不丢弃，视情况而定，这里假设原文总是有值)
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
            self.log_signal.emit(f"翻译处理错误: {e}")
            self.finished_signal.emit(text, f"错误: {e}")

    def send_osc(self, text):
        if not text: return
        try:
            self.client.send_message("/chatbox/input", [text, True, True])
            if self.cfg.get("sound_cues"): winsound.Beep(1000, 100)
            self.log_signal.emit(f"📤 已发送 OSC")
        except Exception as e:
            self.log_signal.emit(f"OSC 发送失败: {e}")