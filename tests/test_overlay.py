"""P4 Step 5: OverlayUI tests — mock MemoryReader/Predictor UI 测试。

策略：
  - MemoryReader 用 MagicMock(spec=MemoryReader) 模拟（无 pymem 依赖）
  - ActionPredictor 用 MagicMock(spec=ActionPredictor) 模拟（无模型依赖）
  - CombatStateTracker 用真实实例（纯逻辑）验证状态流
  - 不启动真实 DearPyGUI 窗口：DPG 调用通过 patch("src.ui.overlay.dpg") mock
  - _compute_frame 为纯逻辑方法，无需 DPG 即可测试

覆盖：
  - 构造：依赖存储、无 DPG 副作用
  - 录制开关回调
  - _compute_frame zone gating / 无实体 / 正常帧 / 状态更新顺序
  - nova warning / predictor 预测 / 预测节流 / predictor 未加载
  - action_buffer 读取与清理
  - update_logic 异常处理
  - _apply_display DPG 更新
  - 结构约束：无 pymem 直读、无 shared_state、_compute_frame 无 DPG
"""

import logging
import threading
import time
from collections import deque
from unittest.mock import MagicMock, patch

import pytest

from src.config.offsets import OFFSETS
from src.core.memory_reader import MemoryReader
from src.core.state_tracker import CombatStateTracker
from src.model.predictor import ActionPredictor
from src.ui.overlay import OverlayUI

FAKE_MONSTER_PTR = 0x30000000
FAKE_P_COORDS = [100.0, 0.0, 200.0]
FAKE_M_COORDS = [110.0, 0.0, 210.0]
FAKE_M_QUAT = [0.0, 1.0, 0.0, 0.0]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_reader():
    """返回模拟 MemoryReader，默认提供有效战斗数据。"""
    reader = MagicMock(spec=MemoryReader)
    reader.check_zone.return_value = OFFSETS.ZONE_FATALIS
    reader.find_monster.return_value = FAKE_MONSTER_PTR
    reader.read_player_coords.return_value = FAKE_P_COORDS
    reader.read_monster_coords.return_value = FAKE_M_COORDS
    reader.read_monster_quat.return_value = FAKE_M_QUAT
    reader.read_monster_hp.return_value = 0.65
    reader.read_enrage_state.return_value = (0.0, 180.0)
    return reader


@pytest.fixture
def mock_predictor():
    """返回模拟 ActionPredictor（已加载模型）。"""
    pred = MagicMock(spec=ActionPredictor)
    pred.is_loaded = True
    pred.predict.return_value = [(37, 0.45), (53, 0.30), (81, 0.15)]
    return pred


@pytest.fixture
def state():
    """真实 CombatStateTracker。"""
    return CombatStateTracker(is_recording=True)


@pytest.fixture
def buffer():
    return deque(maxlen=100)


@pytest.fixture
def lock():
    return threading.Lock()


@pytest.fixture
def overlay(mock_reader, mock_predictor, state, buffer, lock):
    return OverlayUI(mock_reader, state, mock_predictor, buffer, lock)


# =============================================================================
# 1. 构造
# =============================================================================

class TestInitialization:
    def test_stores_dependencies(self, mock_reader, mock_predictor, state, buffer, lock):
        ui = OverlayUI(mock_reader, state, mock_predictor, buffer, lock)
        assert ui._reader is mock_reader
        assert ui._state is state
        assert ui._predictor is mock_predictor
        assert ui._buffer is buffer
        assert ui._lock is lock

    def test_init_no_dpg_side_effects(self, mock_reader, mock_predictor, state, buffer, lock):
        """__init__ 不应创建 DPG context 或调用任何 DPG 函数。"""
        with patch("src.ui.overlay.dpg") as mock_dpg:
            ui = OverlayUI(mock_reader, state, mock_predictor, buffer, lock)
            assert ui._widgets == {}  # 未创建任何 widget
            mock_dpg.create_context.assert_not_called()
            mock_dpg.create_viewport.assert_not_called()
            mock_dpg.setup_dearpygui.assert_not_called()

    def test_init_no_ctypes(self, mock_reader, mock_predictor, state, buffer, lock):
        """__init__ 不应执行 ctypes（Win32 逻辑只在 _setup_dpg）。"""
        with patch("ctypes.windll") as mock_windll:
            OverlayUI(mock_reader, state, mock_predictor, buffer, lock)
            mock_windll.user32.assert_not_called()


