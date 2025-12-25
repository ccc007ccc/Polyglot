from abc import ABC, abstractmethod
from typing import Any, Union

class ISTTEngine(ABC):
    """
    语音识别引擎抽象接口 (Interface for Speech-to-Text Engine)
    """

    @abstractmethod
    def initialize(self) -> None:
        """加载模型资源"""
        pass

    @abstractmethod
    def transcribe(self, audio_data: Union[str, Any], language: str = "zh") -> str:
        """
        转录音频
        :param audio_data: 文件路径(str) 或 内存音频数据(numpy/bytes)
        :param language: 目标语言代码
        :return: 识别后的文本
        """
        pass

    @abstractmethod
    def is_ready(self) -> bool:
        """检查引擎是否就绪"""
        pass