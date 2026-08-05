"""P5.1 + P5.3: AppController — 应用生命周期协调器。

Dashboard（UI 层）通过 AppController 间接控制底层模块：
  - 游戏附着/分离（attach_game / detach_game）
  - Recorder 启停（state_tracker.is_recording / recorder.stop()）
  - 覆盖层子进程（start_overlay / stop_overlay —— P5.3 双进程架构）
  - Trainer 子进程（--pipeline: data_cleaner → train_lgbm）启动/取消/输出轮询

P5.3 双进程架构（ADR-P5.2）：
  - Overlay 是**独立进程**（`python overlay.py`），自管 DPG context + 生命周期
  - 本 Controller 只负责**启动/终止**覆盖层子进程，不创建 OverlayUI 实例
  - 因此 attach_game 不再导入 src.ui.overlay —— 仅组装 P4 数据模块

设计约束:
  - 不直接操作 pymem / DPG widgets
  - 构造仅依赖 config——P4 模块通过 attach_game() 延迟附着（无游戏时 Dashboard 仍可运行）
  - P4 模块在 attach_game 内惰性 import（不在模块级 import pymem/dearpygui → Linux CI 安全）
  - 可在 Linux CI import（无 dearpygui 依赖）
"""

import logging
import os
import queue
import subprocess
import sys
import threading
from collections import deque
from pathlib import Path

from src.app.config import AppConfig

logger = logging.getLogger("BlackDragon")


