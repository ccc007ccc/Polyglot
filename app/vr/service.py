# app/vr/service.py
import openvr
import math
import logging
from OpenGL.GL import *
from PySide6.QtCore import QObject, Signal, QThread, QTimer, Qt, Slot
from PySide6.QtGui import QImage, QSurfaceFormat, QOpenGLContext, QOffscreenSurface

from app.config import ConfigManager
from .config import VRConfig
from .ui.panel import VRPanel
from .input_handler import VRInputHandler

# === 矩阵数学工具库 (Mat4) ===
class Mat4:
    @staticmethod
    def identity():
        return [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0]
        ]

    @staticmethod
    def from_hmd_matrix34(m):
        """将 OpenVR HmdMatrix34_t 转换为 4x4 列表"""
        return [
            [m.m[0][0], m.m[0][1], m.m[0][2], m.m[0][3]],
            [m.m[1][0], m.m[1][1], m.m[1][2], m.m[1][3]],
            [m.m[2][0], m.m[2][1], m.m[2][2], m.m[2][3]],
            [0.0,       0.0,       0.0,       1.0]
        ]

    @staticmethod
    def to_hmd_matrix34(m_list):
        """将 4x4 列表转换回 OpenVR HmdMatrix34_t"""
        t = openvr.HmdMatrix34_t()
        for i in range(3):
            for j in range(4):
                t.m[i][j] = m_list[i][j]
        return t

    @staticmethod
    def multiply(a, b):
        """矩阵乘法 A * B"""
        result = [[0.0]*4 for _ in range(4)]
        for i in range(4):
            for j in range(4):
                for k in range(4):
                    result[i][j] += a[i][k] * b[k][j]
        return result

    @staticmethod
    def inverse(m):
        """计算刚体变换矩阵(旋转+平移)的逆矩阵"""
        r = [[m[i][j] for j in range(3)] for i in range(3)]
        t = [m[0][3], m[1][3], m[2][3]]
        
        r_inv = [[r[j][i] for j in range(3)] for i in range(3)]
        
        t_inv = [0.0, 0.0, 0.0]
        for i in range(3):
            val = 0.0
            for k in range(3):
                val += r_inv[i][k] * t[k]
            t_inv[i] = -val
            
        res = Mat4.identity()
        for i in range(3):
            for j in range(3):
                res[i][j] = r_inv[i][j]
            res[i][3] = t_inv[i]
        return res

    @staticmethod
    def transform_point(m, p):
        """矩阵变换点 (x, y, z)"""
        x = m[0][0]*p[0] + m[0][1]*p[1] + m[0][2]*p[2] + m[0][3]
        y = m[1][0]*p[0] + m[1][1]*p[1] + m[1][2]*p[2] + m[1][3]
        z = m[2][0]*p[0] + m[2][1]*p[1] + m[2][2]*p[2] + m[2][3]
        return (x, y, z)

    @staticmethod
    def get_pos(m):
        return (m[0][3], m[1][3], m[2][3])

