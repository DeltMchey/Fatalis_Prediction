---
title: Memory Reading
tags:
  - reverse-engineering
  - pymem
  - memory
  - game-hacking
created: 2026-07-26
updated: 2026-07-26
---

# Memory Reading

## 概述

BlackDragon 通过 Windows 进程内存读取（而非屏幕截图）获取游戏实时状态。这是实现实时 AI 预测的基础。

## 技术选择

### 为什么选择 pymem

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| pymem | Python 原生、封装好、支持多级指针 | Windows-only | ✅ 采用 |
| ReadProcessMemory (ctypes) | 无依赖、完全控制 | 需手动封装 Win32 API | 备选 |
| 屏幕截图 + CV | 不依赖内存结构、游戏更新不受影响 | 延迟高、精度低、计算开销大 | 不适用 |

## 核心函数

### get_ptr() — 多级指针解引用

```python
def get_ptr(pm, base, offsets):
    """沿多级指针链解引用，返回最终地址"""
    addr = pm.read_longlong(base)
    for o in offsets[:-1]:
        addr = pm.read_longlong(addr + o)
    return addr + offsets[-1]
```

**使用示例**:
```python
# 怪物实例: Monster Base → +0x698 → [i*8] → +0x138 → [0]
ptr = get_ptr(pm, base, [0x698, i*0x8, 0x138, 0])

# 玩家坐标: Player Base → +0x50 → +0xC0 → +0x670
player = get_ptr(pm, base, [0x50, 0xC0, 0x670])
```

### find_monster() — 怪物实例查找

```python
def find_monster(pm, base):
    for i in range(OFFSETS.MONSTER_MAX_SLOTS):  # 10
        ptr = get_ptr(pm, base, [
            OFFSETS.MONSTER_LIST_FIRST,         # 0x698
            i * OFFSETS.MONSTER_LIST_STRIDE,    # i*8
            OFFSETS.MONSTER_LIST_NEXT,          # 0x138
            OFFSETS.MONSTER_LIST_TERMINAL,      # 0
        ])
        if ptr:
            hp = pm.read_longlong(ptr + OFFSETS.MONSTER_HP_BASE)
            if pm.read_float(hp + OFFSETS.HP_MAX) > OFFSETS.MONSTER_MIN_HP:
                return ptr  # 找到黑龙
    return 0  # 没找到
```

**关键逻辑**:
- MHW 最多同时存在 10 只大型怪物
- 通过 HP > 500 的阈值识别黑龙（其他怪物 HP 较低）
- 找到即返回，不继续遍历

## 读取流程

### Step 1: 连接游戏进程

```python
pm = pymem.Pymem("MonsterHunterWorld.exe")
base = pymem.process.module_from_name(
    pm.process_handle, "MonsterHunterWorld.exe"
).lpBaseOfDll
```

### Step 2: 计算三大基址

```python
PLAYER_BASE  = base + 0x050139A0  # 玩家数据起点
MONSTER_BASE = base + 0x051238C8  # 怪物列表起点
ZONE_BASE    = base + 0x0500ECA0  # 区域数据起点
```

### Step 3: 区域检测（门禁）

```python
zone_addr = get_ptr(pm, ZONE_BASE, [0xAED0])
zone_id = pm.read_int(zone_addr)  # 417 = 虚黑城
if zone_id != 417:
    return  # 不在黑龙任务中，休眠
```

### Step 4: 读取怪物数据

每 0.1s（录制线程）和每帧（UI 线程）读取：

```python
# 坐标（float×3, 共 12 字节）
m_coords = [pm.read_float(monster + 0x160 + i*4) for i in range(3)]

# 四元数旋转（float×4, 共 16 字节）
m_quat = [pm.read_float(monster + 0x170 + i*4) for i in range(4)]

# HP（两级指针）
hp_ptr = pm.read_longlong(monster + 0x7670)
hp_current = pm.read_float(hp_ptr + 0x64)
hp_max = pm.read_float(hp_ptr + 0x60)
hp_percent = hp_current / hp_max

# 动作 ID（int32）
action_id = pm.read_int(monster + 0x6278)

# 发怒状态（结构体内两个 float）
enrage_timer = pm.read_float(monster + 0x1BE30 + 0x24)
enrage_max   = pm.read_float(monster + 0x1BE30 + 0x28)
is_enraged   = 1 if (0 < enrage_timer < enrage_max) else 0
```

### Step 5: 读取玩家坐标

```python
player = get_ptr(pm, PLAYER_BASE, [0x50, 0xC0, 0x670])
p_coords = [pm.read_float(player + i*4) for i in range(3)]
```

## 数据解析

### 四元数 → Yaw 角

```python
monster_yaw = math.degrees(math.atan2(
    2.0 * (quat[1] * quat[3] + quat[0] * quat[2]),
    1.0 - 2.0 * (quat[0]**2 + quat[1]**2)
))
```

游戏使用 **四元数 (w, x, y, z)** 表示怪物旋转（Y 轴 up），需要提取 Yaw 角计算相对朝向。

### 浮点数格式

所有坐标、HP、角度均使用 IEEE 754 单精度浮点数（`read_float`）。

## 逆向工具

### enrage.py

独立诊断工具，实时扫描并显示发怒结构体周围的 float 值：

```bash
python enrage.py  # 需要游戏运行中
```

扫描范围: `+0x1BE30` 起 11 个 4 字节偏移 (`+0x00` ~ `+0x28`)  
刷新率: 每 0.2s  
用途: 观察发怒瞬间数值变化，定位计时器字段

## 健壮性设计

| 场景     | 处理方式                               |
| ------ | ---------------------------------- |
| 游戏未运行  | `pymem.Pymem()` 抛异常 → 打印 "未找到游戏进程" |
| 指针链断裂  | `get_ptr()` 返回 0                   |
| 不在虚黑城  | zone != 417 → UI 休眠、状态清零           |
| 怪物未找到  | `find_monster()` 返回 0 → 跳过本次循环     |
| 内存读取失败 | `except Exception` + logger 记录     |

## 平台限制

> [!warning] Windows Only
> pymem 依赖 Windows 进程 API（`OpenProcess`, `ReadProcessMemory`），不支持 Linux/macOS。

## 游戏版本锁定

| 版本组件 | 状态 |
|----------|------|
| 基址（3 个） | 游戏更新后可能变化 |
| 内部偏移量（20 个） | 小更新通常不变 |
| 动作 ID 映射 | 大更新可能变化 |

参见 [[Game_Reverse/Offset_System|Offset System]] 和 [[../docs/legacy/offsets_guide|Offsets Guide]]。
