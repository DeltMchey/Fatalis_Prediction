---
title: Training Process
tags:
  - training
  - XGBoost
  - LightGBM
  - hyperparameters
  - dataset
created: 2026-07-26
updated: 2026-09-16
---

# Training Process

## 概述

v1.2.0 起，生产模型训练由 `src/model/production_backend.py` 完成（FLAML AutoML Run B 采纳配置，ADR-P6.1）：从 `ML_Ready_Dataset.csv` 加载派生对数据，确定性重训 XGBoost Pipeline，几秒完成（fit ~1.8s，单线程无 CPU 尖峰）。旧入口 `train_lgbm.py`（`--train`）保留为 legacy LightGBM 路径。

## 训练管线（production_backend.py）

```mermaid
graph LR
    A[ML_Ready_Dataset.csv] --> B[load_ml_dataset]
    B --> C[分层切分 8:2<br/>random_state=42]
    C --> D[FeatureBuilder<br/>仅 fit 于 train_80<br/>防泄漏红线]
    D --> E[稀有类 auto_augment<br/>镜像 FLAML 语义<br/>1949 → 2175 行]
    E --> F[shuffle random_state=1<br/>+ LabelEncoder]
    F --> G[XGBClassifier<br/>Run B 配置<br/>190 树 / n_jobs=1]
    G --> H[LabelDecodedEstimator<br/>包装 → sklearn Pipeline]
    H --> I[写 .tmp → 原子提升<br/>两代备份链]
    I --> J[产物: .pkl + gain 特征图<br/>+ sidecar + 训练日志]
```

> [!important] 复现要点（P7 排查成果）
> FLAML 的稀有类增广与 shuffle 必须**逐语义镜像**，否则类别先验（booster base_score）与训练行集不同，top3 偏差 +0.6pp。升级 FLAML 版本时需重新核对这两个隐藏行为。

## 超参数配置（Run B）

```python
RUNB_BEST_CONFIG = {
    "n_estimators": 190,      # 树数
    "max_depth": 4,           # 最大树深度
    "max_leaves": 4,          # 叶节点数
    "learning_rate": 0.078,   # 学习率（FLAML 搜索产物 0.07796…）
    "subsample": 0.946,       # 行采样（0.94573…）
    # 固定附加: objective=多分类 / enable_categorical / n_jobs=1（不设 random_state）
}
```

| 参数 | 值 | 作用 |
|------|-----|------|
| `n_estimators` | 190 | 树数（AutoML 搜索产物，非手工设定） |
| `max_depth` / `max_leaves` | 4 / 4 | 浅树防过拟合；浅树更易利用分箱后的距离档位 |
| `learning_rate` | 0.078 | 较大步长配合少树，训练几秒完成 |
| `subsample` | 0.946 | 行采样增强泛化 |
| `n_jobs` | 1 | 单线程训练与推理（Windows OpenMP 堆损坏教训，见 ADR-P6.1 Decision 2） |
| FeatureBuilder fit 范围 | 仅 train_80 | 派生特征统计量（如 prev_action_freq）不接触测试集，防泄漏 |

## 训练数据

| 指标 | 数值 |
|------|------|
| 原始录制文件 | 19 个（随发行包分发，作数据集重建保险） |
| 数据集样本数 | 2444 行派生对 |
| 留出集（holdout） | 488 行 / 46 类 |
| 外部输入特征 | 6（Pipeline 内扩展 12 列） |
| 招式类别数 | 46 |
| Train/Test 比例 | 80% / 20%（分层切分，random_state=42） |
| 稀有类增广 | train_80 内 <20 样本类整行复制（1949 → 2175 行，镜像 FLAML auto_augment） |

## 训练命令

```bash
# 推荐：一键管线（数据清洗 → Run B 后端重训）
python launch.py --pipeline
#   = data_cleaner（合并语义：保留历史会话）→ production_backend（XGBoost Run B）
#   训练前输出: 📊 本次训练数据：X 会话 / Y 行 / Z 类
#   输出 tee 到 models/train_YYYYMMDD_HHMMSS.log（保留最近 10 份）

# legacy：LightGBM 路径（向后兼容保留）
python train_lgbm.py          # 或 python launch.py --train
```

## 守门与可观测

| 机制 | 行为 |
|------|------|
| 数据摘要行 | 训练前打印本次 vs 上代的 会话数 / 行数 / 类数 |
| 破坏性变化告警 | 数据集行数 < 上代 50%、holdout < 100 行、类数降 ≥20% 时打 ⚠ 警告（**只警告不阻塞**，写 sidecar `gate_warnings`） |
| 训练日志 | 每次训练 tee 到 `models/train_*.log`，保留最近 10 份 |
| 备份链 | 提升走 `promote_with_backup`（`src/core/backup_chain.py`）：`.bak`（上一版）→ `.bak2`（上上版）；同 sha 跳过轮换（重复训练不吃掉备份） |
| 出厂副本 | `models/factory_model.pkl` 不可变，训练/轮换永不触碰 |

## 训练产物

| 文件 | 大小 | 说明 |
|------|------|------|
| `models/fatalis_ai_model.pkl` | 7.46 MB | joblib 序列化的 XGBoost Pipeline（FeatureBuilder + LabelDecodedEstimator） |
| `models/fatalis_ai_model.pkl.meta.json` | ~2 KB | sidecar：来源链 / sha256 / 门槛数据 / gate_warnings / 回滚程序 |
| `models/feature_importance.png` | ~50 KB | 12 列特征 gain 重要性条形图 |
| `models/train_*.log` | — | 最近 10 份训练日志 |
| `models/*.pkl.bak` / `.bak2` | — | 两代备份链 |
| `models/factory_model.pkl` | 7.46 MB | 出厂模型（不可变回滚副本） |

## 评估指标

详见 [[AI_Model/Model_Evaluation|Model Evaluation]]。

| 指标 | 计算方式 | v1.2.0 留出集 |
|------|----------|------|
| Top-1 | 预测第一位命中 | 32.58% |
| Top-3（raw） | 真实标签在预测 Top-3 中的比例 | 66.19% |
| Top-3（filtered，实战口径） | 阶段+姿态硬过滤后 | 65.37% |

## 技术债与改进方向

| # | 问题 | 现状 / 计划 |
|---|------|------|
| #6 | 无模型版本管理 | **已基本解决（v1.2.0）**：sidecar meta.json + 两代备份链 + factory_model 回滚层；仍缺多版本并存管理 |
| #7 | 无增量学习 | 未做（XGBoost 全量重训仅几秒，动机减弱） |
| #9 | 缺少特征消融实验 | **已做（P6）**：Run A（仅 6 特征）vs Run B（12 列）对照，派生特征贡献 50.71% gain，见 [[docs/AutoML_RunB_Feature_Insights|Run B Feature Insights]] |
| — | sha256 工具三处副本 | follow-up：`scripts/{adopt_model,benchmark_model,train_automl}.py` 改为 import `src/core/backup_chain.py` 的实现 |
