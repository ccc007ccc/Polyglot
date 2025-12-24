# app/vr/input_handler.py
import openvr
from PySide6.QtCore import QPoint, QEvent, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget, QPushButton

class VRInputHandler:
    Y_INVERT = False 

    def __init__(self, target_widget):
        self.widget = target_widget
        self.pressed_widget = None
        # 防止重复触发
        self._last_click_state = False

    # [新增] 手动射线输入接口
    def process_manual_raycast(self, uv, is_trigger_down):
        """
        处理自制的射线输入
        :param uv: (x, y) 范围 0.0 ~ 1.0，如果没射中则为 None
        :param is_trigger_down: 扳机键是否按下
        """
        w = self.widget.width()
        h = self.widget.height()
        
        # 1. 处理光标位置
        if uv is None:
            # 没射中，隐藏光标
            if hasattr(self.widget, "set_debug_cursor"):
                self.widget.set_debug_cursor(-1, -1)
            return
        
        # 映射坐标
        raw_x, raw_y = uv
        target_x = int(raw_x * w)
        if self.Y_INVERT:
            target_y = int((1.0 - raw_y) * h)
        else:
            target_y = int(raw_y * h)
            
        target_x = max(0, min(target_x, w - 1))
        target_y = max(0, min(target_y, h - 1))

        # 更新红点位置
        if hasattr(self.widget, "set_debug_cursor"):
            self.widget.set_debug_cursor(target_x, target_y)

        # 2. 构造 Qt 事件
        # 只有坐标发生变化或点击状态改变时才频繁发送，这里简化为每帧发送 Move
        global_pos = self.widget.mapToGlobal(QPoint(target_x, target_y))
        local_pos = QPoint(target_x, target_y)

        # 发送移动事件 (Hover 效果)
        self._send_qt_event(QEvent.MouseMove, local_pos, global_pos, Qt.NoButton)

        # 3. 处理点击逻辑 (模拟 Down / Up)
        if is_trigger_down and not self._last_click_state:
            # Press
            self._send_qt_event(QEvent.MouseButtonPress, local_pos, global_pos, Qt.LeftButton)
            
            # 手动处理按钮视觉
            child = self.widget.childAt(local_pos)
            receiver = child if child else self.widget
            if isinstance(receiver, QPushButton):
                receiver.setDown(True)
                self.pressed_widget = receiver
                
        elif not is_trigger_down and self._last_click_state:
            # Release
            self._send_qt_event(QEvent.MouseButtonRelease, local_pos, global_pos, Qt.LeftButton)
            
            # 触发点击
            if self.pressed_widget:
                self.pressed_widget.setDown(False)
                # 再次检查释放位置是否还在按钮上
                child = self.widget.childAt(local_pos)
                if child == self.pressed_widget:
                    self.pressed_widget.click()
                self.pressed_widget = None

        self._last_click_state = is_trigger_down

    def _send_qt_event(self, type, local_pos, global_pos, btn):
        child = self.widget.childAt(local_pos)
        receiver = child if child else self.widget
        receiver_pos = receiver.mapFrom(self.widget, local_pos)
        
        event = QMouseEvent(
            type, receiver_pos, global_pos, 
            btn if btn != Qt.NoButton else Qt.NoButton,
            btn if btn != Qt.NoButton else Qt.NoButton,
            Qt.NoModifier
        )
        QApplication.postEvent(receiver, event)

    # 保留原有的 handle_event 以兼容菜单模式（如果 SteamVR 仍然发送事件的话）
    def handle_event(self, event):
        # ... (此处代码可保留原样，作为备用) ...
        pass