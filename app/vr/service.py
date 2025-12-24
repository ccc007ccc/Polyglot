# app/vr/service.py
import openvr
import math
from OpenGL.GL import *
from PySide6.QtCore import QObject, Signal, QThread, QTimer, Qt, Slot
from PySide6.QtGui import QImage, QSurfaceFormat, QOpenGLContext, QOffscreenSurface

from app.config import ConfigManager
from .config import VRConfig
from .ui.panel import VRPanel
from .input_handler import VRInputHandler

class Vector3:
    def __init__(self, x, y, z): self.x, self.y, self.z = x, y, z
    def __add__(self, o): return Vector3(self.x+o.x, self.y+o.y, self.z+o.z)
    def __sub__(self, o): return Vector3(self.x-o.x, self.y-o.y, self.z-o.z)
    def __mul__(self, v): return Vector3(self.x*v, self.y*v, self.z*v)
    def length(self): return math.sqrt(self.x**2 + self.y**2 + self.z**2)
    def normalize(self):
        l = self.length()
        return Vector3(self.x/l, self.y/l, self.z/l) if l > 0 else Vector3(0,0,0)

def transform_point(m, v):
    x = m[0][0]*v.x + m[0][1]*v.y + m[0][2]*v.z + m[0][3]
    y = m[1][0]*v.x + m[1][1]*v.y + m[1][2]*v.z + m[1][3]
    z = m[2][0]*v.x + m[2][1]*v.y + m[2][2]*v.z + m[2][3]
    return Vector3(x, y, z)

def get_matrix_inverse(m):
    r00, r01, r02 = m[0][0], m[0][1], m[0][2]
    r10, r11, r12 = m[1][0], m[1][1], m[1][2]
    r20, r21, r22 = m[2][0], m[2][1], m[2][2]
    tx, ty, tz = m[0][3], m[1][3], m[2][3]
    ntx = -(r00*tx + r10*ty + r20*tz)
    nty = -(r01*tx + r11*ty + r21*tz)
    ntz = -(r02*tx + r12*ty + r22*tz)
    return [[r00, r10, r20, ntx], [r01, r11, r21, nty], [r02, r12, r22, ntz]]

