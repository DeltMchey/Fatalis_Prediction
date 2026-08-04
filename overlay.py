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

from src.app.config import AppConfig
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
    predictor = ActionPredictor("models/fatalis_ai_model.pkl")
    if predictor.is_loaded:
        logger.info("成功加载 AI 预测模型")
        print("✅ 成功加载 AI 预测模型！")

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


if __name__ == "__main__":
    main()
