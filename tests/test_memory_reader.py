"""P4 Step 2: MemoryReader tests — mock pymem 内存读取测试。

策略：
  - 使用 unittest.mock.MagicMock 模拟 pymem.Pymem 接口
  - 对 follow_pointer_chain 通过实例级 patch 控制返回值（分离链遍历与单点读取测试）
  - 对 read_float / read_longlong / read_int 通过 MagicMock 直接控制
  - 使用固定 base 地址 0x140000000（模拟 MonsterHunterWorld.exe 基址）

覆盖：
  - follow_pointer_chain: 单级/多级/空链/异常
  - check_zone: 正常/空地址/异常
  - find_monster: 首槽成功/后续槽成功/HP过低/全部空/HP读异常
  - read_player_coords: 正常/异常/空链
  - read_monster_coords: 正常/异常
  - read_monster_quat: 正常/异常
  - read_monster_hp: 正常/零分母/异常
  - read_monster_action: 正常/异常
  - read_enrage_state: 正常/异常
"""

from unittest.mock import MagicMock

import pytest

from src.core.memory_reader import MemoryReader

# 固定 base 地址
FAKE_BASE = 0x140000000

# 模拟玩家地址
FAKE_PLAYER_ADDR = 0x20000000

# 模拟怪物地址
FAKE_MONSTER_ADDR = 0x30000000


# =============================================================================
# Fixture
# =============================================================================

@pytest.fixture
def mock_pm():
    """返回模拟 pymem 实例（只暴露 MemoryReader 使用的方法）。"""
    pm = MagicMock(spec=["read_longlong", "read_float", "read_int"])
    return pm


# =============================================================================
# 1. follow_pointer_chain
# =============================================================================

class TestFollowPointerChain:
    def test_single_offset_no_intermediate_jumps(self, mock_pm):
        """单级 offset → 直接读基址 + 最后 offset（不对 offset 做中间跳转）。"""
        mock_pm.read_longlong.return_value = 0x1000
        reader = MemoryReader(mock_pm, FAKE_BASE)

        result = reader.follow_pointer_chain(FAKE_BASE, [0x10])
        mock_pm.read_longlong.assert_called_once_with(FAKE_BASE)
        assert result == 0x1010  # 0x1000 + 0x10

    def test_multi_level_chain(self, mock_pm):
        """多级 offset → 每级中间 offset 做一次 read_longlong，最后直接加。

        调用次数 = len(offsets)：1 次初始基址读取 + (len-1) 次中间跳转。
        """
        mock_pm.read_longlong.side_effect = [0x2000, 0x3000, 0x4000]
        reader = MemoryReader(mock_pm, FAKE_BASE)

        # offsets = [0xA, 0xB, 0xC] → 3 次调用
        result = reader.follow_pointer_chain(FAKE_BASE, [0xA, 0xB, 0xC])
        assert mock_pm.read_longlong.call_count == 3
        # 第 1 次：read_longlong(FAKE_BASE) → 0x2000
        # 第 2 次：read_longlong(0x2000 + 0xA) → 0x3000
        # 第 3 次：read_longlong(0x3000 + 0xB) → 0x4000
        # 最终：0x4000 + 0xC
        assert result == 0x400C

    def test_exception_returns_zero(self, mock_pm):
        """任意 read_longlong 抛异常 → 返回 0。"""
        mock_pm.read_longlong.side_effect = OSError("memory read error")
        reader = MemoryReader(mock_pm, FAKE_BASE)

        result = reader.follow_pointer_chain(FAKE_BASE, [0x10, 0x20])
        assert result == 0

    def test_zero_base_returns_zero_plus_last_offset(self, mock_pm):
        """read_longlong 返回 0 → 最终地址 = 0 + last_offset。"""
        mock_pm.read_longlong.return_value = 0
        reader = MemoryReader(mock_pm, FAKE_BASE)

        result = reader.follow_pointer_chain(FAKE_BASE, [0x10, 0x8, 0x4])
        assert result == 0x4  # 0 + 0x4


# =============================================================================
# 2. check_zone
# =============================================================================

