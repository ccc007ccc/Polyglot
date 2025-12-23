# app/ui/theme.py

class Theme:
    # 调色板 (Cyberpunk / Modern Dark)
    COLOR_BG = "#121212"        # 极深背景
    COLOR_SURFACE = "#1e1e1e"   # 卡片背景
    COLOR_SURFACE_HOVER = "#2d2d2d"
    
    COLOR_PRIMARY = "#3498db"   # 主色调 (蓝)
    COLOR_ACCENT = "#9b59b6"    # 强调色 (紫)
    
    COLOR_SUCCESS = "#2ecc71"   # 成功/录音中
    COLOR_WARNING = "#f1c40f"   # 处理中
    COLOR_ERROR = "#e74c3c"     # 错误
    
    COLOR_TEXT_MAIN = "#ffffff"
    COLOR_TEXT_SUB = "#b0b0b0"
    
    FONT_FAMILY = "Microsoft YaHei, Segoe UI, sans-serif"

    # 全局样式表
    GLOBAL_STYLES = f"""
        QMainWindow {{
            background-color: {COLOR_BG};
        }}
        QWidget {{
            font-family: "{FONT_FAMILY}";
            font-size: 14px;
            color: {COLOR_TEXT_MAIN};
        }}
        /* 滚动条美化 */
        QScrollBar:vertical {{
            border: none;
            background: {COLOR_BG};
            width: 8px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: #444;
            min-height: 20px;
            border-radius: 4px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        
        /* 文本框 */
        QLineEdit, QTextEdit {{
            background-color: #252526;
            border: 1px solid #3e3e42;
            border-radius: 4px;
            padding: 5px;
            color: #eee;
            selection-background-color: {COLOR_PRIMARY};
        }}
        QLineEdit:focus, QTextEdit:focus {{
            border: 1px solid {COLOR_PRIMARY};
        }}
        
        /* 组合框 */
        QComboBox {{
            background-color: #252526;
            border: 1px solid #3e3e42;
            border-radius: 4px;
            padding: 5px;
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        
        /* 标签 */
        QLabel {{
            color: {COLOR_TEXT_MAIN};
        }}
    """