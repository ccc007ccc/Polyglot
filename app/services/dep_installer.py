import os
import requests
from zipfile import ZipFile
from PySide6.QtCore import QThread, Signal
from app.config import BIN_DIR

class FFmpegInstaller(QThread):
    progress_signal = Signal(str)
    finished_signal = Signal(bool)

    def run(self):
        if self._check_installed():
            self.progress_signal.emit("FFmpeg 环境已就绪")
            self.finished_signal.emit(True)
            return
        
        try:
            url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            self.progress_signal.emit("正在下载 FFmpeg 组件...")
            os.makedirs(BIN_DIR, exist_ok=True)
            zip_path = os.path.join(BIN_DIR, "ffmpeg.zip")
            
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(zip_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            self.progress_signal.emit("正在解压组件...")
            with ZipFile(zip_path, 'r') as z:
                for file in z.namelist():
                    if file.endswith("ffmpeg.exe"):
                        with open(os.path.join(BIN_DIR, "ffmpeg.exe"), 'wb') as f:
                            f.write(z.read(file))
                            
            if os.path.exists(zip_path): os.remove(zip_path)
            self.progress_signal.emit("组件安装完成")
            self.finished_signal.emit(True)
        except Exception as e:
            self.progress_signal.emit(f"组件安装失败: {str(e)}")
            self.finished_signal.emit(False)

    def _check_installed(self):
        return os.path.exists(os.path.join(BIN_DIR, "ffmpeg.exe"))
