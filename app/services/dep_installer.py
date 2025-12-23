import os
import requests
from zipfile import ZipFile
from PySide6.QtCore import QThread, Signal
from app.config import BIN_DIR
from app.services.lang_service import LanguageService # 导入

class FFmpegInstaller(QThread):
    progress_signal = Signal(str)
    finished_signal = Signal(bool)

    def __init__(self):
        super().__init__()
        self.ls = LanguageService() # 实例化

    def run(self):
        if self._check_installed():
            self.progress_signal.emit(self.ls.tr("log_ffmpeg_ready"))
            self.finished_signal.emit(True)
            return
        
        try:
            url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            self.progress_signal.emit(self.ls.tr("log_ffmpeg_downloading"))
            os.makedirs(BIN_DIR, exist_ok=True)
            zip_path = os.path.join(BIN_DIR, "ffmpeg.zip")
            
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(zip_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            self.progress_signal.emit(self.ls.tr("log_ffmpeg_unzipping"))
            with ZipFile(zip_path, 'r') as z:
                for file in z.namelist():
                    if file.endswith("ffmpeg.exe"):
                        with open(os.path.join(BIN_DIR, "ffmpeg.exe"), 'wb') as f:
                            f.write(z.read(file))
                            
            if os.path.exists(zip_path): os.remove(zip_path)
            self.progress_signal.emit(self.ls.tr("log_ffmpeg_success"))
            self.finished_signal.emit(True)
        except Exception as e:
            self.progress_signal.emit(self.ls.tr("log_ffmpeg_fail").format(e))
            self.finished_signal.emit(False)

    def _check_installed(self):
        return os.path.exists(os.path.join(BIN_DIR, "ffmpeg.exe"))