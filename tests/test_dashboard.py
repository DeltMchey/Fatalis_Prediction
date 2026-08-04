"""P5: Dashboard tests — 控制中心 UI。

策略：
  - Linux CI 上 dearpygui 未安装：模块级预装 stub → import 成功
  - 所有测试 patch src.dashboard.*.dpg → 不启动真实窗口
  - mock AppController → 验证 UI 调用正确方法

覆盖：
  - 构造（无 DPG 副作用）
  - _build_ui 创建 tabs + widgets
  - 控制台回调（overlay toggle、recording toggle）
  - StatusBar.update 值刷新
  - LogView append/refresh
  - TrainingPanel build/refresh/回调
  - _on_frame 驱动 overlay + 状态刷新
"""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────────────────────────────────────────────────────────
# 跨平台 stub：dearpygui 是 Windows-only 依赖，Linux CI 不安装。
# 在 import dashboard 模块之前预装空模块，使 import 成功。
# ─────────────────────────────────────────────────────────────────────────
if "dearpygui" not in sys.modules:
    _dpg_stub = types.ModuleType("dearpygui")
    _dpg_mod = types.ModuleType("dearpygui.dearpygui")
    _dpg_stub.dearpygui = _dpg_mod
    sys.modules["dearpygui"] = _dpg_stub
    sys.modules["dearpygui.dearpygui"] = _dpg_mod

from src.dashboard.log_view import LogView
from src.dashboard.main_window import Dashboard
from src.dashboard.status_bar import StatusBar
from src.dashboard.training_panel import TrainingPanel


@pytest.fixture
def mock_controller():
    """返回 mock AppController。"""
    ctrl = MagicMock()
    ctrl.is_game_connected = True
    ctrl.is_model_loaded = True
    ctrl.is_recording = True
    ctrl.is_overlay_running = False
    ctrl.is_training = False
    ctrl.get_training_output.return_value = []
    ctrl.data_dir = "data"
    ctrl._config = MagicMock()
    ctrl._config.data_dir = "data"
    return ctrl


@pytest.fixture
def mock_dpg_all():
    """同时 patch 四个 dashboard 子模块的 dpg 引用。

    _build_ui() 会调用 training_panel/log_view/status_bar 的 build()，
    它们各自使用自己模块命名空间中的 dpg —— 必须全部替换。
    """
    with patch("src.dashboard.main_window.dpg") as mw, \
            patch("src.dashboard.training_panel.dpg"), \
            patch("src.dashboard.log_view.dpg"), \
            patch("src.dashboard.status_bar.dpg"):
        yield mw


# =============================================================================
# 1. 构造
# =============================================================================

class TestConstruction:
    def test_constructor_stores_controller(self, mock_controller):
        dash = Dashboard(mock_controller)
        assert dash._controller is mock_controller

    def test_constructor_no_dpg_side_effects(self, mock_controller):
        """构造函数不应创建 DPG context。"""
        with patch("src.dashboard.main_window.dpg") as mock_dpg:
            Dashboard(mock_controller)
            mock_dpg.create_context.assert_not_called()
            mock_dpg.create_viewport.assert_not_called()


# =============================================================================
# 2. UI 构建
# =============================================================================

class TestBuildUI:
    def test_build_ui_creates_tabs(self, mock_controller, mock_dpg_all):
        dash = Dashboard(mock_controller)
        dash._build_ui()
        # tab_bar 被调用（创建 tab 结构）
        assert mock_dpg_all.tab_bar.call_count == 1
        # tab 调用（控制台/训练/日志）
        assert mock_dpg_all.tab.call_count == 3
        # window 被创建
        mock_dpg_all.window.assert_called_once()

    def test_build_ui_creates_console_widgets(self, mock_controller, mock_dpg_all):
        dash = Dashboard(mock_controller)
        dash._build_ui()
        assert "overlay_btn" in dash._widgets
        assert "record_chk" in dash._widgets
        assert "csv_list" in dash._widgets


# =============================================================================
# 3. 控制台回调
# =============================================================================

class TestConsoleCallbacks:
    def test_overlay_toggle_start(self, mock_controller, mock_dpg_all):
        """P5.3: 覆盖层未运行 → start_overlay 启动子进程。"""
        mock_controller.is_overlay_running = False
        mock_controller.start_overlay.return_value = True
        dash = Dashboard(mock_controller)
        dash._build_ui()
        dash._on_overlay_toggle()
        mock_controller.start_overlay.assert_called_once()
        mock_controller.stop_overlay.assert_not_called()

    def test_overlay_toggle_stop(self, mock_controller, mock_dpg_all):
        """P5.3: 覆盖层运行中 → stop_overlay 终止子进程。"""
        mock_controller.is_overlay_running = True
        dash = Dashboard(mock_controller)
        dash._build_ui()
        dash._on_overlay_toggle()
        mock_controller.stop_overlay.assert_called_once()
        mock_controller.start_overlay.assert_not_called()

    def test_recording_toggle_calls_controller(self, mock_controller):
        with patch("src.dashboard.main_window.dpg"):
            dash = Dashboard(mock_controller)
            dash._on_recording_toggle(None, True)
        mock_controller.set_recording.assert_called_once_with(True)


