import json
import requests
import winsound
import re
import traceback
from pythonosc import udp_client
from pypinyin import pinyin, Style
from PySide6.QtCore import QObject, Signal, QThread, QRunnable, QThreadPool

class TranslationWorker(QRunnable):
    """
    使用 QRunnable 放入线程池执行 API 请求
    """
    def __init__(self, text, config, lang_service, callbacks):
        super().__init__()
        self.text = text
        self.cfg = config
        self.ls = lang_service
        self.finished_signal = callbacks['finished']
        self.log_signal = callbacks['log']

    def _get_pinyin(self, text):
        if not text: return ""
        pinyin_list = pinyin(text, style=Style.NORMAL)
        raw = " ".join([item[0] for item in pinyin_list])
        return re.sub(r'\s+([^\w\s])', r'\1', raw)

    def run(self):
        try:
            langs = self.cfg.get("langs")
            pinyin_text = self._get_pinyin(self.text) if langs.get("pinyin") else ""
            
            data_map = {
                "text": self.text, "zh": self.text,
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
                        {"role": "user", "content": self.text}
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
                    except Exception as e:
                        self.log_signal.emit(f"JSON Parse Error: {e}")
                else:
                    self.log_signal.emit(self.ls.tr("err_api_code").format(resp.status_code))
            else:
                data_map["en"] = self.ls.tr("err_no_api_key")

            # 模板处理
            tpl_osc = self.cfg.get("tpl_osc")
            tpl_disp = self.cfg.get("tpl_display")
            
            osc_msg = tpl_osc
            for k, v in data_map.items():
                osc_msg = osc_msg.replace(f"{{{k}}}", str(v))
            osc_msg = osc_msg.replace("\\n", "\n")

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
            self.log_signal.emit(self.ls.tr("err_trans_process").format(str(e)))
            self.finished_signal.emit(self.text, self.ls.tr("err_general").format(str(e)))

class TranslationService(QObject):
    finished_signal = Signal(str, str) # osc_msg, display_msg
    log_signal = Signal(str)

    def __init__(self, config_manager, lang_service):
        super().__init__()
        self.client = udp_client.SimpleUDPClient("127.0.0.1", 9000)
        self.cfg = config_manager
        self.ls = lang_service
        self.pool = QThreadPool.globalInstance()

    def process(self, text):
        worker = TranslationWorker(
            text, self.cfg, self.ls,
            {'finished': self.finished_signal, 'log': self.log_signal}
        )
        self.pool.start(worker)

    def send_osc(self, text):
        if not text: return
        try:
            self.client.send_message("/chatbox/input", [text, True, True])
            if self.cfg.get("sound_cues"): winsound.Beep(1000, 100)
            self.log_signal.emit(self.ls.tr("log_osc_sent"))
        except Exception as e:
            self.log_signal.emit(self.ls.tr("err_osc_fail").format(e))