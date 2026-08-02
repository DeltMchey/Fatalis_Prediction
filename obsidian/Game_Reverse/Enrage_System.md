---
title: Enrage System
tags:
  - enrage
  - reverse-engineering
  - memory
  - game-mechanics
created: 2026-07-26
updated: 2026-07-26
---

# Enrage System

## 概述

BlackDragon 实现了**硬件级发怒检测**——直接读取游戏引擎内部的发怒计时器，替代传统的"软计时器推测法"。

## 两种检测方案对比

| 方案 | 原理 | 精度 | 可靠性 | 实现 |
|------|------|------|--------|------|
| **软计时器法**（旧） | 检测到怒吼动作(4,5,179) → 倒计时 180s | 秒级 | 低（可能漏检/误判） | data_upgrade.py 使用 |
| **硬件级读取**（新） | 读取引擎内部发怒秒表 | 帧级 | 高（绝对准确） | ai_engine.py 使用 |

> [!important] 核心创新
> 硬件级发怒检测是 BlackDragon 相对于传统游戏辅助的重要优势——不需要猜测或推算，直接读取引擎的权威状态。

## 硬件级检测原理

### 结构体位置

```
Monster Instance + 0x1BE30  →  Enrage Structure
    ├── +0x00 ~ +0x20: 未知字段（可能是积蓄值、状态标志等）
    ├── +0x24 (float): 发怒计时器（每秒递减）
    └── +0x28 (float): 发怒最大持续时间（常数，如 150s）
```

### 检测逻辑

```python
enrage_timer = self.pm.read_float(monster + OFFSETS.ENRAGE_STRUCT + OFFSETS.ENRAGE_TIMER)
enrage_max   = self.pm.read_float(monster + OFFSETS.ENRAGE_STRUCT + OFFSETS.ENRAGE_MAX)

# 核心判定：计时器在 (0, max) 区间内 = 正在发怒
shared_state['is_enraged'] = 1 if (0.0 < enrage_timer < enrage_max) else 0
```

**为什么是 `0 < timer < max`？**
- `timer <= 0`: 发怒已结束
- `timer >= max`: 尚未发怒（或处于异常状态）
- `0 < timer < max`: 发怒进行中

## 逆向发现过程

### Step 1: 假设

通过分析老式软计时器方法（怒吼 → 180s），知道存在一个持续 150-180 秒的发怒状态。推测引擎内部有一个倒计时变量。

### Step 2: 探测

使用 `enrage.py` 扫描工具：

```bash
python enrage.py  # 需要游戏运行，并在发怒前后观察
```

### Step 3: 扫描

对 `monster + 0x1BE30` 起 11 个 4 字节偏移（+0x00 ~ +0x28）：
- 发怒前记录所有值
- 用钩爪拍脸触发发怒
- 观察哪个值从 0 瞬间变成了 ~150，然后匀速递减
- **结果**: +0x24 位置的值完全符合发怒计时器特征

### Step 4: 验证

- +0x24: 发怒瞬间从 0 跳到 ~150，每秒递减 ~1
- +0x28: 恒定值（发怒最大时长），不随发怒状态改变
- 发怒结束后 +0x24 归零

## enrage.py — 发怒结构体扫描器

独立诊断工具，不参与主流程：

```python
def scan_enrage_structure():
    # 连接游戏
    pm = pymem.Pymem("MonsterHunterWorld.exe")
    
    while True:
        monster_ptr = find_monster(pm, MONSTER_BASE)
        if monster_ptr:
            enrage_struct_addr = monster_ptr + OFFSETS.ENRAGE_STRUCT
            
            for offset in [0x0, 0x4, 0x8, 0xC, 0x10, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28]:
                val = pm.read_float(enrage_struct_addr + offset)
                print(f"偏移量 +0x{offset:02X} : {val:10.3f}")
        
        time.sleep(0.2)
```

**用途**: 
- 发现新的发怒相关字段
- 验证游戏更新后偏移量是否变化
- 辅助其他逆向分析

## 发怒对游戏的影响

| 维度 | 不发怒 | 发怒 |
|------|--------|------|
| 移动速度 | 正常 | 更快 |
| 攻击频率 | 正常 | 更高 |
| 连段模式 | 常规 | 更激进 |
| 物理抗性 | 正常 | 略高（？） |

## 软计时器法（data_upgrade.py 使用）

对于历史上的旧 CSV（缺少 `is_enraged` 列），通过软计时器回溯：

```python
enrage_end_time = 0.0
for idx, row in df.iterrows():
    action = int(row['action_id'])
    # 怒吼动作检测
    if action in {4, 5, 179}:
        enrage_end_time = current_time + 180.0  # 怒吼后 180 秒为发怒期
    
    is_enraged = 1 if current_time < enrage_end_time else 0
```

**局限性**:
- 不是 100% 准确（可能漏检其他触发方式）
- 180s 为硬编码（实际可能在 150-180s 间）
- 不适用于实时推理（需要帧精度）

## 在 AI 模型中的作用

`is_enraged` 是 6 维特征之一：
- 发怒 vs 不发怒的招式分布可能有差异
- 特征重要性预期较低（相对于 phase/posture/previous_action）
- 但在某些边界情况下提供区分能力

## 相关文件

- [[Game_Reverse/Offset_System#4-发怒结构体-3-个|Offset System — 发怒结构体字段]]
- [[Game_Reverse/Memory_Reading#step-4-读取怪物数据|Memory Reading — 发怒读取流程]]
- [[AI_Model/Feature_Engineering#6-is_enraged-发怒状态|Feature Engineering — is_enraged 特征]]
