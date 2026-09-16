# AutoML 实验完整实施规划（BlackDragon — MHW 黑龙下一招预测）

> 状态：Approved Plan（供 Coder 直接执行）
> 分支：`feature/automl-experiment`（基于 main @ 4149ede）
> 日期：2026-09-15
> 范围：只规划、不写实现代码。本文档中的"接口签名/伪代码"仅为契约说明。
> 需求与技术选型已由用户确认锁定（FLAML 2.6.0、5 算法搜索空间、自定义 top-3 指标、6 特征锁定），本文不重新论证选型，只落地实施。

---

## 0. Executive Summary

**目标**：用 FLAML 2.6.0 自动搜索优于现有手工固定超参 LightGBM 的下一招预测模型，同时保证推理时延、内存、模型体积三项工程指标不劣化到影响实战（与 3A 游戏同机并行）。

**核心方案**：9 阶段流水线——依赖冒烟 → 共享数据模块重构（锁定与基线完全一致的留出集）→ benchmark 脚本 → 基线补测（一切门槛的分母）→ FLAML 训练脚本（统一数值编码喂入，规避 pandas 3 / category dtype 兼容风险）→ 原生 estimator 导出（零 flaml 运行时依赖）→ 候选训练与对比 → 条件性 EXE 适配 → 决策与合并。全程生产模型路径物理隔离，产物独立命名 `fatalis_ai_model_automl.pkl`。

**关键门槛**：top-3 ≥ 基线 + 3.0pp 才采纳；推理 p95 ≤ 20ms 且 ≤ 2× 基线；模型文件 ≤ 40MB；训练预算 ≤ 90min/run。

**关键风险**：FLAML 与 pandas 3.0.2 兼容性（P0 冒烟硬闸门）、xgboost 胜出引入运行时二进制依赖（体积门槛+次优回退规则）、2444 样本/51 类的高方差（配对留出集 + 分组 CV 双口径对照）。

**预估总量**：6–8 人日开发 + 4–6 小时机器时间（训练与 benchmark）。

---

## 1. 实验目标与成功判据

### 1.1 目标

1. **效果**：在固定分层留出集上，AutoML 最优模型的 top-3 准确率显著超过现有生产基线（手工超参 LightGBM），top-1 不显著回退。
2. **工程**：推理时延、稳态内存、模型体积、EXE 包体积全部在预算内（推理进程与 3A 游戏同机并行，工程指标与效果指标同权重）。
3. **资产**：无论采纳与否，沉淀可复用的 benchmark 脚本、AutoML 训练脚本、模型导出模块——后续 P6「模型工程化」直接复用。
4. **预期管理（明确写入）**：MLP 在数千样本量级上大概率不敌 LGBM，其纳入价值是搜索空间多样性，不构成成功条件；若最终胜者仍是 lgbm 家族（仅超参更优），实验同样算成功。

### 1.2 成功判据（决策门槛）

设基线实测值为 `B_top1 / B_top3 / B_p95 / B_rss_delta / B_size`（Phase P3 产出 `baseline_report.json`，当前未知，第一优先级补测）。

| ID | 门槛 | 数值 | 理由 |
|----|------|------|------|
| **G1 效果主门槛** | 留出集 top-3（raw 口径，与 train_lgbm 打印口径一致） | **≥ B_top3 + 3.0pp → 采纳**；[B_top3+1.0, B_top3+3.0) → 人工评审；< B_top3+1.0 → 拒绝 | 留出集约 488 样本；top-3 在 50–70% 区间的独立二项 95% CI 半宽约 ±4.4pp，但基线与候选在同一留出集上**配对比较**，有效噪声显著更小；+3.0pp 覆盖配对噪声；+1.0pp 下限避免为边际收益承担生产切换风险 |
| **G2 top-1 守门** | 留出集 top-1 | ≥ B_top1 − 1.0pp | 优化目标是 top-3，但 overlay 首行是用户最强感知位；防止 top-3 以牺牲 top-1 为代价 |
| **G3 时延** | 端到端全链路（特征构造→predict_proba→过滤→重归一化→top-3） | **p95 ≤ 20ms 且 ≤ 2.0 × B_p95**；mean ≤ 10ms | 生产节奏 0.5s/次，单次预算需容纳内存读取 + DPG 渲染；20ms 绝对上限 + 2 倍相对上限双保险；项目自称基线 < 5ms（brief），待实测 |
| **G4 模型体积** | 模型文件大小 | **≤ 40MB 硬上限**（建议 ≤ 30MB） | 现基线 19.0MB；PyInstaller 包内模型约 2 份拷贝（`_internal/models/` + surfaced `models/`），40MB → 包增量 ≤ ~42MB |
| **G5 内存** | 加载 RSS 增量 / 稳态 RSS / 5min 漂移 | 加载增量 ≤ 100MB；稳态 RSS ≤ B_rss + 150MB；5 分钟漂移 ≤ 5%（无泄漏） | 推理进程与游戏同机；基线进程 RSS 待实测 |
| **G6 包体积** | 发布 zip 总体积（仅采纳时考核） | ≤ 300MB（现 227MB，增量预算 ~73MB） | 若 xgboost 胜出需额外评估其 DLL 体积，超预算则取门槛内次优模型（见 5.4 回退规则） |
| **G7 训练预算** | 单次 FLAML 搜索 wall time | `time_budget_s = 5400`（90min 硬上限），目标 ≤ 60min；两个 run 合计 ≤ 4h | 保持实验可迭代；训练在开发机离线执行，不影响游戏运行时 |
| **G8 可复现** | 切分/导出确定性 | 留出集索引与基线**逐索引一致**（golden 测试）；导出模型同输入同输出（逐位一致）；FLAML 搜索序列允许非确定，但导出模型 = 最优 config 的确定性提取/重训 | 决策必须建立在可复现的数字上 |

**决策规则汇总**：
- **采纳（Tier 1）**：G1 达 +3.0pp 且 G2–G8 全过 → 执行 P7/P8 采纳流程。
- **人工评审（Tier 2）**：G1 在 [+1.0, +3.0) 且 G2–G8 全过 → 输出决策矩阵交用户裁决；裁决参考分组 CV 口径是否同向（见 3.4）。
- **拒绝（Tier 3）**：G1 < +1.0pp，或任一工程门槛失败 → 保留基线，写"不采纳"ADR，工具链（benchmark/训练/导出脚本）仍合并入库作为资产。