class VRWorker(QObject):
    sig_started = Signal(bool, str)
    sig_input_update = Signal(object, bool)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.vr_system = None
        self.overlay = None
        self.overlay_handle = None
        self.gl_ctx = None
        self.surface = None
        self.texture_id = None
        self.timer = None
        
        self.idx_right_hand = -1
        self.attached_device_index = -1
        self.frame_count = 0
        
        # [New] 动态位置偏移量 (相对于左手)
        self.offset = Vector3(0.0, 0.25, -0.35) 
        # [New] 动态宽度 (缩放)
        self.width_meters = VRConfig.WIDTH_IN_METERS

    @Slot()
    def start_loop(self):
        try:
            print("[VR Worker] Init OpenVR...")
            self.vr_system = openvr.init(openvr.VRApplication_Overlay)
            self.overlay = openvr.IVROverlay()
            
            if not self._init_opengl():
                self.sig_started.emit(False, "OpenGL Init Failed")
                return

            self.overlay_handle = self.overlay.createOverlay(VRConfig.OVERLAY_KEY, VRConfig.OVERLAY_NAME)
            self.overlay.setOverlayWidthInMeters(self.overlay_handle, self.width_meters)
            self.overlay.setOverlayInputMethod(self.overlay_handle, openvr.VROverlayInputMethod_Mouse)
            
            self._update_attachment()
            self.overlay.showOverlay(self.overlay_handle)
            
            self.running = True
            self.timer = QTimer()
            self.timer.timeout.connect(self._process_frame)
            self.timer.start(16) # 60 FPS
            
            self.sig_started.emit(True, "Connected")
            
        except Exception as e:
            self.sig_started.emit(False, str(e))

    @Slot()
    def stop(self):
        self.running = False
        if self.timer: self.timer.stop()
        try:
            if self.gl_ctx:
                self.gl_ctx.makeCurrent(self.surface)
                if self.texture_id: glDeleteTextures([self.texture_id])
            openvr.shutdown()
        except: pass

    @Slot(float, float)
    def move_overlay(self, dx, dy):
        """接收 UI 传来的相对位移"""
        if not self.running: return
        # 简单叠加位移
        self.offset.x += dx
        self.offset.y += dy
        # 立即更新位置
        self._update_attachment(self.attached_device_index)

    @Slot(float)
    def resize_overlay(self, d_scale):
        if not self.running: return
        new_width = self.width_meters + d_scale
        # 限制范围 (0.1米 ~ 2.0米)
        self.width_meters = max(0.1, min(new_width, 2.0))
        try:
            self.overlay.setOverlayWidthInMeters(self.overlay_handle, self.width_meters)
        except: pass

    @Slot(QImage)
    def upload_texture(self, image):
        if not self.running or not self.gl_ctx: return
        try:
            if self.gl_ctx.makeCurrent(self.surface):
                glBindTexture(GL_TEXTURE_2D, self.texture_id)
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, image.width(), image.height(), 
                             0, GL_RGBA, GL_UNSIGNED_BYTE, image.constBits())
                
                tex = openvr.Texture_t()
                tex.handle = int(self.texture_id)
                tex.eType = openvr.TextureType_OpenGL
                tex.eColorSpace = openvr.ColorSpace_Auto
                self.overlay.setOverlayTexture(self.overlay_handle, tex)
        except: pass

    def _process_frame(self):
        if not self.running: return
        try:
            self.frame_count += 1
            if self.frame_count % 60 == 0:
                self._check_devices_and_attach()

            # 寻找右手
            if self.idx_right_hand == -1 or not self.vr_system.isTrackedDeviceConnected(self.idx_right_hand):
                self._find_right_hand()
                if self.idx_right_hand == -1: return

            poses = self.vr_system.getDeviceToAbsoluteTrackingPose(
                openvr.TrackingUniverseSeated, 0, openvr.k_unMaxTrackedDeviceCount
            )
            target_idx = self.attached_device_index if self.attached_device_index != -1 else openvr.k_unTrackedDeviceIndex_Hmd
            
            target_pose = poses[target_idx]
            ctrl_pose = poses[self.idx_right_hand]

            if not target_pose.bPoseIsValid or not ctrl_pose.bPoseIsValid: return

            # 坐标转换与射线检测
            m_target = target_pose.mDeviceToAbsoluteTracking
            m_ctrl = ctrl_pose.mDeviceToAbsoluteTracking
            inv_target = get_matrix_inverse(m_target)
            
            # 射线方向：向下倾斜45度
            beam_local = Vector3(0, -0.707, -0.707).normalize()
            
            p_ctrl_world = transform_point(m_ctrl, Vector3(0,0,0))
            p_beam_end_world = transform_point(m_ctrl, beam_local)
            v_beam_world = (p_beam_end_world - p_ctrl_world).normalize()
            
            p_origin_local = transform_point(inv_target, p_ctrl_world)
            p_end_local = transform_point(inv_target, p_ctrl_world + v_beam_world)
            v_dir_local = (p_end_local - p_origin_local).normalize()
            
            # 使用动态偏移量 offset.z
            plane_z = self.offset.z
            
            uv_result = None
            is_click = False

            if abs(v_dir_local.z) > 1e-6:
                t = (plane_z - p_origin_local.z) / v_dir_local.z
                if t > 0:
                    hit_point = p_origin_local + v_dir_local * t
                    
                    # 动态中心点 offset.y, offset.x
                    center_y = self.offset.y
                    center_x = self.offset.x
                    
                    dx = hit_point.x - center_x
                    dy = hit_point.y - center_y
                    
                    # 动态宽度
                    half_size = self.width_meters / 2.0
                    
                    if -half_size <= dx <= half_size and -half_size <= dy <= half_size:
                        u = (dx + half_size) / self.width_meters
                        v_coord = (dy + half_size) / self.width_meters
                        v_tex = 1.0 - v_coord 
                        uv_result = (u, v_tex)
                        
                        state = self.vr_system.getControllerState(self.idx_right_hand)[1]
                        is_click = (state.ulButtonPressed & (1 << openvr.k_EButton_SteamVR_Trigger)) != 0
            
            self.sig_input_update.emit(uv_result, is_click)
            
            e = openvr.VREvent_t()
            self.overlay.pollNextOverlayEvent(self.overlay_handle, e)

        except Exception: pass

    def _init_opengl(self):
        fmt = QSurfaceFormat()
        fmt.setRenderableType(QSurfaceFormat.OpenGL)
        fmt.setVersion(4, 1)
        fmt.setProfile(QSurfaceFormat.CoreProfile)
        self.gl_ctx = QOpenGLContext(); self.gl_ctx.setFormat(fmt)
        if not self.gl_ctx.create(): return False
        self.surface = QOffscreenSurface(); self.surface.setFormat(fmt); self.surface.create()
        if not self.gl_ctx.makeCurrent(self.surface): return False
        self.texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        return True

    def _check_devices_and_attach(self):
        idx = self.vr_system.getTrackedDeviceIndexForControllerRole(openvr.TrackedControllerRole_LeftHand)
        if idx != -1 and idx != self.attached_device_index:
            self._update_attachment(force_idx=idx)

    def _update_attachment(self, force_idx=None):
        if not self.overlay or not self.overlay_handle: return
        try:
            t = openvr.HmdMatrix34_t()
            # Identity
            for i in range(3):
                for j in range(4): t.m[i][j] = 0.0
            t.m[0][0]=1.0; t.m[1][1]=1.0; t.m[2][2]=1.0
            
            target_idx = -1
            if force_idx is not None: idx = force_idx
            else: idx = self.vr_system.getTrackedDeviceIndexForControllerRole(openvr.TrackedControllerRole_LeftHand)
            
            if idx != -1:
                # 使用动态变量
                t.m[0][3] = self.offset.x
                t.m[1][3] = self.offset.y 
                t.m[2][3] = self.offset.z
                target_idx = idx
                self.attached_device_index = idx
            else:
                # HMD 默认位置
                t.m[1][3] = 0.0
                t.m[2][3] = -1.5
                target_idx = openvr.k_unTrackedDeviceIndex_Hmd
                self.attached_device_index = openvr.k_unTrackedDeviceIndex_Hmd
            
            self.overlay.setOverlayTransformTrackedDeviceRelative(self.overlay_handle, target_idx, t)
        except: pass

    def _find_right_hand(self):
        idx = self.vr_system.getTrackedDeviceIndexForControllerRole(openvr.TrackedControllerRole_RightHand)
        if idx != -1: self.idx_right_hand = idx
        else:
            idx = self.vr_system.getTrackedDeviceIndexForControllerRole(openvr.TrackedControllerRole_LeftHand)
            if idx != -1: self.idx_right_hand = idx

