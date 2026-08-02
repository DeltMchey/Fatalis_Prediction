---
title: Training Process
tags:
  - training
  - LightGBM
  - hyperparameters
  - dataset
created: 2026-07-26
updated: 2026-07-26
---

# Training Process

## 概述

模型训练由 `train_lgbm.py` 脚本完成，从 `ML_Ready_Dataset.csv` 加载清洗后的派生对数据，训练一个 LightGBM 多分类器。

## 训练管线

```mermaid
graph LR
    A[ML_Ready_Dataset.csv] --> B[加载数据]
    B --> C[过滤罕见招式<br/>出现次数 < 3]
    C --> D[类别特征编码<br/>astype category]
    D --> E[8:2 Train/Test Split<br/>random_state=42]
    E --> F[LightGBM 训练<br/>300 estimators<br/>early_stopping=15]
    F --> G[评估]
    G --> H[保存 .pkl + 特征重要性图]
```

## 超参数配置

```python
model = lgb.LGBMClassifier(
    objective='multiclass',
    num_leaves=63,           # 叶节点数，控制模型复杂度
    max_depth=7,              # 最大树深度，防止过拟合
    learning_rate=0.03,       # 学习率
    n_estimators=300,         # 最大树数（配合 early_stopping 实际可能更少）
    random_state=42,
    class_weight='balanced',  # 自动平衡稀有/常见招式权重
    n_jobs=-1,                # 使用全部 CPU 核心
    subsample=0.8,            # 行采样：每棵树随机 80% 样本
    colsample_bytree=0.8,     # 列采样：每棵树随机 80% 特征
    importance_type='gain'    # 特征重要性计算方式
)
```

## 超参数详解

| 参数 | 值 | 作用 | 调参理由 |
|------|-----|------|----------|
| `num_leaves` | 63 | 树复杂度 | 配合 max_depth=7，63 < 2^7=128，避免过拟合 |
| `max_depth` | 7 | 限制树深度 | 数据集较小（数千样本），浅树防过拟合 |
| `learning_rate` | 0.03 | 学习率 | 较小学习率配合较多树，提升泛化能力 |
| `n_estimators` | 300 | 最大树数 | 配合 early_stopping=15，实际通常早停 |
| `subsample` | 0.8 | 行采样 | 每棵树随机 80% 样本，增强泛化 |
| `colsample_bytree` | 0.8 | 列采样 | 每棵树随机 80% 特征（6 取 5），多样性 |
| `class_weight` | balanced | 类别权重 | 稀有招式（如捕食）和常见招式（龙车/火球）自动平衡 |
| `early_stopping` | 15 | 早停轮数 | 验证 loss 连续 15 轮不降则停止，节省时间 |

## 训练数据

| 指标 | 数值 |
|------|------|
| 原始录制文件 | 17 个 |
| 原始数据总大小 | ~11 MB |
| 清洗后样本数 | 数千条派生对 |
| 特征维度 | 6 |
| 招式类别数 | ~40-60 个 |
| 每类最少样本 | ≥3（训练前过滤） |
| Train/Test 比例 | 80% / 20% |

## 训练命令

```bash
# 步骤 1: 清洗数据
python data_cleaner.py
# 输出: "✅ V4.5 纯粹观测流数据提纯完成！有效样本: N 条"

# 步骤 2: 训练模型
python train_lgbm.py
# 输出:
#   🏆 绝对准确率 (Accuracy): XX.XX%
#   🌟 实战黄金指标：Top-3 命中率: XX.XX%
#   💾 模型已保存至: models/fatalis_ai_model.pkl
#   📈 图表已保存为 models/feature_importance.png
```

## 训练产物

| 文件 | 大小 | 说明 |
|------|------|------|
| `models/fatalis_ai_model.pkl` | ~18 MB | joblib 序列化的 LightGBM 模型 |
| `models/feature_importance.png` | ~50 KB | 6 维特征重要性条形图 |

## 评估指标

详见 [[AI_Model/Model_Evaluation|Model Evaluation]]。

| 指标 | 计算方式 | 说明 |
|------|----------|------|
| Accuracy | `accuracy_score(y_test, y_pred)` | Top-1 命中率 |
| Top-3 命中率 | `真实标签在预测 Top-3 中的比例` | 实战核心指标 |

## 技术债与改进方向

| # | 问题 | 计划 |
|---|------|------|
| #6 | 无模型版本管理 | P5: 文件名加时间戳 + metadata.json |
| #7 | 无增量学习 | P5: `init_model` 参数支持 |
| #9 | 缺少特征消融实验 | P5: 逐特征移除对比准确率变化 |
