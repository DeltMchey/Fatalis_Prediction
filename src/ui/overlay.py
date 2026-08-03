"""P4 Step 5: OverlayUI — 黑龙雷达 DearPyGui 覆盖层界面。

从 ai_engine.py 迁移：
  - `Ultimate_Radar_UI` 类（原 L319–L469）整体迁移为 OverlayUI 类

设计约束（与架构计划 Step 5 一致）：
  - __init__ 只保存注入依赖，不创建 DPG context、不执行 ctypes
  - _compute_frame 实现原 update_logic 核心逻辑，禁止调用 DearPyGUI
  - _apply_display 只负责 DearPyGUI 更新
  - _setup_dpg 负责 DPG context/window/widgets/viewport + Win32 透明窗口
  - 依赖 dearpygui / ctypes / time / traceback / threading / collections
  - 不依赖 pymem / joblib / pandas / numpy（全部通过注入组件访问）
"""

import ctypes
import queue
import threading
import time
import traceback
from collections import deque

from dearpygui import dearpygui as dpg

from src.config.actions import ACTION_DB
from src.config.offsets import OFFSETS
from src.logging_config import setup_logging

logger = setup_logging()

# Win32 透明窗口常量（WS_EX_LAYERED | WS_EX_TRANSPARENT）
_WIN32_EX_STYLE: int = -20
_WIN32_LAYERED: int = 0x80000
_WIN32_TRANSPARENT: int = 0x20

# AI 预测节流间隔（秒）— 与 ai_engine.py 原 L436 一致
_AI_THROTTLE_INTERVAL: float = 0.5


