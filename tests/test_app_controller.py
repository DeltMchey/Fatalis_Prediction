"""P5: AppController tests — 生命周期协调器。

策略：
  - mock StateTracker / Recorder / Predictor / MemoryReader / Overlay
  - 验证状态查询、录制开关、overlay 启停、训练子进程、shutdown

覆盖：
  - 状态查询（game/recording/model/overlay/training）
  - 录制控制（toggle/set）
  - Overlay 启停（含未注入降级）
  - 训练启动/取消/输出队列
  - shutdown 优雅退出
"""

from unittest.mock import MagicMock

import pytest

from src.app.config import AppConfig
from src.app.controller import AppController


@pytest.fixture
def deps():
    """返回一组 mock 依赖 + 组装好的 controller。

    注: AppController 构造轻量化（仅 config）——P4 模块通过设置
    私有属性模拟"已附着"状态（与 attach_game 效果等价）。
    """
    state = MagicMock()
    state.is_recording = True
    recorder = MagicMock()
    predictor = MagicMock()
    predictor.is_loaded = True
    reader = MagicMock()
    reader.check_zone.return_value = 417
    overlay = MagicMock()
    config = AppConfig()
    controller = AppController(config)
    # 模拟 attach_game 后的状态
    controller._state = state
    controller._recorder = recorder
    controller._predictor = predictor
    controller._reader = reader
    controller._overlay = overlay
    controller._game_attached = True
    return {
        "state": state, "recorder": recorder, "predictor": predictor,
        "reader": reader, "overlay": overlay, "config": config,
        "controller": controller,
    }


# =============================================================================
# 1. 状态查询
# =============================================================================

class TestStatus:
    def test_game_connected(self, deps):
        deps["reader"].check_zone.return_value = 417
        assert deps["controller"].is_game_connected is True

    def test_game_disconnected_zone_none(self, deps):
        deps["reader"].check_zone.return_value = None
        assert deps["controller"].is_game_connected is False

    def test_game_disconnected_exception(self, deps):
        deps["reader"].check_zone.side_effect = RuntimeError("boom")
        assert deps["controller"].is_game_connected is False

    def test_recording_status(self, deps):
        assert deps["controller"].is_recording is True
        deps["state"].is_recording = False
        assert deps["controller"].is_recording is False

    def test_model_loaded(self, deps):
        assert deps["controller"].is_model_loaded is True
        deps["predictor"].is_loaded = False
        assert deps["controller"].is_model_loaded is False

    def test_overlay_initial_hidden(self, deps):
        assert deps["controller"].is_overlay_visible is False

    def test_training_initial_false(self, deps):
        assert deps["controller"].is_training is False


# =============================================================================
# 2. 录制控制
# =============================================================================

class TestRecordingControl:
    def test_toggle_recording_on_to_off(self, deps):
        deps["state"].is_recording = True
        result = deps["controller"].toggle_recording()
        assert result is False
        deps["state"].is_recording = False

    def test_toggle_recording_off_to_on(self, deps):
        deps["state"].is_recording = False
        result = deps["controller"].toggle_recording()
        assert result is True
        deps["state"].is_recording = True

    def test_set_recording(self, deps):
        deps["controller"].set_recording(False)
        assert deps["state"].is_recording is False
        deps["controller"].set_recording(True)
        assert deps["state"].is_recording is True


# =============================================================================
# 3. Overlay 启停
# =============================================================================

class TestOverlayControl:
    def test_start_overlay(self, deps):
        """start_overlay 投递 show 命令（overlay 线程执行 DPG 调用）。"""
        deps["controller"]._overlay_visible = False
        ok = deps["controller"].start_overlay()
        assert ok is True
        deps["overlay"].show.assert_called_once()
        assert deps["controller"].is_overlay_visible is True

    def test_stop_overlay(self, deps):
        deps["controller"]._overlay_visible = True
        ok = deps["controller"].stop_overlay()
        assert ok is True
        deps["overlay"].hide.assert_called_once()
        assert deps["controller"].is_overlay_visible is False

    def test_start_overlay_without_injection(self, deps):
        deps["controller"]._overlay = None
        ok = deps["controller"].start_overlay()
        assert ok is False

    def test_stop_overlay_without_injection(self, deps):
        deps["controller"]._overlay = None
        assert deps["controller"].stop_overlay() is False


