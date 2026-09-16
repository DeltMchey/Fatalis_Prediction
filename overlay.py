"""P5.3: BlackDragon — Overlay 独立进程入口（双进程架构）。

在独立进程中组装 P4 模块并运行透明覆盖层：
  - 每个进程拥有自己的 DPG context + 主线程 → 规避 DPG 2.x / GLFW
    的 main-thread 限制（ADR-P5.2 双进程决策）
  - 与 Dashboard（launch.py）完全隔离——互不阻塞、互不崩溃

ADR-P5.3（自动启动）：
  - 读取共享 AppConfig（blackdragon_config.json）决定录制默认状态
  - 游戏进程连接采用重试循环——Dashboard 启动时可先于游戏运行，
    overlay 进程在游戏出现后自动进入工作状态

Usage:
    python overlay.py          # 独立覆盖层（由 launch.py / Dashboard 启动，或手动）
    overlay --selftest         # 自检模式：路径解析→模型加载→一次推理→exit 0/1
                               # （frozen EXE 冒烟与 CWD 矩阵验证入口，跳过游戏/UI）

Entry points:
    python launch.py           # Dashboard + Overlay（推荐）
    python overlay.py          # 仅 Overlay
    python main.py             # P4 standalone overlay（legacy）

线程模型：
  - main 线程: OverlayUI 的 DearPyGui event loop（阻塞）
  - daemon 线程: CombatRecorder 录制（由 recorder.start() 启动）
"""

import sys
import threading
import time
import traceback
from collections import deque

import pymem
import pymem.process

from src.logging_config import setup_logging

from src.app.config import AppConfig, resolve_runtime_path
from src.core.memory_reader import MemoryReader
from src.core.state_tracker import CombatStateTracker
from src.model.predictor import ActionPredictor
from src.data.recorder import CombatRecorder
from src.ui.overlay import OverlayUI

logger = setup_logging()

# 游戏进程重试参数（ADR-P5.3 方案 A：启动可先于游戏运行）
_RETRY_INTERVAL: float = 2.0   # 重试间隔（秒）
_MAX_RETRIES: int = 60         # 最大重试次数（总计约 2 分钟）


def _ensure_utf8_stdio() -> None:
    """Windows 控制台/PIPE 默认 GBK——emoji 输出（如 ✅）触发 UnicodeEncodeError。

    强制 stdout/stderr 使用 UTF-8（errors=replace 兜底），兼容：
      - Python 3.12 开发模式（python overlay.py）
      - PyInstaller frozen 模式（BlackDragonOverlay.exe，stdout 被 PIPE 重定向）
    与 launch.py --train 模式的 UTF-8 修复方式一致。

    reconfigure 不存在（极老 Python）或失败时静默忽略——不因编码初始化崩溃。
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass  # 非 TTY / 不支持 reconfigure 时忽略


def _find_game_process():
    """轮询查找游戏进程：最多 _MAX_RETRIES 次，间隔 _RETRY_INTERVAL 秒。

    Returns:
        pymem.Pymem: 连接成功的实例；超时返回 None。
    """
    for attempt in range(_MAX_RETRIES):
        try:
            return pymem.Pymem("MonsterHunterWorld.exe")
        except Exception:
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_INTERVAL)
    return None


def main() -> None:
    """组装并运行覆盖层进程：连接游戏 → 创建共享模块 → 启动录制 → 运行 UI。

    与 main.py 等价（P4 composition root），但作为独立进程运行。
    ADR-P5.3: 读取共享 AppConfig 决定录制默认状态；游戏未运行时重试等待。
    """
    # 0. Windows UTF-8 编码修复——最早阶段，避免后续 emoji print 触发 GBK 错误
    _ensure_utf8_stdio()

    config = AppConfig.load()

    # 1. 连接游戏进程（重试等待——启动可先于游戏运行）
    pm = _find_game_process()
    if pm is None:
        logger.error("等待超时，未找到游戏进程")
        return print("未找到游戏进程")

    base = pymem.process.module_from_name(
        pm.process_handle, "MonsterHunterWorld.exe"
    ).lpBaseOfDll

    # 2. 核心共享模块
    memory_reader = MemoryReader(pm, base)
    state_tracker = CombatStateTracker(is_recording=config.auto_record)

    # 3. AI 预测（UI 专用）
    #    hotfix RC2: frozen 模式下 CWD 不确定（双击/压缩软件内启动），
    #    相对路径 "models/..." 会指向不存在的文件 → 模型加载静默失败。
    #    resolve_runtime_path 在冻结模式基于 exe 目录解析。
    model_path = str(resolve_runtime_path("models/fatalis_ai_model.pkl"))
    predictor = ActionPredictor(model_path)
    if predictor.is_loaded:
        logger.info("成功加载 AI 预测模型: %s", model_path)
        print("✅ 成功加载 AI 预测模型！")
    else:
        # hotfix RC1: 失败分支曾完全无痕（stdout 又被 controller DEVNULL 吞掉），
        # UI 侧仅显示固定提示——ERROR 日志是用户可回传的唯一线索
        logger.error("AI 预测模型未加载（预测功能禁用）— 解析路径: %s", model_path)

    # 4. 通信通道
    action_buffer = deque(maxlen=100)
    action_lock = threading.Lock()

    # 5. 后台录制（daemon 线程）
    recorder = CombatRecorder(
        memory_reader, state_tracker, action_buffer, action_lock
    )
    recorder.start()

    # 6. UI 覆盖层（阻塞——DPG event loop 运行在 main 线程）
    overlay = OverlayUI(
        memory_reader, state_tracker, predictor, action_buffer, action_lock
    )
    overlay.run()


def _selftest() -> int:
    """冻结模式自检：路径解析 → 模型加载 → 一次推理 → 退出码。

    Hotfix 防再漏措施（RC2）：跑在真实 Overlay EXE 进程里——本模块的
    模块级 import（pymem / DPG / xgboost pickle 链）与生产启动完全一致，
    但跳过游戏连接与 UI 主循环。构建冒烟（build_exe.ps1）与
    "非 exe 目录 CWD 启动"矩阵验证均以本入口为准。

    Returns:
        0 = 模型加载 + 推理管线通过；1 = 任一环节失败（详见 blackdragon.log）。
    """
    _ensure_utf8_stdio()
    model_path = str(resolve_runtime_path("models/fatalis_ai_model.pkl"))
    print(f"[selftest] 模型路径解析: {model_path}")
    logger.info("[selftest] Overlay 自检开始, 模型路径: %s", model_path)

    predictor = ActionPredictor(model_path)
    if not predictor.is_loaded:
        logger.error("[selftest] FAIL: AI 模型加载失败: %s", model_path)
        print("[selftest] FAIL: AI 模型加载失败")
        return 1
    print("[selftest] 模型加载成功")

    try:
        results = predictor.predict(1500.0, 45.0, 1, 37, 1, 0)
    except Exception:
        logger.error("[selftest] FAIL: 推理管线异常\n%s", traceback.format_exc())
        print("[selftest] FAIL: 推理管线异常")
        return 1

    top = f"{results[0][0]}: {results[0][1] * 100:.1f}%" if results else "(空)"
    print(f"[selftest] predict 返回 {len(results)} 个候选, top={top}")
    print("[selftest] PASS")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    main()
