"""P4 Step 2: MemoryReader — 封装所有 pymem 进程内存读取操作。

唯一负责通过 pymem 读取 MonsterHunterWorld.exe 进程内存的模块。
所有方法返回原始数据值，不做任何语义解释（phase/enrage/posture/nova 等
状态判断由 StateTracker 负责）。

设计约束：
  - 仅依赖 pymem + src.config.offsets
  - 不依赖 dearpygui / pandas / joblib / lightgbm / threading / StateTracker
  - 所有公共方法在读取失败时返回安全的默认值（None / 0 / 空列表）
  - 与 ai_engine.py 原始内存读取逻辑保持 1:1 一致
"""

from src.config.offsets import OFFSETS


class MemoryReader:
    """通过 pymem 读取 MonsterHunterWorld.exe 进程内存。

    构造函数接收已连接的 pymem 实例和模块基址，计算 PLAYER/MONSTER/ZONE
    绝对地址。所有后续读取方法通过实例内部的 _pm 和预计算地址完成。
    """

    def __init__(self, pm, base: int):
        """初始化内存读取器。

        Args:
            pm: pymem.Pymem 实例（已连接到 MonsterHunterWorld.exe）
            base: MonsterHunterWorld.exe 模块基址（lpBaseOfDll）
        """
        self._pm = pm
        self._player_base = base + OFFSETS.PLAYER_BASE
        self._monster_base = base + OFFSETS.MONSTER_BASE
        self._zone_base = base + OFFSETS.ZONE_BASE

    # ================= 指针链遍历 =================

    def follow_pointer_chain(self, address: int, offsets: list[int]) -> int:
        """遍历多级指针链，返回最终地址。

        与 ai_engine.py get_ptr() 逻辑完全一致：
          - offsets[:-1] 为中间跳转，逐级 read_longlong
          - offsets[-1] 直接加法（最终偏移，不再解引用）

        Args:
            address: 起始地址
            offsets: 偏移列表（至少 1 个）

        Returns:
            最终地址（失败时返回 0）
        """
        try:
            addr = self._pm.read_longlong(address)
            for o in offsets[:-1]:
                addr = self._pm.read_longlong(addr + o)
            return addr + offsets[-1]
        except Exception:
            return 0

    # ================= 区域检测 =================

    def check_zone(self) -> int | None:
        """读取当前区域 ID。

        Returns:
            zone_id (int) 或 None（读取失败时）
        """
        try:
            zone_addr = self.follow_pointer_chain(self._zone_base, [OFFSETS.ZONE_OFFSET])
            if zone_addr == 0:
                return None
            return self._pm.read_int(zone_addr)
        except Exception:
            return None

    # ================= 怪物实体查找 =================

    def find_monster(self) -> int | None:
        """遍历怪物实体槽位，查找 HP > 500 的有效怪物（黑龙）。

        与 ai_engine.py find_monster() 逻辑完全一致：
          - 遍历 10 个槽位
          - 通过 MONSTER_LIST_FIRST → i*STRIDE → NEXT → TERMINAL 链定位
          - 检查 HP_MAX > MONSTER_MIN_HP 判定有效实体

        Returns:
            怪物实体指针（int）或 None（未找到）
        """
        for i in range(OFFSETS.MONSTER_MAX_SLOTS):
            ptr = self.follow_pointer_chain(self._monster_base, [
                OFFSETS.MONSTER_LIST_FIRST,
                i * OFFSETS.MONSTER_LIST_STRIDE,
                OFFSETS.MONSTER_LIST_NEXT,
                OFFSETS.MONSTER_LIST_TERMINAL,
            ])
            if ptr:
                try:
                    hp = self._pm.read_longlong(ptr + OFFSETS.MONSTER_HP_BASE)
                    if self._pm.read_float(hp + OFFSETS.HP_MAX) > OFFSETS.MONSTER_MIN_HP:
                        return ptr
                except Exception:
                    pass
        return None

    # ================= 玩家数据 =================

    def read_player_coords(self) -> list[float] | None:
        """读取玩家坐标。

        指针链：PLAYER_CHAIN_1 → PLAYER_CHAIN_2 → PLAYER_COORDS

        Returns:
            [x, y, z] 或 None（读取失败时）
        """
        try:
            player = self.follow_pointer_chain(self._player_base, [
                OFFSETS.PLAYER_CHAIN_1,
                OFFSETS.PLAYER_CHAIN_2,
                OFFSETS.PLAYER_COORDS,
            ])
            if player == 0:
                return None
            return [self._pm.read_float(player + i * 4) for i in range(3)]
        except Exception:
            return None

    # ================= 怪物数据（均以怪物实体指针为参数）=================

    def read_monster_coords(self, monster_ptr: int) -> list[float] | None:
        """读取怪物坐标（[x, y, z]）。"""
        try:
            return [
                self._pm.read_float(monster_ptr + OFFSETS.MONSTER_COORDS + i * 4)
                for i in range(3)
            ]
        except Exception:
            return None

    def read_monster_quat(self, monster_ptr: int) -> list[float] | None:
        """读取怪物旋转四元数（游戏存储顺序 [x, y, z, w]）。"""
        try:
            return [
                self._pm.read_float(monster_ptr + OFFSETS.MONSTER_QUAT + i * 4)
                for i in range(4)
            ]
        except Exception:
            return None

    def read_monster_hp(self, monster_ptr: int) -> float | None:
        """读取怪物 HP 百分比（0.0 ~ 1.0）。

        读取链：MONSTER_HP_BASE → HP_CURRENT / HP_MAX
        """
        try:
            hp_ptr = self._pm.read_longlong(monster_ptr + OFFSETS.MONSTER_HP_BASE)
            current = self._pm.read_float(hp_ptr + OFFSETS.HP_CURRENT)
            max_hp = self._pm.read_float(hp_ptr + OFFSETS.HP_MAX)
            return current / max_hp if max_hp > 0 else 0.0
        except Exception:
            return None

    def read_monster_action(self, monster_ptr: int) -> int | None:
        """读取怪物当前动作 ID（原始动画帧 ID）。"""
        try:
            return self._pm.read_int(monster_ptr + OFFSETS.MONSTER_ACTION_ID)
        except Exception:
            return None

    def read_enrage_state(self, monster_ptr: int) -> tuple[float, float]:
        """读取引擎内部发怒秒表（硬件级检测）。

        Returns:
            (enrage_timer: float, enrage_max: float)；
            读取失败时返回 (0.0, 0.0)
        """
        try:
            timer = self._pm.read_float(
                monster_ptr + OFFSETS.ENRAGE_STRUCT + OFFSETS.ENRAGE_TIMER)
            max_val = self._pm.read_float(
                monster_ptr + OFFSETS.ENRAGE_STRUCT + OFFSETS.ENRAGE_MAX)
            return (timer, max_val)
        except Exception:
            return (0.0, 0.0)