---

## 2. 分阶段实施计划

依赖关系图：

```
P0 依赖冒烟 ──► P1 数据模块重构 ──► P2 benchmark 脚本 ──► P3 基线补测 ─┐
      │                  │                                              │
      │                  └──────────────► P4 AutoML 训练脚本（可与 P2/P3 并行）
      │                                                                 │
      └──────────────────────────────► P5 导出模块 ◄── P4 完成 ─────────┤
                                                                        ▼
                                              P6 候选训练与对比评审 ◄─（消费 P3 基线 + P5 导出）
                                                        │
                                       [采纳?] ── 是 ──► P7 EXE 打包适配 ──► P8 决策与合并
                                          │ 否 ─────────────────────────────► P8 决策与合并
```

每阶段提交独立 commit（`feat(automl): P<n> ...`），阶段末运行全量测试。

---

### P0 — 环境准备与依赖冒烟（0.5 人日）

**目标**：实验依赖安装到位，并在此**硬性验证** FLAML 2.6.0 在钉版环境（pandas 3.0.2 / numpy 2.4.4 / sklearn 1.8.0 / Python 3.12.6 / Windows 原生）下的可用性。此阶段是 R-01 风险的闸门，**冒烟不通过则停止后续所有阶段并升级决策**。

**涉及文件**：
- 新增 `requirements-experiment.txt`：`flaml==2.6.0`、`xgboost==<冒烟时确定的钉版>`（须与 numpy 2.4.4 / sklearn 1.8.0 兼容的最新稳定版）、`psutil==<钉版>`。**不改动 `requirements.txt`**（运行时零新增依赖原则，采纳 xgboost 胜出时另行评审）。
- 新增 `scripts/smoke_test_automl.py`（或并入 P4 训练脚本的 `--smoke` 模式）：一次性冒烟脚本，不必入库长期维护，但执行记录存入 experiments 目录。

**冒烟清单（全部必须通过）**：
1. `import flaml` / `import xgboost` / `import psutil` 成功，版本打印。
2. xgboost sklearn API（`XGBClassifier`）在合成多分类数据上 fit/predict/predict_proba/joblib round-trip 成功。
3. FLAML 微搜索：合成多分类数据（~50 类 × 2000 行，模拟真实规模），`estimator_list=['lgbm','xgboost','rf','extra_trees']`，`time_budget_s=60`，`eval_method='cv'` 跑通。
4. FLAML 自定义 learner 注册路径验证：`@register_learner`（或 flaml 2.6.0 实际等价 API，以官方文档为准）注册 `Pipeline(OneHotEncoder, MLPClassifier)` wrapper 后，`estimator_list` 含自定义名可被搜索。
5. FLAML 自定义 metric 契约验证：签名 `(X_val, y_val, estimator, labels) → (name, value, higher_is_better=True)` 的 callable 可被 `AutoML(metric=...)` 接受。
6. FLAML 对输入 DataFrame 的处理路径观察：喂入**纯数值列** DataFrame（本计划统一方案）确认无 category/object 触发的内部异常。
7. `automl.model` 属性可访问且其类型为原生 estimator（或可从中提取原生 estimator）。

**产出**：`experiments/automl_<date>/smoke_report.md`（记录钉版号、通过项、任何 warning）+ `requirements-experiment.txt`。
**验证方式**：冒烟清单 7/7 通过；现有 581 测试不受影响（未动任何现有代码）。
**工作量**：0.5 人日。

---

### P1 — 共享数据模块重构 + 数据集会话标注（0.5–1 人日）

**目标**：(a) 把 `train_lgbm.py` 的"加载→过滤→切分"逻辑提取为共享模块，使基线补测与 AutoML 训练使用**字面上同一份代码**产生同一留出集；(b) 为数据集增加 `source_session` 列以支持分组 CV 对照（防泄漏稳健性检查）。

**涉及文件**：
- 新增 `src/model/dataset.py`：
  - `load_ml_dataset(csv_path) -> pd.DataFrame`：读 CSV + NaN label 过滤 + 数值化 + ACTION_DB 未知 label 过滤 + 类频 ≥3 过滤（逐条复刻 `train_lgbm.py:24-69` 现有顺序与 warning 输出，含日志）。
  - `make_holdout_split(df, test_size=0.2, random_state=42) -> (train_df, holdout_df)`：分层切分（含小数据集降级逻辑，复刻 `train_lgbm.py:84-98`）。
  - 常量：`FEATURE_COLS`（6 锁定列）、`LABEL_COL`。
- 修改 `train_lgbm.py`：删除内联过滤/切分代码，改为调用上述函数。**行为零变化**（打印、日志、warning 语义保持）。
- 修改 `data_cleaner.py`：输出 DataFrame 增加 `source_session` 列（值为源 CSV 文件名/序号），纯增量列；`train_lgbm.py` 因显式 `df[feature_cols]` 选列天然不受影响。重新生成数据集后需验证与现数据集的 7 个特征/标签列**逐行一致**（确定性检查，见验证方式）。
- 修改 `tests/test_data_cleaner.py`：列断言更新（+1 列）。
- 新增 `tests/test_dataset_split.py`（golden 测试）：
  - 重构前先用现版 `train_lgbm.py` 在真实 `ML_Ready_Dataset.csv` 上导出 `X_test.index` 与 `y_test.values` 为 golden 文件（一次性生成，数据集本身不入库，golden 文件提交其 SHA-256 与行数断言而非全量数据）；
  - 重构后断言：同数据集 → 同 train/test 索引、同 y 序列；
  - `source_session` 列存在性、additive 性（不影响 6 特征列）、稀有类过滤行为不变。

**产出**：`src/model/dataset.py`、golden 测试通过、重新生成的带 `source_session` 的 `ML_Ready_Dataset.csv`。
**验证方式**：581 旧测试全绿（`test_train_lgbm.py` 5 项是重构回归的主力保障）；golden 索引一致；新旧数据集特征列 diff 为空。
**工作量**：0.5–1 人日。

---

### P2 — benchmark 脚本（1 人日）

