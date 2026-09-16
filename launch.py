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
  - 流水线模式: python launch.py --pipeline → data_cleaner → Run B 后端（冻结模式由 controller 拉起）
  - 训练模式:  python launch.py --train  → 仅运行 train_lgbm.py（legacy，向后兼容）
  - 自检模式:  launch --selftest → 动态 import + 模型加载 + 推理自检 → exit 0/1（构建冒烟入口）
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


def _selftest() -> int:
    """冻结模式自检（Dashboard EXE）：动态 import 链 + 模型加载 + 一次推理。

    Hotfix 防再漏措施：与 overlay.py --selftest 等价，额外覆盖 Dashboard
    进程特有的动态 import 高危点（data_cleaner / production_backend——
    均为运行期 import，PyInstaller 静态分析不可见，历史上曾漏打包）。
    模块级 import（Dashboard/dearpygui 链）在本函数执行前已完成——
    import 失败即进程非零退出，同样被冒烟判定捕获。

    Returns:
        0 = 全部通过；1 = 任一环节失败（详见 blackdragon.log）。
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass  # 非 TTY / 不支持 reconfigure 时忽略

    # 1. 动态 import 链（hiddenimports 高危点）
    try:
        from data_cleaner import clean_combat_data  # noqa: F401
        from src.model.production_backend import train_runb_backend  # noqa: F401
        print("[selftest] 动态依赖 import 成功 (data_cleaner / production_backend)")
    except Exception:
        logger.error("[selftest] FAIL: 动态依赖 import 失败\n%s",
                     traceback.format_exc())
        print("[selftest] FAIL: 动态依赖 import 失败")
        return 1

    # 2. 模型路径解析（hotfix RC2）+ 加载 + 一次推理
    #    （函数内 import 同样是 frozen 高危点——一并纳入 try）
    try:
        from src.app.config import resolve_runtime_path
        from src.model.predictor import ActionPredictor

        model_path = str(resolve_runtime_path("models/fatalis_ai_model.pkl"))
        print(f"[selftest] 模型路径解析: {model_path}")
        logger.info("[selftest] Dashboard 自检开始, 模型路径: %s", model_path)

        predictor = ActionPredictor(model_path)
        if not predictor.is_loaded:
            logger.error("[selftest] FAIL: AI 模型加载失败: %s", model_path)
            print("[selftest] FAIL: AI 模型加载失败")
            return 1
        print("[selftest] 模型加载成功")

        results = predictor.predict(1500.0, 45.0, 1, 37, 1, 0)
    except Exception:
        logger.error("[selftest] FAIL: 自检环节异常\n%s",
                     traceback.format_exc())
        print("[selftest] FAIL: 自检环节异常")
        return 1

    print(f"[selftest] predict 返回 {len(results)} 个候选")
    print("[selftest] PASS")
    return 0


def main() -> None:
    """组装并运行 Dashboard 控制中心 + Overlay 子进程。

    运行模式（PyInstaller 打包支持）：
      - 默认:        Dashboard 控制中心（launch.py / BlackDragon.exe）
      - --pipeline:  数据清洗 + Run B 训练后端（一键流程，frozen 模式下由 controller 拉起）
      - --train:     仅模型训练（legacy train_lgbm，向后兼容）
    """
    # 0. --selftest 模式：冻结 EXE 自检（构建冒烟 / CWD 矩阵验证入口，
    #    跳过 DependencyChecker / Overlay 启动 / Dashboard 主循环）
    if "--selftest" in sys.argv:
        sys.argv.remove("--selftest")
        sys.exit(_selftest())

    # 0a. --pipeline 模式：data_cleaner → Run B 后端（一键训练流程）
    if "--pipeline" in sys.argv:
        sys.argv.remove("--pipeline")
        # Windows 控制台/PIPE 默认 GBK——脚本含 emoji 输出，强制 UTF-8 避免 UnicodeEncodeError
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass  # 非 TTY/不支持 reconfigure 时忽略
        from data_cleaner import clean_combat_data
        from src.model.production_backend import train_runb_backend
        clean_combat_data()
        train_runb_backend()
        return

    # 0b. --train 模式：进入训练入口（frozen 模式下由 controller 拉起）
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