class TestCheckZone:
    def test_valid_zone_id(self, mock_pm):
        """正常读取区域 ID。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        reader.follow_pointer_chain = MagicMock(return_value=0x5000)
        mock_pm.read_int.return_value = 417

        result = reader.check_zone()
        assert result == 417

    def test_null_address_returns_none(self, mock_pm):
        """指针链返回 0 → None。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        reader.follow_pointer_chain = MagicMock(return_value=0)

        result = reader.check_zone()
        assert result is None

    def test_read_exception_returns_none(self, mock_pm):
        """read_int 异常 → None。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        reader.follow_pointer_chain = MagicMock(return_value=0x5000)
        mock_pm.read_int.side_effect = RuntimeError("fail")

        result = reader.check_zone()
        assert result is None


# =============================================================================
# 3. find_monster
# =============================================================================

class TestFindMonster:
    def test_first_slot_found(self, mock_pm):
        """第一个槽位就找到有效怪物。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        # slot 0 返回有效地址
        reader.follow_pointer_chain = MagicMock(return_value=FAKE_MONSTER_ADDR)
        mock_pm.read_longlong.return_value = 0x4000
        mock_pm.read_float.return_value = 800.0  # > 500

        result = reader.find_monster()
        assert result == FAKE_MONSTER_ADDR
        # 只调用一次（第一个槽就匹配）
        assert reader.follow_pointer_chain.call_count == 1

    def test_found_in_later_slot(self, mock_pm):
        """前两个槽位无效，第三个槽位找到。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        # slots 0-1: 返回 0（无实体）；slot 2: 返回怪物地址
        reader.follow_pointer_chain = MagicMock()
        reader.follow_pointer_chain.side_effect = [0, 0, FAKE_MONSTER_ADDR]
        mock_pm.read_longlong.return_value = 0x4000
        mock_pm.read_float.return_value = 800.0

        result = reader.find_monster()
        assert result == FAKE_MONSTER_ADDR
        assert reader.follow_pointer_chain.call_count == 3

    def test_hp_too_low_skipped(self, mock_pm):
        """HP ≤ 500 → 跳过该槽位。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        reader.follow_pointer_chain = MagicMock(return_value=FAKE_MONSTER_ADDR)
        mock_pm.read_longlong.return_value = 0x4000
        mock_pm.read_float.return_value = 30.0  # < 500

        result = reader.find_monster()
        assert result is None

    def test_all_slots_empty_returns_none(self, mock_pm):
        """10 个槽位全部返回 0 → None。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        reader.follow_pointer_chain = MagicMock(return_value=0)

        result = reader.find_monster()
        assert result is None
        assert reader.follow_pointer_chain.call_count == 10

    def test_hp_read_exception_skips_slot(self, mock_pm):
        """HP 读取异常 → 该槽位被跳过，继续下一个。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        # slot 0: 有效 ptr 但 HP 读失败；slot 1: 有效 ptr + 有效 HP
        reader.follow_pointer_chain = MagicMock()
        reader.follow_pointer_chain.side_effect = [FAKE_MONSTER_ADDR + 1, FAKE_MONSTER_ADDR + 2]
        mock_pm.read_longlong.side_effect = [
            OSError("fail"),   # slot 0 HP 读失败
            0x4000,             # slot 1 HP 正常
        ]
        mock_pm.read_float.return_value = 800.0

        result = reader.find_monster()
        assert result == FAKE_MONSTER_ADDR + 2


# =============================================================================
# 4. read_player_coords
# =============================================================================

class TestReadPlayerCoords:
    def test_valid_coords(self, mock_pm):
        """正常读取玩家三维坐标。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        reader.follow_pointer_chain = MagicMock(return_value=FAKE_PLAYER_ADDR)
        mock_pm.read_float.side_effect = [1.0, 2.0, 3.0]

        result = reader.read_player_coords()
        assert result == [1.0, 2.0, 3.0]

    def test_null_chain_returns_none(self, mock_pm):
        """指针链返回 0 → None。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        reader.follow_pointer_chain = MagicMock(return_value=0)

        result = reader.read_player_coords()
        assert result is None

    def test_coord_read_exception_returns_none(self, mock_pm):
        """坐标读取异常 → None。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        reader.follow_pointer_chain = MagicMock(return_value=FAKE_PLAYER_ADDR)
        mock_pm.read_float.side_effect = RuntimeError("fail")

        result = reader.read_player_coords()
        assert result is None


# =============================================================================
# 5. read_monster_coords
# =============================================================================

class TestReadMonsterCoords:
    def test_valid_coords(self, mock_pm):
        """正常读取怪物三维坐标。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        mock_pm.read_float.side_effect = [10.0, 20.0, 30.0]

        result = reader.read_monster_coords(FAKE_MONSTER_ADDR)
        assert result == [10.0, 20.0, 30.0]

    def test_exception_returns_none(self, mock_pm):
        mock_pm.read_float.side_effect = OSError("fail")
        reader = MemoryReader(mock_pm, FAKE_BASE)

        result = reader.read_monster_coords(FAKE_MONSTER_ADDR)
        assert result is None


