"""P5.1: GameService tests — 后台游戏检测线程。

策略:
  - mock AppController（验证 attach/detach 调用）
  - pymem 惰性 import——通过 monkeypatch sys.modules 注入 mock
  - 不启动真实线程（直接调用 _try_attach/_monitor/_run 单轮）

覆盖:
  - start/stop 生命周期
  - _try_attach 成功 → attach_game
  - _try_attach 失败 → 静默（无 attach）
  - _monitor 健康检查正常 → 不分离
  - _monitor 连续失败达到阈值 → detach_game
  - _run 单轮循环逻辑
"""

import sys
import types
from unittest.mock import MagicMock

import pytest

# ─────────────────────────────────────────────────────────────────────────
# 跨平台 stub：pymem 是 Windows-only 依赖，Linux CI 不安装。
# 在 import game_service 之前预装空模块，使 import 成功。
# ─────────────────────────────────────────────────────────────────────────
if "pymem" not in sys.modules:
    _pymem_stub = types.ModuleType("pymem")
    _pymem_proc = types.ModuleType("pymem.process")
    # 预定义属性——monkeypatch.setattr 需要属性已存在（module 是 immutable 属性集）
    _pymem_stub.Pymem = None
    _pymem_proc.module_from_name = None
    _pymem_stub.process = _pymem_proc
    sys.modules["pymem"] = _pymem_stub
    sys.modules["pymem.process"] = _pymem_proc

from src.app.game_service import GameService


@pytest.fixture
def controller():
    """mock AppController——模拟未附着状态。"""
    ctrl = MagicMock()
    ctrl.is_game_attached = False
    ctrl.is_game_connected = True
    ctrl.attach_game.return_value = True
    return ctrl


@pytest.fixture
def service(controller):
    return GameService(controller)


# =============================================================================
# 1. 生命周期
# =============================================================================

class TestLifecycle:
    def test_initial_state(self, service):
        assert service.is_running is False
        assert service._thread is None

    def test_start_spawns_daemon_thread(self, service):
        service.start()
        assert service.is_running is True
        assert service._thread is not None
        assert service._thread.is_alive() is True
        assert service._thread.daemon is True
        service.stop()
        service._thread.join(timeout=5)

    def test_start_twice_single_thread(self, service):
        service.start()
        first = service._thread
        service.start()  # 幂等
        assert service._thread is first
        service.stop()
        service._thread.join(timeout=5)

    def test_stop_ends_thread(self, service):
        service.start()
        service.stop()
        service._thread.join(timeout=5)
        assert service._thread.is_alive() is False


# =============================================================================
# 2. _try_attach
# =============================================================================

class TestTryAttach:
    def test_attach_success(self, service, monkeypatch):
        """pymem 连接成功 → controller.attach_game 被调用。"""
        mock_pm = MagicMock()
        # patch stub 模块的属性（pymem 是 Windows-only，测试用 stub module）
        monkeypatch.setattr("pymem.Pymem", MagicMock(return_value=mock_pm))
        monkeypatch.setattr(
            "pymem.process.module_from_name",
            MagicMock(return_value=MagicMock(lpBaseOfDll=0x140000000)))
        service._try_attach()
        service._controller.attach_game.assert_called_once()
        # 传参: (pm, base)
        args = service._controller.attach_game.call_args[0]
        assert args[0] is mock_pm
        assert args[1] == 0x140000000

    def test_attach_failure_silent(self, service, monkeypatch):
        """pymem 连接失败 → 不调用 attach_game，不抛异常。"""
        monkeypatch.setattr(
            "pymem.Pymem", MagicMock(side_effect=RuntimeError("no game")))
        service._try_attach()  # 不应抛
        service._controller.attach_game.assert_not_called()

    def test_attach_but_controller_rejects(self, service, monkeypatch):
        """attach_game 返回 False（初始化失败）→ 静默。"""
        service._controller.attach_game.return_value = False
        monkeypatch.setattr("pymem.Pymem", MagicMock())
        monkeypatch.setattr(
            "pymem.process.module_from_name",
            MagicMock(return_value=MagicMock(lpBaseOfDll=0x140000000)))
        service._try_attach()  # 不应抛
        service._controller.attach_game.assert_called_once()


# =============================================================================
# 3. _monitor
# =============================================================================

class TestMonitor:
    def test_game_alive_no_detach(self, service):
        """健康检查通过 → 不分离，fail_count 清零。"""
        service._fail_count = 2
        service._monitor()
        service._controller.detach_game.assert_not_called()
        assert service._fail_count == 0

    def test_game_dead_one_failure(self, service, controller):
        """单次失败（低于阈值）→ 不分离。"""
        controller.is_game_connected = False
        service._monitor()
        service._controller.detach_game.assert_not_called()
        assert service._fail_count == 1

    def test_game_dead_reaches_threshold(self, service, controller):
        """连续失败达到阈值 → detach_game。"""
        controller.is_game_connected = False
        for _ in range(service._FAIL_THRESHOLD):
            service._monitor()
        service._controller.detach_game.assert_called_once()
        assert service._fail_count == 0  # 已重置


# =============================================================================
# 4. _run 单轮逻辑
# =============================================================================

class TestRun:
    def test_run_attaches_when_not_attached(self, service, monkeypatch):
        service._try_attach = MagicMock()
        service._monitor = MagicMock()
        service._running = True
        # 手动执行一轮后停止
        original_sleep = __import__("time").sleep
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("time.sleep", lambda s: setattr(service, "_running", False))
            service._run()
        service._try_attach.assert_called_once()
        service._monitor.assert_not_called()

    def test_run_monitors_when_attached(self, service, controller, monkeypatch):
        controller.is_game_attached = True
        service._try_attach = MagicMock()
        service._monitor = MagicMock()
        service._running = True
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("time.sleep", lambda s: setattr(service, "_running", False))
            service._run()
        service._try_attach.assert_not_called()
        service._monitor.assert_called_once()