# === Worker 核心 ===
class VRWorker(QObject):
    sig_started = Signal(bool, str)
    sig_input_update = Signal(object, bool)
    
    STATE_IDLE = 0
    STATE_DRAGGING = 1
    STATE_RESIZING = 2

    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager() # 加载配置管理器
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
        
        # --- [LOAD] 从配置中读取位置和大小 ---
        self.local_transform = self.cfg.get("vr_matrix")
        self.width_meters = self.cfg.get("vr_width")
        
        # 如果读取失败（比如旧版本配置），重置为默认
        if not self.local_transform or len(self.local_transform) != 4:
            self.local_transform = Mat4.identity()
            self.local_transform[0][3] = 0.0
            self.local_transform[1][3] = 0.25 
            self.local_transform[2][3] = -0.35
        
        if not self.width_meters: 
            self.width_meters = VRConfig.WIDTH_IN_METERS

        self.state = self.STATE_IDLE
        
        self.grab_relative_transform = None 
        self.resize_start_hand_x = 0.0      
        self.resize_start_width = 0.0

    @Slot(object)
    def set_surface(self, surface):
        self.surface = surface

    @Slot()
    def start_loop(self):
        try:
            self.vr_system = openvr.init(openvr.VRApplication_Overlay)
            self.overlay = openvr.IVROverlay()
            
            if not self._init_opengl():
                print("VR: OpenGL init warning")

            self.overlay_handle = self.overlay.createOverlay(VRConfig.OVERLAY_KEY, VRConfig.OVERLAY_NAME)
            self.overlay.setOverlayWidthInMeters(self.overlay_handle, self.width_meters)
            self.overlay.setOverlayInputMethod(self.overlay_handle, openvr.VROverlayInputMethod_Mouse)
            
            self._update_attachment()
            self.overlay.showOverlay(self.overlay_handle)
            
            self.running = True
            self.timer = QTimer()
            self.timer.timeout.connect(self._process_frame)
            self.timer.start(16)
            
            self.sig_started.emit(True, "Connected")
            
        except Exception as e:
            self.sig_started.emit(False, str(e))

    @Slot()
    def stop(self):
        self.running = False
        if self.timer: self.timer.stop()
        try:
            openvr.shutdown()
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

            if self.idx_right_hand == -1: self._find_right_hand()
            if self.idx_right_hand == -1: return

            poses = self.vr_system.getDeviceToAbsoluteTrackingPose(
                openvr.TrackingUniverseSeated, 0, openvr.k_unMaxTrackedDeviceCount
            )
            
            target_idx = self.attached_device_index if self.attached_device_index != -1 else openvr.k_unTrackedDeviceIndex_Hmd
            
            pose_anchor = poses[target_idx]
            pose_hand = poses[self.idx_right_hand]

            if not pose_anchor.bPoseIsValid or not pose_hand.bPoseIsValid: return

            mat_anchor_world = Mat4.from_hmd_matrix34(pose_anchor.mDeviceToAbsoluteTracking)
            mat_hand_world = Mat4.from_hmd_matrix34(pose_hand.mDeviceToAbsoluteTracking)
            inv_anchor_world = Mat4.inverse(mat_anchor_world)

            state = self.vr_system.getControllerState(self.idx_right_hand)[1]
            is_trigger_down = (state.ulButtonPressed & (1 << openvr.k_EButton_SteamVR_Trigger)) != 0

            # === 状态机 ===
            
            if self.state == self.STATE_IDLE:
                uv, is_hit = self._calculate_raycast(mat_hand_world, mat_anchor_world)
                
                if is_trigger_down and is_hit and uv:
                    u, v = uv
                    
                    if v < 0.15: # 拖拽区域
                        self.state = self.STATE_DRAGGING
                        mat_overlay_world = Mat4.multiply(mat_anchor_world, self.local_transform)
                        inv_hand_world = Mat4.inverse(mat_hand_world)
                        self.grab_relative_transform = Mat4.multiply(inv_hand_world, mat_overlay_world)
                        self.sig_input_update.emit(None, False)
                        
                    elif u > 0.85 and v > 0.85: # 缩放区域
                        self.state = self.STATE_RESIZING
                        p_hand_local = Mat4.transform_point(inv_anchor_world, Mat4.get_pos(mat_hand_world))
                        self.resize_start_hand_x = p_hand_local[0]
                        self.resize_start_width = self.width_meters
                        self.sig_input_update.emit(None, False)
                    else:
                        self.sig_input_update.emit(uv, True)
                else:
                    self.sig_input_update.emit(uv, False)

            elif self.state == self.STATE_DRAGGING:
                if not is_trigger_down:
                    self.state = self.STATE_IDLE
                    self.grab_relative_transform = None
                    # --- [SAVE] 拖拽结束，保存位置 ---
                    self.cfg.set("vr_matrix", self.local_transform)
                    self.cfg.save()
                    print("VR Config Saved (Position)")
                else:
                    new_overlay_world = Mat4.multiply(mat_hand_world, self.grab_relative_transform)
                    self.local_transform = Mat4.multiply(inv_anchor_world, new_overlay_world)
                    self._update_attachment(target_idx)
                    self.sig_input_update.emit(None, False)

            elif self.state == self.STATE_RESIZING:
                if not is_trigger_down:
                    self.state = self.STATE_IDLE
                    # --- [SAVE] 缩放结束，保存大小 ---
                    self.cfg.set("vr_width", self.width_meters)
                    self.cfg.save()
                    print("VR Config Saved (Size)")
                else:
                    p_hand_local = Mat4.transform_point(inv_anchor_world, Mat4.get_pos(mat_hand_world))
                    current_x = p_hand_local[0]
                    delta_x = current_x - self.resize_start_hand_x
                    new_width = self.resize_start_width + (delta_x * 2.0)
                    self.width_meters = max(0.1, min(new_width, 2.0))
                    
                    self.overlay.setOverlayWidthInMeters(self.overlay_handle, self.width_meters)
                    self.sig_input_update.emit(None, False)

            e = openvr.VREvent_t()
            self.overlay.pollNextOverlayEvent(self.overlay_handle, e)

        except Exception: pass

    def _calculate_raycast(self, mat_hand_world, mat_anchor_world):
        ray_origin = Mat4.get_pos(mat_hand_world)
        
        # 45度向下
        beam_local_end = (0, -0.707, -0.707)
        ray_end = Mat4.transform_point(mat_hand_world, beam_local_end)
        
        ray_dir = (ray_end[0]-ray_origin[0], ray_end[1]-ray_origin[1], ray_end[2]-ray_origin[2])
        length = math.sqrt(ray_dir[0]**2 + ray_dir[1]**2 + ray_dir[2]**2)
        if length < 1e-5: return None, False
        ray_dir = (ray_dir[0]/length, ray_dir[1]/length, ray_dir[2]/length)

        mat_overlay_world = Mat4.multiply(mat_anchor_world, self.local_transform)
        plane_center = Mat4.get_pos(mat_overlay_world)
        z_point = Mat4.transform_point(mat_overlay_world, (0,0,1))
        plane_normal = (z_point[0]-plane_center[0], z_point[1]-plane_center[1], z_point[2]-plane_center[2])
        nl = math.sqrt(plane_normal[0]**2 + plane_normal[1]**2 + plane_normal[2]**2)
        plane_normal = (plane_normal[0]/nl, plane_normal[1]/nl, plane_normal[2]/nl)

        denom = plane_normal[0]*ray_dir[0] + plane_normal[1]*ray_dir[1] + plane_normal[2]*ray_dir[2]
        if abs(denom) < 1e-4: return None, False
        
        vec_co = (plane_center[0]-ray_origin[0], plane_center[1]-ray_origin[1], plane_center[2]-ray_origin[2])
        t = (vec_co[0]*plane_normal[0] + vec_co[1]*plane_normal[1] + vec_co[2]*plane_normal[2]) / denom
        
        if t < 0: return None, False
        
        hit_point = (ray_origin[0] + ray_dir[0]*t, ray_origin[1] + ray_dir[1]*t, ray_origin[2] + ray_dir[2]*t)

        inv_overlay = Mat4.inverse(mat_overlay_world)
        hit_local = Mat4.transform_point(inv_overlay, hit_point)
        
        dx = hit_local[0]
        dy = hit_local[1]
        
        half_w = self.width_meters / 2.0
        half_h = half_w 
        
        if -half_w <= dx <= half_w and -half_h <= dy <= half_h:
            u = (dx + half_w) / self.width_meters
            v_coord = (dy + half_h) / self.width_meters
            return (u, 1.0 - v_coord), True
            
        return None, False

    def _init_opengl(self):
        try:
            fmt = QSurfaceFormat()
            fmt.setRenderableType(QSurfaceFormat.OpenGL)
            fmt.setVersion(4, 1)
            fmt.setProfile(QSurfaceFormat.CoreProfile)
            self.gl_ctx = QOpenGLContext()
            self.gl_ctx.setFormat(fmt)
            if not self.gl_ctx.create(): return False
            if self.surface and not self.gl_ctx.makeCurrent(self.surface): 
                return False
            self.texture_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.texture_id)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            return True
        except: return False

    def _check_devices_and_attach(self):
        idx = self.vr_system.getTrackedDeviceIndexForControllerRole(openvr.TrackedControllerRole_LeftHand)
        if idx != -1 and idx != self.attached_device_index:
            self._update_attachment(idx)

    def _update_attachment(self, idx=None):
        if not self.overlay or not self.overlay_handle: return
        if idx is None: idx = self.attached_device_index
        if idx == -1: idx = openvr.k_unTrackedDeviceIndex_Hmd
        
        self.attached_device_index = idx
        t = Mat4.to_hmd_matrix34(self.local_transform)
        self.overlay.setOverlayTransformTrackedDeviceRelative(self.overlay_handle, idx, t)

    def _find_right_hand(self):
        idx = self.vr_system.getTrackedDeviceIndexForControllerRole(openvr.TrackedControllerRole_RightHand)
        if idx != -1: self.idx_right_hand = idx
        else:
            idx = self.vr_system.getTrackedDeviceIndexForControllerRole(openvr.TrackedControllerRole_LeftHand)
            if idx != -1: self.idx_right_hand = idx