**目标**：实现 4 项评价指标的统一测量工具，任何模型（基线 pkl / AutoML 候选 pkl）用同一命令得到同 schema 的 JSON 报告。

**涉及文件**：新增 `scripts/benchmark_model.py`。

**接口设计（契约）**：
```
python scripts/benchmark_model.py --model <path.pkl> --report <out.json> \
    [--holdout-csv <cached.csv>] [--latency-iters 1000] [--mem-duration 300] [--skip-mem]
```

**四项指标的测量设计**：

1. **top-1 / top-3 准确率（同一留出集）**
   - 数据：P1 的 `make_holdout_split`（random_state=42）产出的留出集；首次运行时把留出集缓存为 `experiments/<run>/holdout_cache.csv`（含 SHA-256），后续所有模型复用**同一缓存**，保证逐模型同集。
   - `top1 = accuracy_score(y, argmax(predict_proba(X)))`。
   - `top3_raw`：`np.argsort(probs, axis=1)[:, -3:]` 命中率——**与 `train_lgbm.py:127-129` 口径逐行一致**（决策门槛口径）。
   - `top3_filtered`（实战口径，附加记录，不设门槛）：对每行以其自身 `phase/posture` 值调用 `src/model/predictor.py` 的静态方法 `filter_probs_by_phase / filter_probs_by_posture / renormalize_probs` 后按 `select_top_k(3, 0.03)` 判命中。**注意**：导出模型若内部重排了 `classes_` 顺序，此处用模型自身 `classes_` 对齐。
   - 同时记录 macro/micro 两组（46 类长尾，macro 暴露小类表现）。
   - 类别 dtype 处理：基线模型需要 category dtype 输入（训练时如此）；导出模型的输入格式由 P5 契约统一处理。benchmark 内部按模型 `meta` 或探测逻辑适配（见 P5 兼容层），**两组模型在同一原始 6 列行上评估**。

2. **端到端推理时延**
   - 链路 = **复用 `src/model/predictor.py` 的 `ActionPredictor(model_path).predict(...)`**——它与 `ai_engine.py:441-455` 逐行等价且就是生产链路，比复制 legacy 代码更忠实。
   - 输入：从留出集随机抽 1000 行（seed=42）参数化为 `(distance, angle, posture, prev_action, phase, enrage)` 逐次调用。
   - 预热 10 次后测 1000 次，报告 mean / p50 / p95 / p99 / max（perf_counter）。

3. **CPU / 内存开销（干净子进程隔离）**
   - 结构：父进程 `subprocess.spawn` 一个 runner 子进程；runner 加载模型、以 0.5s 节奏连续推理 5 分钟并自报时延；父进程用 psutil 按 10s 间隔采样 runner 的 RSS 与 `cpu_percent(interval=1)`。
   - 报告项：加载前后 RSS 差（runner 在加载前上报基线 RSS）、稳态 RSS 曲线（min/mean/max）、5 分钟末漂移斜率（线性拟合，判定泄漏）、模型文件字节数。
   - psutil 采样开销与被测进程隔离（父进程测子进程），不污染时延数字。

4. **EXE 包体积增量**（仅 P7 采纳阶段执行）：`build_exe.ps1` 产物 zip 前后体积对比，记录到采纳报告。

**报告 schema**（JSON，键固定，供横向 diff）：`{model_path, model_sha256, dataset_sha256, holdout_sha256, metrics: {top1, top3_raw, top3_filtered, macro_top3, micro_top3}, latency_ms: {mean, p50, p95, p99}, memory: {load_rss_delta_mb, steady_rss_mb, drift_mb_per_5min, model_file_mb}, env: {python, sklearn, lightgbm, xgboost, os}, timestamp}`。

**涉及测试**：新增 `tests/test_benchmark_model.py`——合成小数据集 + mini 模型（沿用 `test_train_lgbm.py` 的确定性 mini 数据模式）：top-3 手算对照、报告 schema 键齐全、数值有限、两次运行同输入结果一致；时延模块用极小迭代数跑通。

**产出**：`scripts/benchmark_model.py` + 测试。
**验证方式**：在 mini 模型上全指标产出合法 JSON；pytest 绿。
**工作量**：1 人日。

---

### P3 — 基线补测（0.5 人日 + ~0.5h 机器）

**目标**：产出 `baseline_report.json`——所有决策门槛的分母。**这是全实验的第一优先级交付物**。

**步骤**：
1. 用现有生产模型 `models/fatalis_ai_model.pkl`（19.0MB，不动它）跑 P2 benchmark 全项 → `experiments/<run>/reports/baseline.json`。
2. 补充测量"基线再训练复现性"：用重构后的 `train_lgbm.py`（等价超参）在 train_80 上重训一次，留出集指标与生产模型对比（验证：当前生产模型是否可由管线复现；若偏差大，说明生产模型来自旧数据快照——记录事实，门槛仍以**生产模型**实测为准，因为它是被替换对象）。
3. 采集基线进程画像：`B_rss`（稳态 RSS）、`B_p95`，写入报告。

**产出**：`baseline_report.json`（含 B_top1/B_top3/B_p95/B_rss_delta/B_size 六个锚点值）。
**验证方式**：报告 schema 合法；B_top3 与 `train_lgbm.py` 训练时打印的 Top-3 数字同量级（差异应可解释：早停轮次 vs 300 棵全量）。
**工作量**：0.5 人日。

---

### P4 — AutoML 训练脚本（1–1.5 人日）

**目标**：实现 FLAML 搜索 CLI，落实已锁定决策（算法空间、自定义指标、超参约束、特征策略）。

**涉及文件**：
- 新增 `configs/automl_experiment.json`（与项目 JSON 配置习惯一致）：`seed, time_budget_s, estimator_list, custom_hp 约束表, n_splits, holdout_size, feature_run 定义（A/B）, 输出目录, mlp 隐层上限`。
- 新增 `scripts/train_automl.py`（仅 dev 使用，不进 EXE）。
- 新增 `src/model/features.py`（与 P5 共用，见下）。

**核心设计**：

