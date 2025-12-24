# app/ui/theme.py

class Theme:
    # 调色板 (Deep Space / Modern SaaS)
    COLOR_BG = "#0f1115"        # 更深邃的背景
    COLOR_SURFACE = "#181b21"   # 卡片背景
    COLOR_SURFACE_HOVER = "#22262e"
    
    COLOR_PRIMARY = "#4f9af9"   # 现代蓝
    COLOR_PRIMARY_HOVER = "#3982e0"
    
    COLOR_ACCENT = "#8e44ad"    # 紫色
    
    COLOR_SUCCESS = "#00c853"   # 鲜亮绿
    COLOR_WARNING = "#ffab00"   # 琥珀色
    COLOR_ERROR = "#ff3d00"     # 活力红
    
    COLOR_TEXT_MAIN = "#f0f0f0"
    COLOR_TEXT_SUB = "#8b949e"
    COLOR_BORDER = "#30363d"    # 边框色

    FONT_FAMILY = "Segoe UI, Microsoft YaHei, sans-serif"

    # 全局样式表
    GLOBAL_STYLES = f"""
        QMainWindow {{
            background-color: {COLOR_BG};
        }}
        QWidget {{
            font-family: "{FONT_FAMILY}";
            font-size: 13px;
            color: {COLOR_TEXT_MAIN};
        }}
        
        /* 滚动条 */
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
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        
        /* 输入框 */
        QLineEdit, QTextEdit, QPlainTextEdit {{
            background-color: #0d1117;
            border: 1px solid {COLOR_BORDER};
            border-radius: 6px;
            padding: 8px;
            color: #e6edf3;
            selection-background-color: {COLOR_PRIMARY};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
            border: 1px solid {COLOR_PRIMARY};
            background-color: #0d1117;
        }}
        
        /* 组合框 */
        QComboBox {{
            background-color: #21262d;
            border: 1px solid {COLOR_BORDER};
            border-radius: 6px;
            padding: 5px 10px;
            min-height: 24px;
        }}
        QComboBox:hover {{ border-color: #8b949e; }}
        QComboBox::drop-down {{ border: none; width: 20px; }}
        QComboBox QAbstractItemView {{
            background-color: {COLOR_SURFACE};
            border: 1px solid {COLOR_BORDER};
            selection-background-color: {COLOR_PRIMARY};
        }}
        
        /* 复选框 */
        QCheckBox {{ spacing: 8px; color: {COLOR_TEXT_MAIN}; }}
        QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 1px solid {COLOR_BORDER}; background: #0d1117; }}
        QCheckBox::indicator:checked {{ background-color: {COLOR_PRIMARY}; border-color: {COLOR_PRIMARY}; image: url(app/assets/icons/check.png); }}
        
        /* 标签 */
        QLabel {{ color: {COLOR_TEXT_MAIN}; }}
        
        /* 提示框 */
        QToolTip {{
            background-color: {COLOR_SURFACE};
            color: {COLOR_TEXT_MAIN};
            border: 1px solid {COLOR_BORDER};
            padding: 5px;
        }}
    """