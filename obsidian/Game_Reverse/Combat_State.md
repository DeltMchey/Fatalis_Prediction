---
title: Combat State
tags:
  - reverse-engineering
  - combat
  - action
  - posture
  - enrage
  - nova
created: 2026-08-04
updated: 2026-08-04
---

# Combat State — BlackDragon v1.0

> 战斗状态全景（合并旧 Action_System + Enrage_System 的概览版）。动作数据库权威源：`src/config/actions.py`。发怒逆向细节见原 [[Game_Reverse/Enrage_System|Enrage System]]。

## 1. 战斗状态全景

BlackDragon 追踪 5 类战斗状态，用于特征构造 + 物理规则过滤：

| 状态 | 取值 | 来源 | 用途 |
|------|------|------|------|
| 动作 (action) | 144 个 ID | `ACTION_DB` + `ACTION_MAPPING` | previous_action 特征 |
| 姿态 (posture) | 0-4 | Posture FSM（动作触发） | Posture Filter |
| 阶段 (phase) | 1/2/3 | HP% 推导 | Phase Filter |
| 发怒 (enrage) | 0/1 | 硬件级读取引擎秒表 | is_enraged 特征 |
| Nova (warning) | bool | HP 阈值 FSM | UI 红色预警 |

## 2. 动作系统

### ACTION_DB（144 条）

将游戏内存数字 ID → 中文招式名：

```python
ACTION_DB: dict[int, str] = {
    306: "等待", 309: "开场吼", 4: "怒吼", 30: "趴下", ...
}
```

### ACTION_MAPPING（54 条合并映射）

动画**帧** ID → 起手式 **Base** ID。防止模型学到"假转移"（龙车帧1→帧2→帧3）：

```
38, 39, 40 → 37  (龙车·立)
54, 55, 56, 57 → 53  (连咬·立)
50, 51, 52 → 49  (龙车·趴)
69, 70, 71, 72 → 68  (连咬·趴)
209-216 → 208  (捕食)
```

## 3. 姿态状态机（5 态 FSM）

| 值 | 状态 | 触发招式集合 |
|----|------|-------------|
| 0 | 趴下 (Prone) | `POSTURE_PRONE`（如 49,50,51,52, 138...） |
| 1 | 站立 (Standing) | `POSTURE_STAND`（如 115,116,121,122, 197...） |
| 2 | 飞行 (Flying) | `POSTURE_FLY`（如 107,108, 167, 179） |
| 3 | 倒地 (Downed) | `DOWN_IDS`（如 75,221,232,236, 241...） |
| 4 | 演出 (Scripted) | `SCRIPTED_IDS`（157-197 转阶段动画） |

**实现**：`CombatStateTracker.update_posture(action)` 维护 FSM 游标。

## 4. 阶段系统

```
HP > 78%   → P1（基础招式）
50-78%     → P2（蓄力火、飞天俯冲、孕吐、吐痰）
HP < 50%   → P3（360 扫火、左右火、捕食、三连蓄力火）
```

**阶段专属招式集合**：

| 集合 | 含义 | 过滤规则 |
|------|------|----------|
| `P1_ONLY_IDS` | P1 专属（龙车·立、连咬·立...） | Phase > 1 时概率归零 |
| `P2_PLUS_IDS` | P2+ 解锁（蓄力火、趴下招式...） | Phase < 2 时概率归零 |
| `P3_ONLY_IDS` | P3 专属（捕食、360 扫火...） | Phase < 3 时概率归零 |

**实现**：`CombatStateTracker.update_phase(hp_percent)` + `ActionPredictor.filter_probs_by_phase()`。

## 5. 发怒系统（硬件级检测）

**原理**：直接读取游戏引擎内部发怒秒表（替代软计时器推测）：

```python
enrage_timer = read_float(monster + 0x1BE30 + 0x24)
enrage_max   = read_float(monster + 0x1BE30 + 0x28)
is_enraged   = 1 if (0 < enrage_timer < enrage_max) else 0
```

**为何 `0 < timer < max`**：`timer <= 0` 发怒结束；`timer >= max` 未发怒；中间 = 进行中。

**逆向发现**：`enrage.py` 扫描器对 +0x1BE30 起 11 个 float 偏移，钩爪拍脸触发发怒 → 观察 +0x24 从 0 跳 ~150 后匀速递减。

**旧数据回填**：`data_upgrade.py` 对历史 CSV 用软计时器（怒吼动作 4,5,179 → +180s 窗口）。

**实现**：`CombatStateTracker.update_enrage(timer, max)`。

## 6. Nova 预警系统（飞天火）

**阈值**（`NOVA_THRESHOLDS`）：

| 阈值 | HP% | 含义 |
|------|-----|------|
| 0.78 | ≤78% | P1→P2 转阶段 |
| 0.50 | ≤50% | P2→P3 转阶段 |
| 0.41 | ≤41% | P3 第一次 Nova |
| 0.26 | ≤26% | P3 第二次 Nova |
| 0.06 | ≤6% | P3 第三次 Nova（最终） |

**重置动作**：197, 167, 179（演出动作）清除 warning。

**实现**：`CombatStateTracker.update_nova(hp_percent, action)` → `nova_warning` → OverlayUI 显示红色预警。

## 7. 特殊招式分类

| 集合 | 用途 |
|------|------|
| `DOWN_IDS` | 倒地姿态触发（训练时作为 label 排除） |
| `SCRIPTED_IDS` (157-197) | 演出姿态 + 训练排除 |
| `MINOR_AND_PASSIVE` | 小动作/被动（等待/怒吼/索敌——不作为 label） |

## 8. 实现映射

| 状态 | 模块 | 方法 |
|------|------|------|
| 动作合并 | src/core/state_tracker.py | `map_action()` |
| 姿态 FSM | src/core/state_tracker.py | `update_posture()` |
| 阶段 | src/core/state_tracker.py | `update_phase()` |
| 发怒 | src/core/state_tracker.py | `update_enrage()` |
| Nova | src/core/state_tracker.py | `update_nova()` |
| Phase/Posture 过滤 | src/model/predictor.py | `filter_probs_by_phase()` / `filter_probs_by_posture()` |
| 数据源 | src/config/actions.py | 全部集合常量 |
