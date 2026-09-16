"""P5.4: Training pipeline integration tests — --pipeline flag (v1.1).

验证:
  - --pipeline 依次调用 clean_combat_data() → train_runb_backend()（调用顺序）
    （P8 起路由到 src.model.production_backend；train_lgbm 为 --train legacy 入口）
  - 冻结模式命令: [exe, --pipeline]
  - 开发模式命令: [python, launch.py, --pipeline]
  - clean 失败（无原始 CSV）→ 优雅返回，不崩溃
  - train 失败（ML_Ready_Dataset.csv 缺失）→ 优雅返回，不覆盖旧模型
  - 数据含未知动作（v1.1.1）→ pipeline 优雅完成，不崩溃
  - 取消训练终止 pipeline 子进程
"""

import os
import sys
import types
from unittest.mock import MagicMock

import pandas as pd
import pytest

# 确保 matplotlib 使用无 GUI 后端（CI Linux 无 DISPLAY 时也必须可运行）
os.environ.setdefault("MPLBACKEND", "Agg")

# ─────────────────────────────────────────────────────────────────────────
# 跨平台 stub：launch.py 不应再模块级 import pymem——
# 若仍存在，import launch 会失败（Linux CI 无 pymem）。
# 这里预装 stub 以便检查 import 成功。
# ─────────────────────────────────────────────────────────────────────────
if "pymem" not in sys.modules:
    _pymem_stub = types.ModuleType("pymem")
    _pymem_proc = types.ModuleType("pymem.process")
    _pymem_stub.process = _pymem_proc
    sys.modules["pymem"] = _pymem_stub
    sys.modules["pymem.process"] = _pymem_proc

import launch  # noqa: E402
from tests.conftest import write_combat_csv  # noqa: E402


# =============================================================================
# 1. Pipeline 调用顺序（launch.main --pipeline）
# =============================================================================

class TestPipelineCallOrder:
    def test_pipeline_flag_calls_clean_then_train_in_order(self, monkeypatch):
        """--pipeline → 先 clean 后 train（Run B 后端），且不启动 Dashboard。"""
        calls = []
        monkeypatch.setattr("data_cleaner.clean_combat_data",
                            lambda: calls.append("clean"))
        monkeypatch.setattr(
            "src.model.production_backend.train_runb_backend",
            lambda: calls.append("train"))
        old_argv = sys.argv
        try:
            sys.argv = ["BlackDragon.exe", "--pipeline"]
            launch.main()
        finally:
            sys.argv = old_argv
        assert calls == ["clean", "train"]

    def test_pipeline_flag_removed_from_argv(self, monkeypatch):
        """--pipeline 应从 sys.argv 中移除。"""
        monkeypatch.setattr("data_cleaner.clean_combat_data", MagicMock())
        monkeypatch.setattr(
            "src.model.production_backend.train_runb_backend", MagicMock())
        old_argv = sys.argv
        try:
            sys.argv = ["BlackDragon.exe", "--pipeline", "extra"]
            launch.main()
            assert "--pipeline" not in sys.argv
        finally:
            sys.argv = old_argv

    def test_pipeline_does_not_start_dashboard(self, monkeypatch):
        """--pipeline 模式不应启动 Dashboard（训练子进程专用入口）。"""
        mock_clean = MagicMock()
        mock_train = MagicMock()
        monkeypatch.setattr("data_cleaner.clean_combat_data", mock_clean)
        monkeypatch.setattr(
            "src.model.production_backend.train_runb_backend", mock_train)
        monkeypatch.setattr(launch, "Dashboard", MagicMock())
        monkeypatch.setattr(launch, "GameService", MagicMock())
        old_argv = sys.argv
        try:
            sys.argv = ["BlackDragon.exe", "--pipeline"]
            launch.main()
        finally:
            sys.argv = old_argv
        launch.Dashboard.assert_not_called()

    def test_train_flag_still_works(self, monkeypatch):
        """--train flag 不受影响（向后兼容）。"""
        mock_train = MagicMock()
        monkeypatch.setattr("train_lgbm.train_fatalis_ai", mock_train)
        old_argv = sys.argv
        try:
            sys.argv = ["BlackDragon.exe", "--train"]
            launch.main()
        finally:
            sys.argv = old_argv
        mock_train.assert_called_once()


# =============================================================================
# 2. Frozen / Dev 模式命令（controller.start_training）
# =============================================================================

