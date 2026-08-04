"""P5.3: BlackDragon — Dual-process launcher（推荐入口）。

启动 **Dashboard + Overlay 双进程**（ADR-P5.2 + ADR-P5.3）：
  1. bootstrap.ensure()  — 环境检查（Python 版本 + 依赖完整性）
  2. 若 config.auto_start_overlay=True — 启动 overlay 子进程
     （独立 DPG context + 主线程 → 规避 GLFW main-thread 限制）
  3. AppController(config) — 轻量构造（P4 模块延迟附着）
  4. GameService 后台检测游戏
  5. Dashboard.run() — 控制中心（无游戏也可运行）

运行模式（PyInstaller 打包支持）：
  - 开发模式:  python launch.py          → spawn `python overlay.py`
  - 冻结模式:  BlackDragon.exe           → spawn `BlackDragonOverlay.exe`
  - 训练模式:  python launch.py --train  → 仅运行 train_lgbm.py（冻结模式由 controller 拉起）
  （由 sys.frozen 检测；冻结模式下跳过 DependencyChecker——依赖已打包）

Usage:
    python launch.py          # 双进程：Overlay 子进程 + Dashboard（推荐）
    python overlay.py         # 仅 Overlay
    main.py / ai_engine.py    # legacy（见 archive/）
"""

import sys
import traceback

from src.logging_config import setup_logging

from src.app.config import AppConfig
from src.app.controller import AppController
from src.app.game_service import GameService
from src.bootstrap.checker import DependencyChecker
from src.dashboard.main_window import Dashboard

logger = setup_logging()


def main() -> None:
    """组装并运行 Dashboard 控制中心 + Overlay 子进程。

    运行模式（PyInstaller 打包支持）：
      - 默认:        Dashboard 控制中心（launch.py / BlackDragon.exe）
      - --train:     训练模式（仅冻结模式由 controller.start_training 拉起）
    """
    # 0. --train 模式：进入训练入口（frozen 模式下由 controller 拉起）
    if "--train" in sys.argv:
        sys.argv.remove("--train")
        # Windows 控制台/PIPE 默认 GBK——训练脚本含 emoji 输出，强制 UTF-8 避免 UnicodeEncodeError
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass  # 非 TTY/不支持 reconfigure 时忽略
        from train_lgbm import train_fatalis_ai
        train_fatalis_ai()
        return

    # 1. 环境检查（bootstrap）——仅开发模式；冻结模式依赖已打包，跳过
    if not getattr(sys, "frozen", False):
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
