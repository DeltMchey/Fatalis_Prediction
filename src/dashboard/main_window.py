"""P5: Dashboard — 用户控制中心主窗口。

DPG primary viewport 承载：
  - 控制台 Tab: Overlay 启停、录制开关、CSV 文件列表
  - 训练 Tab: TrainingPanel
  - 日志 Tab: LogView
  - 底部状态栏: StatusBar

线程模型（与 P4 一致）:
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
          1. overlay.update_logic()（若覆盖层已启动）
          2. 状态栏刷新
          3. 日志/训练输出轮询
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
        """控制台 Tab: Overlay 启停 + 录制开关 + CSV 列表。"""
        with dpg.group():
            with dpg.group(horizontal=True):
                self._widgets["overlay_btn"] = dpg.add_button(
                    label="启动覆盖层", callback=self._on_overlay_toggle)
                self._widgets["record_chk"] = dpg.add_checkbox(
                    label="录制实战数据",
                    default_value=self._controller.is_recording,
                    callback=self._on_recording_toggle)
            dpg.add_spacer(height=8)
            self._widgets["csv_list"] = dpg.add_text("CSV 文件:", wrap=0)

    # ================= 每帧刷新 =================

    def _on_frame(self) -> None:
        """每帧刷新：状态栏 + 日志 + CSV 列表 + 按钮状态。

        Overlay 在独立线程自驱动——Dashboard 不驱动其 update_logic()。
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
            overlay=self._controller.is_overlay_visible,
        )

    def _refresh_csv_list(self) -> None:
        """刷新 CSV 文件列表（每 2 秒——用帧计数节流）。"""
        if not hasattr(self, "_csv_tick"):
            self._csv_tick = 0
        self._csv_tick += 1
        if self._csv_tick % 60 != 0:
            return
        data_dir = Path(self._controller.data_dir)
        if not data_dir.is_dir():
            dpg.set_value(self._widgets["csv_list"], "CSV 文件: (无法读取)")
            return
        try:
            files = sorted(data_dir.glob("fatalis_combat_data_*.csv"))
            lines = [f"CSV 文件: {len(files)} 个"]
            for f in files[-8:]:
                lines.append(f"  - {f.name} ({f.stat().st_size // 1024} KB)")
            dpg.set_value(self._widgets["csv_list"], "\n".join(lines))
        except Exception:
            dpg.set_value(self._widgets["csv_list"], "CSV 文件: (无法读取)")

    # ================= 回调 =================

    def _on_overlay_toggle(self, sender=None, app_data=None) -> None:
        """Overlay 启停按钮回调（toggle）。"""
        if self._controller.is_overlay_visible:
            self._controller.stop_overlay()
            dpg.configure_item(self._widgets["overlay_btn"], label="启动覆盖层")
        else:
            ok = self._controller.start_overlay()
            if ok:
                dpg.configure_item(self._widgets["overlay_btn"], label="关闭覆盖层")

    def _on_recording_toggle(self, sender=None, value=None) -> None:
        """录制开关回调。"""
        self._controller.set_recording(bool(value))