1. **统一数值编码（本计划的关键架构决策）**：`src/model/features.py` 提供 `FeatureBuilder`（fit/transform 分离的纯变换，无 flaml 依赖）：
   - 输入：生产格式 DataFrame（6 锁定列，4 列 category dtype）。
   - 输出：纯数值矩阵（列名保留）——4 个类别列映射为**固定词表**的有序数值码（词表来源：posture/phase/is_enraged 枚举 + `ACTION_DB` 已知动作 ID 全集；未见值映射到显式 `-1` 哨兵码）。
   - **效果**：FLAML 及全部 5 种 learner 只见数值矩阵 → 同时消除两个高危风险：FLAML 内部对 pandas 3 category dtype 的兼容不确定性（R-01 收窄）、FLAML 内部编码与生产 category 输入格式的不一致（R-02 根除）。基线模型不重训、按自身管线评估，编码差异属于候选方案本身，不影响公平性（比较对象是端到端模型）。

2. **特征两 run 对比（按已定"退一档"方案）**：
   - **Run A**：仅 6 锁定列（数值编码后）。
   - **Run B**：6 列 + 派生候选列——`sin/cos(relative_angle)`（解决 ±180° 断裂）、`distance` 等频分箱（5–10 箱，**箱边缘仅在 train_80 上 fit**）、`distance × is_enraged`、`posture × phase` 交互、`previous_action` 频次编码（**频率表仅在 train_80 上 fit**，防泄漏）。
   - 派生列全部由 `FeatureBuilder` 内部生成（fit 于 train、transform 于推理），保证导出后接口仍是生产 6 列。
   - 两 run 各自独立 FLAML 搜索，人工对比决策。

3. **FLAML 调用配置**（伪契约）：
   - `AutoML(task='classification', metric=top3_metric, eval_method='cv', split_type='stratifiedcv', n_splits=5, seed=42, time_budget_s=5400, estimator_list=['lgbm','xgboost','rf','extra_trees','mlp_custom'], custom_hp=<约束表>, log_file_name=<run 目录>, retrain_full=True, verbose=...)`
   - **只把 train_80 喂给 `automl.fit`**，留出集绝不进入搜索（见 3.3）。
   - `top3_metric(X_val, y_val, estimator, labels) -> ('top3_acc', value, True)`：内部 `estimator.predict_proba(X_val)` → argsort 前 3 命中率（与 train_lgbm 口径一致）；top-1 由 FLAML 内置 `train_loss`/日志另行记录。
   - custom_hp 约束（已锁定）：lgbm `n_estimators≤400, num_leaves≤127, max_depth≤9`；xgboost `n_estimators≤400, max_depth≤8`；rf/extra_trees `n_estimators≤500, max_depth≤16`；mlp wrapper 隐层 ≤ (128,64)、`max_iter≤500`。
4. **MLP 自定义 learner**（已锁定）：`@register_learner` 注册 wrapper —— `Pipeline(OneHotEncoder(类别码列), BalancedMLPClassifier)`；`BalancedMLPClassifier` 是 `MLPClassifier` 薄封装，`fit` 内按类权重过采样/欠采样实现类别均衡（MLPClassifier 无 `class_weight`）。
5. **分组 CV 对照**（稳健性，非门槛）：用 `source_session` 作组标签跑一次 `StratifiedGroupKFold(5)` 下的最优 config 复评（手动 CV 循环，不进 FLAML 搜索），报告分组口径 top-3（见 3.4）。
6. **运行清单（manifest）**：每次 run 落盘 `run_manifest.json`：config 全文、数据集 SHA-256、库版本指纹、FLAML log csv 路径、best_config、best CV top-3。

**涉及测试**：新增 `tests/test_features.py`（见第 6 节）+ `tests/test_train_automl.py`（integration 标记：合成数据、`time_budget_s≈20`、2 个 learner、断言产物齐全且可导出）。
**产出**：训练脚本、features 模块、配置文件、测试。
**验证方式**：mini run 端到端跑通；pytest 绿；`train_lgbm.py` 行为未变。
**工作量**：1–1.5 人日。

---

### P5 — 模型导出与兼容性验证（1 人日）

**目标**：把 FLAML 产物转成**零 flaml 运行时依赖**的生产可加载对象，并证明 `ActionPredictor` 不改一行代码即可使用。

**涉及文件**：新增 `scripts/export_model.py`、`src/model/features.py`（补导出用序列化逻辑）；新增 `tests/test_model_export.py`。