class SteamVRService(QObject):
    req_toggle_rec = Signal()
    req_send = Signal()
    sig_connection_status = Signal(bool, str)
    
    _sig_upload_texture = Signal(QImage)
    _sig_stop_worker = Signal()
    _sig_start_worker = Signal()
    _sig_set_surface = Signal(object)

    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager()
        self.is_running = False
        
        self.panel = VRPanel(VRConfig.WIDTH, VRConfig.HEIGHT)
        self.input_handler = VRInputHandler(self.panel)
        
        self.panel.req_toggle_rec.connect(self.req_toggle_rec)
        self.panel.req_send.connect(self.req_send)
        self.panel.request_repaint.connect(self._on_repaint_requested)
        
        self.surface = QOffscreenSurface()
        self.surface.create()
        
        self.thread = QThread()
        self.worker = VRWorker()
        self.worker.moveToThread(self.thread)
        
        self._sig_start_worker.connect(self.worker.start_loop)
        self._sig_stop_worker.connect(self.worker.stop)
        self._sig_upload_texture.connect(self.worker.upload_texture)
        self._sig_set_surface.connect(self.worker.set_surface)
        
        self.worker.sig_started.connect(self._on_worker_started)
        self.worker.sig_input_update.connect(self._on_input_update)
        
        self.thread.start()
        
        self._sig_set_surface.emit(self.surface)

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
        self.is_running = success
        self.sig_connection_status.emit(success, msg)
        if success:
            self._on_repaint_requested()