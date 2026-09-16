"""P5 + P5.3: AppController tests — 生命周期协调器。

策略：
  - mock StateTracker / Recorder / Predictor / MemoryReader
  - Overlay 是**独立子进程**（P5.3 双进程）——用 subprocess.Popen mock 验证
  - 验证状态查询、录制开关、覆盖层子进程启停、训练子进程、shutdown

覆盖：
  - 状态查询（game/recording/model/overlay/training）
  - 录制控制（toggle/set）
  - 覆盖层子进程启停（start/stop/is_overlay_running）
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
    config = AppConfig()
    controller = AppController(config)
    # 模拟 attach_game 后的状态
    controller._state = state
    controller._recorder = recorder
    controller._predictor = predictor
    controller._reader = reader
    controller._game_attached = True
    return {
        "state": state, "recorder": recorder, "predictor": predictor,
        "reader": reader, "config": config,
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

    def test_overlay_initial_not_running(self, deps):
        """P5.3: 无子进程 → is_overlay_running False。"""
        assert deps["controller"].is_overlay_running is False

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
# 3. 覆盖层子进程（P5.3 双进程）
# =============================================================================

class TestOverlaySubprocess:
    def test_start_overlay_launches_subprocess(self, deps, monkeypatch):
        """start_overlay 启动 `python overlay.py` 子进程。"""
        import subprocess
        import sys
        proc = MagicMock()
        proc.poll.return_value = None  # 运行中
        monkeypatch.setattr(subprocess, "Popen", MagicMock(return_value=proc))
        ok = deps["controller"].start_overlay()
        assert ok is True
        args = subprocess.Popen.call_args[0][0]  # [sys.executable, "overlay.py"]
        assert args[0] == sys.executable
        assert args[1] == "overlay.py"
        assert deps["controller"].is_overlay_running is True

    def test_start_overlay_custom_script(self, deps, monkeypatch):
        """overlay_script 来自 config（可配置）。"""
        import subprocess
        deps["config"].overlay_script = "custom_overlay.py"
        proc = MagicMock()
        proc.poll.return_value = None
        monkeypatch.setattr(subprocess, "Popen", MagicMock(return_value=proc))
        deps["controller"].start_overlay()
        args = subprocess.Popen.call_args[0][0]
        assert args[1] == "custom_overlay.py"

    def test_start_overlay_already_running(self, deps, monkeypatch):
        """已在运行 → 返回 False，不重复启动。"""
        import subprocess
        proc = MagicMock()
        proc.poll.return_value = None
        deps["controller"]._overlay_proc = proc
        monkeypatch.setattr(subprocess, "Popen", MagicMock())
        ok = deps["controller"].start_overlay()
        assert ok is False
        subprocess.Popen.assert_not_called()

    def test_start_overlay_popen_failure(self, deps, monkeypatch):
        """Popen 抛异常 → 返回 False，_overlay_proc 置回 None。"""
        import subprocess
        monkeypatch.setattr(
            subprocess, "Popen", MagicMock(side_effect=RuntimeError("no python")))
        ok = deps["controller"].start_overlay()
        assert ok is False
        assert deps["controller"].is_overlay_running is False

    def test_stop_overlay_terminates(self, deps):
        proc = MagicMock()
        proc.poll.return_value = None  # 运行中
        deps["controller"]._overlay_proc = proc
        ok = deps["controller"].stop_overlay()
        assert ok is True
        proc.terminate.assert_called_once()

    def test_stop_overlay_none(self, deps):
        assert deps["controller"].stop_overlay() is False

    def test_stop_overlay_already_exited(self, deps):
        proc = MagicMock()
        proc.poll.return_value = 0  # 已退出
        deps["controller"]._overlay_proc = proc
        assert deps["controller"].stop_overlay() is False


# =============================================================================
# 4. 训练子进程
# =============================================================================

class TestTraining:
    @pytest.fixture(autouse=True)
    def _isolate_train_log_dir(self, tmp_path, monkeypatch):
        """v3(F5): 训练输出落盘有文件副作用——CWD 隔离到 tmp_path。"""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "models").mkdir(exist_ok=True)

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

    def test_start_training_frozen_uses_pipeline_flag(self, deps, monkeypatch,
                                                      tmp_path):
        """冻结模式: start_training 应使用 [exe, --pipeline] 而非 [exe, train_lgbm.py]。

        防止 BlackDragon.exe train_lgbm.py 重新启动 Dashboard。
        伪 exe 路径用 tmp_path（v3/F5 起训练日志会向 exe 目录 mkdir 写文件）。
        """
        import subprocess
        import sys
        proc = MagicMock()
        proc.poll.return_value = None
        proc.stdout = ["line1\n"]
        monkeypatch.setattr(subprocess, "Popen", MagicMock(return_value=proc))
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        fake_exe = tmp_path / "dist" / "BlackDragon.exe"
        monkeypatch.setattr(sys, "executable", str(fake_exe))

        ok = deps["controller"].start_training()
        assert ok is True
        cmd = subprocess.Popen.call_args[0][0]
        assert cmd == [str(fake_exe), "--pipeline"]


# =============================================================================
# 4a. v3(F5) 训练输出落盘（tee + 滚动清理）
# =============================================================================

class TestTrainingLogTee:
    @pytest.fixture(autouse=True)
    def _isolate_train_log_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "models").mkdir(exist_ok=True)

    def test_output_teed_to_log_file(self, deps, monkeypatch):
        """训练 stdout 双路：UI 队列照常 + 完整落盘 models/train_*.log。"""
        import subprocess
        proc = MagicMock()
        proc.poll.return_value = None
        proc.stdout = ["line1\n", "line2\n", "📊 本次训练数据：X 会话\n"]
        proc.wait.return_value = 0
        monkeypatch.setattr(subprocess, "Popen", MagicMock(return_value=proc))

        ctrl = deps["controller"]
        assert ctrl.start_training() is True
        ctrl._training_thread.join(timeout=5)

        # UI 队列行为不变（含退出标记）
        out = ctrl.get_training_output()
        assert out[:3] == ["line1", "line2", "📊 本次训练数据：X 会话"]
        assert out[-1] == "[训练结束] 退出码: 0"

        # 落盘内容与 stdout 逐行一致
        import glob
        logs = glob.glob("models/train_*.log")
        assert len(logs) == 1
        with open(logs[0], encoding="utf-8") as f:
            assert f.read() == "line1\nline2\n📊 本次训练数据：X 会话\n"

    def test_tee_failure_does_not_break_ui_queue(self, deps, monkeypatch):
        """日志文件 open 失败 → 训练照常启动，仅 UI 队列展示。"""
        import subprocess
        import src.app.controller as controller_mod
        proc = MagicMock()
        proc.poll.return_value = None
        proc.stdout = ["line1\n"]
        proc.wait.return_value = 0
        monkeypatch.setattr(subprocess, "Popen", MagicMock(return_value=proc))
        monkeypatch.setattr(
            controller_mod, "resolve_runtime_path",
            MagicMock(side_effect=OSError("disk full")))

        ctrl = deps["controller"]
        assert ctrl.start_training() is True
        ctrl._training_thread.join(timeout=5)
        assert ctrl._training_log_file is None
        assert "line1" in ctrl.get_training_output()

    def test_prune_train_logs_keeps_newest(self, tmp_path):
        """滚动清理：12 份历史日志 → 仅保留最新 10 份；无关文件不动。"""
        from src.app.controller import prune_train_logs
        models = tmp_path / "models"
        models.mkdir(exist_ok=True)
        for i in range(1, 13):
            (models / f"train_20260916_{i:06d}.log").write_text(f"v{i}")
        (models / "fatalis_ai_model.pkl").write_bytes(b"m")
        (models / "train_readme_notes.txt").write_text("not a log")

        removed = prune_train_logs(models)

        assert removed == 2
        remaining = sorted(p.name for p in models.glob("train_*.log"))
        assert len(remaining) == 10
        assert remaining[0] == "train_20260916_000003.log"  # 最旧两份被删
        assert remaining[-1] == "train_20260916_000012.log"
        assert (models / "fatalis_ai_model.pkl").exists()
        assert (models / "train_readme_notes.txt").exists()

    def test_prune_train_logs_under_limit_noop(self, tmp_path):
        """不足保留份数 → 零删除。"""
        from src.app.controller import prune_train_logs
        models = tmp_path / "models"
        models.mkdir(exist_ok=True)
        (models / "train_20260916_000001.log").write_text("v")
        assert prune_train_logs(models) == 0
        assert (models / "train_20260916_000001.log").exists()

    def test_prune_train_logs_missing_dir(self, tmp_path):
        from src.app.controller import prune_train_logs
        assert prune_train_logs(tmp_path / "nope") == 0


# =============================================================================
# 4b. Frozen 模式路径（PyInstaller）
# =============================================================================

class TestFrozenPaths:
    def test_data_dir_frozen_resolves_to_exe_dir(self, monkeypatch):
        """sys.frozen=True → data_dir 返回 <exe_dir>/data。"""
        import sys
        from pathlib import Path
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", r"C:\dist\BlackDragon\BlackDragon.exe")
        ctrl = AppController(AppConfig())
        assert ctrl.data_dir == Path(r"C:\dist\BlackDragon\data")

    def test_data_dir_dev_uses_config_value(self):
        """开发模式（无 sys.frozen）→ data_dir 返回相对 Path("data")。"""
        from pathlib import Path
        ctrl = AppController(AppConfig())
        assert ctrl.data_dir == Path("data")

    def test_start_training_frozen_flag(self, deps, monkeypatch):
        """冻结模式 start_training 传 [exe, --pipeline]（覆盖层冻结分支）。"""
        import subprocess
        import sys
        proc = MagicMock()
        proc.poll.return_value = None
        proc.stdout = []
        monkeypatch.setattr(subprocess, "Popen", MagicMock(return_value=proc))
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", r"C:\dist\BlackDragon.exe")
        deps["controller"].start_training()
        cmd = subprocess.Popen.call_args[0][0]
        assert cmd == [r"C:\dist\BlackDragon.exe", "--pipeline"]


# =============================================================================
# 5. Shutdown
# =============================================================================

class TestShutdown:
    def test_shutdown_stops_recorder(self, deps):
        deps["controller"].shutdown()
        deps["recorder"].stop.assert_called_once()

    def test_shutdown_terminates_overlay_proc(self, deps):
        """shutdown 终止覆盖层子进程。"""
        proc = MagicMock()
        proc.poll.return_value = None  # 运行中
        deps["controller"]._overlay_proc = proc
        deps["controller"].shutdown()
        proc.terminate.assert_called_once()

    def test_shutdown_idempotent(self, deps):
        deps["controller"].shutdown()
        deps["controller"].shutdown()  # 不应抛异常
        assert deps["recorder"].stop.call_count == 2

    def test_shutdown_without_recorder(self, deps):
        deps["controller"]._recorder = None
        deps["controller"].shutdown()  # 不应抛异常

    def test_shutdown_without_overlay(self, deps):
        deps["controller"]._overlay_proc = None
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
        assert ctrl._overlay_proc is None
        assert ctrl.is_game_attached is False
        assert ctrl.is_game_connected is False
        assert ctrl.is_recording is False
        assert ctrl.is_model_loaded is False
        assert ctrl.is_overlay_running is False

    def test_recording_toggle_without_attach_returns_false(self):
        ctrl = AppController(AppConfig())
        assert ctrl.toggle_recording() is False
        ctrl.set_recording(True)  # 不应抛异常

    def test_start_overlay_without_config(self):
        """未附着游戏也能启动覆盖层子进程（独立进程）。"""
        ctrl = AppController(AppConfig())
        assert ctrl._overlay_proc is None

    def test_data_dir_property(self):
        """S1: data_dir 通过公共属性暴露（返回 Path，保留 config 自定义）。"""
        from pathlib import Path
        cfg = AppConfig()
        cfg.data_dir = "custom_data"
        ctrl = AppController(cfg)
        assert ctrl.data_dir == Path("custom_data")


class TestAttachGame:
    def test_attach_game_creates_modules(self, monkeypatch):
        """attach_game 创建 P4 数据模块并启动 recorder（不创建 OverlayUI）。"""
        ctrl = AppController(AppConfig())
        mock_mr = MagicMock()
        mock_st = MagicMock()
        mock_pred = MagicMock()
        mock_rec = MagicMock()

        # attach_game 内部惰性 import P4 模块 —— 用 monkeypatch.setitem
        # 临时替换 sys.modules（测试后自动恢复，不污染其他测试）
        import sys
        import types
        mock_classes = {
            "src.core.memory_reader": ("MemoryReader", mock_mr),
            "src.core.state_tracker": ("CombatStateTracker", mock_st),
            "src.model.predictor": ("ActionPredictor", mock_pred),
            "src.data.recorder": ("CombatRecorder", mock_rec),
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
        mock_rec.start.assert_called_once()
        # P5.3: attach_game 不再创建/启动 OverlayUI
        assert ctrl._overlay_proc is None

    def test_attach_game_uses_config_auto_record_true(self, monkeypatch):
        """ADR-P5.3: 默认 auto_record=True → CombatStateTracker(is_recording=True)。"""
        import sys
        import types
        ctrl = AppController(AppConfig())
        mock_mr = MagicMock()
        mock_st = MagicMock()
        mock_pred = MagicMock()
        mock_rec = MagicMock()
        mock_classes = {
            "src.core.memory_reader": ("MemoryReader", mock_mr),
            "src.core.state_tracker": ("CombatStateTracker", mock_st),
            "src.model.predictor": ("ActionPredictor", mock_pred),
            "src.data.recorder": ("CombatRecorder", mock_rec),
        }
        captured = {}
        for mod_name, (cls_name, instance) in mock_classes.items():
            m = types.ModuleType(mod_name)
            cls = MagicMock(return_value=instance)
            if cls_name == "CombatStateTracker":
                captured["CombatStateTracker"] = cls
            setattr(m, cls_name, cls)
            monkeypatch.setitem(sys.modules, mod_name, m)

        ok = ctrl.attach_game(MagicMock(), 0x140000000)
        assert ok is True
        assert captured["CombatStateTracker"].call_args[1]["is_recording"] is True

    def test_attach_game_uses_config_auto_record_false(self, monkeypatch):
        """ADR-P5.3: auto_record=False → CombatStateTracker(is_recording=False)。"""
        import sys
        import types
        cfg = AppConfig()
        cfg.auto_record = False
        ctrl = AppController(cfg)
        mock_mr = MagicMock()
        mock_st = MagicMock()
        mock_pred = MagicMock()
        mock_rec = MagicMock()
        mock_classes = {
            "src.core.memory_reader": ("MemoryReader", mock_mr),
            "src.core.state_tracker": ("CombatStateTracker", mock_st),
            "src.model.predictor": ("ActionPredictor", mock_pred),
            "src.data.recorder": ("CombatRecorder", mock_rec),
        }
        captured = {}
        for mod_name, (cls_name, instance) in mock_classes.items():
            m = types.ModuleType(mod_name)
            cls = MagicMock(return_value=instance)
            if cls_name == "CombatStateTracker":
                captured["CombatStateTracker"] = cls
            setattr(m, cls_name, cls)
            monkeypatch.setitem(sys.modules, mod_name, m)

        ok = ctrl.attach_game(MagicMock(), 0x140000000)
        assert ok is True
        assert captured["CombatStateTracker"].call_args[1]["is_recording"] is False

    def test_attach_game_does_not_import_overlay(self, monkeypatch):
        """P5.3: attach_game 不导入 src.ui.overlay（覆盖层是独立进程）。"""
        import sys
        ctrl = AppController(AppConfig())
        # 记录 attach_game 调用期间是否导入了 src.ui.overlay
        overlay_imported = []
        real_import = __import__
        def spy_import(name, *a, **kw):
            if name == "src.ui.overlay":
                overlay_imported.append(name)
            return real_import(name, *a, **kw)
        monkeypatch.setattr("builtins.__import__", spy_import)

        mock_mr = MagicMock()
        mock_st = MagicMock()
        mock_pred = MagicMock()
        mock_rec = MagicMock()
        import types
        mock_classes = {
            "src.core.memory_reader": ("MemoryReader", mock_mr),
            "src.core.state_tracker": ("CombatStateTracker", mock_st),
            "src.model.predictor": ("ActionPredictor", mock_pred),
            "src.data.recorder": ("CombatRecorder", mock_rec),
        }
        for mod_name, (cls_name, instance) in mock_classes.items():
            m = types.ModuleType(mod_name)
            setattr(m, cls_name, MagicMock(return_value=instance))
            monkeypatch.setitem(sys.modules, mod_name, m)

        ok = ctrl.attach_game(MagicMock(), 0x140000000)
        assert ok is True
        assert overlay_imported == []  # 未导入 overlay

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
        assert deps["controller"].is_game_attached is False
        assert deps["controller"]._state is None
        # P5.3: detach 不终止覆盖层子进程（独立进程，用户手动关闭）
        assert deps["controller"]._overlay_proc is None

    def test_detach_idempotent(self):
        ctrl = AppController(AppConfig())
        ctrl.detach_game()  # 未附着也能安全调用
        assert ctrl.is_game_attached is False