# =============================================================================
# 2. 录制开关回调
# =============================================================================

class TestRecordingToggle:
    def test_toggle_sets_is_recording(self, overlay):
        overlay._on_recording_toggle(None, False)
        assert overlay._state.is_recording is False
        overlay._on_recording_toggle(None, True)
        assert overlay._state.is_recording is True


# =============================================================================
# 3. _compute_frame — zone gating
# =============================================================================

class TestZoneGating:
    def test_wrong_zone_returns_dormant(self, overlay, mock_reader):
        mock_reader.check_zone.return_value = 123
        display = overlay._compute_frame()
        assert display is not None
        assert display["state_text"] == "未在虚黑城，雷达已休眠..."
        assert display["state_color"] == [255, 255, 255, 255]
        assert display["ai_text"] == ""

    def test_zone_none_returns_dormant(self, overlay, mock_reader):
        mock_reader.check_zone.return_value = None
        display = overlay._compute_frame()
        assert display["state_text"] == "未在虚黑城，雷达已休眠..."

    def test_zone_change_resets_state(self, overlay, mock_reader, state):
        """离开虚黑城 → state_tracker 彻底重置。"""
        # 先构造一个"战斗进行中"的状态
        state.update_phase(0.30)          # phase=3
        state.update_enrage(5.0, 10.0)    # is_enraged=1
        state.update_posture(49)          # posture=0
        state.update_nova(0.90, 37)       # 初始化（无阈值触发）
        state.update_nova(0.30, 37)       # 跨过阈值 → nova_warning=True
        assert state.nova_warning is True

        mock_reader.check_zone.return_value = 123
        overlay._compute_frame()

        assert state.posture == 1
        assert state.phase == 1
        assert state.is_enraged == 0
        assert state.nova_warning is False
        assert state.hp_initialized is False
        assert state.triggered_novas == set()

    def test_zone_change_clears_buffer(self, overlay, mock_reader, buffer):
        """离开虚黑城 → action_buffer 被清空。"""
        buffer.extend([37, 53, 81])
        mock_reader.check_zone.return_value = 123
        overlay._compute_frame()
        assert len(buffer) == 0

    def test_in_fatalis_continues(self, overlay, mock_reader):
        """在虚黑城 → 正常生成显示数据。"""
        display = overlay._compute_frame()
        assert display is not None
        assert display["state_text"] != "未在虚黑城，雷达已休眠..."


# =============================================================================
# 4. _compute_frame — 无实体
# =============================================================================

class TestEntityMissing:
    def test_no_monster_returns_none(self, overlay, mock_reader):
        mock_reader.find_monster.return_value = None
        assert overlay._compute_frame() is None

    def test_no_player_returns_none(self, overlay, mock_reader):
        mock_reader.read_player_coords.return_value = None
        assert overlay._compute_frame() is None


# =============================================================================
# 5. _compute_frame — 正常帧
# =============================================================================

class TestNormalFrame:
    def test_state_text_content(self, overlay, buffer):
        """正常帧生成正确状态文本。"""
        buffer.append(37)  # 37 → "龙车"
        display = overlay._compute_frame()
        assert display["state_text"] == (
            "[动作]: 龙车 | P2 [未怒]\n"
            "[状态]: 距:14 | 角:45° | 血:65.0%"
        )

    def test_ai_text_contains_prediction(self, overlay, mock_predictor, buffer):
        """预测结果格式化进入 ai_text。"""
        buffer.append(37)
        display = overlay._compute_frame()
        assert "预测下一招:" in display["ai_text"]
        assert "龙车: 45.0%" in display["ai_text"]
        assert "连咬: 30.0%" in display["ai_text"]
        assert display["ai_color"] == [150, 255, 150, 255]

    def test_predictor_called_with_6_features(self, overlay, mock_predictor, buffer):
        """predict 被调用且传入 6 个特征。"""
        buffer.append(37)
        overlay._compute_frame()
        mock_predictor.predict.assert_called_once()
        args = mock_predictor.predict.call_args[0]
        # (distance, relative_angle, posture, previous_action, phase, is_enraged)
        assert len(args) == 6
        assert abs(args[0] - 14.1421) < 0.01   # distance
        assert args[2] == 1                     # posture
        assert args[3] == 37                    # previous_action
        assert args[4] == 2                     # phase (hp=0.65 → P2)
        assert args[5] == 0                     # is_enraged