**导出架构（主路径：提取）**：
- 导出对象 = `Pipeline([('features', FeatureBuilder 已 fit 实例), ('estimator', 从 automl.model 提取的原生 estimator)])：
  - lgbm/xgboost/rf/extra_trees → 对应 `LGBMClassifier / XGBClassifier / RandomForestClassifier / ExtraTreesClassifier`；
  - mlp → `Pipeline(OneHotEncoder, BalancedMLPClassifier)`（wrapper 类必须可导入——**BalancedMLP 定义放 `src/model/`（随应用分发）而非 scripts/**，否则 pickle 无法反序列化；OneHotEncoder 连同持久化，已锁定）。
- 契约：导出对象 `joblib.load` 后，`predict_proba(DataFrame[6 列, 4 列 category dtype])` 可用、`classes_` 可访问（sklearn Pipeline 经 `available_if` 委托末步，测试显式断言）。`ActionPredictor` 的推理链路（predict_proba → 过滤 → 归一化 → top-3）对导出对象完全透明。
- 提取后**重持久化**（joblib.dump 到新文件），确认 pickle 内容不含 flaml 引用。
- **备选路径（确定性重训）**：若提取对象的 pickle 仍引用 flaml 内部类，则用 `best_config` 以原生 API（sklearn/lightgbm/xgboost，`seed=42, n_jobs=1`）在 train_80 上重训等价模型；接受条件：重训版与提取版在留出集上 top-3 差异 ≤ 0.5pp。

**兼容性验证（必须全过）**：
1. **无 flaml 环境加载**：子进程中屏蔽 `flaml` 导入（如 `sys.modules['flaml'] = None` 注入或独立 venv）后 `joblib.load` + 单行推理成功。
2. `ActionPredictor(exported_path).predict(...)` 返回合法 top-3（概率和 ≈ 1、阈值语义正确）——**用 4 个家族的 mini stub 模型各测一遍**。
3. 确定性：同输入 1000 次，输出逐位一致。
4. `classes_` ⊆ ACTION_DB 训练标签集；未见类别输入（哨兵码）不崩溃、返回有限概率。

**产物命名与 sidecar**（详见第 5 节）。
**工作量**：1 人日。

---

### P6 — 候选训练与对比评审（0.5 人日 + 2–4h 机器）

**目标**：跑正式实验，产出决策矩阵。

**步骤**：
1. Run A（仅 6 特征）与 Run B（含派生）各一次 FLAML 搜索（`time_budget_s=5400`；先跑 Run A，若 Run A 已达 Tier 1 门槛且 Run B 无明显 CV 优势可提前终止 Run B，节省机时——终止决定记录在案）。
2. 每个候选（Run A best、Run B best，如有必要加 runner-up）走 P5 导出 → P2 benchmark → 汇入对比表。
3. 基线 vs 候选对比表：G1–G8 逐项判定 + 分组 CV 口径对照列；Rank 翻转检测（raw 口径 vs 分组口径排名不一致 → 标注升级人工评审）。
4. （可选，若 Tier 2 边界）finalist 以 3 个种子复评留出集，报告均值±范围，辅助人工裁决。

**产出**：`experiments/<run>/comparison.md`（决策矩阵）+ 各模型 benchmark JSON。
**工作量**：0.5 人日人工 + 2–4h 机器（后台执行）。

---

### P7 — EXE 打包适配（0.5–1 人日，**仅当决策 = 采纳时执行**）

**目标**：胜出模型进入发布包，且冻结模式全部回归通过。

**步骤与涉及文件**：
1. `requirements.txt`：仅当胜者非 sklearn/lgbm 家族（即 xgboost）时新增 `xgboost==<pin>`，走独立评审（体积影响先测 wheel 安装后体积）。
2. `build/BlackDragon.spec` / `build/BlackDragonOverlay.spec`：`datas` 中模型条目保持文件名 `fatalis_ai_model.pkl` 不变（采纳时由导出文件复制覆盖，spec 零改动为最优路径）；xgboost 情形需在两个 spec 增 `hiddenimports`（`xgboost` + 其 `libxgboost.dll` 由 PyInstaller hook 收集，P0 冒烟已验证 import 路径）。
3. `scripts/build_exe.ps1`：模型 surface 逻辑零改动（文件名不变）。
4. 冻结回归清单：
   - `BlackDragon.exe --pipeline` 退出码 0（一键训练不因新模型存在而异常——训练仍走 train_lgbm 旧管线，AutoML 不接入冻结训练，范围守卫）；
   - `BlackDragonOverlay.exe` 启动后 ActionPredictor 加载新模型、overlay 显示 AI 预测正常（人工冒烟，按 `tests/manual_checklist.md` 惯例记录）；
   - 包体积测量 → G6 判定；
   - 干净机器（无 Python）解压运行冒烟。
5. 回滚程序演练：恢复 `fatalis_ai_model.pkl.bak` → 冻结冒烟恢复 → 记录回滚步骤入采纳报告。

**产出**：新构建 zip + 冻结回归记录 + 体积报告。
**工作量**：0.5–1 人日。

---

### P8 — 结果评审与合并决策（0.5 人日）

**目标**：闭环决策、写档、合并。

**步骤**：
1. 产出决策矩阵终版（Tier 1/2/3 判定）。
2. 写 ADR：`obsidian/docs/architecture/ADR-P6.1-automl-model-selection.md`——无论采纳与否（采纳：记录胜者 config、门槛达成数字、生产切换步骤；不采纳：记录"工具链资产保留、模型维持基线"及原因）。
3. 更新 `obsidian/memory_bank/`（activeContext、progress、changelog）与 `CHANGELOG.md`；采纳时另更新 `README.md`（指标数字）。
4. 验收清单（第 8 节）逐项勾选。
5. PR 评审 → 合并回 main → 删除分支。采纳情形：采纳 commit（模型文件替换 + .bak 轮换）独立于工具链 commit，便于单独 revert。

**工作量**：0.5 人日。

---

## 3. 数据切分设计

### 3.1 数据现状（实测）

`ML_Ready_Dataset.csv`：**2444 行 / 51 类**；类频 max=209 / median=32 / min=1；类频 <3 的类 5 个（被 `train_lgbm.py` 过滤，有效约 46 类、约 2438 行）；类频 <10 的类 10 个。来源 19 个战斗 CSV 会话。

### 3.2 切分方案（主门槛口径）

```
ML_Ready_Dataset.csv
   │  load_ml_dataset()：NaN → 数值化 → ACTION_DB 已知 → 类频≥3（顺序复刻 train_lgbm.py:24-69）
   ▼
train_80 (≈1950 行) ────────────────► FLAML 搜索（eval_method='cv'，5 折分层，只喂这部分）
   │                                        │
   │                                        └── CV 仅供搜索期模型排序，不产生门槛数字
   ▼
holdout_20 (≈488 行, random_state=42, stratify=y)
   │  不参与任何搜索/早停/特征词表 fit
   ▼
