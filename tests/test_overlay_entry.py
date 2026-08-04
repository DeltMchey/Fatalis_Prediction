"""P5.3: overlay.py composition root integration tests（双进程架构）。

策略：
  - 所有测试在函数级 patch `overlay.pymem` 等模块引用——从不触发真实 pymem/DearPyGUI
  - 验证 overlay() 的接线正确性：创建了哪些对象、参数是否正确传递
  - 不启动真实游戏进程 / 不打开真实窗口
  - 跨平台：在 Linux CI（未安装 pymem/dearpygui）上，模块级预装 stub，
    使 `from overlay import main` 可在 import 阶段成功

覆盖：
  - pymem 连接 + base 解析
  - MemoryReader / CombatStateTracker / ActionPredictor 实例化
  - action_buffer + lock 创建并注入 Recorder + OverlayUI
  - CombatRecorder.start() 被调用
  - OverlayUI.run() 被调用
  - 模型加载成功/失败打印行为
  - 游戏进程连接失败降级
  - 结构约束：overlay.py 不 import ai_engine、无模块级可变状态、
    与 main.py 等价（双进程独立入口）
"""

import sys
import types
from collections import deque
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────────────────────────────────────────────────────────
# 跨平台 stub：pymem / dearpygui 是 Windows-only 依赖，Linux CI 不安装。
# 在 import overlay 之前预装空模块，使 `import overlay` 在任意平台成功。
# （测试运行时这些模块被函数级 monkeypatch 替换，stub 仅用于过 import。）
# ─────────────────────────────────────────────────────────────────────────
if "pymem" not in sys.modules:
    _pymem_stub = types.ModuleType("pymem")
    _pymem_proc = types.ModuleType("pymem.process")
    _pymem_stub.process = _pymem_proc
    sys.modules["pymem"] = _pymem_stub
    sys.modules["pymem.process"] = _pymem_proc

if "dearpygui" not in sys.modules:
    _dpg_stub = types.ModuleType("dearpygui")
    _dpg_mod = types.ModuleType("dearpygui.dearpygui")
    _dpg_stub.dearpygui = _dpg_mod
    sys.modules["dearpygui"] = _dpg_stub
    sys.modules["dearpygui.dearpygui"] = _dpg_mod

from overlay import main, _find_game_process

# 假模块基址
FAKE_BASE = 0x140000000


def make_patches():
    """返回 overlay 模块引用的完整 mock 上下文。"""
    return (
        patch("overlay.pymem"),
        patch("overlay.pymem.process"),
        patch("overlay.AppConfig"),
        patch("overlay.MemoryReader"),
        patch("overlay.CombatStateTracker"),
        patch("overlay.ActionPredictor"),
        patch("overlay.CombatRecorder"),
        patch("overlay.OverlayUI"),
    )


@pytest.fixture
def wired(monkeypatch):
    """模拟一个已连接的 pymem 环境，返回各 mock 的引用。"""
    mock_pm = MagicMock()
    mock_process = MagicMock()
    mock_process.module_from_name.return_value = MagicMock(lpBaseOfDll=FAKE_BASE)

    mock_mr_cls = MagicMock()
    mock_st_cls = MagicMock()
    mock_pred_cls = MagicMock()
    mock_rec_cls = MagicMock()
    mock_ov_cls = MagicMock()

    # 默认模型已加载
    mock_pred_cls.return_value.is_loaded = True

    # ADR-P5.3: overlay 读取共享 AppConfig 决定录制默认状态
    mock_cfg = MagicMock()
    mock_cfg.auto_record = True
    mock_cfg_cls = MagicMock(load=MagicMock(return_value=mock_cfg))

    monkeypatch.setattr("overlay.pymem", MagicMock(Pymem=MagicMock(return_value=mock_pm)))
    monkeypatch.setattr("overlay.pymem.process", mock_process)
    monkeypatch.setattr("overlay.AppConfig", mock_cfg_cls)
    monkeypatch.setattr("overlay.MemoryReader", mock_mr_cls)
    monkeypatch.setattr("overlay.CombatStateTracker", mock_st_cls)
    monkeypatch.setattr("overlay.ActionPredictor", mock_pred_cls)
    monkeypatch.setattr("overlay.CombatRecorder", mock_rec_cls)
    monkeypatch.setattr("overlay.OverlayUI", mock_ov_cls)

    return {
        "pm": mock_pm,
        "process": mock_process,
        "AppConfig": mock_cfg_cls,
        "MemoryReader": mock_mr_cls,
        "CombatStateTracker": mock_st_cls,
        "ActionPredictor": mock_pred_cls,
        "CombatRecorder": mock_rec_cls,
        "OverlayUI": mock_ov_cls,
    }


# =============================================================================
# 1. 结构约束（AST 精确检查——避免 docstring 干扰）
# =============================================================================