class AppController:
    """协调 Recorder / Overlay 子进程 / Trainer 生命周期。

    与 Dashboard 的关系:
      Dashboard 持有 AppController 引用 → call commands + poll status.
      Dashboard NEVER 直接操作 Recorder / OverlayUI.
    """

    def __init__(self, config: AppConfig):
        """轻量构造——仅 config 必选。

        Args:
            config: AppConfig — 设置读写

        P4 模块（state/recorder/predictor/reader/buffer/lock）初始为
        None，由 GameService 检测到游戏后通过 attach_game() 附着。
        覆盖层是独立子进程（_overlay_proc），非 P4 模块。
        """
        self._config = config

        # P4 模块（延迟附着）
        self._state = None          # CombatStateTracker
        self._recorder = None       # CombatRecorder
        self._predictor = None      # ActionPredictor
        self._reader = None         # MemoryReader
        self._buffer = None         # deque
        self._lock = None           # threading.Lock

        self._game_attached: bool = False

        # 覆盖层子进程（P5.3 双进程）—— 独立 python overlay.py
        self._overlay_proc = None

        # 训练子进程管理
        self._training_proc = None
        self._training_queue: "queue.Queue[tuple]" = queue.Queue()
        self._training_thread = None

    # ================= 游戏附着 / 分离 =================

    def attach_game(self, pm, base) -> bool:
        """游戏进程连接后初始化全部 P4 数据模块。

        Args:
            pm: pymem.Pymem 实例（已连接 MonsterHunterWorld.exe）
            base: 模块基址（lpBaseOfDll）

        Returns:
            bool: 是否成功附着。失败时回滚已创建的部分模块。

        注意: 本方法不创建 OverlayUI（P5.3 覆盖层是独立进程）——
        也不调用任何 DPG 方法，因此可安全地从 GameService 后台线程调用。
        """
        # 惰性导入 P4 模块（避免模块级依赖）
        from src.core.memory_reader import MemoryReader
        from src.core.state_tracker import CombatStateTracker
        from src.model.predictor import ActionPredictor
        from src.data.recorder import CombatRecorder

        # 暂存已创建的模块——失败时回滚
        created = {}
        try:
            reader = MemoryReader(pm, base)
            created["reader"] = reader
            # ADR-P5.3: 录制默认状态由 auto_record 配置决定
            state = CombatStateTracker(is_recording=self._config.auto_record)
            created["state"] = state
            predictor = ActionPredictor(self._config.model_path)
            created["predictor"] = predictor
            buffer = deque(maxlen=100)
            lock = threading.Lock()
            created["buffer"] = buffer
            created["lock"] = lock
            recorder = CombatRecorder(reader, state, buffer, lock,
                                      data_dir=str(self.data_dir))
            created["recorder"] = recorder
        except Exception:
            logger.error("attach_game 初始化失败", exc_info=True)
            return False

        # 全部创建成功 → 附着
        self._reader = reader
        self._state = state
        self._predictor = predictor
        self._buffer = buffer
        self._lock = lock
        self._recorder = recorder
        self._game_attached = True

        # 启动录制 daemon 线程
        try:
            recorder.start()
        except Exception:
            logger.error("启动录制失败", exc_info=True)
        logger.info("游戏已附着，P4 模块初始化完成")
        return True

    def detach_game(self) -> None:
        """游戏进程退出后清理全部 P4 数据模块。

        覆盖层子进程是独立的——本方法不终止它（用户可手动关闭）。
        """
        if self._recorder is not None:
            try:
                self._recorder.stop()
            except Exception:
                pass
        self._game_attached = False
        # 清理引用（旧实例由 GC 回收）
        self._reader = None
        self._state = None
        self._predictor = None
        self._buffer = None
        self._lock = None
        self._recorder = None
        logger.info("游戏已分离，P4 模块已清理")

    # ================= 状态查询（Dashboard 轮询）=================

    @property
    def is_game_attached(self) -> bool:
        """P4 模块是否已初始化（游戏已连接）。"""
        return self._game_attached

    @property
    def is_game_connected(self) -> bool:
        """游戏进程是否仍存活（已附着 + 内存可读）。"""
        if not self._game_attached or self._reader is None:
            return False
        try:
            return self._reader.check_zone() is not None
        except Exception:
            return False

    @property
    def is_recording(self) -> bool:
        """是否处于录制状态（user 开关）。"""
        if self._state is None:
            return False
        return bool(self._state.is_recording)

    @property
    def is_model_loaded(self) -> bool:
        """AI 模型是否成功加载。"""
        if self._predictor is None:
            return False
        return bool(self._predictor.is_loaded)

    @property
    def is_overlay_running(self) -> bool:
        """覆盖层子进程是否在运行（P5.3）。"""
        if self._overlay_proc is None:
            return False
        return self._overlay_proc.poll() is None

    @property
    def is_training(self) -> bool:
        """训练子进程是否在运行。"""
        return self._training_proc is not None and self._training_proc.poll() is None

    @property
    def data_dir(self) -> "Path":
        """录制 CSV 输出目录（Dashboard 显示文件列表用）。

        冻结模式（PyInstaller）下解析为 <exe_dir>/<data_dir>，避免 CWD 不确定：
          开发模式: python launch.py      → Path(config.data_dir)（相对项目根）
          冻结模式: BlackDragon.exe       → Path(sys.executable).parent / data_dir
        保留 config.data_dir 自定义能力（绝对路径直接使用，相对路径在冻结模式基于 exe 目录）。
        """
        path = self._config.data_dir
        if getattr(sys, "frozen", False) and not os.path.isabs(path):
            return Path(sys.executable).parent / path
        return Path(path)

    # ================= 命令（Dashboard 按钮绑定）=================

    def toggle_recording(self) -> bool:
        """切换录制开关，返回新状态。"""
        if self._state is None:
            return False
        self._state.is_recording = not bool(self._state.is_recording)
        return bool(self._state.is_recording)

    def set_recording(self, enabled: bool) -> None:
        """显式设置录制开关。"""
        if self._state is not None:
            self._state.is_recording = bool(enabled)

    def start_overlay(self) -> bool:
        """启动覆盖层子进程。

        运行模式（PyInstaller 打包支持）：
          - 开发模式:  [sys.executable, "overlay.py"]
          - 冻结模式:  [<exe_dir>/BlackDragonOverlay.exe]（与 BlackDragon.exe 同目录）
        由 getattr(sys, "frozen", False) 检测当前运行环境。

        P5.3：Overlay 是独立进程——每个进程自己的 DPG context + 主线程，
        规避 DPG 2.x / GLFW 的 main-thread 限制（ADR-P5.2）。

        Returns:
            bool: 是否成功启动（已在运行/启动失败返回 False）。
        """
        if self.is_overlay_running:
            logger.info("覆盖层子进程已在运行")
            return False
        try:
            if getattr(sys, "frozen", False):
                # 冻结模式：spawn 与当前 exe 同目录的 BlackDragonOverlay.exe
                exe_dir = os.path.dirname(os.path.abspath(sys.executable))
                overlay_exe = os.path.join(exe_dir, "BlackDragonOverlay.exe")
                cmd = [overlay_exe]
            else:
                # 开发模式：python overlay.py
                cmd = [sys.executable, self._config.overlay_script]
            self._overlay_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            logger.error("启动覆盖层子进程失败", exc_info=True)
            self._overlay_proc = None
            return False
        logger.info("覆盖层子进程已启动: %s", self._config.overlay_script)
        return True

    def stop_overlay(self) -> bool:
        """终止覆盖层子进程。返回是否有进程被终止。"""
        if not self.is_overlay_running:
            return False
        try:
            self._overlay_proc.terminate()
            return True
        except Exception:
            logger.error("终止覆盖层子进程失败", exc_info=True)
            return False

    def start_training(self) -> bool:
        """启动训练子进程（v1.1: --pipeline = data_cleaner → train_lgbm）。

        运行模式（PyInstaller 打包支持）：
          - 开发模式:  [sys.executable, "launch.py", "--pipeline"]
          - 冻结模式:  [sys.executable, "--pipeline"]（同一 exe 的流水线模式）
        由 getattr(sys, "frozen", False) 检测当前运行环境。

        返回是否成功启动（已在训练时返回 False）。
        """
        if self.is_training:
            return False
        try:
            if getattr(sys, "frozen", False):
                # 冻结模式：spawn 同 exe 的 --pipeline 训练模式
                cmd = [sys.executable, "--pipeline"]
                # 训练脚本始终在 exe 所在目录运行（不依赖 CWD —— 兼容双击/快捷方式/其他目录启动）
                popen_kwargs = {"cwd": os.path.dirname(sys.executable)}
            else:
                # 开发模式：python launch.py --pipeline
                cmd = [sys.executable, "launch.py", "--pipeline"]
                popen_kwargs = {}
            self._training_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                **popen_kwargs,
            )
        except Exception:
            logger.error("启动训练失败", exc_info=True)
            return False
        self._training_queue = queue.Queue()
        self._training_thread = threading.Thread(
            target=self._read_training_output, daemon=True
        )
        self._training_thread.start()
        logger.info("训练已启动: %s", "launch.py --pipeline")
        return True

    def cancel_training(self) -> bool:
        """终止训练子进程。返回是否有进程被终止。"""
        if self._training_proc is None or self._training_proc.poll() is not None:
            return False
        try:
            self._training_proc.terminate()
            return True
        except Exception:
            logger.error("取消训练失败", exc_info=True)
            return False

    def get_training_output(self) -> list[str]:
        """从训练子进程输出队列取所有待显示行（非阻塞）。"""
        lines = []
        while not self._training_queue.empty():
            try:
                lines.append(self._training_queue.get_nowait())
            except queue.Empty:
                break
        return lines

    # ================= 生命周期 =================

    def shutdown(self) -> None:
        """优雅退出：停止录制 → 终止覆盖层子进程 → 终止训练。"""
        try:
            if self._recorder is not None:
                self._recorder.stop()
        except Exception:
            logger.error("停止录制失败", exc_info=True)
        try:
            if self.is_overlay_running:
                self._overlay_proc.terminate()
        except Exception:
            logger.error("终止覆盖层子进程失败", exc_info=True)
        try:
            if self.is_training:
                self._training_proc.terminate()
        except Exception:
            pass
        self._game_attached = False
        logger.info("BlackDragon 已关闭")

    # ================= 内部：训练输出读取 =================

    def _read_training_output(self) -> None:
        """后台线程：读取训练子进程 stdout → 推送队列。"""
        try:
            for line in self._training_proc.stdout:
                self._training_queue.put(line.rstrip())
        except Exception:
            pass
        finally:
            # 进程结束：push 退出标记
            try:
                code = self._training_proc.wait()
                self._training_queue.put(f"[训练结束] 退出码: {code}")
            except Exception:
                pass