基线复评 + 每个候选模型各评一次 → benchmark 报告 → 门槛判定
```

- **留出集完全不参与搜索**：FLAML 的 `eval_method='cv'` 在 train_80 内部做 5 折分层 CV；派生特征的分箱边缘/频次表/编码词表一律 fit 于 train_80；留出集仅在最终 benchmark 时被每个候选触碰一次。
- **与基线可比性**：切分代码就是从 `train_lgbm.py` 提取的同一函数（P1），索引逐位一致（golden 测试锁定）——基线模型当初的 80/20 口径与本次评估口径同分布同划分，这是"公平"的根基。
- **候选排序与终评分离**：候选间排序优先参考 FLAML CV top-3（train 内部），holdout 仅做终评——缓解"holdout 被多个候选复用导致的选择偏置"（R-06）；G1 的 +3.0pp 采纳线进一步覆盖该残余噪声。

### 3.3 时间相关性判断（设计结论）

战斗转移样本在**同一场战斗内**存在相关性（玩家行为连续、阶段推进），纯随机分层切分会把同场战斗的相邻转移分进 train 与 holdout，产生轻度乐观泄漏。但本设计仍选择随机分层为主门槛口径，理由：

1. **类覆盖约束是硬约束**：46 类/2438 行、10 个类频 <10 的类集中在少数战斗，按会话分组留出会导致稀有类整类缺失或无法分层（sklearn 分层要求每类在两侧均有样本），分组**留出**在数学上不可行。
2. **部署场景匹配**：上线后的推理发生在"同类型新战斗"中，与训练战斗非同一场——严格说理想评估是"按会话留出"；但玩家对同一 Boss 的行为模式跨场次高度相似，随机切分的泄漏对**基线与所有候选同向等量**，排名基本保持，端到端数字略乐观但不失公平。
3. **基线可比性优先**：基线（含生产模型的历史评估）均为随机分层口径，主门槛必须同口径才可判定 G1。

**泄漏对照组（设计内的稳健性检查）**：P1 增加 `source_session` 列后，P4/P6 用 `StratifiedGroupKFold(5)`（按会话分组）对** finalist 们与基线重训版**复评 top-3（分组 CV 口径，非留出）。判定规则：
- 分组口径下基线与候选的**相对排名不变** → 随机口径结论可信，正常走门槛；
- 排名翻转 → 标注"泄漏敏感"，强制升级 Tier 2 人工评审，附两口径完整数字。

**不做时序切分的理由**：数据无跨场次全局时间轴意义（19 场战斗录制时间跨度 4 个月，场次间无顺序依赖）；"按时间切分"在此数据结构下退化为"按会话分组"的特例，已由分组对照覆盖；且时序切分同样面临稀有类整类缺失问题。

### 3.4 类别不平衡处理

- 沿用现有两级防线：cleaner 的未知动作过滤 + `train_lgbm` 的类频 ≥3 过滤（AutoML 侧同样调用 `load_ml_dataset`，口径一致）。
- lgbm/xgboost 保留 `class_weight='balanced'` 语义（FLAML custom_hp 中放开/默认启用该参数）；MLP 由 wrapper 内均衡采样实现（已锁定）。
- 评估报告同时给 macro/micro top-3，macro 作诊断记录，不设门槛（避免过度约束）。
- 本实验**不引入**新的重采样/代价敏感策略（超范围，留待 P6 模型工程化）。

---

## 4. 目录 / 文件结构规划

### 4.1 新增文件

```
BlackDragon/
├── configs/
│   └── automl_experiment.json        # 实验配置（seed/time_budget/estimator 约束/特征 run 定义）
├── requirements-experiment.txt       # flaml==2.6.0 / xgboost==pin / psutil==pin（仅实验环境）
├── scripts/
│   ├── train_automl.py               # FLAML 搜索 CLI（dev-only，不进 EXE）
│   ├── benchmark_model.py            # 4 指标基准 CLI（基线/候选通用）
│   ├── export_model.py               # 模型导出 CLI（--adopt 受保护操作，见第 5 节）
│   └── build_exe.ps1                 # [既有]
├── src/model/
│   ├── dataset.py                    # load_ml_dataset / make_holdout_split（自 train_lgbm 提取）
│   ├── features.py                   # FeatureBuilder：数值编码 + 派生特征（训练/导出共用，无 flaml 依赖）
│   ├── mlp_learner.py                # BalancedMLPClassifier + OneHot Pipeline wrapper（pickle 可导入性要求 ⇒ 放 src/ 而非 scripts/）
│   └── predictor.py                  # [既有，零改动]
├── tests/
│   ├── test_dataset_split.py         # golden 索引一致 + source_session additive
│   ├── test_features.py              # 派生正确性 / 词表确定 / fit-transform 分离防泄漏
│   ├── test_automl_metric.py         # top-3 metric 手算对照 + FLAML 契约
│   ├── test_train_automl.py          # integration 标记，mini budget 端到端
│   ├── test_model_export.py          # 无 flaml 加载 / ActionPredictor 兼容 / 确定性
│   └── test_benchmark_model.py       # schema / 数值正确性回归
└── experiments/                      # 运行产物（.gitignore 新增）
    └── automl_YYYYMMDD_HHMM/
        ├── smoke_report.md           # P0 冒烟记录
        ├── runA/ runB/               # FLAML log csv + run_manifest.json + best_config
        ├── holdout_cache.csv         # 留出集缓存（+SHA-256）
        ├── candidates/               # 导出的候选模型（临时，最终产物拷贝到 models/）
        └── reports/                  # baseline.json / candidate_*.json / comparison.md
