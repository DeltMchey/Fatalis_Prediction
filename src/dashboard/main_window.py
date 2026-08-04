"""P5: Dashboard — 用户控制中心主窗口。

DPG primary viewport 承载：
  - 控制台 Tab: 覆盖层子进程启停、录制开关、CSV 文件列表
  - 训练 Tab: TrainingPanel
  - 日志 Tab: LogView
  - 底部状态栏: StatusBar

P5.3 双进程架构（ADR-P5.2）:
  - Overlay 是独立子进程（overlay.py）—— Dashboard 只负责启动/终止子进程
  - Dashboard.run() 阻塞运行在 main 线程（DPG event loop）
  - CombatRecorder daemon 线程（由 main/launch 启动）
  - 训练子进程（AppController 管理）
"""

from pathlib import Path

from dearpygui import dearpygui as dpg

from src.dashboard.log_view import LogView
from src.dashboard.status_bar import StatusBar
from src.dashboard.training_panel import TrainingPanel


class Dashboard:
    """控制中心主窗口。构造函数只存引用，run() 创建 DPG。"""

    _WINDOW_WIDTH: int = 820
    _WINDOW_HEIGHT: int = 600
    _VIEWPORT_TITLE: str = "BlackDragon Control"

    def __init__(self, controller):
        """注入 AppController。"""
        self._controller = controller
        self._widgets: dict = {}
        self._log_view = LogView()
        self._training_panel = TrainingPanel(controller)
        self._status_bar = StatusBar()

    # ================= 生命周期 =================

    def run(self) -> None:
        """创建 DPG context + 主窗口 + viewport，进入 event loop。

        每帧:
          1. 状态栏刷新
          2. 日志/训练输出轮询
        """
        dpg.create_context()
        from src.ui.fonts import setup_cjk_font
        setup_cjk_font()  # Bug 2 fix: 加载中文字体
        try:
            self._build_ui()
            dpg.create_viewport(title=self._VIEWPORT_TITLE,
                                width=self._WINDOW_WIDTH,
                                height=self._WINDOW_HEIGHT)
            dpg.setup_dearpygui()
            dpg.show_viewport()
            while dpg.is_dearpygui_running():
                self._on_frame()
                dpg.render_dearpygui_frame()
        finally:
            self._controller.shutdown()
            dpg.destroy_context()

    # ================= UI 构建 =================

    def _build_ui(self) -> None:
        """创建主窗口 + Tabs + 状态栏。"""
        with dpg.window(label="BlackDragon 控制中心", width=self._WINDOW_WIDTH,
                        height=self._WINDOW_HEIGHT,
                        no_resize=True, no_move=True):  # Bug 3 fix: 固定窗口
            with dpg.tab_bar():
                with dpg.tab(label="控制台"):
                    self._build_console_tab()
                with dpg.tab(label="训练"):
                    self._training_panel.build()
                with dpg.tab(label="日志"):
                    self._log_view.build()
            dpg.add_separator()
            self._status_bar.build()

    def _build_console_tab(self) -> None:
        """控制台 Tab: 覆盖层子进程启停 + 录制开关 + CSV 列表。

        P5.3: Overlay 按钮启动/终止 `overlay.py` 子进程（独立进程）。
        """
        with dpg.group():
            with dpg.group(horizontal=True):
                self._widgets["overlay_btn"] = dpg.add_button(
                    label="启动覆盖层", callback=self._on_overlay_toggle)
                self._widgets["record_chk"] = dpg.add_checkbox(
                    label="录制实战数据",
                    default_value=self._controller.is_recording,
                    callback=self._on_recording_toggle)
            dpg.add_spacer(height=8)
            self._widgets["csv_list"] = dpg.add_text("战斗记录: 加载中...", wrap=0)
            self._widgets["training_data"] = dpg.add_text("训练数据: 检查中...", wrap=0)

    # ================= 每帧刷新 =================

    def _on_frame(self) -> None:
        """每帧刷新：状态栏 + 日志 + CSV 列表 + 按钮状态。

        Overlay 是独立子进程自驱动——Dashboard 不驱动其 update_logic()。
        """
        self._refresh_status()
        self._log_view.refresh()
        self._training_panel.refresh()
        self._refresh_csv_list()
        self._refresh_button_states()

    def _refresh_button_states(self) -> None:
        """根据游戏附着状态启用/禁用控制台按钮。

        需求 B: 无游戏进程时按钮 disabled，游戏附着后 enabled。
        """
        attached = self._controller.is_game_attached
        if "overlay_btn" in self._widgets:
            dpg.configure_item(self._widgets["overlay_btn"],
                               enabled=attached)
        if "record_chk" in self._widgets:
            dpg.configure_item(self._widgets["record_chk"],
                               enabled=attached)

    def _refresh_status(self) -> None:
        """刷新状态栏。"""
        self._status_bar.update(
            game=self._controller.is_game_connected,
            model=self._controller.is_model_loaded,
            recording=self._controller.is_recording,
            overlay=self._controller.is_overlay_running,
        )

    def _refresh_csv_list(self) -> None:
        """刷新战斗记录 + 训练数据状态（每 2 秒——用帧计数节流）。

        - 战斗记录: 只匹配 fatalis_combat_data_*.csv（CombatRecorder 录制产物）
        - 训练数据: 检查 data/ML_Ready_Dataset.csv 是否存在
        使用 controller.data_dir（冻结模式下解析为 <exe_dir>/data）而非
        cwd-relative 路径，确保 Dashboard 和 Recorder 读取同一目录。
        """
        if not hasattr(self, "_csv_tick"):
            self._csv_tick = 0
        self._csv_tick += 1
        if self._csv_tick % 60 != 0:
            return
        data_dir = self._controller.data_dir  # controller.data_dir 已返回 Path

        # ── 战斗记录状态 ──
        try:
            if not data_dir.is_dir():
                dpg.set_value(self._widgets["csv_list"],
                              "战斗记录: 0 个（目录不存在）")
            else:
                files = sorted(data_dir.glob("fatalis_combat_data_*.csv"))
                if not files:
                    dpg.set_value(
                        self._widgets["csv_list"],
                        "战斗记录: 暂无战斗记录（开始游戏录制后自动生成）")
                else:
                    lines = [f"战斗记录: {len(files)} 个"]
                    for f in files[-8:]:
                        lines.append(
                            f"  - {f.name} ({f.stat().st_size // 1024} KB)")
                    dpg.set_value(self._widgets["csv_list"], "\n".join(lines))
        except Exception:
            dpg.set_value(self._widgets["csv_list"], "战斗记录: (无法读取)")

        # ── 训练数据状态 ──
        try:
            dataset = data_dir / "ML_Ready_Dataset.csv"
            if dataset.is_file():
                dpg.set_value(self._widgets["training_data"],
                              "训练数据: ML_Ready_Dataset.csv ✓")
            else:
                dpg.set_value(self._widgets["training_data"],
                              "训练数据: 未找到")
        except Exception:
            dpg.set_value(self._widgets["training_data"], "训练数据: (无法读取)")

    # ================= 回调 =================

    def _on_overlay_toggle(self, sender=None, app_data=None) -> None:
        """覆盖层子进程启停按钮回调（P5.3：启动/终止 overlay.py）。"""
        if self._controller.is_overlay_running:
            self._controller.stop_overlay()
            dpg.configure_item(self._widgets["overlay_btn"], label="启动覆盖层")
        else:
            ok = self._controller.start_overlay()
            if ok:
                dpg.configure_item(self._widgets["overlay_btn"], label="关闭覆盖层")

    def _on_recording_toggle(self, sender=None, value=None) -> None:
        """录制开关回调。"""
        self._controller.set_recording(bool(value))
