import openvr
import math
from OpenGL.GL import *
from PySide6.QtCore import QObject, Signal, QThread, QTimer, Qt, Slot
from PySide6.QtGui import QImage, QSurfaceFormat, QOpenGLContext, QOffscreenSurface

from app.config import ConfigManager
from .config import VRConfig
from .ui.panel import VRPanel
from .input_handler import VRInputHandler

# === 数学工具类 ===
class Vector3:
    def __init__(self, x, y, z): self.x, self.y, self.z = x, y, z
    def __add__(self, o): return Vector3(self.x+o.x, self.y+o.y, self.z+o.z)
    def __sub__(self, o): return Vector3(self.x-o.x, self.y-o.y, self.z-o.z)
    def __mul__(self, v): return Vector3(self.x*v, self.y*v, self.z*v)
    def dot(self, o): return self.x*o.x + self.y*o.y + self.z*o.z
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

# === VR 工作线程 ===
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
        
        # 设备索引缓存
        self.idx_right_hand = -1
        self.idx_left_hand = -1
        self.attached_device_index = -1 # 当前吸附在哪个设备上
        self.frame_count = 0 # 用于定时检测设备连接

    @Slot()
    def start_loop(self):
        try:
            print("[VR Worker] Init OpenVR...")
            self.vr_system = openvr.init(openvr.VRApplication_Overlay)
            self.overlay = openvr.IVROverlay()
            
            if not self._init_opengl():
                self.sig_started.emit(False, "OpenGL Fail")
                return

            self.overlay_handle = self.overlay.createOverlay(VRConfig.OVERLAY_KEY, VRConfig.OVERLAY_NAME)
            self.overlay.setOverlayWidthInMeters(self.overlay_handle, VRConfig.WIDTH_IN_METERS)
            self.overlay.setOverlayInputMethod(self.overlay_handle, openvr.VROverlayInputMethod_Mouse)
            
            # 初始位置设置 (尝试寻找左手)
            self._update_attachment()
            self.overlay.showOverlay(self.overlay_handle)
            
            self.running = True
            self.timer = QTimer()
            self.timer.timeout.connect(self._process_frame)
            
            # [修改] 60 FPS (1000ms / 60 ≈ 16ms)
            self.timer.start(16) 
            
            self.sig_started.emit(True, "VR Ready (60FPS)")
            print("[VR Worker] Loop Started")
            
        except Exception as e:
            print(f"[VR Worker] Init Error: {e}")
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
        except Exception as e:
            print(f"Upload Error: {e}")

    def _process_frame(self):
        if not self.running: return
        try:
            self.frame_count += 1
            
            # 每 60 帧 (约1秒) 检查一次左手是否上线，如果上线了就吸附过去
            if self.frame_count % 60 == 0:
                self._check_devices_and_attach()

            # 1. 寻找右手作为射线源 (Interaction Source)
            if self.idx_right_hand == -1 or not self.vr_system.isTrackedDeviceConnected(self.idx_right_hand):
                self._find_right_hand()
                if self.idx_right_hand == -1: return # 没有右手，无法互动

            # 2. 获取姿态
            poses = self.vr_system.getDeviceToAbsoluteTrackingPose(
                openvr.TrackingUniverseSeated, 0, openvr.k_unMaxTrackedDeviceCount
            )
            # 我们需要知道 overlay 当前相对于世界的位置
            # 因为 overlay 附着在左手(或HMD)上，我们不需要直接读 overlay 的 pose
            # 而是通过父节点的 pose 来推算，或者更简单的：把射线转换到父节点空间进行相交检测
            
            # 获取附着目标 (Parent) 的 Pose
            # 如果没附着，或者附着失效，默认为 HMD
            target_idx = self.attached_device_index if self.attached_device_index != -1 else openvr.k_unTrackedDeviceIndex_Hmd
            
            target_pose = poses[target_idx]
            ctrl_pose = poses[self.idx_right_hand]

            if not target_pose.bPoseIsValid or not ctrl_pose.bPoseIsValid: return

            # 3. 坐标转换准备
            m_target = target_pose.mDeviceToAbsoluteTracking # 左手(或HMD)的世界矩阵
            m_ctrl = ctrl_pose.mDeviceToAbsoluteTracking     # 右手的世界矩阵
            inv_target = get_matrix_inverse(m_target)        # 世界 -> 左手空间的逆矩阵
            
            # 4. 计算右手射线
            # [修改] 45度倾角优化
            # 0度是正前方(0,0,-1)。向下45度: Y = -sin(45), Z = -cos(45)
            # 0.707
            beam_local = Vector3(0, -0.707, -0.707).normalize()
            
            # 转为世界坐标
            p_ctrl_world = transform_point(m_ctrl, Vector3(0,0,0))
            p_beam_end_world = transform_point(m_ctrl, beam_local)
            v_beam_world = (p_beam_end_world - p_ctrl_world).normalize()
            
            # 转为目标(左手)空间坐标
            p_origin_local = transform_point(inv_target, p_ctrl_world)
            p_end_local = transform_point(inv_target, p_ctrl_world + v_beam_world)
            v_dir_local = (p_end_local - p_origin_local).normalize()
            
            # 5. 射线检测 (在左手空间进行)
            # 我们定义的窗口位置 (在 _update_attachment 中设置的)
            if target_idx == openvr.k_unTrackedDeviceIndex_Hmd:
                plane_z = -1.5 # HMD 模式比较远
            else:
                plane_z = -0.35 # [修改] 左手模式：前方 35cm
            
            # 射线与平面 Z = plane_z 求交
            uv_result = None
            is_click = False

            # 注意：如果 v_dir_local.z 接近 0，说明射线平行于屏幕
            if abs(v_dir_local.z) > 1e-6:
                t = (plane_z - p_origin_local.z) / v_dir_local.z
                
                # t > 0 代表向前射击
                if t > 0:
                    hit_point = p_origin_local + v_dir_local * t
                    
                    # 检查是否在窗口范围内
                    # 左手模式下，窗口中心可能还需要 Y 轴偏移
                    # 在 _update_attachment 中，我们设置了 Y=0.25 (25cm Up)
                    # 所以检测中心应该是 (0, 0.25, -0.35)
                    # 我们需要把 hit_point 转换到 "UI 平面坐标系"
                    
                    center_y = 0.0 if target_idx == openvr.k_unTrackedDeviceIndex_Hmd else 0.25
                    
                    # 相对中心的偏移
                    dx = hit_point.x - 0.0
                    dy = hit_point.y - center_y
                    
                    half_size = VRConfig.WIDTH_IN_METERS / 2.0
                    
                    if -half_size <= dx <= half_size and -half_size <= dy <= half_size:
                        # 命中!
                        u = (dx + half_size) / VRConfig.WIDTH_IN_METERS
                        v_coord = (dy + half_size) / VRConfig.WIDTH_IN_METERS
                        v_tex = 1.0 - v_coord 
                        uv_result = (u, v_tex)
                        
                        # 检测扳机
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
        """检测左手是否上线，如果上线了但没附着，就附着过去"""
        idx = self.vr_system.getTrackedDeviceIndexForControllerRole(openvr.TrackedControllerRole_LeftHand)
        
        # 如果找到了左手，且当前没附着在左手上 (或者之前附着在 HMD 上)
        if idx != -1 and idx != self.attached_device_index:
            self._update_attachment(force_left_hand_idx=idx)
            print(f"[VR Worker] Window attached to Left Hand (ID: {idx})")

    def _update_attachment(self, force_left_hand_idx=None):
        """更新窗口附着位置"""
        if not self.overlay or not self.overlay_handle: return
        try:
            t = openvr.HmdMatrix34_t()
            # 基础旋转 (Identity)
            t.m[0][0]=1.0; t.m[0][1]=0.0; t.m[0][2]=0.0; t.m[0][3]=0.0
            t.m[1][0]=0.0; t.m[1][1]=1.0; t.m[1][2]=0.0; t.m[1][3]=0.0
            t.m[2][0]=0.0; t.m[2][1]=0.0; t.m[2][2]=1.0; t.m[2][3]=0.0
            
            target_idx = -1
            
            # 1. 尝试附着到左手
            if force_left_hand_idx:
                idx = force_left_hand_idx
            else:
                idx = self.vr_system.getTrackedDeviceIndexForControllerRole(openvr.TrackedControllerRole_LeftHand)
            
            if idx != -1:
                # === 左手模式配置 ===
                # 位置：上方 25cm (Y=0.25)，前方 35cm (Z=-0.35)
                # 这是一个典型的“看表”或“战术板”位置
                t.m[1][3] = 0.25 
                t.m[2][3] = -0.35
                target_idx = idx
                self.attached_device_index = idx
            else:
                # === 降级模式：HMD ===
                # 位置：正前方 1.5m
                t.m[1][3] = 0.0
                t.m[2][3] = -1.5
                target_idx = openvr.k_unTrackedDeviceIndex_Hmd
                self.attached_device_index = openvr.k_unTrackedDeviceIndex_Hmd # 标记为 HMD
            
            self.overlay.setOverlayTransformTrackedDeviceRelative(
                self.overlay_handle, target_idx, t
            )
            
        except: pass

    def _find_right_hand(self):
        # 寻找射线发射源（优先右手）
        idx = self.vr_system.getTrackedDeviceIndexForControllerRole(openvr.TrackedControllerRole_RightHand)
        if idx != -1: 
            self.idx_right_hand = idx
            return
        # 实在没有右手，用左手当射线源也行（虽然这时候左手如果挂着窗口会很怪）
        idx = self.vr_system.getTrackedDeviceIndexForControllerRole(openvr.TrackedControllerRole_LeftHand)
        if idx != -1: self.idx_right_hand = idx

# === 主线程服务 ===
class SteamVRService(QObject):
    req_toggle_rec = Signal()
    req_send = Signal()
    _sig_upload_texture = Signal(QImage)
    _sig_stop_worker = Signal()
    _sig_start_worker = Signal()

    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager()
        self.is_running = False
        
        self.panel = VRPanel(VRConfig.WIDTH, VRConfig.HEIGHT)
        self.panel.resize(VRConfig.WIDTH, VRConfig.HEIGHT)
        self.input_handler = VRInputHandler(self.panel)
        
        self.panel.req_toggle_rec.connect(self.req_toggle_rec)
        self.panel.req_send.connect(self.req_send)
        self.panel.request_repaint.connect(self._on_repaint_requested)
        
        self.thread = QThread()
        self.worker = VRWorker()
        self.worker.moveToThread(self.thread)
        
        self._sig_start_worker.connect(self.worker.start_loop)
        self._sig_stop_worker.connect(self.worker.stop)
        self._sig_upload_texture.connect(self.worker.upload_texture)
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
        if success:
            print(f"[VR Service] Connection SUCCESS: {msg}")
            self.is_running = True
            self._on_repaint_requested()
        else:
            print(f"[VR Service] Connection FAILED: {msg}")