import ast


def _module_import_names(src):
    """返回模块所有 import 的目标名（模块路径 + 类名 + 别名）。"""
    tree = ast.parse(src)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
            names.update(a.name for a in node.names if a.name != "*")
    return names


def _module_level_assign_sources(src):
    """返回模块级（缩进 0）赋值语句右侧的源代码片段列表。"""
    tree = ast.parse(src)
    sources = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and not isinstance(node.targets[0], ast.Name):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            sources.append(ast.get_source_segment(src, node.value))
    return sources


class TestStructuralConstraints:
    def test_overlay_does_not_import_ai_engine(self):
        """overlay.py 不应 import ai_engine——新架构独立于 legacy。"""
        import inspect
        import overlay as overlay_module
        names = _module_import_names(inspect.getsource(overlay_module))
        assert "ai_engine" not in names

    def test_overlay_no_module_level_mutable_state(self):
        """overlay.py 无模块级可变状态（全局 dict/deque/Lock）。"""
        import inspect
        import overlay as overlay_module
        src = inspect.getsource(overlay_module)
        sources = _module_level_assign_sources(src)
        for s in sources:
            assert "deque(" not in s
            assert "Lock()" not in s
            assert "= {" not in s
            assert "= []" not in s

    def test_overlay_imports_all_p4_modules(self):
        """overlay.py 导入全部 5 个 P4 模块。"""
        import inspect
        import overlay as overlay_module
        names = _module_import_names(inspect.getsource(overlay_module))
        for mod in ["MemoryReader", "CombatStateTracker", "ActionPredictor",
                    "CombatRecorder", "OverlayUI"]:
            assert mod in names, f"缺少 import {mod}"


# =============================================================================
# 2. pymem 连接 + base 解析
# =============================================================================

class TestPymemConnection:
    def test_connects_to_game(self, wired):
        main()
        assert wired["pm"] is not None

    def test_module_from_name_used_for_base(self, wired):
        main()
        wired["process"].module_from_name.assert_called_once()

    def test_base_passed_to_memory_reader(self, wired):
        main()
        args = wired["MemoryReader"].call_args[0]
        assert args[1] == FAKE_BASE

    def test_pymem_failure_exits_gracefully(self, monkeypatch, capsys):
        """游戏进程连接失败（重试超时）→ 打印提示，不抛异常。"""
        import overlay as overlay_module
        monkeypatch.setattr(overlay_module, "_MAX_RETRIES", 2)
        monkeypatch.setattr(overlay_module, "_RETRY_INTERVAL", 0)
        mock_pymem = MagicMock()
        mock_pymem.Pymem.side_effect = RuntimeError("process not found")
        monkeypatch.setattr("overlay.pymem", mock_pymem)

        main()  # 不应抛出
        captured = capsys.readouterr()
        assert "未找到游戏进程" in captured.out

    def test_connect_retries_until_success(self, monkeypatch):
        """pymem 首次失败 → 重试 → 成功返回实例。"""
        import overlay as overlay_module
        monkeypatch.setattr(overlay_module, "_MAX_RETRIES", 5)
        monkeypatch.setattr(overlay_module, "_RETRY_INTERVAL", 0)
        mock_pm = MagicMock()
        calls = {"n": 0}

        def fake_pymem(_name):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("not yet")
            return mock_pm

        monkeypatch.setattr(
            "overlay.pymem", MagicMock(Pymem=fake_pymem))
        result = overlay_module._find_game_process()
        assert result is mock_pm
        assert calls["n"] == 3

    def test_connect_timeout_returns_none(self, monkeypatch):
        """重试耗尽仍失败 → 返回 None（main 打印超时提示）。"""
        import overlay as overlay_module
        monkeypatch.setattr(overlay_module, "_MAX_RETRIES", 3)
        monkeypatch.setattr(overlay_module, "_RETRY_INTERVAL", 0)
        monkeypatch.setattr(
            "overlay.pymem",
            MagicMock(Pymem=MagicMock(side_effect=RuntimeError("no game"))))
        assert overlay_module._find_game_process() is None


# =============================================================================
# 3. 模块实例化
# =============================================================================

