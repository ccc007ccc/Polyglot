# 更新日志 (Changelog)

All notable changes to this project will be documented in this file.

## [2.4] - 2025-12-24
### ✨ New Features
- **UI 交互升级**: 引入 `NoScroll` 组件，彻底解决设置页面滚轮误触参数的问题。
- **悬浮窗增强**: 优化了 Overlay 的锁定逻辑与鼠标穿透性能。
- **配置持久化**: 增强了 `ConfigManager` 的健壮性。

### ⚡ Performance
- **FunASR 优化**: 重构了 `funasr_local.py` 的日志屏蔽逻辑，静默加载，提升启动速度。
- **FFmpeg**: 优化了 `dep_installer.py` 的下载解压线程逻辑。

## [Legacy]
- 初始化项目架构。
- 实现 Faster-Whisper 与 OpenAI API 的对接。
- 实现 VRChat OSC 通信协议。