# =============================================================================
# 4. 训练子进程
# =============================================================================

class TestTraining:
    def test_start_training(self, deps, monkeypatch):
        import subprocess
        proc = MagicMock()
        proc.poll.return_value = None
        proc.stdout = ["line1\n", "line2\n"]
        monkeypatch.setattr(subprocess, "Popen", MagicMock(return_value=proc))
        ok = deps["controller"].start_training()
        assert ok is True
        assert deps["controller"].is_training is True

    def test_start_training_twice_returns_false(self, deps, monkeypatch):
        import subprocess
        proc = MagicMock()
        proc.poll.return_value = None
        monkeypatch.setattr(subprocess, "Popen", MagicMock(return_value=proc))
        deps["controller"].start_training()
        assert deps["controller"].start_training() is False

    def test_cancel_training(self, deps, monkeypatch):
        import subprocess
        proc = MagicMock()
        proc.poll.return_value = None
        monkeypatch.setattr(subprocess, "Popen", MagicMock(return_value=proc))
        deps["controller"].start_training()
        assert deps["controller"].cancel_training() is True
        proc.terminate.assert_called_once()

    def test_cancel_training_none(self, deps):
        assert deps["controller"].cancel_training() is False

    def test_get_training_output_empty(self, deps):
        assert deps["controller"].get_training_output() == []

    def test_get_training_output_drains_queue(self, deps):
        deps["controller"]._training_queue.put("msg1")
        deps["controller"]._training_queue.put("msg2")
        out = deps["controller"].get_training_output()
        assert out == ["msg1", "msg2"]
        # 队列已排空
        assert deps["controller"].get_training_output() == []


# =============================================================================
# 5. Shutdown
# =============================================================================

class TestShutdown:
    def test_shutdown_stops_recorder(self, deps):
        deps["controller"].shutdown()
        deps["recorder"].stop.assert_called_once()

    def test_shutdown_stops_overlay(self, deps):
        deps["controller"].shutdown()
        deps["overlay"].stop.assert_called_once()

    def test_shutdown_idempotent(self, deps):
        deps["controller"].shutdown()
        deps["controller"].shutdown()  # 不应抛异常
        assert deps["recorder"].stop.call_count == 2

    def test_shutdown_without_recorder(self, deps):
        deps["controller"]._recorder = None
        deps["controller"].shutdown()  # 不应抛异常

    def test_shutdown_without_overlay(self, deps):
        deps["controller"]._overlay = None
        deps["controller"].shutdown()  # 不应抛异常


# =============================================================================
# 6. P5.1: 构造轻量化 + attach/detach_game
# =============================================================================

class TestLightweightConstructor:
    def test_constructor_only_config(self):
        """构造仅需 config——P4 模块初始为 None。"""
        ctrl = AppController(AppConfig())
        assert ctrl._state is None
        assert ctrl._recorder is None
        assert ctrl._predictor is None
        assert ctrl._reader is None
        assert ctrl._overlay is None
        assert ctrl.is_game_attached is False
        assert ctrl.is_game_connected is False
        assert ctrl.is_recording is False
        assert ctrl.is_model_loaded is False

    def test_recording_toggle_without_attach_returns_false(self):
        ctrl = AppController(AppConfig())
        assert ctrl.toggle_recording() is False
        ctrl.set_recording(True)  # 不应抛异常

    def test_start_overlay_without_attach_returns_false(self):
        ctrl = AppController(AppConfig())
        assert ctrl.start_overlay() is False

    def test_data_dir_property(self):
        """S1: data_dir 通过公共属性暴露。"""
        cfg = AppConfig()
        cfg.data_dir = "custom_data"
        ctrl = AppController(cfg)
        assert ctrl.data_dir == "custom_data"