# =============================================================================
# 6. StateTracker 状态更新顺序
# =============================================================================

class TestStateUpdateOrder:
    def test_phase_updated_from_hp(self, overlay, state):
        overlay._compute_frame()
        assert state.phase == 2  # hp=0.65 → P2

    def test_enrage_updated(self, overlay, state, mock_reader):
        mock_reader.read_enrage_state.return_value = (5.0, 180.0)
        overlay._compute_frame()
        assert state.is_enraged == 1

    def test_posture_updated_from_buffer_action(self, overlay, state, buffer):
        buffer.append(49)  # 49 ∈ POSTURE_PRONE
        overlay._compute_frame()
        assert state.posture == 0

    def test_nova_state_updated(self, overlay, state, mock_reader):
        """低血量 → nova_warning 触发（先初始化后跨阈值）。"""
        mock_reader.read_monster_hp.side_effect = [0.90, 0.20]
        overlay._compute_frame()  # 高血量初始化（无阈值触发）
        overlay._compute_frame()  # 低血量 → 跨过阈值 → warning
        assert state.nova_warning is True


# =============================================================================
# 7. nova warning
# =============================================================================

class TestNovaWarning:
    def test_nova_warning_display(self, overlay, mock_reader, buffer):
        """nova_warning → 显示红色预警文本。"""
        mock_reader.read_monster_hp.side_effect = [0.90, 0.20]
        buffer.append(37)
        overlay._compute_frame()  # 初始化
        display = overlay._compute_frame()  # 触发
        assert display["ai_text"] == "【飞天火预警】血线触发，请立刻准备规避！"
        assert display["ai_color"] == [255, 100, 100, 255]

    def test_nova_warning_skips_prediction(self, overlay, mock_reader,
                                           mock_predictor, buffer):
        """nova_warning 时预测被跳过。"""
        mock_reader.read_monster_hp.side_effect = [0.90, 0.20, 0.20]
        buffer.append(37)
        overlay._compute_frame()  # 初始化
        overlay._compute_frame()  # 触发 nova_warning
        # 第三次调用仍处于 nova_warning → 不调用 predict
        mock_predictor.predict.reset_mock()
        overlay._compute_frame()
        mock_predictor.predict.assert_not_called()


# =============================================================================
# 8. predictor 节流
# =============================================================================

class TestPredictionThrottle:
    def test_first_call_predicts(self, overlay, mock_predictor, buffer):
        """首次调用（_last_ai_time=0）应执行预测。"""
        buffer.append(37)
        overlay._compute_frame()
        mock_predictor.predict.assert_called_once()

    def test_throttled_within_half_second(self, overlay, mock_predictor, buffer):
        """0.5s 内再次调用 → 预测被跳过（ai_text=None）。"""
        buffer.append(37)
        overlay._compute_frame()
        mock_predictor.predict.assert_called_once()

        # 立即再次调用（距上次 < 0.5s）
        display = overlay._compute_frame()
        assert display["ai_text"] is None
        mock_predictor.predict.assert_called_once()  # 仍只调用一次

    def test_throttle_expired_after_half_second(self, overlay, mock_predictor, buffer):
        """超过 0.5s → 预测再次执行。"""
        buffer.append(37)
        overlay._compute_frame()
        overlay._last_ai_time = time.time() - 1.0  # 模拟已过 1s
        overlay._compute_frame()
        assert mock_predictor.predict.call_count == 2

    def test_action_minus_one_skips_prediction(self, overlay, mock_predictor):
        """buffer 为空（action=-1）→ 预测被跳过。"""
        overlay._compute_frame()
        mock_predictor.predict.assert_not_called()