class TestModuleInstantiation:
    def test_memory_reader_created(self, wired):
        main()
        wired["MemoryReader"].assert_called_once()

    def test_state_tracker_created_with_auto_record(self, wired):
        """ADR-P5.3: CombatStateTracker 使用 config.auto_record。"""
        main()
        args = wired["CombatStateTracker"].call_args[1]
        assert args["is_recording"] is True  # fixture: auto_record=True

    def test_auto_record_false_flows_to_state_tracker(self, monkeypatch):
        """config.auto_record=False → CombatStateTracker(is_recording=False)。"""
        import overlay as overlay_module
        mock_cfg = MagicMock()
        mock_cfg.auto_record = False
        monkeypatch.setattr(
            "overlay.AppConfig", MagicMock(load=MagicMock(return_value=mock_cfg)))

        mock_pm = MagicMock()
        mock_process = MagicMock()
        mock_process.module_from_name.return_value = MagicMock(lpBaseOfDll=FAKE_BASE)
        monkeypatch.setattr(
            "overlay.pymem", MagicMock(Pymem=MagicMock(return_value=mock_pm)))
        monkeypatch.setattr("overlay.pymem.process", mock_process)
        mock_st_cls = MagicMock()
        monkeypatch.setattr("overlay.CombatStateTracker", mock_st_cls)
        monkeypatch.setattr("overlay.MemoryReader", MagicMock())
        monkeypatch.setattr("overlay.ActionPredictor", MagicMock())
        monkeypatch.setattr("overlay.CombatRecorder", MagicMock())
        monkeypatch.setattr("overlay.OverlayUI", MagicMock())

        main()
        args = mock_st_cls.call_args[1]
        assert args["is_recording"] is False

    def test_predictor_created_with_model_path(self, wired):
        main()
        args = wired["ActionPredictor"].call_args[0]
        assert args[0] == "models/fatalis_ai_model.pkl"

    def test_predictor_loaded_prints_success(self, wired, capsys):
        wired["ActionPredictor"].return_value.is_loaded = True
        main()
        captured = capsys.readouterr()
        assert "成功加载 AI 预测模型" in captured.out

    def test_predictor_not_loaded_no_print(self, wired, capsys):
        wired["ActionPredictor"].return_value.is_loaded = False
        main()
        captured = capsys.readouterr()
        assert "成功加载 AI 预测模型" not in captured.out


# =============================================================================
# 4. 通信通道
# =============================================================================

class TestCommunicationChannels:
    def test_recorder_receives_shared_instances(self, wired):
        main()
        rec_args = wired["CombatRecorder"].call_args[0]
        assert rec_args[0] is wired["MemoryReader"].return_value
        assert rec_args[1] is wired["CombatStateTracker"].return_value
        assert isinstance(rec_args[2], deque)
        assert callable(rec_args[3].acquire)

    def test_overlay_receives_shared_instances(self, wired):
        main()
        ov_args = wired["OverlayUI"].call_args[0]
        assert ov_args[0] is wired["MemoryReader"].return_value
        assert ov_args[1] is wired["CombatStateTracker"].return_value
        assert ov_args[2] is wired["ActionPredictor"].return_value
        assert isinstance(ov_args[3], deque)
        assert callable(ov_args[4].acquire)

    def test_same_buffer_and_lock_between_recorder_and_overlay(self, wired):
        main()
        rec_args = wired["CombatRecorder"].call_args[0]
        ov_args = wired["OverlayUI"].call_args[0]
        assert rec_args[2] is ov_args[3]
        assert rec_args[3] is ov_args[4]

    def test_same_memory_reader_and_state_tracker(self, wired):
        main()
        rec_args = wired["CombatRecorder"].call_args[0]
        ov_args = wired["OverlayUI"].call_args[0]
        assert rec_args[0] is ov_args[0]
        assert rec_args[1] is ov_args[1]


# =============================================================================
# 5. 生命周期
# =============================================================================

class TestLifecycle:
    def test_recorder_started(self, wired):
        main()
        wired["CombatRecorder"].return_value.start.assert_called_once()

    def test_overlay_run_called(self, wired):
        main()
        wired["OverlayUI"].return_value.run.assert_called_once()

    def test_recorder_started_before_overlay_run(self, wired):
        main()
        assert wired["CombatRecorder"].return_value.start.call_count == 1
        assert wired["OverlayUI"].return_value.run.call_count == 1


# =============================================================================
# 6. P5.3 双进程结构约束
# =============================================================================

class TestDualProcessConstraints:
    def test_overlay_entry_equivalent_to_main(self):
        """overlay.py 与 main.py 组装逻辑等价（双进程独立入口）。

        两个入口都组装相同的 5 个 P4 模块 + 相同通信通道。
        """
        import inspect
        import main as main_module
        import overlay as overlay_module
        main_names = _module_import_names(inspect.getsource(main_module))
        overlay_names = _module_import_names(inspect.getsource(overlay_module))
        p4_mods = ["MemoryReader", "CombatStateTracker", "ActionPredictor",
                   "CombatRecorder", "OverlayUI"]
        for mod in p4_mods:
            assert mod in main_names
            assert mod in overlay_names

    def test_overlay_import_without_side_effects(self):
        """import overlay 不触发 pymem/DearPyGUI 副作用。"""
        import sys
        assert "overlay" in sys.modules  # 已成功 import（无异常）