class TestControllerPipelineCommand:
    def test_start_training_frozen_uses_pipeline_flag(self, monkeypatch):
        """冻结模式: cmd = [exe, --pipeline], cwd = exe 所在目录。"""
        import subprocess
        from src.app.config import AppConfig
        from src.app.controller import AppController

        proc = MagicMock()
        proc.poll.return_value = None
        proc.stdout = []
        monkeypatch.setattr(subprocess, "Popen", MagicMock(return_value=proc))
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", r"C:\dist\BlackDragon.exe")

        ctrl = AppController(AppConfig())
        ok = ctrl.start_training()
        assert ok is True

        cmd = subprocess.Popen.call_args[0][0]
        assert cmd == [r"C:\dist\BlackDragon.exe", "--pipeline"]
        kwargs = subprocess.Popen.call_args[1]
        assert kwargs["cwd"] == r"C:\dist"

    def test_start_training_dev_uses_launch_py_pipeline(self, monkeypatch):
        """开发模式: cmd = [python, launch.py, --pipeline]。"""
        import subprocess
        from src.app.config import AppConfig
        from src.app.controller import AppController

        proc = MagicMock()
        proc.poll.return_value = None
        proc.stdout = []
        monkeypatch.setattr(subprocess, "Popen", MagicMock(return_value=proc))

        ctrl = AppController(AppConfig())
        ok = ctrl.start_training()
        assert ok is True

        cmd = subprocess.Popen.call_args[0][0]
        assert cmd[0] == sys.executable
        assert cmd[1] == "launch.py"
        assert cmd[2] == "--pipeline"

    def test_cancel_terminates_pipeline(self, monkeypatch):
        """取消训练终止 pipeline 子进程。"""
        import subprocess
        from src.app.config import AppConfig
        from src.app.controller import AppController

        proc = MagicMock()
        proc.poll.return_value = None
        monkeypatch.setattr(subprocess, "Popen", MagicMock(return_value=proc))

        ctrl = AppController(AppConfig())
        ctrl.start_training()
        assert ctrl.is_training is True

        ok = ctrl.cancel_training()
        assert ok is True
        proc.terminate.assert_called_once()


# =============================================================================
# 3. clean 失败（无原始 CSV）
# =============================================================================

class TestCleanFailure:
    def test_clean_no_csv_graceful(self, pipeline_workdir, capsys):
        """data/ 无 fatalis_combat_data_*.csv → clean 打印错误并返回，不崩溃。"""
        import data_cleaner
        result = data_cleaner.clean_combat_data()
        assert result is None
        captured = capsys.readouterr()
        assert "未找到任何战斗数据文件" in captured.out

    def test_pipeline_full_run_no_data_graceful(self, pipeline_workdir):
        """完整 --pipeline 在空数据目录下优雅结束（clean 无输出 + train 输入检查兜底）。"""
        old_argv = sys.argv
        try:
            sys.argv = ["python", "launch.py", "--pipeline"]
            launch.main()  # 不抛异常即通过
        finally:
            sys.argv = old_argv
        # 目录中不应产生训练数据集
        assert not (pipeline_workdir / "data" / "ML_Ready_Dataset.csv").exists()


# =============================================================================
# 4. train 失败（数据集缺失）→ 不覆盖旧模型
# =============================================================================

class TestTrainFailure:
    def test_train_missing_dataset_does_not_overwrite_model(
            self, pipeline_workdir, caplog):
        """ML_Ready_Dataset.csv 缺失 → train 优雅失败，且不覆盖已有旧模型。"""
        import logging
        import train_lgbm

        # 预置一个"旧模型"，训练失败时不应被覆盖
        old_model_path = pipeline_workdir / "models" / "fatalis_ai_model.pkl"
        old_model_path.write_bytes(b"OLD_MODEL_SENTINEL")

        with caplog.at_level(logging.ERROR, logger="BlackDragon"):
            train_lgbm.train_fatalis_ai()

        messages = [r.message for r in caplog.records if r.levelno >= logging.ERROR]
        assert any("找不到" in m for m in messages), f"未记录缺失错误: {messages}"
        # 旧模型未被覆盖（未生成 .bak，原文件保持原样）
        assert old_model_path.read_bytes() == b"OLD_MODEL_SENTINEL"


# =============================================================================
# 5. 数据含未知动作（v1.1.1 — 训练崩溃根因修复）
# =============================================================================

class TestPipelineUnknownActionGraceful:
    """完整 --pipeline 在数据含未知动作（如 117）时优雅完成，不崩溃。"""

    def _write_unknown_csv(self, pipeline_workdir):
        """写入含未知动作 117 的原始战斗 CSV。"""
        rows = [
            {"timestamp": 0.0, "hp_percent": 0.90, "phase": 1, "is_enraged": 0,
             "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 37},
            {"timestamp": 1.0, "hp_percent": 0.90, "phase": 1, "is_enraged": 0,
             "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 117},
            {"timestamp": 2.0, "hp_percent": 0.90, "phase": 1, "is_enraged": 0,
             "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 53},
        ]
        write_combat_csv(
            pipeline_workdir / "data" / "fatalis_combat_data_unknown.csv", rows)

    def test_pipeline_with_unknown_action_does_not_crash(self, pipeline_workdir):
        """--pipeline 遇到未知动作 → 清洗过滤 + 训练完成，不抛异常。"""
        self._write_unknown_csv(pipeline_workdir)

        old_argv = sys.argv
        try:
            sys.argv = ["python", "launch.py", "--pipeline"]
            launch.main()  # 不抛异常即通过
        finally:
            sys.argv = old_argv

        # 清洗产物不应包含未知动作 label
        out_path = pipeline_workdir / "data" / "ML_Ready_Dataset.csv"
        if out_path.exists():
            df = pd.read_csv(out_path)
            assert (df["next_action"] == 117).sum() == 0
