import sys
import ctypes
import openvr
from OpenGL.GL import *
from PySide6.QtCore import QObject, Signal, QTimer, QPoint, Qt, QRect, QEvent
from PySide6.QtGui import QImage, QSurfaceFormat, QOpenGLContext, QOffscreenSurface, QPainter, QColor, QPen, QFont, QMouseEvent
from PySide6.QtWidgets import QApplication, QPushButton, QLabel, QVBoxLayout, QWidget
from app.config import ConfigManager
from app.ui.vr_dashboard import VRDashboard

CALIBRATION = {
    "scale_x": 1.0,   
    "scale_y": 1.0,  
    "offset_x": 0.0,
    "offset_y": 0.0 
}

class VRService(QObject):
    """
    SteamVR Overlay 服务控制器 
    """
    req_toggle_rec = Signal()
    req_send = Signal()

    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager()
        self.vr_system = None
        self.overlay = None
        self.overlay_handle = None
        self.is_active = False
        
        self.gl_ctx = None
        self.gl_surface = None
        self.texture_id = None
        
        self.attached_device_index = openvr.k_unTrackedDeviceIndexInvalid
        self.debug_uv = (0.0, 0.0)
        self.last_press_target = None
        self.debug_hit_rect = None # 用于绘制命中的控件边框
        
        self.dashboard = VRDashboard()
        self.dashboard.resize(800, 600)
        
        # === 🔧 布局强修正: 确保按钮沉底 ===
        # 很多时候 QLabel 没内容时不占位，导致按钮上浮
        # 我们在 layout 顶部加一个弹簧，把内容压到底部
        # (注意：这需要访问 VRDashboard 内部 layout，这里做一个简单的 hack)
        try:
            self.dashboard.layout.insertStretch(0, 1)
        except: pass
        
        self.dashboard.req_toggle_rec.connect(self.req_toggle_rec)
        self.dashboard.req_send.connect(self.req_send)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_loop)
        
    def _init_opengl(self):
        if self.gl_ctx: return True
        try:
            fmt = QSurfaceFormat()
            fmt.setRenderableType(QSurfaceFormat.OpenGL)
            fmt.setVersion(4, 1)
            fmt.setProfile(QSurfaceFormat.CoreProfile)
            
            self.gl_ctx = QOpenGLContext()
            self.gl_ctx.setFormat(fmt)
            if not self.gl_ctx.create(): return False
                
            self.gl_surface = QOffscreenSurface()
            self.gl_surface.setFormat(fmt)
            self.gl_surface.create()
            
            if not self.gl_ctx.makeCurrent(self.gl_surface): return False
            return True
        except Exception as e:
            print(f"[VR] GL Init Error: {e}")
            return False

    def start(self):
        if not self.cfg.get("enable_steamvr"): return

        try:
            print("[VR] Initializing OpenVR...")
            self.vr_system = openvr.init(openvr.VRApplication_Overlay)
            self.overlay = openvr.IVROverlay()
            
            if not self._init_opengl():
                print("[VR] OpenGL init failed.")
                return

            key = "polyglot.overlay.v13" 
            name = "Polyglot VR Pro"
            
            self.overlay_handle = self.overlay.createOverlay(key, name)
            self.overlay.setOverlayWidthInMeters(self.overlay_handle, 0.35)
            self.overlay.setOverlayInputMethod(self.overlay_handle, openvr.VROverlayInputMethod_Mouse)
            self.overlay.hideOverlay(self.overlay_handle)
            
            self.is_active = True
            self.timer.start(16)
            print(f"[VR] Service Started. Calibration: {CALIBRATION}")
            
        except Exception as e:
            print(f"[VR] Start Error: {e}")
            self.is_active = False

    def stop(self):
        if self.is_active:
            self.timer.stop()
            try:
                if self.gl_ctx and self.texture_id:
                    self.gl_ctx.makeCurrent(self.gl_surface)
                    glDeleteTextures([self.texture_id])
                if self.overlay and self.overlay_handle:
                    self.overlay.hideOverlay(self.overlay_handle)
                openvr.shutdown()
            except: pass
            self.is_active = False

    def update_content(self, text, status, is_rec):
        if self.is_active:
            self.dashboard.update_content(text)
            self.dashboard.update_status(status, is_rec)

    def _find_and_attach_controller(self):
        if self.attached_device_index != openvr.k_unTrackedDeviceIndexInvalid:
            if self.vr_system.isTrackedDeviceConnected(self.attached_device_index): return
            else: self.attached_device_index = openvr.k_unTrackedDeviceIndexInvalid

        for role in [openvr.TrackedControllerRole_LeftHand, openvr.TrackedControllerRole_RightHand]:
            idx = self.vr_system.getTrackedDeviceIndexForControllerRole(role)
            if idx != openvr.k_unTrackedDeviceIndexInvalid:
                self._attach_to_device(idx)
                return
        
        for i in range(openvr.k_unMaxTrackedDeviceCount):
            if self.vr_system.getTrackedDeviceClass(i) == openvr.TrackedDeviceClass_Controller:
                if self.vr_system.isTrackedDeviceConnected(i):
                    self._attach_to_device(i)
                    return

    def _attach_to_device(self, device_index):
        self.attached_device_index = device_index
        print(f"[VR] Attaching Overlay to Index {device_index}")
        
        transform = openvr.HmdMatrix34_t()
        transform.m[0][0] = 1.0; transform.m[0][1] = 0.0; transform.m[0][2] = 0.0
        transform.m[1][0] = 0.0; transform.m[1][1] = 1.0; transform.m[1][2] = 0.0
        transform.m[2][0] = 0.0; transform.m[2][1] = 0.0; transform.m[2][2] = 1.0
        
        transform.m[0][3] = 0.0   
        transform.m[1][3] = 0.20  
        transform.m[2][3] = -0.15 
        
        self.overlay.setOverlayTransformTrackedDeviceRelative(self.overlay_handle, device_index, transform)
        self.overlay.showOverlay(self.overlay_handle)

    def _update_loop(self):
        if not self.is_active or not self.overlay: return

        try:
            self._find_and_attach_controller()

            event = openvr.VREvent_t()
            max_events = 10 
            while max_events > 0 and self.overlay.pollNextOverlayEvent(self.overlay_handle, event):
                max_events -= 1
                if event.eventType != 0:
                    self._handle_input(event)

            if not self.gl_ctx: return
            self.gl_ctx.makeCurrent(self.gl_surface)
            
            # 1. 渲染 UI
            if self.dashboard.width() != 800: self.dashboard.resize(800, 600)
            img = QImage(self.dashboard.size(), QImage.Format_RGBA8888)
            img.fill(Qt.transparent)
            self.dashboard.render(img)
            
            # 2. 绘制调试层
            painter = QPainter()
            if painter.begin(img):
                try:
                    # 绿色外框
                    painter.setPen(QPen(Qt.green, 6))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(0, 0, img.width(), img.height())
                    
                    # 蓝色命中框 (显示你到底点到了哪里)
                    if self.debug_hit_rect:
                        painter.setPen(QPen(Qt.cyan, 4))
                        painter.drawRect(self.debug_hit_rect)

                    # 红色准星
                    u, v = self.debug_uv
                    x = int(u * 800)
                    y = int(v * 600)
                    if u > 0:
                        painter.setPen(QPen(Qt.red, 3))
                        painter.drawEllipse(QPoint(x, y), 10, 10)
                        
                        # 显示坐标
                        info_text = f"Y:{y}"
                        painter.setFont(QFont("Arial", 16, QFont.Bold))
                        painter.setPen(Qt.yellow)
                        painter.drawText(x + 20, y, info_text)

                except: pass
                finally:
                    painter.end()
            
            # 3. 翻转 & 上传
            img = img.mirrored(False, True)
            width = img.width()
            height = img.height()
            ptr = img.constBits()
            
            if self.texture_id is None:
                self.texture_id = glGenTextures(1)
                glBindTexture(GL_TEXTURE_2D, self.texture_id)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
            
            glBindTexture(GL_TEXTURE_2D, self.texture_id)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, ptr)
            
            texture = openvr.Texture_t()
            texture.handle = int(self.texture_id)
            texture.eType = openvr.TextureType_OpenGL
            texture.eColorSpace = openvr.ColorSpace_Auto
            self.overlay.setOverlayTexture(self.overlay_handle, texture)
            
        except Exception as e:
            print(f"[VR Loop Error] {e}")

    def _handle_input(self, event):
        try:
            data = event.data.mouse
            width = self.dashboard.width()
            height = self.dashboard.height()
            
            # === 校准逻辑 ===
            calib_x = data.x * CALIBRATION["scale_x"] + CALIBRATION["offset_x"]
            calib_y = data.y * CALIBRATION["scale_y"] + CALIBRATION["offset_y"]
            
            self.debug_uv = (calib_x, calib_y)
            
            x = int(calib_x * width)
            y = int(calib_y * height)
            pos = QPoint(x, y)

            if event.eventType == openvr.VREvent_MouseButtonDown:
                child = self.dashboard.childAt(pos)
                
                # 更新调试框：显示命中的控件位置
                if child:
                    # 获取控件在 Dashboard 中的相对坐标
                    local_rect = child.rect()
                    mapped_pos = child.mapTo(self.dashboard, QPoint(0,0))
                    self.debug_hit_rect = QRect(mapped_pos, local_rect.size())
                    
                    if isinstance(child, QPushButton):
                         print(f"[VR] CLICK BUTTON: {child.text()} at {x},{y}")
                         child.click()
                         child.setDown(True)
                    else:
                        print(f"[VR] Hit Non-Button: {child} at {x},{y}")
                else:
                    self.debug_hit_rect = None
                    print(f"[VR] Hit Background at {x},{y}")
                
                # 无论是否命中按钮，都尝试注入事件 (保底)
                target = child if child else self.dashboard
                self.last_press_target = target
                local_pos = target.mapFrom(self.dashboard, pos)
                
                QApplication.postEvent(target, QMouseEvent(
                    QEvent.MouseButtonPress, local_pos, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))

            elif event.eventType == openvr.VREvent_MouseButtonUp:
                if self.last_press_target:
                    target = self.last_press_target
                    local_pos = target.mapFrom(self.dashboard, pos)
                    QApplication.postEvent(target, QMouseEvent(
                        QEvent.MouseButtonRelease, local_pos, pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
                    
                    if isinstance(target, QPushButton):
                        target.setDown(False)
                    self.last_press_target = None
                    # 延时清除调试框
                    QTimer.singleShot(500, lambda: setattr(self, 'debug_hit_rect', None))

        except Exception as e:
            print(f"[VR Input Error] {e}")