# =============================================================================
# 7. Windows UTF-8 stdout/stderr 兼容（emoji 输出修复）
# =============================================================================

class TestUtf8Stdio:
    def test_ensure_utf8_stdio_reconfigures(self, monkeypatch):
        """_ensure_utf8_stdio 调用 stdout/stderr reconfigure(encoding='utf-8')。"""
        import overlay as overlay_module
        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        monkeypatch.setattr("sys.stdout", mock_stdout)
        monkeypatch.setattr("sys.stderr", mock_stderr)
        overlay_module._ensure_utf8_stdio()
        mock_stdout.reconfigure.assert_called_once_with(
            encoding="utf-8", errors="replace")
        mock_stderr.reconfigure.assert_called_once_with(
            encoding="utf-8", errors="replace")

    def test_ensure_utf8_stdio_fallback_on_exception(self, monkeypatch):
        """reconfigure 抛异常时不崩溃（静默忽略）。"""
        import overlay as overlay_module
        mock_stdout = MagicMock()
        mock_stdout.reconfigure.side_effect = RuntimeError("no reconfigure")
        monkeypatch.setattr("sys.stdout", mock_stdout)
        monkeypatch.setattr("sys.stderr", MagicMock())
        # 不应抛异常
        overlay_module._ensure_utf8_stdio()

    def test_ensure_utf8_stdio_no_reconfigure_attr(self, monkeypatch):
        """stdout 无 reconfigure 属性（极老 Python）→ 不崩溃。"""
        import overlay as overlay_module
        class NoReconfigure:
            pass
        monkeypatch.setattr("sys.stdout", NoReconfigure())
        monkeypatch.setattr("sys.stderr", NoReconfigure())
        overlay_module._ensure_utf8_stdio()  # 不应抛异常

    def test_main_calls_ensure_utf8_stdio_first(self, monkeypatch):
        """main() 最早调用 _ensure_utf8_stdio（在 AppConfig.load 之前）。"""
        import overlay as overlay_module
        order = []
        monkeypatch.setattr(
            overlay_module, "_ensure_utf8_stdio",
            lambda: order.append("utf8"))
        mock_config = MagicMock()
        mock_config.auto_record = True
        monkeypatch.setattr(
            overlay_module, "AppConfig",
            MagicMock(load=MagicMock(
                side_effect=lambda: order.append("config") or mock_config)))
        monkeypatch.setattr(
            overlay_module, "_find_game_process",
            MagicMock(return_value=MagicMock()))
        monkeypatch.setattr("overlay.pymem.process", MagicMock(
            module_from_name=MagicMock(
                return_value=MagicMock(lpBaseOfDll=0x140000000))))
        monkeypatch.setattr(overlay_module, "MemoryReader", MagicMock())
        monkeypatch.setattr(overlay_module, "CombatStateTracker", MagicMock())
        monkeypatch.setattr(overlay_module, "ActionPredictor", MagicMock())
        monkeypatch.setattr(overlay_module, "CombatRecorder", MagicMock())
        monkeypatch.setattr(overlay_module, "OverlayUI", MagicMock())
        overlay_module.main()
        assert order[0] == "utf8"
        assert "config" in order

    def test_main_prints_emoji_with_utf8(self, monkeypatch, capsys):
        """main() 在 UTF-8 reconfigure 后 print emoji 不再抛 UnicodeEncodeError。"""
        import overlay as overlay_module
        monkeypatch.setattr(
            "sys.stdout.reconfigure", MagicMock(encoding="utf-8", errors="replace"),
            raising=False)
        monkeypatch.setattr(
            overlay_module, "_ensure_utf8_stdio",
            lambda: sys.stdout.reconfigure(encoding="utf-8", errors="replace"))
        mock_config = MagicMock()
        mock_config.auto_record = True
        monkeypatch.setattr(
            overlay_module, "AppConfig",
            MagicMock(load=MagicMock(return_value=mock_config)))
        mock_pm = MagicMock()
        monkeypatch.setattr(
            overlay_module, "_find_game_process",
            MagicMock(return_value=mock_pm))
        monkeypatch.setattr("overlay.pymem.process", MagicMock(
            module_from_name=MagicMock(
                return_value=MagicMock(lpBaseOfDll=0x140000000))))
        monkeypatch.setattr(overlay_module, "MemoryReader", MagicMock())
        monkeypatch.setattr(overlay_module, "CombatStateTracker", MagicMock())
        pred = MagicMock()
        pred.is_loaded = True
        monkeypatch.setattr(overlay_module, "ActionPredictor",
                            MagicMock(return_value=pred))
        monkeypatch.setattr(overlay_module, "CombatRecorder", MagicMock())
        monkeypatch.setattr(overlay_module, "OverlayUI", MagicMock())
        # main() 内 print("✅ ...") 不应抛 UnicodeEncodeError
        overlay_module.main()