class TestAttachGame:
    def test_attach_game_creates_modules(self, monkeypatch):
        """attach_game 创建全部 P4 模块并启动 recorder。"""
        ctrl = AppController(AppConfig())
        mock_mr = MagicMock()
        mock_st = MagicMock()
        mock_pred = MagicMock()
        mock_rec = MagicMock()
        mock_ov = MagicMock()

        # attach_game 内部惰性 import P4 模块 —— 用 monkeypatch.setitem
        # 临时替换 sys.modules（测试后自动恢复，不污染其他测试）
        import sys
        import types
        mock_classes = {
            "src.core.memory_reader": ("MemoryReader", mock_mr),
            "src.core.state_tracker": ("CombatStateTracker", mock_st),
            "src.model.predictor": ("ActionPredictor", mock_pred),
            "src.data.recorder": ("CombatRecorder", mock_rec),
            "src.ui.overlay": ("OverlayUI", mock_ov),
        }
        for mod_name, (cls_name, instance) in mock_classes.items():
            m = types.ModuleType(mod_name)
            setattr(m, cls_name, MagicMock(return_value=instance))
            monkeypatch.setitem(sys.modules, mod_name, m)

        ok = ctrl.attach_game(MagicMock(), 0x140000000)
        assert ok is True
        assert ctrl.is_game_attached is True
        assert ctrl._reader is mock_mr
        assert ctrl._state is mock_st
        assert ctrl._predictor is mock_pred
        assert ctrl._recorder is mock_rec
        assert ctrl._overlay is mock_ov
        mock_rec.start.assert_called_once()
        mock_ov.start.assert_called_once()  # 自动启动覆盖层线程
        assert ctrl._overlay_visible is True

    def test_attach_game_failure_rolls_back(self, monkeypatch):
        """attach_game 中途失败 → 返回 False，不附着。"""
        import sys
        import types
        ctrl = AppController(AppConfig())
        mr_mod = types.ModuleType("src.core.memory_reader")
        mr_mod.MemoryReader = MagicMock(side_effect=RuntimeError("boom"))
        monkeypatch.setitem(sys.modules, "src.core.memory_reader", mr_mod)
        ok = ctrl.attach_game(MagicMock(), 0x140000000)
        assert ok is False
        assert ctrl.is_game_attached is False
        assert ctrl._state is None

    def test_attach_game_recorder_failure_still_attached(self, monkeypatch):
        """recorder.start() 失败不阻断附着（仅日志）。"""
        import sys
        import types
        ctrl = AppController(AppConfig())
        mock_rec = MagicMock()
        mock_rec.start.side_effect = RuntimeError("start fail")
        # 用显式的类名映射（模块名 ≠ 类名）
        cls_map = {
            "src.core.memory_reader": "MemoryReader",
            "src.core.state_tracker": "CombatStateTracker",
            "src.model.predictor": "ActionPredictor",
            "src.ui.overlay": "OverlayUI",
        }
        for mod_name, cls_name in cls_map.items():
            m = types.ModuleType(mod_name)
            setattr(m, cls_name, MagicMock())
            monkeypatch.setitem(sys.modules, mod_name, m)
        rec_mod = types.ModuleType("src.data.recorder")
        rec_mod.CombatRecorder = MagicMock(return_value=mock_rec)
        monkeypatch.setitem(sys.modules, "src.data.recorder", rec_mod)

        ok = ctrl.attach_game(MagicMock(), 0x140000000)
        assert ok is True  # 附着成功（录制启动失败仅记录）
        assert ctrl.is_game_attached is True


class TestDetachGame:
    def test_detach_cleans_up(self, deps):
        deps["controller"].detach_game()
        deps["recorder"].stop.assert_called_once()
        deps["overlay"].stop.assert_called_once()
        assert deps["controller"].is_game_attached is False
        assert deps["controller"]._state is None
        assert deps["controller"]._overlay is None

    def test_detach_idempotent(self):
        ctrl = AppController(AppConfig())
        ctrl.detach_game()  # 未附着也能安全调用
        assert ctrl.is_game_attached is False



