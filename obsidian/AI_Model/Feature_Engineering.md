---
title: Feature Engineering
tags:
  - features
  - design
  - XGBoost
  - LightGBM
  - phase
  - posture
created: 2026-07-26
updated: 2026-09-16
---

# Feature Engineering

## 概述

BlackDragon 的 AI 模型外部输入为 **6 维用户指定特征**（v1.2.0 起，由 Pipeline 内的 `FeatureBuilder`（`src/model/features.py`）确定性扩展为 **12 列**：6 个用户指定 + 6 个派生），涵盖空间关系、怪物状态和历史上下文三个维度。派生特征贡献 50.71% 的分裂增益（gain 口径），是 v1.2.0 模型效果提升的直接来源之一。

## 特征矩阵

### 用户指定特征（6，外部输入 / 推理接口）

| # | 特征名 | 类型 | 物理含义 | 来源 |
|---|--------|------|----------|------|
| 0 | `distance` | float | 玩家与怪物在 XZ 平面的欧几里得距离 | `calc_distance_2d(p_coords, m_coords)` |
| 1 | `relative_angle` | float | 从怪物朝向到玩家位置的相对角度 | `calc_relative_angle(p_coords, m_coords, m_quat)` |
| 2 | `posture` | int(0-4) | 怪物当前姿态 | Posture FSM |
| 3 | `previous_action` | int | 上一招 Base ID（合并后） | ACTION_MAPPING |
| 4 | `phase` | int(1-3) | 当前战斗阶段 | HP% 推导 |
| 5 | `is_enraged` | int(0-1) | 是否处于发怒状态 | 硬件级读取 |

### 派生特征（6，FeatureBuilder 在 Pipeline 内生成）

| # | 特征名 | 构造方式 | 设计意图 |
|---|--------|----------|----------|
| 6 | `distance_bin` | 距离等频分箱 | 离散化距离档位，浅树（depth 4）更易利用（gain 第一名 14.68%，反超原始 distance 2.2 倍） |
| 7 | `posture_x_phase` | 姿态×阶段交互码 | 编码"同一姿态在不同阶段动作集不同"的领域规则 |
| 8 | `prev_action_freq` | 上一动作的全局频率 | 马尔可夫先验（"上一招本身有多常见"） |
| 9 | `distance_x_enraged` | 距离×发怒交互 | 发怒改变距离-动作关系（远距离发怒技） |
| 10 | `angle_sin` | 相对角 sin 编码 | 周期信号三角展开，对树模型更友好 |
| 11 | `angle_cos` | 相对角 cos 编码 | 同上（sin+cos 合计 9.08%，约为原始 angle 的 2.3 倍） |

## 防泄漏设计（FeatureBuilder fit/transform）

`FeatureBuilder` 是 sklearn transformer，遵循 fit/transform 分离：

- **fit 仅在 train_80 上执行**——派生特征依赖的统计量（如 `prev_action_freq` 的频率表、`distance_bin` 的分箱边界）只从训练集学习，不接触 holdout（防泄漏红线，ADR-P6.1 Decision 4）
- **transform 纯确定性**——推理时（`ActionPredictor.predict`）Pipeline 内部自动执行同样的 6 → 12 列扩展，推理方无需感知派生特征
- `src/model/features.py` 随应用分发（pickle 反序列化需要），并显式进 PyInstaller hiddenimports

## 特征详解（用户指定 6 维）

### 1. distance — 玩家-怪物 XZ 距离

```python
def calc_distance_2d(p_coords, m_coords):
    """XZ 平面二维欧几里得距离（忽略 Y 轴高度）"""
    return math.sqrt((p_x - m_x)**2 + (p_z - m_z)**2)
```

**为什么忽略 Y 轴**：怪物飞行高度变化不影响水平距离判断。近距离 (< 200) 时龙车/咬击概率高，远距离 (> 1000) 时火球概率高。

### 2. relative_angle — 相对角度

```python
def calc_relative_angle(p_coords, m_coords, m_quat):
    """怪物朝向 vs 玩家方位的相对角 [-180, 180]"""
    monster_yaw = degrees(atan2(2*(wz+xy), 1-2*(w²+x²)))  # 四元数→yaw
    target_yaw = degrees(atan2(p_x - m_x, p_z - m_z))       # 位置差→方位角
    return (target_yaw - monster_yaw + 180) % 360 - 180    # 归一化
```

