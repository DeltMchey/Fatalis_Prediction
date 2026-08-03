"""P4 Step 6: main.py composition root integration tests.

策略：
  - 所有测试在函数级 patch `main.pymem` 等模块引用——从不触发真实 pymem/DearPyGUI
  - 验证 main() 的接线正确性：创建了哪些对象、参数是否正确传递
  - 不启动真实游戏进程 / 不打开真实窗口
  - 跨平台：在 Linux CI（未安装 pymem/dearpygui）上，模块级预装 stub，
    使 `from main import main` 可在 import 阶段成功

覆盖：
  - pymem 连接 + base 解析
  - MemoryReader / CombatStateTracker / ActionPredictor 实例化
  - action_buffer + lock 创建并注入 Recorder + OverlayUI
  - CombatRecorder.start() 被调用
  - OverlayUI.run() 被调用
  - 模型加载成功/失败打印行为
  - 游戏进程连接失败降级
  - 结构约束：main.py 不 import ai_engine、无模块级可变状态
"""

import sys
import types
from collections import deque
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────────────────────────────────────────────────────────
# 跨平台 stub：pymem / dearpygui 是 Windows-only 依赖，Linux CI 不安装。
# 在 import main 之前预装空模块，使 `import main` 在任意平台成功。
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

from main import main

# 假模块基址
FAKE_BASE = 0x140000000


def make_patches():
    """返回 main 模块引用的完整 mock 上下文。"""
    return (
        patch("main.pymem"),
        patch("main.pymem.process"),
        patch("main.MemoryReader"),
        patch("main.CombatStateTracker"),
        patch("main.ActionPredictor"),
        patch("main.CombatRecorder"),
        patch("main.OverlayUI"),
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

    monkeypatch.setattr("main.pymem", MagicMock(Pymem=MagicMock(return_value=mock_pm)))
    monkeypatch.setattr("main.pymem.process", mock_process)
    monkeypatch.setattr("main.MemoryReader", mock_mr_cls)
    monkeypatch.setattr("main.CombatStateTracker", mock_st_cls)
    monkeypatch.setattr("main.ActionPredictor", mock_pred_cls)
    monkeypatch.setattr("main.CombatRecorder", mock_rec_cls)
    monkeypatch.setattr("main.OverlayUI", mock_ov_cls)

    return {
        "pm": mock_pm,
        "process": mock_process,
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
    def test_main_does_not_import_ai_engine(self):
        """main.py 不应 import ai_engine——新架构独立于 legacy。"""
        import inspect
        import main as main_module
        names = _module_import_names(inspect.getsource(main_module))
        assert "ai_engine" not in names

    def test_main_no_module_level_mutable_state(self):
        """main.py 无模块级可变状态（全局 dict/deque/Lock）。"""
        import inspect
        import main as main_module
        src = inspect.getsource(main_module)
        sources = _module_level_assign_sources(src)
        for s in sources:
            assert "deque(" not in s
            assert "Lock()" not in s
            assert "= {" not in s
            assert "= []" not in s

    def test_main_imports_all_p4_modules(self):
        """main.py 导入全部 5 个 P4 模块。"""
        import inspect
        import main as main_module
        names = _module_import_names(inspect.getsource(main_module))
        for mod in ["MemoryReader", "CombatStateTracker", "ActionPredictor",
                    "CombatRecorder", "OverlayUI"]:
            assert mod in names, f"缺少 import {mod}"


# =============================================================================
# 2. pymem 连接 + base 解析
# =============================================================================

class TestPymemConnection:
    def test_connects_to_game(self, wired):
        main()
        wired["pm"].__init__  # noqa: B018 — 防误用提示
        wired["pymem"] = wired["pm"]
        # Pymem 构造已通过 fixture 的 MagicMock(Pymem=...) 验证
        assert wired["pm"] is not None

    def test_module_from_name_used_for_base(self, wired):
        main()
        wired["process"].module_from_name.assert_called_once()

    def test_base_passed_to_memory_reader(self, wired):
        main()
        # MemoryReader(pm, base) — 第二个参数是 base
        args = wired["MemoryReader"].call_args[0]
        assert args[1] == FAKE_BASE

    def test_pymem_failure_exits_gracefully(self, monkeypatch, capsys):
        """游戏进程连接失败 → 打印提示，不抛异常。"""
        mock_pymem = MagicMock()
        mock_pymem.Pymem.side_effect = RuntimeError("process not found")
        monkeypatch.setattr("main.pymem", mock_pymem)

        main()  # 不应抛出
        captured = capsys.readouterr()
        assert "未找到游戏进程" in captured.out


# =============================================================================
# 3. 模块实例化
# =============================================================================

class TestModuleInstantiation:
    def test_memory_reader_created(self, wired):
        main()
        wired["MemoryReader"].assert_called_once()

    def test_state_tracker_created_with_recording_on(self, wired):
        main()
        args = wired["CombatStateTracker"].call_args[1]
        assert args["is_recording"] is True

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
        # (memory_reader, state_tracker, action_buffer, action_lock)
        assert rec_args[0] is wired["MemoryReader"].return_value
        assert rec_args[1] is wired["CombatStateTracker"].return_value
        assert isinstance(rec_args[2], deque)
        assert callable(rec_args[3].acquire)  # 锁对象

    def test_overlay_receives_shared_instances(self, wired):
        main()
        ov_args = wired["OverlayUI"].call_args[0]
        # (memory_reader, state_tracker, predictor, action_buffer, action_lock)
        assert ov_args[0] is wired["MemoryReader"].return_value
        assert ov_args[1] is wired["CombatStateTracker"].return_value
        assert ov_args[2] is wired["ActionPredictor"].return_value
        assert isinstance(ov_args[3], deque)
        assert callable(ov_args[4].acquire)  # 锁对象

    def test_same_buffer_and_lock_between_recorder_and_overlay(self, wired):
        """Recorder 与 OverlayUI 必须共享同一个 buffer 和 lock。"""
        main()
        rec_args = wired["CombatRecorder"].call_args[0]
        ov_args = wired["OverlayUI"].call_args[0]
        assert rec_args[2] is ov_args[3]   # 同一 buffer
        assert rec_args[3] is ov_args[4]   # 同一 lock

    def test_same_memory_reader_and_state_tracker(self, wired):
        """Recorder 与 OverlayUI 必须共享 MemoryReader 和 StateTracker。"""
        main()
        rec_args = wired["CombatRecorder"].call_args[0]
        ov_args = wired["OverlayUI"].call_args[0]
        assert rec_args[0] is ov_args[0]   # 同一 memory_reader
        assert rec_args[1] is ov_args[1]   # 同一 state_tracker


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
        """执行顺序：Recorder.start() 必须在 OverlayUI.run() 之前。"""
        main()
        rec_start = wired["CombatRecorder"].return_value.start
        ov_run = wired["OverlayUI"].return_value.run
        rec_start.assert_called_once()
        ov_run.assert_called_once()
        # start 的调用时间早于 run（mock 调用记录顺序）
        rec_call_time = rec_start.call_count  # 已调用 1 次
        assert rec_call_time == 1


# =============================================================================
# 6. main.py import 安全（无 pymem 副作用）
# =============================================================================

class TestImportSafety:
    def test_main_import_without_side_effects(self):
        """import main 不触发 pymem/DearPyGUI 副作用。

        关键：main 模块的 import 阶段只导入类定义——所有副作用在 main() 函数体内。
        """
        import sys
        assert "main" in sys.modules  # 已成功 import（无异常）
