"""P4 Step 4: CombatRecorder — 战斗数据录制线程（daemon）。

从 ai_engine.py 迁移：
  - `data_logger_thread`（原 L271–L316）整体迁移为 CombatRecorder 类

设计约束（与架构计划 Step 4 一致）：
  - 所有内存读取仅通过 MemoryReader（禁止直接 pymem / pm.read_*）
  - 所有状态读取仅通过 CombatStateTracker（禁止 shared_state dict）
  - 依赖 threading / csv / os / time / datetime
  - 不依赖 dearpygui / pandas / joblib / lightgbm
  - CSV 列格式与 ai_engine.py 原 data_logger_thread 完全一致
  - daemon 生命周期：单帧异常 logger.warning → sleep → continue；stop() 显式关闭
"""

import csv
import os
import threading
import time
import traceback
from collections import deque
from datetime import datetime

from src.config.offsets import OFFSETS
from src.logging_config import setup_logging

logger = setup_logging()


class CombatRecorder:
    """后台录制线程：将战斗帧数据写入 CSV。

    用法：
        recorder = CombatRecorder(memory_reader, state_tracker, action_buffer, lock)
        recorder.start()          # 启动 daemon 线程（立即返回）
        ...
        recorder.stop()           # 显式关闭（下一轮循环退出）

    每帧数据流：
        MemoryReader 读取原始数据
          → action_id 写入共享 action_buffer（带 action_lock）
          → CombatStateTracker 状态 + 距离/角度 → CSV 追加一行
    """

    # CSV 列名（与 ai_engine.py data_logger_thread 头部完全一致）
    _COLUMNS: list[str] = [
        "timestamp", "hp_percent", "phase", "is_enraged",
        "distance", "relative_angle", "posture", "action_id",
    ]
    # 暂停轮询周期（未录制 / 不在虚黑城时）
    _PAUSE_INTERVAL: float = 1.0
    # 帧轮询周期
    _FRAME_INTERVAL: float = 0.1

    def __init__(
        self,
        memory_reader,
        state_tracker,
        action_buffer: deque,
        action_lock: threading.Lock,
        data_dir: str = "data",
    ):
        """初始化录制器。

        Args:
            memory_reader: MemoryReader 实例（所有 pymem 读取的唯一入口）
            state_tracker: CombatStateTracker 实例（读取 is_recording/phase/posture/is_enraged）
            action_buffer: deque，action_id 写入目标（与 UI 线程共享）
            action_lock: threading.Lock，保护 action_buffer
            data_dir: CSV 输出目录（默认 "data"，不存在时自动创建）
        """
        self._reader = memory_reader
        self._state = state_tracker
        self._buffer = action_buffer
        self._lock = action_lock
        self._data_dir = data_dir
        self._running: bool = False
        self._thread: threading.Thread | None = None
        self._file_created: bool = False
        self._filename: str | None = None

    # ================= 生命周期 =================

    @property
    def is_running(self) -> bool:
        """录制循环是否运行（stop() 后为 False）。"""
        return self._running

    def start(self) -> None:
        """启动 daemon 线程（幂等：已运行时直接返回）。"""
        if self._thread is not None and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(
            target=self.run, daemon=True, name="CombatRecorder"
        )
        self._thread.start()

    def stop(self) -> None:
        """显式关闭：置 _running=False，线程在下一次循环迭代退出。"""
        self._running = False

    def run(self) -> None:
        """主循环（线程 target）。NEVER 直接调用——请使用 start()。

        与 ai_engine.py data_logger_thread 循环语义一致：
          - 未录制 / 不在虚黑城 → 长休眠（1s）后重新检查
          - 帧读取或写入异常 → logger.warning → 0.1s 后继续（不自动终止）
        """
        while self._running:
            try:
                if self._should_pause():
                    time.sleep(self._PAUSE_INTERVAL)
                    continue
                self._record_frame()
            except Exception:
                logger.warning(f"录制线程异常:\n{traceback.format_exc()}")
            time.sleep(self._FRAME_INTERVAL)

    # ================= 门控 =================

    def _should_pause(self) -> bool:
        """返回 True 表示暂停（长休眠）：未录制 或 不在虚黑城。

        与 ai_engine.py 门控语义一致：
          - is_recording=False → 暂停
          - zone 读取失败（None/0）或 zone != ZONE_FATALIS → 暂停
        """
        if not self._state.is_recording:
            return True
        if self._reader.check_zone() != OFFSETS.ZONE_FATALIS:
            return True
        return False

    # ================= 帧录制 =================

    def _record_frame(self) -> bool:
        """尝试录制一帧。

        流程（与 ai_engine.py data_logger_thread 逐行等价）：
          1. 查找怪物实体 + 玩家坐标（任一缺失 → 跳过该帧，不写 CSV）
          2. 读取怪物坐标/四元数/HP/动作 ID（任一失败 → 跳过该帧）
          3. action_id 写入共享 action_buffer（带锁）
          4. 首帧创建 CSV 文件 + header（惰性创建）
          5. 计算距离/相对角度（CombatStateTracker 静态方法）
          6. CSV 追加一行

        Returns:
            bool: 是否成功写入一行
        """
        monster = self._reader.find_monster()
        p_coords = self._reader.read_player_coords()
        if monster is None or p_coords is None:
            return False

        m_coords = self._reader.read_monster_coords(monster)
        m_quat = self._reader.read_monster_quat(monster)
        hp_percent = self._reader.read_monster_hp(monster)
        action_id = self._reader.read_monster_action(monster)
        if m_coords is None or m_quat is None or hp_percent is None or action_id is None:
            logger.warning("录制帧数据不完整（内存读取失败），跳过该帧")
            return False

        with self._lock:
            self._buffer.append(action_id)

        if not self._file_created:
            self._filename = self._create_file()
            self._file_created = True

        dist = self._state.calc_distance_2d(p_coords, m_coords)
        rel_angle = self._state.calc_relative_angle(p_coords, m_coords, m_quat)

        with open(self._filename, 'a', newline='') as f:
            csv.writer(f).writerow([
                time.time(),
                hp_percent,
                self._state.phase,
                self._state.is_enraged,
                dist,
                rel_angle,
                self._state.posture,
                action_id,
            ])
        return True

    # ================= CSV 文件管理 =================

    def _create_file(self) -> str:
        """创建新 CSV 文件并写入列名行（每个录制会话仅一次）。

        Returns:
            str: 生成的文件完整路径
        """
        filename = (
            f"fatalis_combat_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        filepath = os.path.join(self._data_dir, filename)
        os.makedirs(self._data_dir, exist_ok=True)
        with open(filepath, 'w', newline='') as f:
            csv.writer(f).writerow(self._COLUMNS)
        return filepath
