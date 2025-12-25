from .whisper_local import FasterWhisperSTT
# 懒加载导入，防止如果用户没装 funasr 导致整个程序崩溃
# 这里我们在工厂方法里动态 import

def create_stt_engine(config_data: dict):
    """
    工厂方法：根据配置生产 STT 引擎实例
    """
    engine_type = config_data.get("stt_engine", "faster_whisper")
    
    if engine_type == "funasr":
        try:
            from .funasr_local import FunASRSTT
            return FunASRSTT()
        except Exception as e:
            print(f"无法加载 FunASR 插件: {e}, 回退到 Whisper")
            return FasterWhisperSTT()

    # 默认 Faster-Whisper
    # [Fix] 从配置中读取模型大小
    size = config_data.get("whisper_model_size", "base")
    return FasterWhisperSTT(
        model_size=size, 
        device="cpu",
        compute_type="int8"
    )