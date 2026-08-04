---
title: Offset System
tags:
  - offset
  - memory
  - configuration
  - GameOffsets
created: 2026-07-26
updated: 2026-07-26
---

# Offset System

## 概述

所有游戏内存偏移量集中在 `src/config/offsets.py`，使用不可变的 `GameOffsets` 数据类定义。游戏版本更新时**只需修改此文件**——业务代码无需改动。

## GameOffsets 完整字段

```python
@dataclass(frozen=True)
class GameOffsets:
    """所有游戏内存偏移量集中定义。frozen=True 保证不可变性。"""
    
    # ═══ 基址（模块内偏移量）═══
    PLAYER_BASE: int  = 0x050139A0   # 玩家数据链起点
    MONSTER_BASE: int = 0x051238C8   # 怪物实体列表起点
    ZONE_BASE: int    = 0x0500ECA0   # 区域数据起点

    # ═══ 怪物实例链（遍历怪物槽位）═══
    MONSTER_LIST_FIRST: int    = 0x698   # 第一个偏移量
    MONSTER_LIST_STRIDE: int   = 0x8     # 槽位间距（字节）
    MONSTER_LIST_NEXT: int     = 0x138   # 下一级指针偏移
    MONSTER_LIST_TERMINAL: int = 0       # 终端偏移（零 = 停止）

    # ═══ 怪物属性 ═══
    MONSTER_HP_BASE: int   = 0x7670  # HP 指针基址
    HP_MAX: int            = 0x60    # 最大 HP 偏移（从 HP 指针）
    HP_CURRENT: int        = 0x64    # 当前 HP 偏移（从 HP 指针）
    MONSTER_COORDS: int    = 0x160   # 怪物坐标（float×3）
    MONSTER_QUAT: int      = 0x170   # 四元数旋转（float×4, wxyz）
    MONSTER_ACTION_ID: int = 0x6278  # 当前动作 ID（int32）

    # ═══ 发怒结构体 ═══
    ENRAGE_STRUCT: int = 0x1BE30  # 发怒结构体基址
    ENRAGE_TIMER: int  = 0x24    # 发怒计时器偏移（float）
    ENRAGE_MAX: int    = 0x28    # 发怒最大时间偏移（float）

    # ═══ 玩家数据链 ═══
    PLAYER_CHAIN_1: int = 0x50   # 第 1 级跳转
    PLAYER_CHAIN_2: int = 0xC0   # 第 2 级跳转
    PLAYER_COORDS: int  = 0x670  # 玩家坐标（float×3）

    # ═══ 区域检测 ═══
    ZONE_OFFSET: int  = 0xAED0   # 区域 ID 偏移
    ZONE_FATALIS: int = 417      # 虚黑城（Fatalis Arena）

    # ═══ 战斗参数 ═══
    MONSTER_MAX_SLOTS: int = 10     # 最大怪物槽位数
    MONSTER_MIN_HP: float  = 500.0  # 识别黑龙的最低 HP 阈值
```

## 字段分类

### 1. 基址（3 个）

| 字段 | 值 | 物理意义 |
|------|-----|----------|
| `PLAYER_BASE` | 0x050139A0 | 指向玩家数据结构的指针 |
| `MONSTER_BASE` | 0x051238C8 | 指向怪物实体数组的指针 |
| `ZONE_BASE` | 0x0500ECA0 | 指向区域/地图数据的指针 |

> [!warning] 游戏更新首要目标
> 这三个基址在游戏更新后最可能变化。使用 Cheat Engine 扫描已知值反推新基址。

### 2. 怪物实例链（4 个）

遍历怪物实体列表的多级指针链：
```
[MONSTER_BASE] → +MONSTER_LIST_FIRST → [i*STRIDE] → +NEXT → [TERMINAL]
```

| 字段 | 作用 |
|------|------|
| `MONSTER_LIST_FIRST` (0x698) | 指向第一个怪物实体的偏移 |
| `MONSTER_LIST_STRIDE` (0x8) | 每槽位 8 字节（64 位指针） |
| `MONSTER_LIST_NEXT` (0x138) | 槽位指针指向的实体偏移 |
| `MONSTER_LIST_TERMINAL` (0) | 解引用链终点 |

### 3. 怪物属性（6 个）

| 字段 | 类型 | 说明 |
|------|------|------|
| `MONSTER_HP_BASE` (0x7670) | ptr→struct | HP 结构的指针 |
| `HP_MAX` (0x60) | float | 从 HP 指针偏移 |
| `HP_CURRENT` (0x64) | float | 从 HP 指针偏移 |
| `MONSTER_COORDS` (0x160) | float×3 | 世界坐标 XYZ |
| `MONSTER_QUAT` (0x170) | float×4 | 旋转四元数 WXYZ |
| `MONSTER_ACTION_ID` (0x6278) | int32 | 动画帧 ID |

### 4. 发怒结构体（3 个）

通过 `enrage.py` 逆向发现：

| 字段 | 说明 |
|------|------|
| `ENRAGE_STRUCT` (0x1BE30) | 发怒数据基址 |
| `ENRAGE_TIMER` (0x24) | 当前发怒倒计时（float，每秒递减） |
| `ENRAGE_MAX` (0x28) | 发怒持续总时间（float，常数） |

**判定逻辑**: `0 < TIMER < MAX` → 处于发怒状态

### 5. 玩家数据链（3 个）

三级指针链获取玩家坐标：
```
[PLAYER_BASE] → +0x50 → [Ptr1] → +0xC0 → [Ptr2] → +0x670 → XYZ
```

### 6. 区域检测（2 个）

| 字段 | 值 | 说明 |
|------|-----|------|
| `ZONE_OFFSET` (0xAED0) | 偏移 | 指向区域 ID |
| `ZONE_FATALIS` (417) | 常量 | 虚黑城的区域编号 |

### 7. 战斗参数（2 个）

| 字段 | 值 | 说明 |
|------|-----|------|
| `MONSTER_MAX_SLOTS` (10) | 最大槽位 | 游戏最多同时存在 10 只大型怪物 |
| `MONSTER_MIN_HP` (500.0) | HP 阈值 | 用于识别黑龙（HP 最高的怪物） |

## 使用方式

```python
from src.config.offsets import OFFSETS

# 单例对象，所有模块统一引用
player_base = base + OFFSETS.PLAYER_BASE
hp_ptr = pm.read_longlong(monster + OFFSETS.MONSTER_HP_BASE)
```

### 优势

| 之前（散落硬编码） | 之后（集中配置） |
|-------------------|------------------|
| 3 个文件中散落魔法数字 | 1 个文件中定义 |
| 游戏更新 → 手动搜索 3 个文件 | 游戏更新 → 只改 offsets.py |
| 可能遗漏修改 | 编译器/IDE 检查引用 |
| 无法测试 | `test_offsets.py` 14 个测试 |

## 测试覆盖

`tests/test_offsets.py` — 14 个测试，覆盖率 100%：
- 所有字段存在且类型正确
- 字段值非空/非零
- dataclass 不可变性（`frozen=True`）
- 模块级单例 `OFFSETS` 正确创建

## 修改指南

游戏版本更新后需要修改偏移量时，参见 [[../docs/legacy/offsets_guide|Offsets Guide]]：
1. 用 Cheat Engine 定位新基址
2. 更新 `offsets.py` 中的对应值
3. 运行 `test_offsets.py` 验证
4. 游戏内测试 `ai_engine.py`