# =============================================================================
# 9. predictor 未加载
# =============================================================================

class TestPredictorNotLoaded:
    def test_unloaded_model_skips_prediction(self, overlay, mock_predictor, buffer):
        mock_predictor.is_loaded = False
        buffer.append(37)
        display = overlay._compute_frame()
        assert display["ai_text"] is None
        mock_predictor.predict.assert_not_called()


# =============================================================================
# 10. action_buffer 交互
# =============================================================================

class TestActionBufferInteraction:
    def test_reads_last_action_from_buffer(self, overlay, state, buffer):
        buffer.append(49)  # 49 ∈ POSTURE_PRONE
        overlay._compute_frame()
        assert state.posture == 0

    def test_empty_buffer_uses_minus_one(self, overlay, mock_predictor, buffer):
        """buffer 为空 → action=-1 → 状态文本显示 (-1)。"""
        display = overlay._compute_frame()
        assert "[动作]: (-1)" in display["state_text"]

    def test_zone_change_clears_buffer_with_lock(self, overlay, mock_reader, buffer):
        """清空动作发生在锁保护下（__enter__ 被调用）。"""
        buffer.extend([37, 53])
        mock_lock = MagicMock()
        overlay._lock = mock_lock
        mock_reader.check_zone.return_value = 123
        overlay._compute_frame()
        assert len(buffer) == 0
        mock_lock.__enter__.assert_called_once()
        mock_lock.__exit__.assert_called_once()


# =============================================================================
# 11. update_logic 异常处理
# =============================================================================

class TestUpdateLogicException:
    def test_memory_exception_logged(self, overlay, mock_reader, caplog):
        """MemoryReader 抛异常 → 被捕获 → logger.error。"""
        mock_reader.find_monster.side_effect = RuntimeError("memory read failed")
        with caplog.at_level(logging.ERROR, logger="BlackDragon"):
            overlay.update_logic()
        assert any("UI 刷新异常" in r.getMessage() for r in caplog.records)

    def test_exception_does_not_propagate(self, overlay, mock_reader):
        mock_reader.find_monster.side_effect = RuntimeError("boom")
        overlay.update_logic()  # 不应抛出异常

    def test_normal_path_applies_display(self, overlay, buffer):
        """update_logic 成功路径 → DPG set_value 被调用。"""
        buffer.append(37)
        overlay._widgets = {"text_state": "state_widget", "text_ai": "ai_widget"}
        with patch("src.ui.overlay.dpg") as mock_dpg:
            overlay.update_logic()
        mock_dpg.set_value.assert_any_call("state_widget",
                                           "[动作]: 龙车 | P2 [未怒]\n"
                                           "[状态]: 距:14 | 角:45° | 血:65.0%")


# =============================================================================
# 12. _apply_display（DPG 更新层）
# =============================================================================

