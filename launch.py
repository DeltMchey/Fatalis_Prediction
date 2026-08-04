"""P5.3: BlackDragon — Dual-process launcher（推荐入口）。

启动 **Dashboard + Overlay 双进程**（ADR-P5.2 + ADR-P5.3）：
  1. bootstrap.ensure()  — 环境检查（Python 版本 + 依赖完整性）
  2. 若 config.auto_start_overlay=True — 启动 `overlay.py` 子进程
     （独立 DPG context + 主线程 → 规避 GLFW main-thread 限制）
  3. AppController(config) — 轻量构造（P4 模块延迟附着）
  4. GameService 后台检测游戏
  5. Dashboard.run() — 控制中心（无游戏也可运行）

Usage:
    python launch.py          # 双进程：Overlay 子进程 + Dashboard（推荐）
    python overlay.py         # 仅 Overlay
    python main.py            # P4 overlay 直启（legacy）
    python ai_engine.py       # legacy God Class
"""

import traceback

from src.logging_config import setup_logging

from src.app.config import AppConfig
from src.app.controller import AppController
from src.app.game_service import GameService
from src.bootstrap.checker import DependencyChecker
from src.dashboard.main_window import Dashboard

logger = setup_logging()


def main() -> None:
    """组装并运行 Dashboard 控制中心 + Overlay 子进程。"""
    # 0. 环境检查（bootstrap）——失败则退出
    if not DependencyChecker.ensure():
        return

    # 1. 轻量 Controller（P4 模块由 GameService 延迟附着）
    config = AppConfig.load()
    controller = AppController(config)

    # 2. 启动覆盖层子进程（双进程——独立 DPG context + 主线程）
    #    仅当 auto_start_overlay 启用（ADR-P5.3）；失败不阻断 Dashboard
    if config.auto_start_overlay:
        controller.start_overlay()

    # 3. Dashboard（无需游戏连接）
    dashboard = Dashboard(controller)

    # 4. 后台游戏检测线程
    game_service = GameService(controller)
    game_service.start()

    # 5. DPG event loop（阻塞）——退出时清理
    try:
        dashboard.run()
    except Exception:
        logger.error(f"控制中心异常退出:\n{traceback.format_exc()}")
    finally:
        game_service.stop()
        controller.shutdown()


if __name__ == "__main__":
    main()
