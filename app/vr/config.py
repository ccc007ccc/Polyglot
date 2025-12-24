# app/vr/config.py

class VRConfig:
    OVERLAY_KEY = "polyglot.overlay.pro.v2.5" # 稍微改下 Key 以重置保存的位置
    OVERLAY_NAME = "Polyglot Assistant"
    
    # === 关键修改：改为正方形分辨率 (1:1) ===
    # 这能从数学上根除长宽比不一致导致的点击拉伸/偏移问题
    WIDTH = 800
    HEIGHT = 800 
    
    # 物理宽度 (米)
    WIDTH_IN_METERS = 0.4
    
    TARGET_FPS = 30