class OverlayUI:
    """黑龙战斗雷达覆盖层界面。

    用法（P4.6 主程序组装）：
        ui = OverlayUI(memory_reader, state_tracker, predictor, action_buffer, action_lock)
        ui.run()          # 阻塞，直到 DPG 窗口关闭

    线程模型（与 ai_engine.py 一致）：
      - OverlayUI 运行在主线程（DPG event loop）
      - CombatRecorder 运行在 daemon 线程（录制）
      - state_tracker / memory_reader / predictor 由两个线程共享
    """

    # 窗口尺寸
    _WINDOW_WIDTH: int = 420
    _WINDOW_HEIGHT: int = 350
    # 休眠提示文本
    _DORMANT_TEXT: str = "未在虚黑城，雷达已休眠..."
    # Nova 预警文本
    _NOVA_WARNING_TEXT: str = "【飞天火预警】血线触发，请立刻准备规避！"

    def __init__(
        self,
        memory_reader,
        state_tracker,
        predictor,
        action_buffer: deque,
        action_lock: threading.Lock,
    ):
        """初始化 OverlayUI — 只保存注入依赖，不做任何 DPG/ctypes 操作。

        Args:
            memory_reader: MemoryReader 实例（所有游戏内存读取的唯一入口）
            state_tracker: CombatStateTracker 实例（读写战斗状态）
            predictor: ActionPredictor 实例（AI 预测）
            action_buffer: deque，存储最近动作 ID（Recorder 写入，UI 读取）
            action_lock: threading.Lock，保护 action_buffer
        """
        self._reader = memory_reader
        self._state = state_tracker
        self._predictor = predictor
        self._buffer = action_buffer
        self._lock = action_lock
        self._last_ai_time: float = 0.0      # AI 预测节流游标
        self._widgets: dict = {}              # DPG widget 句柄
        self._running: bool = False           # event loop 运行标志（run() 内设置）
        self._visible: bool = False           # viewport 可见标志
        self._thread: threading.Thread | None = None  # daemon 线程
        self._command_queue: "queue.Queue[str]" = queue.Queue(maxsize=10)

    # ================= 录制开关回调 =================

    def _on_recording_toggle(self, sender, value) -> None:
        """checkbox 回调：切换录制状态（写入 state_tracker.is_recording）。"""
        self._state.is_recording = bool(value)

    # ================= DPG 生命周期（独立线程） =================

    # 覆盖层 viewport 标题（FindWindowW + configure_viewport 用）
    _VP_TITLE: str = "overlay"

    # 命令常量
    _CMD_STOP: str = "stop"
    _CMD_SHOW: str = "show"
    _CMD_HIDE: str = "hide"

    def _create_widgets(self) -> None:
        """创建字体 + 窗口 + widgets（run() 在独立线程中调用）。"""
        from src.ui.fonts import setup_cjk_font
        setup_cjk_font()

        with dpg.window(label="Fatalis_God_Radar", width=self._WINDOW_WIDTH,
                        height=self._WINDOW_HEIGHT, no_title_bar=True,
                        no_resize=True, no_move=True, no_scrollbar=True,
                        no_background=True):
            dpg.add_checkbox(label="录制实战数据",
                             default_value=self._state.is_recording,
                             callback=self._on_recording_toggle)
            self._widgets["text_state"] = dpg.add_text("等待接敌...")
            self._widgets["text_ai"] = dpg.add_text("")

    def _apply_win32_overlay(self) -> None:
        """设置 Win32 透明无边框覆盖层（ctypes）。仅 Windows 有效。"""
        hwnd = ctypes.windll.user32.FindWindowW(None, "overlay")
        ctypes.windll.user32.SetWindowLongW(
            hwnd, _WIN32_EX_STYLE,
            ctypes.windll.user32.GetWindowLongW(hwnd, _WIN32_EX_STYLE)
            | _WIN32_LAYERED | _WIN32_TRANSPARENT)
        ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x2)
        dpg.set_viewport_pos(
            (ctypes.windll.user32.GetSystemMetrics(0) - self._WINDOW_WIDTH - 20,
             int(ctypes.windll.user32.GetSystemMetrics(1) * 0.25)))

    def _destroy(self) -> None:
        """销毁 DPG context（在 run() finally 中调用）。"""
        dpg.destroy_context()

    # ================= 线程管理（Controller 调用） =================

    def start(self) -> None:
        """启动覆盖层 daemon 线程（幂等）。

        线程运行 run()——创建独立 DPG context + viewport + event loop。
        必须在 Dashboard 的 DPG context 完全初始化后调用（避免 GLFW 冲突）。
        """
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self.run, daemon=True, name="OverlayUI"
        )
        self._thread.start()

    def stop(self) -> None:
        """请求线程退出（queue 命令，非阻塞）。"""
        self._put_command(self._CMD_STOP)

    def show(self) -> None:
        """请求显示覆盖层 viewport（queue 命令，非阻塞）。"""
        self._put_command(self._CMD_SHOW)

    def hide(self) -> None:
        """请求隐藏覆盖层 viewport（queue 命令，非阻塞）。"""
        self._put_command(self._CMD_HIDE)

    @property
    def is_alive(self) -> bool:
        """Overlay 线程是否运行。"""
        return self._thread is not None and self._thread.is_alive()

    # ================= 线程 target =================

    def run(self) -> None:
        """线程 target——创建独立 DPG context + viewport + event loop。

        所有 DPG 调用在此线程执行（thread-local context）。
        永不直接调用——请使用 start()。main.py standalone 路径除外
        （python main.py 直接调用 run() 阻塞主线程，向后兼容）。
        """
        self._running = True
        dpg.create_context()
        try:
            self._create_widgets()
            dpg.create_viewport(title=self._VP_TITLE, width=self._WINDOW_WIDTH,
                                height=self._WINDOW_HEIGHT, decorated=False,
                                always_on_top=True, clear_color=[0, 0, 0, 0])
            dpg.setup_dearpygui()
            dpg.show_viewport()
            self._apply_win32_overlay()
            self._visible = True
            while dpg.is_dearpygui_running() and self._running:
                self._process_commands()
                if self._visible:
                    self.update_logic()
                dpg.render_dearpygui_frame()
        finally:
            self._destroy()
            self._visible = False
            self._running = False

    def _process_commands(self) -> None:
        """处理 Controller 通过 queue 发来的命令（本线程执行 DPG 调用）。"""
        while not self._command_queue.empty():
            try:
                cmd = self._command_queue.get_nowait()
            except queue.Empty:
                break
            if cmd == self._CMD_STOP:
                self._running = False
            elif cmd == self._CMD_SHOW:
                dpg.configure_viewport(self._VP_TITLE, show=True)
                self._visible = True
            elif cmd == self._CMD_HIDE:
                dpg.configure_viewport(self._VP_TITLE, show=False)
                self._visible = False

    def _put_command(self, cmd: str) -> None:
        """非阻塞投递命令——队列满时丢弃最旧命令，保留最新。"""
        try:
            self._command_queue.put_nowait(cmd)
        except queue.Full:
            try:
                self._command_queue.get_nowait()  # 丢弃最旧
            except queue.Empty:
                pass
            self._command_queue.put_nowait(cmd)

    # ================= 每帧刷新 =================

    def update_logic(self) -> None:
        """每帧刷新：计算显示数据 → 应用到 DPG widgets。

        与 ai_engine.py 原 update_logic L358–L465 等价。
        """
        try:
            display = self._compute_frame()
            self._apply_display(display)
        except Exception:
            logger.error(f"UI 刷新异常:\n{traceback.format_exc()}")

    # ================= 帧计算（纯逻辑，禁止 DPG 调用）=================

    def _compute_frame(self) -> dict | None:
        """计算一帧 UI 显示数据。不做任何 DearPyGUI 调用。

        与 ai_engine.py 原 update_logic 核心逻辑逐行等价，调用顺序：
          1. zone gating
          2. monster/player 内存读取
          3. distance/angle 计算
          4. action 获取与映射
          5. StateTracker 状态更新（phase/enrage/nova/posture）
          6. UI 数据生成
          7. Predictor 预测

        Returns:
            dict: {"state_text", "state_color", "ai_text", "ai_color"}
                  ai_text/ai_color 为 None 表示不更新对应 widget
            None: 跳过该帧（玩家/怪物不存在）
        """
        # 1. zone gating
        if self._reader.check_zone() != OFFSETS.ZONE_FATALIS:
            self._state.reset_for_zone_change()
            with self._lock:
                self._buffer.clear()
            return {
                "state_text": self._DORMANT_TEXT,
                "state_color": [255, 255, 255, 255],
                "ai_text": "",
                "ai_color": None,
            }

        # 2. monster/player 内存读取
        monster = self._reader.find_monster()
        p_coords = self._reader.read_player_coords()
        if monster is None or p_coords is None:
            return None

        # 3. distance/angle 计算
        m_coords = self._reader.read_monster_coords(monster)
        m_quat = self._reader.read_monster_quat(monster)
        dist = self._state.calc_distance_2d(p_coords, m_coords)
        rel_angle = self._state.calc_relative_angle(p_coords, m_coords, m_quat)

        # 4. action 获取与映射
        raw_action = self._buffer[-1] if self._buffer else -1
        action = self._state.map_action(raw_action)

        # 5. StateTracker 状态更新
        hp_percent = self._reader.read_monster_hp(monster)
        self._state.update_phase(hp_percent)
        enrage_timer, enrage_max = self._reader.read_enrage_state(monster)
        self._state.update_enrage(enrage_timer, enrage_max)
        self._state.update_nova(hp_percent, action)
        self._state.update_posture(action)

        # 6. UI 数据生成
        state_text = (
            f"[动作]: {ACTION_DB.get(action, f'({action})')} | "
            f"P{self._state.phase} "
            f"{'[怒]' if self._state.is_enraged else '[未怒]'}\n"
            f"[状态]: 距:{dist:.0f} | 角:{rel_angle:.0f}° | 血:{hp_percent * 100:.1f}%"
        )

        # 7. Predictor 预测
        ai_text, ai_color = self._compute_ai_display(action, dist, rel_angle)

        return {
            "state_text": state_text,
            "state_color": None,
            "ai_text": ai_text,
            "ai_color": ai_color,
        }

    def _compute_ai_display(self, action: int, dist: float,
                            rel_angle: float) -> tuple[str | None, list[int] | None]:
        """计算 AI 预测/预警显示文本与颜色。

        与 ai_engine.py 原 L431–L460 等价：
          - nova_warning → 红色预警文本
          - 模型已加载 + 节流通过 + action != -1 → 绿色预测文本
          - 否则 → (None, None) 不更新

        Returns:
            (ai_text, ai_color)：ai_text=None 表示不更新
        """
        if self._state.nova_warning:
            return (self._NOVA_WARNING_TEXT, [255, 100, 100, 255])

        if (self._predictor.is_loaded
                and time.time() - self._last_ai_time > _AI_THROTTLE_INTERVAL
                and action != -1):
            results = self._predictor.predict(
                dist, rel_angle, self._state.posture, action,
                self._state.phase, self._state.is_enraged,
            )
            ai_msg = "预测下一招:\n"
            for class_id, prob in results:
                ai_msg += f"{ACTION_DB.get(class_id, class_id)}: {prob * 100:.1f}%\n"
            self._last_ai_time = time.time()
            return (ai_msg, [150, 255, 150, 255])

        return (None, None)

    # ================= DPG 应用层 =================

    def _apply_display(self, display: dict | None) -> None:
        """将 _compute_frame 返回的显示数据应用到 DPG widgets。

        与 ai_engine.py 原 update_logic 中 dpg.set_value/configure_item 调用等价。
        display 为 None（跳过帧）时不做任何更新。
        """
        if display is None:
            return
        dpg.set_value(self._widgets["text_state"], display["state_text"])
        if display.get("state_color"):
            dpg.configure_item(self._widgets["text_state"],
                               color=display["state_color"])
        if display.get("ai_text") is not None:
            dpg.set_value(self._widgets["text_ai"], display["ai_text"])
        if display.get("ai_color"):
            dpg.configure_item(self._widgets["text_ai"],
                               color=display["ai_color"])