**物理意义**: 
- 0° = 玩家在怪物正前方
- ±90° = 玩家在怪物侧面
- ±180° = 玩家在怪物正后方

高 angle (> 120°) 时扫尾/尾砸概率高；低 angle (< 30°) 时正面攻击概率高。v1.2.0 起该周期信号另经 `angle_sin`/`angle_cos` 三角编码进入模型。

### 3. posture — 怪物姿态（5 态 FSM）

| 值 | 状态 | 含义 | 典型招式 |
|----|------|------|----------|
| 0 | 趴下 (Prone) | 四足着地 | 龙车49, 连咬68, 跳投107 |
| 1 | 站立 (Standing) | 双足站立 | 龙车37, 连咬53, 扇形火154 |
| 2 | 飞行 (Flying) | 空中 | 空中三连火球103, 空中S火109 |
| 3 | 倒地 (Downed) | 被击倒 | 器械倒地236, 破头倒地241 |
| 4 | 演出 (Scripted) | 转阶段动画 | 飞天火全套, 1转2, 2转3 |

### 4. previous_action — 上一招 Base ID

通过 `ACTION_MAPPING` 将动画帧 ID 合并为起手式 Base ID：
- 龙车: 38,39,40 → 37
- 连咬: 54,55,56,57 → 53
- 共 54 条映射

**为什么重要**：黑龙的招式有明显的连段模式（如龙车→后撤→前咬），上一招是预测下一招的最强信号之一（v1.2.0 中其派生列 `prev_action_freq` 携带比动作 ID 本身更多的可分裂信息）。

### 5. phase — 战斗阶段

```
HP > 78%  → Phase 1  (P1)  基础招式
50-78%    → Phase 2  (P2)  新增蓄力火、飞天俯冲、孕吐、吐痰
HP < 50%  → Phase 3  (P3)  新增 360 扫火、左右火、捕食、三连蓄力火
```

每个阶段有不同的可用招式集合（`P1_ONLY_IDS`, `P2_PLUS_IDS`, `P3_ONLY_IDS`）。

### 6. is_enraged — 发怒状态

```python
# 硬件级读取引擎内部秒表
enrage_timer = read_float(monster + 0x1BE30 + 0x24)
enrage_max   = read_float(monster + 0x1BE30 + 0x28)
is_enraged   = 1 if (0 < enrage_timer < enrage_max) else 0
```

发怒状态下黑龙速度更快、连段更激进。详见 [[Game_Reverse/Enrage_System|Enrage System]]。

## 特征重要性（v1.2.0 实测，gain 口径）

XGBoost booster `get_score(importance_type='gain')` 归一化，留出集口径（完整解读见 [[docs/AutoML_RunB_Feature_Insights|Run B Feature Insights]]）：

| 排名 | 特征 | gain % | 分组 |
|------|------|--------|------|
| 1 | `distance_bin` | 14.68 | 派生 |
| 2 | `posture` | 14.58 | 用户指定 |
| 3 | `posture_x_phase` | 14.08 | 派生 |
| 4 | `is_enraged` | 10.10 | 用户指定 |
| 5 | `phase` | 9.86 | 用户指定 |
| 6 | `prev_action_freq` | 7.30 | 派生 |
| 7 | `distance` | 6.54 | 用户指定 |
| 8 | `distance_x_enraged` | 5.57 | 派生 |
| 9 | `angle_cos` | 5.18 | 派生 |
| 10 | `previous_action` | 4.19 | 用户指定 |
| 11 | `relative_angle` | 4.01 | 用户指定 |
| 12 | `angle_sin` | 3.90 | 派生 |

**分组占比：用户指定特征 49.29% ｜ 派生特征 50.71%**——一半的分裂增益来自特征工程；全部 12 列都参与分裂，无冗余列。

> [!note] 特征重要性图
> 每次训练后自动生成 `models/feature_importance.png`，可视化各特征对模型决策的贡献度。

## 为什么不包含的特征

| 不包含的特征 | 原因 |
|-------------|------|
| HP 绝对值 | 与 phase 高度相关（共线性） |
| 时间戳 | 无预测价值，是独立变量 |
| 玩家武器 | 未采集（未来可考虑） |
| 玩家动作 | 未采集（技术债，需更多逆向工程） |
| 多人联机信息 | 未采集 |
| 帧序号 | 无预测价值 |