class TestApplyDisplay:
    @pytest.fixture
    def widgets(self, overlay):
        overlay._widgets = {"text_state": "state_widget", "text_ai": "ai_widget"}
        return overlay._widgets

    def test_normal_frame_updates_both_widgets(self, overlay, widgets):
        display = {
            "state_text": "状态行",
            "state_color": None,
            "ai_text": "预测行",
            "ai_color": [150, 255, 150, 255],
        }
        with patch("src.ui.overlay.dpg") as mock_dpg:
            overlay._apply_display(display)
        mock_dpg.set_value.assert_any_call("state_widget", "状态行")
        mock_dpg.set_value.assert_any_call("ai_widget", "预测行")
        mock_dpg.configure_item.assert_called_with(
            "ai_widget", color=[150, 255, 150, 255])

    def test_dormant_frame_sets_state_color(self, overlay, widgets):
        display = {
            "state_text": "未在虚黑城，雷达已休眠...",
            "state_color": [255, 255, 255, 255],
            "ai_text": "",
            "ai_color": None,
        }
        with patch("src.ui.overlay.dpg") as mock_dpg:
            overlay._apply_display(display)
        mock_dpg.configure_item.assert_called_with(
            "state_widget", color=[255, 255, 255, 255])
        mock_dpg.set_value.assert_any_call("ai_widget", "")

    def test_none_ai_text_skips_ai_widget(self, overlay, widgets):
        display = {
            "state_text": "状态行",
            "state_color": None,
            "ai_text": None,
            "ai_color": None,
        }
        with patch("src.ui.overlay.dpg") as mock_dpg:
            overlay._apply_display(display)
        # set_value 只对 state_widget 调用，不对 ai_widget
        calls = [c[0][0] for c in mock_dpg.set_value.call_args_list]
        assert "state_widget" in calls
        assert "ai_widget" not in calls

    def test_display_none_skips_all(self, overlay, widgets):
        with patch("src.ui.overlay.dpg") as mock_dpg:
            overlay._apply_display(None)
        mock_dpg.set_value.assert_not_called()
        mock_dpg.configure_item.assert_not_called()


# =============================================================================
# 14. DPG 生命周期 smoke tests（mock dpg，不启动真实窗口）
# =============================================================================

class TestDpgLifecycleSmoke:
    def test_run_creates_context_and_loops(self, overlay):
        """run() 创建 DPG context + viewport + event loop，退出时销毁。"""
        with patch("src.ui.overlay.dpg") as mock_dpg, \
                patch("src.ui.overlay.ctypes") as mock_ctypes, \
                patch("src.ui.fonts.dpg"):
            mock_ctypes.windll.user32.GetWindowLongW.return_value = 0
            mock_ctypes.windll.user32.GetSystemMetrics.return_value = 1920
            mock_dpg.is_dearpygui_running.side_effect = [True, False]
            overlay.update_logic = MagicMock()
            overlay.run()

        mock_dpg.create_context.assert_called_once()
        mock_dpg.create_viewport.assert_called_once()
        mock_dpg.setup_dearpygui.assert_called_once()
        mock_dpg.show_viewport.assert_called_once()
        mock_dpg.render_dearpygui_frame.assert_called_once()
        mock_dpg.destroy_context.assert_called_once()
        overlay.update_logic.assert_called_once()
        assert "text_state" in overlay._widgets
        assert "text_ai" in overlay._widgets

    def test_start_spawns_daemon_thread(self, overlay):
        """start() 启动 daemon 线程运行 run()。"""
        with patch("src.ui.overlay.dpg") as mock_dpg, \
                patch("src.ui.overlay.ctypes") as mock_ctypes, \
                patch("src.ui.fonts.dpg"):
            mock_ctypes.windll.user32.GetWindowLongW.return_value = 0
            mock_ctypes.windll.user32.GetSystemMetrics.return_value = 1920
            mock_dpg.is_dearpygui_running.return_value = False  # run() 立即退出
            overlay.start()
            assert overlay._thread is not None
            assert overlay._thread.daemon is True
            overlay._thread.join(timeout=5)
            assert overlay._thread.is_alive() is False

        mock_dpg.create_context.assert_called_once()
        mock_dpg.destroy_context.assert_called_once()

    def test_destroy_calls_destroy_context(self, overlay):
        with patch("src.ui.overlay.dpg") as mock_dpg:
            overlay._destroy()
        mock_dpg.destroy_context.assert_called_once()


# =============================================================================
# 14b. 命令队列（show/hide/stop 由 overlay 线程处理）
# =============================================================================

