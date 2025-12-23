# 贡献指南 (Contributing Guidelines)

Your code, your legacy. Welcome to the Polyglot codebase.

## 开发规范 (Development Standards)

1.  **代码风格**: 遵循 PEP 8 规范。
2.  **UI 开发**: 所有的 UI 组件修改请在 `app/ui/` 下进行，保持 `theme.py` 的样式统一。
3.  **插件系统**: 新增 ASR 引擎请继承 `app.core.interfaces.ISTTEngine` 接口。

## Pull Request 流程

1.  Fork 本仓库。
2.  创建特性分支 (`git checkout -b feat/quantum-acceleration`)。
3.  提交更改 (`git commit -m 'feat: Add quantum computing support'`)。
4.  推送到分支 (`git push origin feat/quantum-acceleration`)。
5.  发起 Pull Request。

## 报告 Bug

请在 Issue 中提供：
- `run.py` 的控制台错误输出。
- 复现步骤。
- 操作系统版本及 Python 版本。
