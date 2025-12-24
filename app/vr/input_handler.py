# app/vr/input_handler.py
import openvr
from PySide6.QtCore import QPoint, QEvent, Qt, QObject
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QPushButton

class VRInputHandler(QObject):
    def __init__(self, target_widget):
        super().__init__()
        self.widget = target_widget
        self.pressed_widget = None
        self._last_click_state = False

    def process_manual_raycast(self, uv, is_trigger_down):
        """
        处理内容区的常规交互（按钮点击、Hover）
        注意：如果 Worker 正在拖拽，它会传入 uv=None，从而暂停 UI 交互
        """
        w = self.widget.width()
        h = self.widget.height()
        
        target_x, target_y = -1, -1
        
        # 1. 坐标映射
        if uv is not None:
            raw_x, raw_y = uv
            target_x = int(raw_x * w)
            target_y = int(raw_y * h)
            target_x = max(0, min(target_x, w - 1))
            target_y = max(0, min(target_y, h - 1))
            
            if hasattr(self.widget, "set_debug_cursor"):
                self.widget.set_debug_cursor(target_x, target_y)
        else:
            if hasattr(self.widget, "set_debug_cursor"):
                self.widget.set_debug_cursor(-1, -1)
            # 如果丢失 UV（比如正在拖拽中），不仅隐藏光标，还要处理松开逻辑以防卡键
            if self._last_click_state and not is_trigger_down:
                pass # 下面会处理 release

        # 2. 点击逻辑
        if is_trigger_down:
            if not self._last_click_state:
                # Press
                if target_x >= 0:
                    self._send_press(target_x, target_y)
            else:
                # Hold (不需要特殊处理，Qt会自动处理)
                pass
        else:
            if self._last_click_state:
                # Release
                # 即使 uv 为 None (target_x=-1)，也要发送 Release 以释放之前的 Press
                # 我们使用上一次的坐标或者 (0,0)
                self._send_release(target_x if target_x >= 0 else 0, target_y if target_y >= 0 else 0)
        
        self._last_click_state = is_trigger_down

        # Hover
        if not is_trigger_down and target_x >= 0:
            self._send_qt_event(QEvent.MouseMove, QPoint(target_x, target_y), Qt.NoButton)

    def _send_press(self, x, y):
        pos = QPoint(x, y)
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