class TestCommandQueue:
    def test_process_show_command(self, overlay):
        """show 命令 → configure_viewport(show=True) + visible=True。"""
        with patch("src.ui.overlay.dpg") as mock_dpg:
            overlay._visible = False
            overlay._command_queue.put("show")
            overlay._process_commands()
        mock_dpg.configure_viewport.assert_called_with("overlay", show=True)
        assert overlay._visible is True

    def test_process_hide_command(self, overlay):
        """hide 命令 → configure_viewport(show=False) + visible=False。"""
        with patch("src.ui.overlay.dpg") as mock_dpg:
            overlay._visible = True
            overlay._command_queue.put("hide")
            overlay._process_commands()
        mock_dpg.configure_viewport.assert_called_with("overlay", show=False)
        assert overlay._visible is False

    def test_process_stop_command(self, overlay):
        """stop 命令 → _running=False（线程退出）。"""
        overlay._running = True
        overlay._command_queue.put("stop")
        overlay._process_commands()
        assert overlay._running is False

    def test_show_hide_put_command(self, overlay):
        """show()/hide()/stop() 仅投递队列命令——不直接调用 DPG。"""
        with patch("src.ui.overlay.dpg") as mock_dpg:
            overlay.show()
            overlay.hide()
            overlay.stop()
        mock_dpg.configure_viewport.assert_not_called()  # 命令由线程处理
        assert overlay._command_queue.qsize() == 3

    def test_put_command_queue_full_drops_oldest(self, overlay):
        """队列满时丢弃最旧命令，保留最新。"""
        for cmd in ["show", "hide", "show", "hide", "show", "hide",
                    "show", "hide", "show", "hide", "stop"]:
            overlay._put_command(cmd)
        # 最多 10 条——最旧的被丢弃，最新的是 stop
        assert overlay._command_queue.qsize() == 10
        commands = []
        while not overlay._command_queue.empty():
            commands.append(overlay._command_queue.get_nowait())
        assert commands[-1] == "stop"


# =============================================================================
# 15. 结构约束：OverlayUI 不得启动自己的 DPG event loop
# =============================================================================

class TestNoOwnEventLoop:
    def test_public_methods_no_own_loop(self):
        """start/stop/show/hide 不启动自己的 DPG event loop。

        这些方法仅投递 queue 命令——event loop 由 overlay 线程的
        run() 管理，DPG 调用在 overlay 线程执行。
        """
        import inspect
        import src.ui.overlay as ov_mod
        public_methods = [
            ov_mod.OverlayUI.start,
            ov_mod.OverlayUI.stop,
            ov_mod.OverlayUI.show,
            ov_mod.OverlayUI.hide,
        ]
        for method in public_methods:
            src = inspect.getsource(method)
            assert "start_dearpygui" not in src, f"{method.__name__} contains start_dearpygui"
            assert "is_dearpygui_running" not in src, f"{method.__name__} contains is_dearpygui_running"
            assert "render_dearpygui_frame" not in src, f"{method.__name__} contains render"

    def test_run_is_thread_target(self):
        """run() 是唯一含 event loop 的方法（线程 target）。"""
        import inspect
        import src.ui.overlay as ov_mod
        src = inspect.getsource(ov_mod.OverlayUI.run)
        assert "is_dearpygui_running" in src
        assert "render_dearpygui_frame" in src
        assert "create_context" in src  # 独立 DPG context
        assert "_destroy" in src        # finally 清理（_destroy 内 destroy_context）

class TestStructuralConstraints:
    def test_no_direct_pymem_or_shared_state(self):
        import inspect
        import re
        import src.ui.overlay as overlay_module
        src = inspect.getsource(overlay_module)
        # 禁止 import pymem
        assert not re.search(r"^\s*(?:import|from)\s+pymem", src, re.MULTILINE)
        # 禁止直接调用 pm.read_*
        assert not re.search(r"\.read_(?:int|float|longlong|ulonglong|string|bytes)\(", src)
        # 禁止读写 shared_state 全局 dict
        assert not re.search(r"\bshared_state\s*[\[.=]", src)

    def test_compute_frame_has_no_dpg_calls(self):
        """_compute_frame 及其依赖必须不含 dpg 调用。"""
        import inspect
        import src.ui.overlay as overlay_module
        src = inspect.getsource(overlay_module.OverlayUI._compute_frame)
        src += inspect.getsource(overlay_module.OverlayUI._compute_ai_display)
        assert "dpg." not in src
