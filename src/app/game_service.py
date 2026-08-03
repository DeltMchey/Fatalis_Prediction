"""P5.1: GameService — 后台游戏检测线程。

需求 B: Dashboard 在无游戏进程时仍可运行——GameService 在后台循环
检测 MonsterHunterWorld.exe：

  - 游戏出现 → controller.attach_game(pm, base)（初始化 P4 模块）
  - 游戏消失（连续 N 次健康检查失败）→ controller.detach_game()

设计约束:
  - pymem 在 _try_attach 内惰性 import（模块级不 import → Linux CI 安全）
  - daemon 线程——进程退出时自动回收
"""

import logging
import threading
import time

logger = logging.getLogger("BlackDragon")


class GameService:
    """后台游戏检测线程。"""

    # 未连接时轮询间隔（秒）
    _POLL_INTERVAL: float = 2.0
    # 健康检查连续失败阈值（超过则 detach）
    _FAIL_THRESHOLD: int = 3
    # 游戏进程名
    _GAME_PROCESS: str = "MonsterHunterWorld.exe"

    def __init__(self, controller):
        """注入 AppController。"""
        self._controller = controller
        self._running: bool = False
        self._thread: threading.Thread | None = None
        self._fail_count: int = 0

    # ================= 生命周期 =================

    def start(self) -> None:
        """启动检测线程（daemon，幂等）。"""
        if self._thread is not None and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="GameService"
        )
        self._thread.start()

    def stop(self) -> None:
        """停止检测线程（下一轮循环退出）。"""
        self._running = False

    @property
    def is_running(self) -> bool:
        """检测线程是否运行。"""
        return self._running

    # ================= 内部 =================

    def _run(self) -> None:
        """检测主循环。"""
        while self._running:
            if not self._controller.is_game_attached:
                self._try_attach()
            else:
                self._monitor()
            time.sleep(self._POLL_INTERVAL)

    def _try_attach(self) -> None:
        """尝试连接游戏进程。成功 → attach_game()。"""
        try:
            # 惰性导入 pymem（模块级不依赖 → Linux CI 安全）
            import pymem
            import pymem.process
            pm = pymem.Pymem(self._GAME_PROCESS)
            base = pymem.process.module_from_name(
                pm.process_handle, self._GAME_PROCESS
            ).lpBaseOfDll
            if self._controller.attach_game(pm, base):
                logger.info("检测到游戏进程，已附着")
        except Exception:
            # 游戏尚未启动——静默等待下次轮询
            pass

    def _monitor(self) -> None:
        """已附着时健康检查——连续失败 N 次则分离。"""
        if self._controller.is_game_connected:
            self._fail_count = 0
            return
        self._fail_count += 1
        if self._fail_count >= self._FAIL_THRESHOLD:
            logger.info("游戏进程已退出，分离 P4 模块")
            self._controller.detach_game()
            self._fail_count = 0