# =============================================================================
# 6. read_monster_quat
# =============================================================================

class TestReadMonsterQuat:
    def test_valid_quat(self, mock_pm):
        """正常读取怪物四元数（4 个 float）。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        mock_pm.read_float.side_effect = [0.0, 1.0, 0.0, 0.0]

        result = reader.read_monster_quat(FAKE_MONSTER_ADDR)
        assert result == [0.0, 1.0, 0.0, 0.0]

    def test_exception_returns_none(self, mock_pm):
        mock_pm.read_float.side_effect = OSError("fail")
        reader = MemoryReader(mock_pm, FAKE_BASE)

        result = reader.read_monster_quat(FAKE_MONSTER_ADDR)
        assert result is None


# =============================================================================
# 7. read_monster_hp
# =============================================================================

class TestReadMonsterHP:
    def test_valid_hp(self, mock_pm):
        """正常读取 HP 百分比（current / max）。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        mock_pm.read_longlong.return_value = 0x5000
        mock_pm.read_float.side_effect = [500.0, 1000.0]  # current=500, max=1000

        result = reader.read_monster_hp(FAKE_MONSTER_ADDR)
        assert result == pytest.approx(0.5)

    def test_max_hp_zero_returns_zero(self, mock_pm):
        """HP_MAX 为 0 → 安全返回 0.0（避免除零错误）。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        mock_pm.read_longlong.return_value = 0x5000
        mock_pm.read_float.side_effect = [500.0, 0.0]  # max=0

        result = reader.read_monster_hp(FAKE_MONSTER_ADDR)
        assert result == 0.0

    def test_exception_returns_none(self, mock_pm):
        """读取异常 → None。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        mock_pm.read_longlong.side_effect = OSError("fail")

        result = reader.read_monster_hp(FAKE_MONSTER_ADDR)
        assert result is None


# =============================================================================
# 8. read_monster_action
# =============================================================================

class TestReadMonsterAction:
    def test_valid_action(self, mock_pm):
        """正常读取怪物动作 ID。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        mock_pm.read_int.return_value = 37

        result = reader.read_monster_action(FAKE_MONSTER_ADDR)
        assert result == 37

    def test_exception_returns_none(self, mock_pm):
        mock_pm.read_int.side_effect = OSError("fail")
        reader = MemoryReader(mock_pm, FAKE_BASE)

        result = reader.read_monster_action(FAKE_MONSTER_ADDR)
        assert result is None


# =============================================================================
# 9. read_enrage_state
# =============================================================================

class TestReadEnrageState:
    def test_valid_state(self, mock_pm):
        """正常读取发怒秒表。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        mock_pm.read_float.side_effect = [5.0, 180.0]  # timer=5, max=180

        timer, max_val = reader.read_enrage_state(FAKE_MONSTER_ADDR)
        assert timer == 5.0
        assert max_val == 180.0

    def test_exception_returns_zeros(self, mock_pm):
        """读取异常 → (0.0, 0.0)。"""
        reader = MemoryReader(mock_pm, FAKE_BASE)
        mock_pm.read_float.side_effect = OSError("fail")

        timer, max_val = reader.read_enrage_state(FAKE_MONSTER_ADDR)
        assert timer == 0.0
        assert max_val == 0.0


# =============================================================================
# 10. 初始化
# =============================================================================

class TestInitialization:
    def test_constructor_stores_base_addresses(self, mock_pm):
        """构造函数计算并保存 PLAYER/MONSTER/ZONE 绝对地址。"""
        from src.config.offsets import OFFSETS
        reader = MemoryReader(mock_pm, FAKE_BASE)

        assert reader._player_base == FAKE_BASE + OFFSETS.PLAYER_BASE
        assert reader._monster_base == FAKE_BASE + OFFSETS.MONSTER_BASE
        assert reader._zone_base == FAKE_BASE + OFFSETS.ZONE_BASE
