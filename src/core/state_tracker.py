"""P4 Step 1: CombatStateTracker — 纯战斗状态管理。

从原始内存数据计算派生战斗状态（phase / enrage / posture / nova），
取代 ai_engine.py 中模块级 `shared_state` dict 的角色。

设计约束（与架构计划 Step 1 一致）：
  - 不依赖 pymem / dearpygui / pandas / joblib / threading / 文件系统
  - 所有方法可由测试直接调用（纯逻辑）
  - 与 ai_engine.py shared_state 语义保持 1:1 对应

迁移说明：
  - 原 `shared_state['action_id']` 字段为死代码（从未被读写），不予保留
  - 原 `action_buffer` + `lock`（deque + threading.Lock）属线程协调职责，
    不在本模块范围内（P4 后续步骤处理）
"""

import math

from src.config.actions import (
    ACTION_MAPPING,
    NOVA_THRESHOLDS,
    POSTURE_STAND, POSTURE_PRONE, POSTURE_FLY,
)

# Nova warning 重置动作（与 ai_engine.py evaluate_nova 默认一致）
_NOVA_RESET_ACTIONS = {197, 167, 179}


class CombatStateTracker:
    """追踪黑龙战斗的派生状态（阶段/发怒/姿态/Nova 预警）。

    状态语义（与 ai_engine.py shared_state 一致）：
      - posture: 0=趴下, 1=站立, 2=飞行
      - phase: 1|2|3（>0.78 → 1, 0.50~0.78 → 2, <0.50 → 3）
      - is_enraged: 0|1（0 < enrage_timer < enrage_max → 1）
      - nova_warning: bool（血线阈值触发飞天火预警）
    """

    def __init__(self, is_recording: bool = True):
        # —— 派生状态 ——
        self.posture: int = 1            # 0=趴下, 1=站立, 2=飞行
        self.phase: int = 1              # 1|2|3
        self.is_enraged: int = 0         # 0|1
        self.nova_warning: bool = False  # 飞天火预警
        self.hp_initialized: bool = False  # 首次 HP 已初始化（Nova 状态机）
        self.triggered_novas: set[float] = set()  # 已触发过的 Nova 阈值集合
        self.is_recording: bool = is_recording   # 录制开关（用户控制）
        self._last_action: int = -1      # 姿态 FSM 的上一动作游标

    # ================= 纯数学工具（P3.3 提取函数镜像）=================

    @staticmethod
    def calc_distance_2d(p_coords, m_coords) -> float:
        """计算玩家与怪物在 XZ 平面上的二维欧几里得距离（忽略 Y 轴）。"""
        return math.sqrt(
            (p_coords[0] - m_coords[0]) ** 2 + (p_coords[2] - m_coords[2]) ** 2
        )

    @staticmethod
    def calc_relative_angle(p_coords, m_coords, m_quat) -> float:
        """计算从怪物朝向到玩家的相对角度（度），归一化到 [-180, 180]。"""
        monster_yaw = math.degrees(math.atan2(
            2.0 * (m_quat[1] * m_quat[3] + m_quat[0] * m_quat[2]),
            1.0 - 2.0 * (m_quat[0] ** 2 + m_quat[1] ** 2)
        ))
        target_yaw = math.degrees(math.atan2(
            p_coords[0] - m_coords[0],
            p_coords[2] - m_coords[2]
        ))
        return (target_yaw - monster_yaw + 180) % 360 - 180

    @staticmethod
    def map_action(raw_action: int) -> int:
        """将原始动画帧 ID 映射为起手 Base ID（无映射则原样返回）。"""
        return ACTION_MAPPING.get(raw_action, raw_action)

    # ================= 状态更新方法 =================

    def update_phase(self, hp_percent: float) -> None:
        """根据 HP 百分比更新战斗阶段（>0.78→1, 0.50~0.78→2, <0.50→3）。"""
        self.phase = 1 if hp_percent > 0.78 else (2 if hp_percent > 0.50 else 3)

    def update_enrage(self, enrage_timer: float, enrage_max: float) -> None:
        """根据引擎内部发怒秒表更新发怒状态（0 < timer < max → 发怒）。

        注意：原 ai_engine.py 在内存读取异常时置 0 的降级逻辑由调用方处理；
        本方法只做纯比较。
        """
        self.is_enraged = 1 if (0.0 < enrage_timer < enrage_max) else 0

    def update_posture(self, action: int) -> int | None:
        """根据动作更新姿态状态机，并维护 last_action 游标。

        与原逻辑一致：仅当 action 变化且非 -1 时触发姿态判定。
        返回新姿态（0/1/2）或无变化（None）。
        """
        if action == self._last_action or action == -1:
            self._last_action = action
            return None
        if action in POSTURE_STAND:
            self.posture = 1
        elif action in POSTURE_PRONE:
            self.posture = 0
        elif action in POSTURE_FLY:
            self.posture = 2
        self._last_action = action
        return self.posture

    def update_nova(self, hp_percent: float, action: int) -> bool:
        """评估 Nova（飞天火）血线预警。

        与 ai_engine.py evaluate_nova 逻辑一致：
          1. 首次初始化：标记所有已越过的阈值
          2. 持续检测：跨过新阈值时触发 warning
          3. 重置：特定动作 (197/167/179) 清除 warning

        Returns:
            bool: 当前 nova_warning 状态
        """
        # 阶段 1：首次初始化——标记所有已越过的阈值
        if not self.hp_initialized:
            for t in NOVA_THRESHOLDS:
                if hp_percent <= t:
                    self.triggered_novas.add(t)
            self.hp_initialized = True

        # 阶段 2：持续检测——发现新越过的阈值
        self.nova_warning = False
        for t in NOVA_THRESHOLDS:
            if hp_percent <= t and t not in self.triggered_novas:
                self.triggered_novas.add(t)
                self.nova_warning = True

        # 阶段 3：重置——特定动作清除 warning
        if action in _NOVA_RESET_ACTIONS:
            self.nova_warning = False

        return self.nova_warning

    def reset_for_zone_change(self) -> None:
        """离开虚黑城区域时彻底重置战斗状态（防污染逻辑）。

        与 ai_engine.py 区域切换逻辑一致：
          posture/phase/is_enraged/hp_initialized/nova_warning/triggered_novas
          全部复位；last_action 游标重置为 -1。

        注意：is_recording 为用户开关，跨区域保留；action_buffer 清空
        属线程协调职责，由调用方（UI）处理。
        """
        self.posture = 1
        self.phase = 1
        self.is_enraged = 0
        self.hp_initialized = False
        self.nova_warning = False
        self.triggered_novas.clear()
        self._last_action = -1
