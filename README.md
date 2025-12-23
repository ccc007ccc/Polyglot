# Polyglot | 智能同传助手 (AI Interpreter)

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-yellow.svg)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

**Polyglot Pro** 是一个专为 VRChat 玩家、跨国会议及跨语言交流者设计的硬核实时 AI 同传终端。它集成了本地高性能语音识别（ASR）引擎与大语言模型（LLM）翻译能力，并通过 OSC 协议实现毫秒级的字幕投射。

> **Polyglot Pro** is a hardcore real-time AI simultaneous interpretation terminal designed for VRChat players and cross-language communication. It integrates local high-performance ASR engines with LLM translation capabilities, delivering millisecond-level subtitle projection via OSC.

## ✨ 核心特性 (Core Features)

* **双核 ASR 引擎**:
    * 🚀 **Faster-Whisper**: 基于 CTranslate2 优化的 Whisper 模型，兼容性极强，资源占用低。
    * 🧠 **FunASR (阿里达摩院)**: 针对中文语境深度优化的工业级识别模型，识别率极高。
* **AI 语境翻译**: 支持接入 OpenAI 接口规范的 LLM (如 DeepSeek, ChatGPT, Claude)，告别生硬机翻，支持 prompt 自定义。
* **赛博朋克 HUD**:
    * 基于 PySide6 绘制的现代化悬浮窗，支持**鼠标穿透 (Click-through)** 模式。
    * 高度可定制：透明度、字体大小、边框强度及显隐逻辑。
* **VRChat 原生支持**: 内置 OSC (Open Sound Control) 客户端，可直接向 VRChat Chatbox 发送双语字幕。
* **自动化依赖管理**: 内置 FFmpeg 自动下载与部署逻辑，开箱即用。

## 🛠️ 安装与部署 (Installation)

### 环境要求
* Python 3.8+
* Windows 10/11 (推荐)
* CUDA Toolkit (可选，推荐用于 GPU 加速)

### 步骤
1.  **克隆仓库**:
    ```bash
    git clone https://github.com/ccc007ccc/Polyglot
    cd Polyglot
    ```

2.  **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **运行**:
    ```bash
    python run.py
    ```
    *首次运行时，程序会自动检测并下载 FFmpeg 环境至 `bin/` 目录。*

## 🎮 使用指南 (Usage)

### 1. 初始化配置
启动后进入 **Settings** 页面：
* **API 设置**: 填写 API Key (推荐 DeepSeek/OpenAI)。
* **音频源**: 选择你的麦克风设备。
* **识别引擎**: 推荐中文用户切换至 `FunASR`。

### 2. 快捷键 (Hotkeys)
* `Ctrl + B`: **开始/停止录音** (默认 Hold 模式，可改为 Toggle)。
* `Ctrl + N`: **手动发送** (当关闭自动发送时使用)。

### 3. VRChat 联动
确保 VRChat 径向菜单中的 `Options -> OSC -> Enabled` 已开启。说话后，翻译结果将自动出现在你头顶的聊天框中。

## 📂 项目结构 (Structure)

```text
Polyglot/
├── app/
│   ├── assets/          # 语言包与资源文件
│   ├── core/            # 核心接口定义 (Interfaces)
│   ├── plugins/         # ASR 引擎插件 (Whisper/FunASR)
│   ├── services/        # 业务逻辑服务 (Audio, Trans, Hotkey)
│   └── ui/              # PySide6 界面逻辑
├── models/              # 本地模型缓存
├── bin/                 # 外部依赖 (FFmpeg)
├── docs/                # 项目文档
├── run.py               # 启动入口
└── requirements.txt     # 依赖清单
```

## 🤝 贡献 (Contributing)

我们欢迎极客们的参与！无论是提交 PR 修复 Bug，还是增加新的 ASR 插件。详情请参阅 [CONTRIBUTING.md](docs/CONTRIBUTING.md)。

## 📄 许可证 (License)

本项目基于 [MIT License](LICENSE) 开源。商业使用请遵循开源协议。
