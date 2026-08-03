"""P4 Step 6: BlackDragon — application composition root.

使用 P4 提取的模块组装应用。ai_engine.py 保留作为 legacy reference
和测试兼容入口（python ai_engine.py 仍可运行）。

Usage:
    python main.py          # 新架构入口（P4+ 推荐）

Legacy:
    python ai_engine.py     # God Class（未修改，参考/回退用）

线程模型：
  - main 线程: OverlayUI 的 DearPyGui event loop（阻塞）
  - daemon 线程: CombatRecorder 录制（由 recorder.start() 启动）
"""

import threading
import traceback
from collections import deque

import pymem
import pymem.process

from src.logging_config import setup_logging

from src.core.memory_reader import MemoryReader
from src.core.state_tracker import CombatStateTracker
from src.model.predictor import ActionPredictor
from src.data.recorder import CombatRecorder
from src.ui.overlay import OverlayUI

logger = setup_logging()


def main() -> None:
    """组装并运行应用：连接游戏 → 创建共享模块 → 启动录制 → 运行 UI。

    与 ai_engine.py 原 main() 行为等价，但使用 P4 提取模块：
      1. 连接 MonsterHunterWorld.exe
      2. MemoryReader + CombatStateTracker（Recorder 与 UI 共享）
      3. ActionPredictor（UI 专用）
      4. action_buffer + action_lock（Recorder ⟷ UI 通信通道）
      5. CombatRecorder daemon 线程
      6. OverlayUI（阻塞运行）
    """
    # 1. 连接游戏进程
    try:
        pm = pymem.Pymem("MonsterHunterWorld.exe")
    except Exception:
        logger.error(f"游戏进程连接失败:\n{traceback.format_exc()}")
        return print("未找到游戏进程")

    base = pymem.process.module_from_name(
        pm.process_handle, "MonsterHunterWorld.exe"
    ).lpBaseOfDll

    # 2. 核心共享模块
    memory_reader = MemoryReader(pm, base)
    state_tracker = CombatStateTracker(is_recording=True)

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