# =============================================================================
# 4. StatusBar
# =============================================================================

class TestStatusBar:
    def test_update_calls_set_value(self, mock_controller):
        with patch("src.dashboard.status_bar.dpg") as mock_dpg:
            bar = StatusBar()
            bar._game_text = "g"
            bar._model_text = "m"
            bar._rec_text = "r"
            bar._ovl_text = "o"
            bar.update(game=True, model=True, recording=True,
                       overlay=True)
        assert mock_dpg.set_value.call_count == 4

    def test_update_recording_on(self, mock_controller):
        with patch("src.dashboard.status_bar.dpg") as mock_dpg:
            bar = StatusBar()
            bar._rec_text = "r"
            bar.update(game=False, model=False, recording=True,
                       overlay=False)
        args = mock_dpg.set_value.call_args[0]
        assert "进行中" in args[1]

    def test_update_recording_off(self, mock_controller):
        with patch("src.dashboard.status_bar.dpg") as mock_dpg:
            bar = StatusBar()
            bar._rec_text = "r"
            bar.update(game=False, model=False, recording=False,
                       overlay=False)
        args = mock_dpg.set_value.call_args[0]
        assert "停止" in args[1]


# =============================================================================
# 5. LogView
# =============================================================================

class TestLogView:
    def test_append_renders(self):
        with patch("src.dashboard.log_view.dpg") as mock_dpg:
            view = LogView()
            view._text_tag = "tag"
            view.append("hello")
            view.append("world")
        calls = mock_dpg.set_value.call_args_list
        assert calls[-1][0][0] == "tag"
        assert "hello\nworld" in calls[-1][0][1]

    def test_append_trims_to_max(self):
        with patch("src.dashboard.log_view.dpg"):
            view = LogView(max_lines=3)
            view._text_tag = "tag"
            for i in range(10):
                view.append(f"line{i}")
            assert len(view._buffer) == 3
            assert view._buffer[0] == "line7"

    def test_refresh_drains_global_queue(self, monkeypatch):
        import queue
        from src.logging_config import get_log_queue
        q = queue.Queue()
        monkeypatch.setattr("src.dashboard.log_view.get_log_queue",
                            lambda: q)
        # 构造一个 LogRecord
        import logging
        rec = logging.LogRecord("BlackDragon", logging.WARNING,
                                __file__, 1, "warn msg", None, None)
        q.put(rec)
        with patch("src.dashboard.log_view.dpg") as mock_dpg:
            view = LogView()
            view._text_tag = "tag"
            view.refresh()
        assert "[WARNING] warn msg" in mock_dpg.set_value.call_args[0][1]


# =============================================================================
# 6. TrainingPanel
# =============================================================================

class TestTrainingPanel:
    def test_build_creates_widgets(self, mock_controller):
        with patch("src.dashboard.training_panel.dpg") as mock_dpg:
            panel = TrainingPanel(mock_controller)
            panel.build()
        assert "start_btn" in panel._widgets
        assert "cancel_btn" in panel._widgets
        assert "status" in panel._widgets
        assert "output" in panel._widgets

    def test_on_start_calls_controller(self, mock_controller):
        mock_controller.start_training.return_value = True
        with patch("src.dashboard.training_panel.dpg"):
            panel = TrainingPanel(mock_controller)
            panel._on_start()
        mock_controller.start_training.assert_called_once()

    def test_on_cancel_calls_controller(self, mock_controller):
        with patch("src.dashboard.training_panel.dpg"):
            panel = TrainingPanel(mock_controller)
            panel._on_cancel()
        mock_controller.cancel_training.assert_called_once()

    def test_refresh_reads_output(self, mock_controller):
        mock_controller.get_training_output.return_value = ["line1", "line2"]
        mock_controller.is_training = True
        with patch("src.dashboard.training_panel.dpg") as mock_dpg:
            panel = TrainingPanel(mock_controller)
            panel._widgets["output"] = "out"
            panel._widgets["status"] = "st"
            panel.refresh()
        assert mock_dpg.set_value.call_count >= 2


# =============================================================================
# 7. _on_frame
# =============================================================================

