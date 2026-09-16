# Run B 特征重要性与预测行为解读（P7 采纳阶段）

> 模型：`experiments/fatalis_ai_model_automl_p6runB.pkl`（xgboost，190 树 / depth 4 / lr 0.078，12 列特征）
> 口径：xgboost gain 重要性（booster `get_score(importance_type='gain')` 归一化），同一留出集缓存 `experiments/holdout_cache.csv`（488 行 / 46 类）
> 图表：本目录 `AutoML_RunB_Feature_Importance.png`（主图）与 `AutoML_RunB_Confidence_Compare.png`（辅助图）
> 关联：决策矩阵见 `AutoML_P6_Comparison.md`（§6 裁决建议 + §9 P7 采纳简报）

## 1. 特征重要性（主图解读）

| 排名 | 特征 | 重要性（gain %） | 分组 |
|----|------|-----------------|------|
| 1 | `distance_bin` | **14.68** | 派生 |
| 2 | `posture` | 14.58 | 用户指定 |
| 3 | `posture_x_phase` | **14.08** | 派生 |
| 4 | `is_enraged` | 10.10 | 用户指定 |
| 5 | `phase` | 9.86 | 用户指定 |
| 6 | `prev_action_freq` | **7.30** | 派生 |
| 7 | `distance` | 6.54 | 用户指定 |
| 8 | `distance_x_enraged` | **5.57** | 派生 |
| 9 | `angle_cos` | **5.18** | 派生 |
| 10 | `previous_action` | 4.19 | 用户指定 |
| 11 | `relative_angle` | 4.01 | 用户指定 |
| 12 | `angle_sin` | **3.90** | 派生 |

**分组占比：用户指定特征 49.29% ｜ 派生特征 50.71%。**

关键发现：

1. **派生特征贡献过半（50.71%）**——这是 Run B（12 列）相对 Run A（仅 6 列）top3 +0.62pp、相对基线 +5.94pp 的直接证据：一半的分裂增益来自特征工程而非原始信号。
2. **前三名中有两个是派生特征**：
   - `distance_bin`（等频分箱距离，14.68%）反超原始 `distance`（6.54%）2.2 倍——浅树（depth 4）更容易利用离散化后的距离档位，而不是在连续距离上做多次阈值切分；
   - `posture_x_phase`（姿态×阶段交互码，14.08%）验证了"同一姿态在不同阶段下动作集不同"的领域直觉（该交互正是 ActionPredictor 过滤链手工编码的规则，模型从数据里自动学到了等价信号）。
3. **角度的三角编码生效但幅度有限**：`angle_sin` + `angle_cos` 合计 9.08%，约为原始 `relative_angle`（4.01%）的 2.3 倍——周期信号经 sin/cos 展开后对树模型更友好。
4. **`prev_action_freq`（上一动作的全局频率，7.30%）显著高于原始 `previous_action` 编码（4.19%）**——马尔可夫先验（"上一动作本身有多常见"）携带了比动作 ID 更多的可分裂信息。
5. **`distance_x_enraged`（5.57%）**：发怒状态改变距离-动作关系（远距离发怒技），交互项提供了单独 `is_enraged`（10.10%）之外的增量信号。
6. 没有特征重要性为零：全部 12 列都参与分裂（无双冗余列，特征设计无浪费）。

## 2. 预测置信度分布（辅助图解读）

同一留出集上 top-1 预测置信度（softmax 最大值）分布对比：

| 模型 | 置信度均值 | 置信度中位数 |
|------|-----------|-------------|
| 基线 LightGBM | 0.465 | 0.430 |
| Run B xgboost | **0.431** | **0.406** |

解读：

1. Run B 在**准确率显著更高的同时置信度反而更低**（top1 +5.53pp、top3 +5.94pp，但均值置信度 −0.034）——基线的部分"高置信"是过拟合式的过度自信；Run B 的概率输出更保守、top-3 内的相对排序信息量更大。
2. 对实战链路的意义：`ActionPredictor` 的 top-3 选择阈值（`prob > 0.03`）在 Run B 下依然宽松可用（最低置信档样本仍远高于 0.03），过滤链 + 重归一化行为不受影响。
3. 实战中 UI 展示的"AI 确信度"读数整体会略降，但换来的是更高的命中率——对玩家感知是"更稳的预测"而非"更弱的预测"。

## 3. 复现与口径说明

- 图表数据与 P7 复现验证（`experiments/automl_20260915/reports/p7_repro_runB.json`）同源：best_config 确定性原生重训与 FLAML 导出物**逐位一致**（predict_proba max_abs_diff = 0.0）。
- gain 口径选择：xgboost 默认 `weight` 口径偏向高频低层特征；`gain` 反映每次分裂的损失下降贡献，与"该特征对预测质量的贡献"语义一致，也是 FLAML/xgboost 社区报告的标准口径。
- 图表脚本：`experiments/automl_20260915/p7_feature_charts.py`（matplotlib，中文字体 Microsoft YaHei）。
