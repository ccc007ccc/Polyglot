import os
import threading
import time
import wave
import json
import requests
import pyaudio
import keyboard
import winsound
from zipfile import ZipFile
from PySide6.QtCore import QObject, Signal, QThread
from faster_whisper import WhisperModel
from pythonosc import udp_client
from pypinyin import pinyin, Style
from config import BIN_DIR, TEMP_AUDIO, ConfigManager

# === FFmpeg 下载/检查线程 ===
class FFmpegWorker(QThread):
    progress_signal = Signal(str)
    finished_signal = Signal(bool)

    def run(self):
        if self._check_installed():
            self.progress_signal.emit("FFmpeg 已就绪")
            self.finished_signal.emit(True)
            return
        
        try:
            url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            self.progress_signal.emit("正在下载 FFmpeg... (首次运行需要)")
            os.makedirs(BIN_DIR, exist_ok=True)
            zip_path = os.path.join(BIN_DIR, "ffmpeg.zip")
            
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(zip_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            self.progress_signal.emit("正在解压...")
            with ZipFile(zip_path, 'r') as z:
                for file in z.namelist():
                    if file.endswith("ffmpeg.exe"):
                        with open(os.path.join(BIN_DIR, "ffmpeg.exe"), 'wb') as f:
                            f.write(z.read(file))
                            
            if os.path.exists(zip_path): os.remove(zip_path)
            self.progress_signal.emit("FFmpeg 安装完成")
            self.finished_signal.emit(True)
        except Exception as e:
            self.progress_signal.emit(f"FFmpeg 安装错误: {str(e)}")
            self.finished_signal.emit(False)

    def _check_installed(self):
        return os.path.exists(os.path.join(BIN_DIR, "ffmpeg.exe"))


# === 核心音频服务 ===
class AudioService(QObject):
    log_signal = Signal(str)
    status_signal = Signal(str, str) # text, color
    result_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.model = None
        self.is_recording = False
        self.frames = []
        self.audio = pyaudio.PyAudio()
        self.cfg = ConfigManager()
    
    # 获取麦克风列表 [index, name]
    def get_input_devices(self):
        devices = []
        info = self.audio.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        for i in range(0, numdevices):
            if (self.audio.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
                name = self.audio.get_device_info_by_host_api_device_index(0, i).get('name')
                # 解决Windows乱码问题 (尝试gbk解码，失败则保持原样)
                try: name = name.encode('cp1252').decode('gbk')
                except: pass
                devices.append((i, name))
        return devices

    def init_model(self):
        self.log_signal.emit("正在加载 AI 模型 (Whisper)...")
        try:
            self.model = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=4)
            self.log_signal.emit("模型加载完成，系统就绪！")
            mode_str = "按住" if self.cfg.get("rec_mode") == "hold" else "按一下"
            self.status_signal.emit(f"就绪 | {mode_str} {self.cfg.get('hotkey_rec')} 说话", "#27ae60")
        except Exception as e:
            self.log_signal.emit(f"模型加载失败: {e}")
            self.status_signal.emit("模型错误", "#c0392b")

    def start_record(self):
        if not self.model: 
            self.log_signal.emit("错误：模型尚未加载")
            return
        if self.is_recording: return

        self.is_recording = True
        self.frames = []
        self.status_signal.emit("🎤 正在录音...", "#e74c3c")
        
        if self.cfg.get("sound_cues"): winsound.Beep(800, 100)
        threading.Thread(target=self._record_loop, daemon=True).start()

    def stop_record(self):
        if not self.is_recording: return
        self.is_recording = False
        
        if self.cfg.get("sound_cues"): winsound.Beep(500, 100)
        self.status_signal.emit("⏳ 正在识别...", "#f39c12")
        threading.Thread(target=self._transcribe, daemon=True).start()
    
    def toggle_record(self):
        if self.is_recording:
            self.stop_record()
        else:
            self.start_record()

    def _record_loop(self):
        stream = None
        try:
            mic_index = self.cfg.get("mic_index")
            # 如果配置的 mic_index 超出范围，使用默认
            try:
                stream = self.audio.open(
                    format=pyaudio.paInt16, 
                    channels=1, 
                    rate=16000, 
                    input=True, 
                    input_device_index=mic_index,
                    frames_per_buffer=1024
                )
            except:
                self.log_signal.emit("指定的麦克风无效，使用默认设备")
                stream = self.audio.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)

            while self.is_recording:
                data = stream.read(1024, exception_on_overflow=False)
                self.frames.append(data)
        except Exception as e:
            self.log_signal.emit(f"录音设备错误: {e}")
        finally:
            if stream:
                stream.stop_stream()
                stream.close()

    def _transcribe(self):
        if not self.frames or len(self.frames) < 5: 
            self.status_signal.emit("时间太短", "#7f8c8d")
            return

        try:
            wf = wave.open(TEMP_AUDIO, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(16000)
            wf.writeframes(b''.join(self.frames))
            wf.close()
            
            segments, _ = self.model.transcribe(TEMP_AUDIO, beam_size=5, language="zh", vad_filter=True)
            text = " ".join([s.text for s in segments]).strip()
            
            if text:
                self.log_signal.emit(f"👂 识别原文: {text}")
                self.result_signal.emit(text)
            else:
                self.log_signal.emit("未检测到有效语音")
                self.status_signal.emit("无语音内容", "#7f8c8d")
                
        except Exception as e:
            self.log_signal.emit(f"识别出错: {e}")
            self.status_signal.emit("识别出错", "#c0392b")
        finally:
            try: os.remove(TEMP_AUDIO)
            except: pass


# === 快捷键服务 (重写版：使用轮询解决组合键冲突) ===
class HotkeyService(QObject):
    # 定义信号通知主线程进行操作
    req_start_rec = Signal()
    req_stop_rec = Signal()
    req_toggle_rec = Signal()
    req_send = Signal()

    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager()
        self.running = True
        self.thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def update_keys(self):
        # 轮询模式下，不需要重置 hook，只要配置变了，下一次循环就会读取新配置
        pass

    def _poll_loop(self):
        # 记录上一次按键状态，用于边缘检测
        last_rec_state = False
        last_send_state = False

        while self.running:
            try:
                time.sleep(0.05) # 20Hz 采样率，足够快且不占 CPU

                rec_key = self.cfg.get("hotkey_rec")
                send_key = self.cfg.get("hotkey_send")
                mode = self.cfg.get("rec_mode") # hold 或 toggle

                # === 1. 处理录音键 ===
                is_rec_pressed = False
                try:
                    if rec_key and keyboard.is_pressed(rec_key):
                        is_rec_pressed = True
                except: pass # 忽略无效键名

                if mode == "hold":
                    # 按住模式：按下且之前没按下 -> 开始；松开且之前按下 -> 停止
                    if is_rec_pressed and not last_rec_state:
                        self.req_start_rec.emit()
                    elif not is_rec_pressed and last_rec_state:
                        self.req_stop_rec.emit()
                else:
                    # 切换模式：按下瞬间 -> 切换
                    if is_rec_pressed and not last_rec_state:
                        self.req_toggle_rec.emit()
                
                last_rec_state = is_rec_pressed

                # === 2. 处理发送键 ===
                is_send_pressed = False
                try:
                    if send_key and keyboard.is_pressed(send_key):
                        is_send_pressed = True
                except: pass

                if is_send_pressed and not last_send_state:
                    self.req_send.emit()
                
                last_send_state = is_send_pressed

            except Exception as e:
                print(f"Hotkey Poll Error: {e}")
                time.sleep(1) # 出错后冷却一下


# === 翻译与OSC服务 ===
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
                        data_map.update(parsed)
                    except: pass
                else:
                    self.log_signal.emit(f"API 错误: {resp.status_code}")
            else:
                data_map["en"] = "[未配置 API Key]"

            tpl_osc = self.cfg.get("tpl_osc")
            tpl_disp = self.cfg.get("tpl_display")
            
            osc_msg = tpl_osc
            disp_msg = tpl_disp
            for k, v in data_map.items():
                osc_msg = osc_msg.replace(f"{{{k}}}", str(v))
                disp_msg = disp_msg.replace(f"{{{k}}}", str(v))
                
            osc_msg = osc_msg.replace("\\n", "\n")
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