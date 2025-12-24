# app/vr/input_handler.py
import openvr
from PySide6.QtCore import QPoint, QEvent, Qt, QObject, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QPushButton

class VRInputHandler(QObject):
    # 发送位移信号 (dx, dy) 单位: 米
    req_move_overlay = Signal(float, float)
    # 发送缩放信号 (delta_scale)
    req_resize_overlay = Signal(float)

    Y_INVERT = False 

    def __init__(self, target_widget):
        super().__init__()
        self.widget = target_widget
        self.pressed_widget = None
        self._last_click_state = False
        
        # 拖拽逻辑状态
        self.drag_mode = None # None, 'move', 'resize'
        self.last_uv = None
        
        # 灵敏度因子
        self.move_sensitivity = 1.0 
        self.resize_sensitivity = 0.5

    def process_manual_raycast(self, uv, is_trigger_down):
        """
        处理射线输入，包含拖动与点击逻辑
        """
        w = self.widget.width()
        h = self.widget.height()
        
        if uv is None:
            if hasattr(self.widget, "set_debug_cursor"):
                self.widget.set_debug_cursor(-1, -1)
            # 丢失追踪时重置拖拽
            self.drag_mode = None
            self.last_uv = None
            return
        
        # 1. 坐标映射
        raw_x, raw_y = uv
        # 修正 Y 轴 (OpenGL 纹理坐标原点在左下，Qt 在左上，但 openvr.TextureType_OpenGL 通常已经翻转，视具体情况而定)
        # 这里假设传入的 uv 已经是左上角原点 (u, 1-v)
        
        target_x = int(raw_x * w)
        target_y = int(raw_y * h)
            
        target_x = max(0, min(target_x, w - 1))
        target_y = max(0, min(target_y, h - 1))

        if hasattr(self.widget, "set_debug_cursor"):
            self.widget.set_debug_cursor(target_x, target_y)

        # 2. 拖拽逻辑核心
        if is_trigger_down:
            if not self._last_click_state:
                # === 按下瞬间 (Press Start) ===
                # 检查是否击中了特殊区域
                child = self.widget.childAt(target_x, target_y)
                
                # 检查是否是 TitleBar (通过 objectName 识别)
                if child and child.objectName() == "VRTitleBar":
                    self.drag_mode = "move"
                    self.last_uv = uv
                # 检查是否是 ResizeHandle
                elif child and child.objectName() == "VRResizeHandle":
                    self.drag_mode = "resize"
                    self.last_uv = uv
                else:
                    # 普通点击，走 Qt 事件分发
                    self._send_press(target_x, target_y)
            else:
                # === 按住阶段 (Holding) ===
                if self.drag_mode == "move" and self.last_uv:
                    # 计算 UV 差值
                    du = uv[0] - self.last_uv[0]
                    dv = uv[1] - self.last_uv[1]
                    
                    # 只有变化足够大才触发，防抖
                    if abs(du) > 0.001 or abs(dv) > 0.001:
                        # 转换 UV 差值到物理位移
                        # 注意：Overlay 坐标系 X轴向右，Y轴向上。
                        # UI UV坐标 u向右，v向下。所以 dy 需要取反
                        self.req_move_overlay.emit(du * self.move_sensitivity, -dv * self.move_sensitivity)
                        self.last_uv = uv
                        
                elif self.drag_mode == "resize" and self.last_uv:
                    du = uv[0] - self.last_uv[0]
                    # 向右拖动增大，向左减小
                    if abs(du) > 0.001:
                        self.req_resize_overlay.emit(du * self.resize_sensitivity)
                        self.last_uv = uv
        else:
            # === 释放阶段 (Release) ===
            if self._last_click_state:
                if self.drag_mode:
                    # 结束拖拽
                    self.drag_mode = None
                    self.last_uv = None
                else:
                    # 普通释放
                    self._send_release(target_x, target_y)
                    
        self._last_click_state = is_trigger_down

        # 始终发送 Hover 事件
        if not self.drag_mode:
            self._send_qt_event(QEvent.MouseMove, QPoint(target_x, target_y), Qt.NoButton)

    def _send_press(self, x, y):
        pos = QPoint(x, y)
        global_pos = self.widget.mapToGlobal(pos)
        self._send_qt_event(QEvent.MouseButtonPress, pos, Qt.LeftButton)
        
        child = self.widget.childAt(pos)
        receiver = child if child else self.widget
        if isinstance(receiver, QPushButton):
            receiver.setDown(True)
            self.pressed_widget = receiver

    def _send_release(self, x, y):
        pos = QPoint(x, y)
        self._send_qt_event(QEvent.MouseButtonRelease, pos, Qt.LeftButton)
        if self.pressed_widget:
            self.pressed_widget.setDown(False)
            child = self.widget.childAt(pos)
            if child == self.pressed_widget:
                self.pressed_widget.click()
            self.pressed_widget = None

    def _send_qt_event(self, type, local_pos, btn):
        child = self.widget.childAt(local_pos)
        receiver = child if child else self.widget
        receiver_pos = receiver.mapFrom(self.widget, local_pos)
        global_pos = self.widget.mapToGlobal(local_pos)
        
        event = QMouseEvent(
            type, receiver_pos, global_pos, 
            btn if btn != Qt.NoButton else Qt.NoButton,
            btn if btn != Qt.NoButton else Qt.NoButton,
            Qt.NoModifier
        )
        QApplication.postEvent(receiver, event)