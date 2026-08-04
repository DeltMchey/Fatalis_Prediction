---
title: Memory Architecture
tags:
  - reverse-engineering
  - memory
  - pymem
  - offset
created: 2026-08-04
updated: 2026-08-04
---

# Memory Architecture — BlackDragon v1.0

> 内存读取架构（合并旧 Memory_Reading 方法学 + 旧 Architecture/Memory_Architecture 偏移布局）。偏移量权威源：`src/config/offsets.py`（`GameOffsets` dataclass）。

## 1. 技术选型

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| pymem | Python 原生、支持多级指针 | Windows-only | ✅ 采用 |
| ReadProcessMemory (ctypes) | 无依赖 | 手动封装 Win32 API | 备选 |
| 屏幕截图 + CV | 不依赖内存结构 | 延迟高、精度低 | 不适用 |

## 2. 三大基址

```
Player Base:  0x050139A0  (module-relative)
Monster Base: 0x051238C8
Zone Base:    0x0500ECA0
```

> [!warning] 版本依赖
> 这三个基址在游戏更新后**最可能变化**。使用 Cheat Engine 定位新值，更新 `src/config/offsets.py` 即可——业务代码无需改动。

## 3. 指针链

### 怪物实例链（遍历 10 槽位）

```
[Monster Base + 0x051238C8]
    → +0x698 → [First MonPtr]
    → +i*0x8 → [Slot i MonPtr]
    → +0x138 → [Next Ptr]
    → [0] → Final Monster Instance

遍历 0 ≤ i < 10，找到 HP > 500 的实例 = 黑龙
```

### 玩家数据链（3 级）

```
[Player Base + 0x050139A0]
    → +0x50 → [Ptr1]
    → +0xC0 → [Ptr2]
    → +0x670 → Player XYZ (float×3)
```

### 区域检测

```
[Zone Base + 0x0500ECA0]
    → +0xAED0 → Zone ID (int32)
    417 = 虚黑城 (Fatalis Arena)
```

## 4. 怪物数据布局

```
Monster Instance (ptr)
    ├── +0x160: Monster XYZ (float×3)
    ├── +0x170: Monster Quaternion (float×4, wxyz)
    ├── +0x6278: Action ID (int32)
    ├── +0x7670: HP Pointer → +0x60 (HP Max, float)
    │                         +0x64 (HP Current, float)
    └── +0x1BE30: Enrage Struct → +0x24 (Timer, float)
                                  +0x28 (Max, float)
```

## 5. 实现：MemoryReader（src/core/memory_reader.py）

所有内存读取的唯一入口（P4.2 提取）：

| 方法 | 说明 |
|------|------|
| `follow_pointer_chain(address, offsets)` | 多级指针解引用 |
| `check_zone()` | 区域 ID（**不含** 417 判断——业务逻辑在调用方） |
| `find_monster()` | 遍历 10 槽位，HP > 500 |
| `read_player_coords()` | 玩家 XYZ |
| `read_monster_coords(ptr)` | 怪物 XYZ |
| `read_monster_quat(ptr)` | 怪物四元数 |
| `read_monster_hp(ptr)` | HP 百分比 |
| `read_monster_action(ptr)` | 动作 ID |
| `read_enrage_state(ptr)` | (timer, max) |

**设计约束**：无业务逻辑，返回原始数据；失败返回 `None`/`(0.0, 0.0)`（与原 fallback 行为一致）；无状态 → 线程安全。

## 6. 健壮性设计

| 场景 | 处理 |
|------|------|
| 游戏未运行 | `pymem.Pymem()` 抛异常 → 重试循环（Overlay）或静默轮询（GameService） |
| 指针链断裂 | 返回 None |
| 不在虚黑城 | zone != 417 → 状态重置 + 休眠 |
| 怪物未找到 | `find_monster()` → None → 跳过本帧 |
| 内存读取失败 | `except Exception` + logger |

## 7. 参考

- 偏移量详解：[[Game_Reverse/Offset_System|Offset System]]
- 修改指南：`docs/legacy/offsets_guide.md`（历史）→ 未来迁移到本目录
- 发怒逆向：[[Game_Reverse/Combat_State|Combat State]]