class TestOnFrame:
    def test_on_frame_refreshes_dashboard_only(self, mock_controller):
        """_on_frame 刷新状态栏/日志/训练/CSV/按钮——不驱动 overlay。

        P5.3: Overlay 是独立子进程自驱动——Dashboard 不调用其 update_logic()。
        """
        with patch("src.dashboard.main_window.dpg"):
            dash = Dashboard(mock_controller)
            dash._log_view.refresh = MagicMock()
            dash._training_panel.refresh = MagicMock()
            dash._refresh_status = MagicMock()
            dash._refresh_csv_list = MagicMock()
            dash._refresh_button_states = MagicMock()
            dash._on_frame()

        dash._log_view.refresh.assert_called_once()
        dash._training_panel.refresh.assert_called_once()
        dash._refresh_status.assert_called_once()
        dash._refresh_csv_list.assert_called_once()
        dash._refresh_button_states.assert_called_once()


# =============================================================================
# 8. run() 生命周期
# =============================================================================

class TestRun:
    def test_run_lifecycle(self, mock_controller, mock_dpg_all):
        """run() 完整生命周期：context → build → viewport → loop → shutdown → destroy。"""
        mock_dpg_all.is_dearpygui_running.side_effect = [True, True, False]
        dash = Dashboard(mock_controller)
        dash._on_frame = MagicMock()
        with patch("src.ui.fonts.dpg") as mock_font_dpg:
            dash.run()
        mock_dpg_all.create_context.assert_called_once()
        mock_dpg_all.create_viewport.assert_called_once()
        mock_dpg_all.setup_dearpygui.assert_called_once()
        mock_dpg_all.show_viewport.assert_called_once()
        assert mock_dpg_all.render_dearpygui_frame.call_count == 2
        mock_dpg_all.destroy_context.assert_called_once()
        mock_controller.shutdown.assert_called_once()

    def test_run_shutdown_on_exception(self, mock_controller, mock_dpg_all):
        """即使 DPG 异常，也保证 shutdown + destroy。"""
        mock_dpg_all.create_viewport.side_effect = RuntimeError("dpg boom")
        dash = Dashboard(mock_controller)
        with patch("src.ui.fonts.dpg"):
            with pytest.raises(RuntimeError):
                dash.run()
        mock_controller.shutdown.assert_called_once()
        mock_dpg_all.destroy_context.assert_called_once()

    def test_run_loads_cjk_font(self, mock_controller, mock_dpg_all):
        """Bug 2: run() 应在 create_context 后加载中文字体。"""
        mock_dpg_all.is_dearpygui_running.side_effect = [False]
        dash = Dashboard(mock_controller)
        # main_window.run() 内部 from src.ui.fonts import setup_cjk_font
        # → patch 源头模块
        with patch("src.ui.fonts.setup_cjk_font") as mock_font:
            dash.run()
        mock_font.assert_called_once()


# =============================================================================
# 10. Bug 3: 窗口固定（不可拖动/缩放）
# =============================================================================

class TestWindowFlags:
    def test_window_is_fixed(self, mock_controller, mock_dpg_all):
        """Dashboard 主窗口应设置 no_resize + no_move。"""
        dash = Dashboard(mock_controller)
        dash._build_ui()
        kwargs = mock_dpg_all.window.call_args.kwargs
        assert kwargs.get("no_resize") is True
        assert kwargs.get("no_move") is True


# =============================================================================
# 9. _refresh_csv_list
# =============================================================================

class TestRefreshCsvList:
    def test_refresh_csv_list_lists_files(self, mock_controller, mock_dpg_all, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "fatalis_combat_data_20260101_000000.csv").write_text("x")
        (data_dir / "fatalis_combat_data_20260101_000001.csv").write_text("y")
        mock_controller.data_dir = str(data_dir)
        dash = Dashboard(mock_controller)
        dash._widgets["csv_list"] = "csv_widget"
        dash._csv_tick = 59  # 下一次 refresh 触发（% 60 == 0）
        dash._refresh_csv_list()
        # 列表文本包含 2 个文件
        call = mock_dpg_all.set_value.call_args
        assert call[0][0] == "csv_widget"
        assert "2 个" in call[0][1]

    def test_refresh_csv_list_throttled(self, mock_controller, mock_dpg_all):
        """帧计数节流：非 60 的倍数不刷新。"""
        dash = Dashboard(mock_controller)
        dash._widgets["csv_list"] = "csv_widget"
        dash._csv_tick = 1
        dash._refresh_csv_list()
        mock_dpg_all.set_value.assert_not_called()

    def test_refresh_csv_list_missing_dir(self, mock_controller, mock_dpg_all, tmp_path):
        """data_dir 不存在 → 显示无法读取。"""
        mock_controller.data_dir = str(tmp_path / "nonexistent")
        dash = Dashboard(mock_controller)
        dash._widgets["csv_list"] = "csv_widget"
        dash._csv_tick = 59  # 下一次 refresh 触发
        dash._refresh_csv_list()
        call = mock_dpg_all.set_value.call_args
        assert "无法读取" in call[0][1]
