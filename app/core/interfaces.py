from abc import ABC, abstractmethod

class ISTTEngine(ABC):
    """
    语音识别引擎抽象接口 (Interface for Speech-to-Text Engine)
    """

    @abstractmethod
    def initialize(self) -> None:
        """加载模型资源"""
        pass

    @abstractmethod
    def transcribe(self, audio_path: str, language: str = "zh") -> str:
        """
        转录音频文件
        :param audio_path: wav 文件路径
        :return: 识别后的文本
        """
        pass

    @abstractmethod
    def is_ready(self) -> bool:
        """检查引擎是否就绪"""
        pass
