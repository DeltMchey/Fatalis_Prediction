"""P5.1.1 + P5.3: launch.py structural tests.

验证:
  - launch.py 无模块级 import pymem（bootstrap 可运行）
  - main() 不直接调用 pymem（GameService 负责）
  - launch 模块可被 import（不触发真实 pymem 依赖）
  - P5.3: main() 启动覆盖层子进程（controller.start_overlay）
  - ADR-P5.3: auto_start_overlay=True → 自动启动；False → 不启动
"""

import ast
import inspect
import sys
import types

import pytest
from unittest.mock import MagicMock

# ─────────────────────────────────────────────────────────────────────────
# 跨平台 stub：launch.py 不应再模块级 import pymem——
# 若仍存在，import launch 会失败（Linux CI 无 pymem）。
# 这里预装 stub 以便检查 import 成功，同时通过 AST 验证无 pymem import。
# ─────────────────────────────────────────────────────────────────────────
if "pymem" not in sys.modules:
    _pymem_stub = types.ModuleType("pymem")
    _pymem_proc = types.ModuleType("pymem.process")
    _pymem_stub.process = _pymem_proc
    sys.modules["pymem"] = _pymem_stub
    sys.modules["pymem.process"] = _pymem_proc

import launch  # noqa: E402


class TestNoModuleLevelPymem:
    def test_no_import_pymem_statement(self):
        """launch.py 源码不应包含模块级 import pymem。"""
        src = inspect.getsource(launch)
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("pymem"), (
                        f"模块级 import pymem 存在: {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("pymem"), (
                    f"模块级 from pymem import 存在: {node.module}"
                )

    def test_main_does_not_reference_pymem(self):
        """main() 函数体不应引用 pymem。"""
        src = inspect.getsource(launch.main)
        assert "pymem" not in src

    def test_launch_imports_without_pymem(self):
        """launch 模块成功 import（即使 pymem 是 stub）。"""
        assert launch is not None


class TestMainStructure:
    def test_main_has_bootstrap_call(self):
        """main() 应调用 DependencyChecker.ensure()。"""
        src = inspect.getsource(launch.main)
        assert "DependencyChecker.ensure()" in src

    def test_main_has_game_service(self):
        """main() 应创建并启动 GameService。"""
        src = inspect.getsource(launch.main)
        assert "GameService(" in src
        assert "game_service.start()" in src

    def test_main_has_dashboard(self):
        """main() 应创建 Dashboard 并运行。"""
        src = inspect.getsource(launch.main)
        assert "Dashboard(" in src
        assert "dashboard.run()" in src

    def test_main_starts_overlay_subprocess(self):
        """P5.3: main() 应启动覆盖层子进程（双进程架构）。"""
        src = inspect.getsource(launch.main)
        assert "controller.start_overlay()" in src

    def test_main_has_controller(self):
        """main() 应创建 AppController（start_overlay 的宿主）。"""
        src = inspect.getsource(launch.main)
        assert "AppController(" in src


# =============================================================================
# ADR-P5.3: auto_start_overlay 行为
# =============================================================================

class TestAutoStartBehavior:
    """main() 依据 config.auto_start_overlay 决定是否启动覆盖层子进程。

    通过 mock launch 模块的依赖，避免真实 bootstrap / DPG / pymem 副作用。
    """

    def _patch_deps(self, monkeypatch, auto_start_overlay=True):
        """patch launch.main 的依赖，返回 mock controller。"""
        mock_config = MagicMock()
        mock_config.auto_start_overlay = auto_start_overlay
        monkeypatch.setattr(
            launch, "AppConfig", MagicMock(load=MagicMock(return_value=mock_config)))
        mock_controller = MagicMock()
        monkeypatch.setattr(
            launch, "AppController", MagicMock(return_value=mock_controller))
        monkeypatch.setattr(
            launch, "DependencyChecker",
            MagicMock(ensure=MagicMock(return_value=True)))
        monkeypatch.setattr(launch, "GameService", MagicMock())
        mock_dash = MagicMock()
        monkeypatch.setattr(launch, "Dashboard", MagicMock(return_value=mock_dash))
        return mock_controller

    def test_auto_start_overlay_true_starts_subprocess(self, monkeypatch):
        """auto_start_overlay=True（默认）→ controller.start_overlay() 被调用。"""
        controller = self._patch_deps(monkeypatch, auto_start_overlay=True)
        launch.main()
        controller.start_overlay.assert_called_once()

    def test_auto_start_overlay_false_skips_subprocess(self, monkeypatch):
        """auto_start_overlay=False → controller.start_overlay() 不被调用。"""
        controller = self._patch_deps(monkeypatch, auto_start_overlay=False)
        launch.main()
        controller.start_overlay.assert_not_called()

    def test_main_still_runs_dashboard_regardless(self, monkeypatch):
        """无论 auto_start_overlay 如何，Dashboard 仍正常运行。"""
        controller = self._patch_deps(monkeypatch, auto_start_overlay=False)
        launch.main()
        controller.shutdown.assert_called_once()  # 走到 finally 清理
