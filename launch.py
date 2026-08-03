"""P5.1: BlackDragon — Dashboard composition root（推荐入口）。

Usage:
    python launch.py          # P5 控制中心（推荐）

Legacy:
    python main.py            # P4 overlay 直启
    python ai_engine.py       # legacy God Class

流程:
  0. bootstrap.ensure()  — 环境检查（Python 版本 + 依赖完整性）
  1. AppController(config) — 轻量构造（P4 模块延迟附着）
  2. GameService 后台检测游戏
  3. Dashboard.run() — 无游戏也可运行，游戏出现后自动启用功能
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
    """组装并运行 Dashboard 控制中心。"""
    # 0. 环境检查（bootstrap）——失败则退出
    if not DependencyChecker.ensure():
        return

    # 1. 轻量 Controller（P4 模块由 GameService 延迟附着）
    config = AppConfig.load()
    controller = AppController(config)

    # 2. Dashboard（无需游戏连接）
    dashboard = Dashboard(controller)

    # 3. 后台游戏检测线程
    game_service = GameService(controller)
    game_service.start()

    # 4. DPG event loop（阻塞）——退出时清理
    try:
        dashboard.run()
    except Exception:
        logger.error(f"控制中心异常退出:\n{traceback.format_exc()}")
    finally:
        game_service.stop()
        controller.shutdown()


if __name__ == "__main__":
    main()
