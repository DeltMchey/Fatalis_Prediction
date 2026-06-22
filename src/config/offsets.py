"""内存偏移量配置 — 唯一数据源

游戏版本更新时只需修改此文件。
所有内存读取模块统一导入：

    from src.config.offsets import OFFSETS

每个偏移量的物理含义见 docs/offsets_guide.md

最后更新：2026-06-22 (P2.3)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GameOffsets:
    """所有游戏内存偏移量集中定义。

    游戏版本更新后修改这些值即可，无需改动业务逻辑代码。
    """

    # ── 基址（模块内偏移量）──
    PLAYER_BASE: int = 0x050139A0
    MONSTER_BASE: int = 0x051238C8
    ZONE_BASE: int = 0x0500ECA0

    # ── 怪物实例链 (用于遍历怪物槽位) ──
    MONSTER_LIST_FIRST: int = 0x698
    MONSTER_LIST_STRIDE: int = 0x8
    MONSTER_LIST_NEXT: int = 0x138
    MONSTER_LIST_TERMINAL: int = 0

    # ── 怪物属性 ──
    MONSTER_HP_BASE: int = 0x7670       # HP 指针基址
    HP_MAX: int = 0x60                   # 最大 HP 偏移
    HP_CURRENT: int = 0x64               # 当前 HP 偏移
    MONSTER_COORDS: int = 0x160          # 坐标 (float×3)
    MONSTER_QUAT: int = 0x170            # 四元数旋转 (float×4)
    MONSTER_ACTION_ID: int = 0x6278      # 当前动作 ID (int32)

    # ── 发怒结构体 ──
    ENRAGE_STRUCT: int = 0x1BE30         # 发怒结构体基址
    ENRAGE_TIMER: int = 0x24             # 发怒计时器偏移
    ENRAGE_MAX: int = 0x28               # 发怒计时器上限偏移

    # ── 玩家链 (用于读取玩家坐标) ──
    PLAYER_CHAIN_1: int = 0x50
    PLAYER_CHAIN_2: int = 0xC0
    PLAYER_COORDS: int = 0x670           # 玩家坐标 (float×3)

    # ── 区域 ──
    ZONE_OFFSET: int = 0xAED0            # 区域 ID 偏移
    ZONE_FATALIS: int = 417              # 虚黑城 (Fatalis arena)

    # ── 战斗参数 ──
    MONSTER_MAX_SLOTS: int = 10          # 最大怪物槽位数
    MONSTER_MIN_HP: float = 500.0        # 识别黑龙的最低 HP 阈值


# 模块级单例 — 全局唯一
OFFSETS = GameOffsets()