```

### 4.2 模型产物位置（详设见第 5 节）

```
models/
├── fatalis_ai_model.pkl              # 生产路径（全程保护，采纳 commit 之外零写入）
├── fatalis_ai_model.pkl.bak          # [既有轮换机制]
├── fatalis_ai_model_automl.pkl       # AutoML 导出产物（独立命名）
└── fatalis_ai_model_automl.meta.json # sidecar 元数据
```

### 4.3 现有文件改动点清单

| 文件 | 改动 | 风险控制 |
|------|------|---------|
| `train_lgbm.py` | 过滤+切分内联逻辑 → 调用 `src/model/dataset.py`（行为零变化） | `tests/test_train_lgbm.py` 5 项 + golden 索引测试 |
| `data_cleaner.py` | 输出增量 `source_session` 列 | 新旧数据集特征列逐行一致校验；`test_data_cleaner.py` 更新列断言 |
| `.gitignore` | 新增 `experiments/` | — |
| `requirements.txt` | **不改**（除非 P7 采纳 xgboost 胜者，独立评审） | 运行时零新增依赖原则 |
| `build/*.spec` | **默认不改**；仅采纳时按 P7 处理 | 文件名不变 ⇒ datas 零改动最优 |
| `launch.py` / `src/model/predictor.py` / `ai_engine.py` | **零改动**（AutoML 不接入 `--pipeline`；导出对象对 ActionPredictor 透明） | 范围守卫 |
| `data/ML_Ready_Dataset.csv` | P1 重新生成（+source_session 列） | 确定性校验 + `.bak` 已有轮换 |

---

## 5. 模型产物与持久化方案

### 5.1 导出格式

- 格式：`joblib.dump(Pipeline([FeatureBuilder, 原生 estimator]), path)` —— 仅依赖 joblib/sklearn/lightgbm（/xgboost 视胜者），**零 flaml 导入需求**。
- 接口契约：`predict_proba(DataFrame[6 列, 4 列 category dtype])` + `.classes_` —— `ActionPredictor`（及 legacy `ai_engine.py`）不改一行即可加载。

### 5.2 命名与元数据

- 主产物：`models/fatalis_ai_model_automl.pkl`。
- Sidecar：`models/fatalis_ai_model_automl.meta.json`：`run_id、数据集 SHA-256、特征 run（A/B）、FLAML best_config、CV top-3、holdout 报告路径、sklearn/lgbm(/xgb) 版本指纹、FeatureBuilder 词表版本、导出时间、提取路径（提取/重训）`。

### 5.3 生产路径保护机制（三层）

1. **物理隔离**：`export_model.py` 与 `train_automl.py` 的写路径白名单只含 `fatalis_ai_model_automl*` 与 `experiments/`，代码层面不存在写 `fatalis_ai_model.pkl` 的语句（测试断言这一约束——`test_model_export.py` 增加"导出路径不含生产文件名"检查）。
2. **显式采纳**：切换生产模型只经 `export_model.py --adopt`（或独立小脚本）：前置校验对应 benchmark 报告存在且 G1–G6 全过 → 按 `train_lgbm.py` 现有机制 `.bak` 轮换 → 拷贝 → 触发全量测试提示；采纳为**独立 commit**，可单独 revert。
3. **回滚程序**：恢复 `.bak` → 冻结冒烟（P7 已演练）→ 记录在采纳报告；`.bak` 轮换链保持单代（与现状一致，避免体积膨胀）。

### 5.4 xgboost 胜出的特殊规则

若胜者为 xgboost：其 pickle 运行时需要 `import xgboost` → 新增运行时二进制依赖（含 `libxgboost.dll`）。规则：先测 wheel 安装体积与 EXE 包增量 → G6（≤300MB）通过且冻结冒烟通过方可采纳；否则在满足全部门槛的候选中取**非 xgboost 的次优**（记录差距数字入 ADR，供未来包体预算放宽时复评）。

---

## 6. 测试计划

纳入现有 pytest 体系（`pytest.ini`：`slow / integration / smoke` 标记已定义；conftest 有 `pipeline_workdir` 等共享 fixture；CI Windows+Ubuntu 双平台）。所有新测试保持默认套件秒级可跑（mini 数据 + 极小预算），重活打 `integration`/`slow` 标记。

| 测试文件 | 关键测试点 | 标记 |
|----------|-----------|------|
| `test_dataset_split.py` | ① golden：重构后 train/holdout 索引与重构前逐位一致（SHA-256 断言）；② `source_session` additive（6 特征列+label 不变）；③ 类频≥3 过滤行为不变；④ 小数据集分层降级分支 | 默认 |
| `test_features.py` | ① sin/cos 周期正确（±180° 连续）；② 分箱边缘/频次表 **fit 于 train、transform 于新数据**（防泄漏：train 与 holdout 分别 transform 结果不同即通过）；③ 词表确定（枚举全集固定、未见值 → -1 哨兵）；④ 输入 category dtype DataFrame 契约 | 默认 |
| `test_automl_metric.py` | ① top-3 metric 与手算对照（构造已知概率矩阵）；② 返回 `(name, value, True)` 契约；③ custom_hp 约束表加载与上限校验 | 默认 |
| `test_train_automl.py` | 合成数据 + `time_budget_s≈20` + 2 learner 端到端：产物（manifest/log/best_config/导出 pkl）齐全 | integration |
| `test_model_export.py` | ① 子进程屏蔽 flaml 后 load + 推理成功；② 4 家族（lgbm/xgb/rf/mlp）mini stub 各过 `ActionPredictor.predict()` 兼容断言（含 `classes_` 存在、概率合法）；③ 同输入 1000 次逐位一致；④ 哨兵类别输入不崩溃；⑤ 导出路径不含生产文件名（保护机制回归） | 默认 |
| `test_benchmark_model.py` | ① 报告 schema 键齐全/数值有限；② top-3 计算正确性；③ 同输入两次运行结果一致（回归保护）；④ mini 模型全指标跑通 | 默认 |
| `test_data_cleaner.py`（改） | 新列 `source_session` 断言；既有 19 项语义不变 | 默认 |
| `test_train_lgbm.py`（不改） | 5 项既有测试 = 重构回归主力 | 默认 |

冻结/打包验证不在 CI 自动化（沿用仓库 `tests/manual_checklist.md` 人工清单惯例），在 P7 执行并留档。

**验收线**：全量套件（581 + 新增）全绿；总覆盖率不低于现状 94%（新模块不拉低）。

---

## 7. 风险清单与缓解措施

| ID | 风险 | 概率 | 影响 | 级别 | 缓解措施 | 触发条件/预案 |
|----|------|------|------|------|---------|--------------|
| R-01 | FLAML 2.6.0 与 pandas 3.0.2 / numpy 2.4.4 不兼容（内部 API 依赖旧版行为） | M | H | 🔥 Critical | P0 冒烟硬闸门（7 项清单）；统一数值编码使 FLAML 输入面最小化 | 冒烟失败 → 评估 FLAML 补丁版/降级 pandas 不可行（钉版）→ 启用备选 Optuna 5.0（已确认的备选，仅单目标复刻本方案） |
| R-02 | FLAML 内部类别编码与生产 category dtype 输入不一致（导出模型线上行为 ≠ 搜索期行为） | M | M | ⚡ High | 统一数值编码 + FeatureBuilder 单一事实源；兼容测试 ② | 兼容断言失败 → 检查词表映射，禁止在导出层做第二次编码 |
| R-03 | xgboost 胜出 → 运行时新增二进制依赖，EXE 体积/打包风险（"零依赖"仅对 sklearn/lgbm 家族成立） | M | M | ⚡ High | 5.4 特殊规则：体积实测 → G6 门槛 → 冻结冒烟 → 次优回退 | 包体 > 300MB 或 DLL 打包失败 → 门槛内取次优，ADR 记录差距 |
| R-04 | MLP 打不过 LGBM（数千样本） | H | L | Medium | 预期管理（写入目标）：MLP 仅贡献多样性；决策看 overall best | 无需预案——不构成失败 |
| R-05 | 派生特征泄漏（频次/分箱用了全量数据） | M | M | ⚡ High | FeatureBuilder 强制 fit/transform 分离；`test_features.py` ② 显式防泄漏断言 | CI 拦截 |
| R-06 | 留出集被多候选复用产生选择偏置 | M | M | Medium | 排序看 CV、终评看 holdout；+3.0pp 采纳线覆盖噪声；finalist 3 种子复评（Tier 2 时强制） | Tier 2 裁决附种子复评结果 |
| R-07 | 小数据高方差 / 稀有类（46 类、10 类 <10 样本） | M | M | Medium | 分层切分 + ≥3 过滤沿用；macro/micro 双报告；不引入新采样（超范围） | 若 B_top3 < 30% → 报告标注"样本量不足"警示，门槛仍相对判定 |
| R-08 | FLAML pickle 提取失败（对象图引用 flaml 内部类） | L | M | Medium | 提取主路径 + 确定性重训备选（差异 ≤0.5pp 才接受） | 备选也不行 → 该候选弃权，取可导出的次优 |
| R-09 | P1 重构破坏现有训练行为 | L | H | ⚡ High | 零行为变更原则 + golden 索引测试 + `test_train_lgbm.py` 5 项回归 | 任一失败即停，修复后才继续 |
| R-10 | 训练超时侵占开发机 | M | L | Low | `time_budget_s` 硬限；后台执行；Run B 提前终止规则（P6 步骤 1） | 超 90min 自动截断，用已有 best 继续 |
| R-11 | 基线模型与当前数据集不匹配（生产模型来自旧数据快照） | M | L | Low | P3 步骤 2 基线复现性测量；门槛以生产模型实测为准（被替换对象） | 偏差大 → 报告注明两个口径，门槛取生产模型口径 |
| R-12 | benchmark 环境（无游戏负载）与实战（CPU 被游戏抢占）差异 | M | L | Low | 标称口径声明；p95 ≤20ms 绝对上限留足抢占余量 | 可选：实战 spot check（游戏运行时人工观测 overlay 延迟） |

---

## 8. 验收清单（合并回 main 前必须全部满足）

**通用（无论采纳与否）**：
- [ ] 1. 全量测试套件（581 既有 + 全部新增）通过；总覆盖率 ≥ 94%。
- [ ] 2. P0 冒烟报告 7/7 通过（`experiments/.../smoke_report.md` 存档）。
- [ ] 3. `baseline_report.json` 产出且含六个锚点值（B_top1/B_top3/B_p95/B_rss_delta/B_size + 数据集 SHA-256）。
- [ ] 4. 决策矩阵（`comparison.md`）产出：G1–G8 逐项判定 + 分组 CV 对照列 + Tier 判定。
- [ ] 5. 生产模型路径全程未被覆盖（`models/fatalis_ai_model.pkl` mtime/git 证据）；AutoML 产物独立命名 + `.meta.json` 齐全。
- [ ] 6. 导出模型通过"无 flaml 环境"加载验证 + `ActionPredictor` 兼容断言（4 家族）。
- [ ] 7. ADR（采纳或不采纳均需）写入 `obsidian/docs/architecture/`；memory-bank（activeContext/progress/changelog）与 `CHANGELOG.md` 已更新。
- [ ] 8. PR 评审通过并合并；`feature/automl-experiment` 分支清理；文档与实际交付一致（偏差已记录）。

**采纳时附加**：
- [ ] 9. 采纳 commit 独立（模型替换 + `.bak` 轮换），回滚程序已演练并留档。
- [ ] 10. 双 EXE 构建成功 + 冻结回归全过（`--pipeline` exit 0、overlay 加载新模型、干净机冒烟）。
- [ ] 11. 包体积 ≤ 300MB 实测记录；若涉及 `requirements.txt` / spec 变更，已独立评审。
- [ ] 12. `README.md` 指标数字更新。

---

## 附录 A：已锁定决策速查（来自用户确认，不重新论证）

| 决策项 | 内容 |
|--------|------|
| 框架 | FLAML 2.6.0（BlendSearch/CFO）；备选 Optuna 5.0（仅多目标时） |
| 搜索空间 | `lgbm, xgboost, rf, extra_trees, mlp(自定义 @register_learner + OneHot Pipeline + 均衡采样)` |
| 优化指标 | 自定义 top-3 accuracy callable（`X_val, y_val, estimator, labels` 签名），top-1 并行记录 |
| 特征 | 6 特征无条件锁定；派生候选（sin/cos 角度、distance 分箱、distance×enrage、posture×phase、prev_action 频次）两 run 对比人工决策 |
| 超参约束 | lgbm ≤400 树/127 叶/深 9；xgb ≤400 树/深 8；rf/et ≤500 树/深 16 |
| 评价指标×4 | top-1 / top-3 / CPU·内存 / 端到端时延（测量口径见 P2） |
| 环境 | Windows 原生，Python 3.12.6，pandas 3.0.2 / numpy 2.4.4 / sklearn 1.8.0 / lgbm 4.6.0 钉版，PyInstaller 6.21.0 |
| 分支 | `feature/automl-experiment`；AutoML 产物独立文件名，达标前不覆盖生产模型 |

## 附录 B：工作量与里程碑汇总

| 阶段 | 内容 | 工作量 | 机器时间 | 前置 |
|------|------|--------|---------|------|
| P0 | 环境准备与依赖冒烟 | 0.5d | ~0.1h | — |
| P1 | 共享数据模块 + session 标注 | 0.5–1d | ~0.1h | P0 |
| P2 | benchmark 脚本 | 1d | — | P1 |
| P3 | 基线补测 | 0.5d | 0.5h | P2 |
| P4 | AutoML 训练脚本 | 1–1.5d | — | P0+P1（可与 P2/P3 并行） |
| P5 | 导出与兼容验证 | 1d | — | P4 |
| P6 | 候选训练与对比 | 0.5d | 2–4h | P3+P5 |
| P7 | EXE 打包适配（条件） | 0.5–1d | ~1h | P6=采纳 |
| P8 | 决策与合并 | 0.5d | — | P6/P7 |
| **合计** | | **6–8 人日** | **4–6h** | |