class SteamVRService(QObject):
    req_toggle_rec = Signal()
    req_send = Signal()
    
    # [Fix] 新增连接状态信号
    sig_connection_status = Signal(bool, str)
    
    _sig_upload_texture = Signal(QImage)
    _sig_stop_worker = Signal()
    _sig_start_worker = Signal()
    _sig_move_overlay = Signal(float, float)
    _sig_resize_overlay = Signal(float)

    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager()
        self.is_running = False
        
        self.panel = VRPanel(VRConfig.WIDTH, VRConfig.HEIGHT)
        self.input_handler = VRInputHandler(self.panel)
        
        # 连接 Panel 的信号
        self.panel.req_toggle_rec.connect(self.req_toggle_rec)
        self.panel.req_send.connect(self.req_send)
        self.panel.request_repaint.connect(self._on_repaint_requested)
        
        # 连接 InputHandler 的拖动信号
        self.input_handler.req_move_overlay.connect(self._sig_move_overlay)
        self.input_handler.req_resize_overlay.connect(self._sig_resize_overlay)
        
        self.thread = QThread()
        self.worker = VRWorker()
        self.worker.moveToThread(self.thread)
        
        self._sig_start_worker.connect(self.worker.start_loop)
        self._sig_stop_worker.connect(self.worker.stop)
        self._sig_upload_texture.connect(self.worker.upload_texture)
        self._sig_move_overlay.connect(self.worker.move_overlay)
        self._sig_resize_overlay.connect(self.worker.resize_overlay)
        
        self.worker.sig_started.connect(self._on_worker_started)
        self.worker.sig_input_update.connect(self._on_input_update)
        
        self.thread.start()

    def start(self):
        if not self.cfg.get("enable_steamvr"): return
        self._sig_start_worker.emit()

    def stop(self):
        if self.is_running:
            self._sig_stop_worker.emit()
            self.thread.quit()
            self.thread.wait()
            self.is_running = False

    def update_content(self, text, status, is_recording):
        if self.is_running:
            self.panel.update_state(text, status, is_recording)

    def _on_repaint_requested(self):
        if not self.is_running: return
        image = QImage(self.panel.size(), QImage.Format_RGBA8888)
        image.fill(Qt.transparent)
        self.panel.render(image)
        image = image.mirrored(False, True)
        self._sig_upload_texture.emit(image)

    def _on_input_update(self, uv, is_click):
        self.input_handler.process_manual_raycast(uv, is_click)

    def _on_worker_started(self, success, msg):
        # [Fix] 接收工作线程的准确结果，并转发给主线程
        self.is_running = success
        self.sig_connection_status.emit(success, msg)
        if success:
            self._on_repaint_requested()