# ADR-P6.1: AutoML Model Migration (FLAML Run B → Production)

- **Date**: 2026-09-16
- **Status**: Accepted (implemented in v1.2.0)
- **Author**: coder-pro (P8 closure)
- **Branch**: `feature/automl-experiment` (4149ede..fa6545e, 24 commits)

> **Scope**: 本 ADR 记录 AutoML 实验的最终架构决策：FLAML 选型、Run B (xgboost) 采纳、G5a 内存代价的用户裁决、`production_backend` 一键训练后端、数据合并语义与两代备份链、以及打包/冻结运行时的三条核心教训。完整实验过程与全部测量数据见 [[../AutoML_P6_Comparison|AutoML P6 Comparison]]（§1–§11），实验规划见 [[../AutoML_Experiment_Plan|AutoML Experiment Plan]]。本文件自包含决策结论与根因，面向未来读者。

---

## Context

v1.1.0 的生产模型是手工调参的 LightGBM（19.05MB，留出集 top3_raw 60.25%）。用户发起 AutoML 实验：用 FLAML 在同一数据集上搜索更强候选，经 8 道门槛（G1 效果 / G2 top1 / G3 时延 / G4 体积 / G5 内存 / G6 包体积 / G7 训练预算 / G8 逐位可复现）评审后决定是否替换生产模型，并让一键训练管线（`--pipeline`）用胜出配置重训。

实验结果：两个候选（Run A 仅 6 特征、Run B 6+6 派生特征 = 12 列）胜者均为 xgboost，Run B 全面占优，经用户 Tier 2 裁决采纳为生产模型，并完成管线接入、冻结打包修复与三个预览包迭代（v1/v2/v3），最终以 v1.2.0 正式发布。

---

## Decision 1: FLAML 作为 AutoML 搜索引擎，Run B xgboost 采纳为生产模型

### 1.1 采纳依据（四指标，同一留出集缓存 488 行 / 46 类）

| 指标 | 基线 LightGBM | Run A (xgboost) | **Run B (xgboost, 采纳)** | Run B Δ vs 基线 |
|------|--------------|-----------------|--------------------------|-----------------|
| top1 | 27.05% | 31.76% | **32.58%** | **+5.53pp** |
| top3_raw | 60.25% | 65.57% | **66.19%** | **+5.94pp** |
| top3_filtered（实战口径，硬过滤后） | 58.81% | 64.55% | **65.37%** | **+6.56pp** |
| macro_top3（长尾小类） | 54.65% | 49.82% ⚠️ | **54.50%** | −0.15pp（无回退） |

Run B 对 Run A 的全面优势：top1 +0.82pp、top3_raw +0.62pp、macro_top3 +4.68pp（消解 Run A 的长尾风险）、模型 7.46MB（Run A 11.45MB、基线 19.05MB）、p95 时延 4.31ms（基线 5.35ms）、推理 cpu_mean 2.3%（基线 407.7%）。辅助口径 top1_macro 27.83% 与 macro_top3_filtered 53.77% 均反超基线。

采纳动作经 `scripts/adopt_model.py` 执行（门槛校验 → .bak 轮换 → 拷贝 → ActionPredictor 加载复核 → sidecar），生产模型 sha256 `ed3db5f8…ce65b5f`，sidecar 记录完整来源链与门槛数据（`models/fatalis_ai_model.pkl.meta.json`）。

### 1.2 FLAML 选型理由

- 唯一同时满足"轻量（无 Ray/Dask 集群依赖）、支持 xgboost/lgbm/rf/et/mlp 多 learner、预算式搜索（5400s wall）、CV 指标可自定义（top3）"的选择。
- 实验依赖钉版于 `requirements-experiment.txt`（flaml==2.6.0, psutil），**运行时零依赖原则**：生产推理不需要 flaml——导出走"提取路径"（重训复现 + 独立导出物，无 flaml 引用）。仅当胜者为 xgboost 时（实际发生），`xgboost==3.4.1`（+ 传递依赖 `scipy==1.18.0`）按规划 5.4 进入 `requirements.txt`。

---

## Decision 2: FLAML `n_jobs=-1` 必须显式覆盖 —— 本实验最重要的基础设施教训

**根因链**（Run B attempt1 堆损坏 0xC0000374 的取证结论）：

```
FLAML AutoML 默认 n_jobs = -1（全核）
  → compute_estimator(..., n_jobs=-1)
  → xgboost wrapper config2params(): params["nthread"] = n_jobs  # = -1
  → XGBClassifier(nthread=-1) → 运行时 omp_set_num_threads(32)
  → 覆盖 OMP_NUM_THREADS=8 环境变量（环境变量只是 OpenMP 默认初值）
  → 32 核并行区 × 5 折 CV 反复进出 → Windows OpenMP 偶发堆损坏
```

同一根因解释两个现象：attempt1 训练崩溃（OMP_NUM_THREADS=8 缓解实际未生效）、Run A 推理 cpu_mean 657%（预测期全核自旋）。

**决策**：任何 Windows 上跑 FLAML/xgboost 训练的场景，线程限制必须打在 **FLAML 注入点**（`automl.fit(n_jobs=1)`，落地为 `scripts/train_automl.py --n-jobs` 参数），不能依赖 OMP 环境变量。有效性证据：重试单核运行合计 ~9000s+ 零异常（attempt1 满核 2011s 即崩）。

**附带收益**：Run B 导出物 pickle 内嵌 `n_jobs=1`，每次 predict 转为 `nthread=1` —— 生产推理天然单线程（cpu 2.3%），部署侧无需任何环境变量/代码改动。

---

## Decision 3: G5a 内存超标（122MB > 100MB）的用户裁决 —— Tier 2 采纳

两候选唯一未过项是 G5a 加载 RSS 增量（Run A 130.4MB / Run B 122.0MB > 100MB）。两轮归因实验（OMP=8 复测 + RSS 分解）证明：**主体是 xgboost booster 反序列化的固有内存表示**（joblib.load 阶段 +189.5MB 分解口径；线程限制仅降 4.2MB），与线程池无关、无法从部署侧消除；双候选同为 xgboost 家族交叉佐证。

**裁决（用户 2026-09-16，Tier 2 人工评审）**：接受 122MB 一次性启动加载增量。理由记录于 sidecar `gates.g5a_override_reason`：
- 超标性质 = 一次性加载增量，非持续占用；G5 的真正守护目标（与游戏同机共存）由稳态 RSS（256.8MB ≤ 316.6MB 预算）与 5min 漂移（+0.09% ≤ 5%）衡量，两项均 PASS。
- 效果收益 top3 +5.94pp 显著且 macro 口径无回退。
- 无泄漏（G8 逐位确定性排除行为异常）。

未来约束：若换用非本管线产出的模型（不同 booster 结构/树数），G5a 需重新评估；减小 `n_estimators` 上限是模型侧唯一的缓解杠杆。

---

## Decision 4: `src/model/production_backend.py` —— Run B 配置的一键训练后端

v1.1.0 的 `--pipeline` 走 LightGBM 旧管线，采纳后模型与训练配置脱节。新增 `src/model/production_backend.py` 将 P7 验证过的确定性复现链路提升为正式后端（正式代码零 `experiments/` 运行时依赖）：

```
load_ml_dataset → 分层切分(random_state=42) → FeatureBuilder 仅 fit 于 train_80（防泄漏红线）
  → FLAML auto_augment 镜像（<20 样本稀有类整行复制，1949→2175 行）
  → shuffle(random_state=1) → LabelEncoder
  → XGBClassifier(RUNB_BEST_CONFIG + objective/enable_categorical/n_jobs=1，不设 random_state)
  → LabelDecodedEstimator 包装 → sklearn Pipeline
  → 写 .tmp → promote_with_backup（两代链）→ joblib 产物 + gain 特征图 + sidecar(backend=runb_config)
```

关键复现要点（P7 排查成果，缺一即 top3 偏差 +0.6pp）：FLAML 的稀有类增广与 shuffle 必须镜像，否则类别先验（booster base_score）与训练行集不同。生产输入仍是 6 列原始特征，12 列派生封装在 Pipeline 内（`src/model/features.py` 随应用分发）。

**路由**：`launch.py --pipeline` = `clean_combat_data()` → `train_runb_backend()`；`--train` 保留 legacy `train_lgbm` 路径（向后兼容）。Dashboard/Controller 零改动。AutoML 候选→生产的采纳入口（`export_model.py` 物理隔离 + `adopt_model.py` 显式采纳）与本后端职责分离不变：后者承接的是 train_lgbm 的"一键训练写生产"角色。

---

## Decision 5: 一键管线数据合并语义 + 两代备份链 + 出厂模型

v3 事故（用户录 1 场新战斗点训练 → 出厂 19 会话/2444 行数据集被静默替换为 164 行单会话）暴露三个数据安全缺陷，修复如下：

1. **合并语义**（`data_cleaner.py`）：重建数据集时，现有 `ML_Ready_Dataset.csv` 中 `source_session` 不在磁盘 CSV 集合内的行**保留**，在场会话重新提取后追加；全量 CSV 在场时输出与工厂数据集**逐字节一致**（零变化保证）。远古格式（无 source_session 列）不合并，告警并留在备份链。
2. **两代备份链**（`src/core/backup_chain.py`，模型与数据集两侧共用）：`promote_with_backup(tmp, target, generations=2)` 原子提升 + `.bak`/`.bak2` 链；**same-sha skip** —— 内容不变（Run B 确定性下同数据重训产生逐位相同的模型）则完全跳过轮换，重复训练不再吃掉备份。
3. **出厂模型 `models/factory_model.pkl`**：随包分发的不可变回滚副本，训练/轮换机制永不触碰。**刻意不用 `.bak` 命名**：`.bak` 是运行时链的第一代，首次变更重训即被推进——"出厂"与"上一版本"不能共享一个槽位。包内同时分发原始战斗 CSV（~11MB）作为数据集重建保险。
4. **训练守门与可观测**（`production_backend.py` + `controller.py`）：训练输出摘要行（本次 vs 上代会话/行/类）；破坏性变更门（数据集行数 < 上代 50%、holdout < 100 行、类数降 ≥20%）**只警告不阻塞**，写 sidecar `gate_warnings`；每次训练 tee 到 `models/train_YYYYMMDD_HHMMSS.log`（保留最近 10 份）。

> **Addendum（2026-09-16 用户裁决）——反转第 3 条"随包附带原始 CSV"一半**：v1.2.0 发行包 `data/` 只附带清洗后的 `ML_Ready_Dataset.csv`，19 个原始战斗 CSV（~11MB）不再随包（`build_exe.ps1` 原 5e 步打包逻辑移除）。**理由**：压缩包体积与发行物整洁优先。**影响**：放弃"数据集从零重建"能力（下文"从随包原始 CSV 逐字节重建"路径自此仅限含原始 CSV 的 dev 仓库）；**重训安全不受影响**——第 1 条 F1 合并语义保证无论原始 CSV 是否在场，`source_session` 不在磁盘的历史会话行都从现有数据集保留，"单场数据替换"事故不会复现（发行包形态边界已有测试锁定：`tests/test_data_cleaner.py::TestMergeSemantics::test_no_raw_csvs_shipped_dataset_untouched`）。出厂回滚仍由 `factory_model.pkl` + 数据集 `.bak`/`.bak2` 链完整保障。

**回滚层级**（用户视角）：`factory_model.pkl`（出厂，任意时刻）→ `.bak`（上一代）→ `.bak2`（上上代）；数据集同理，或删 `ML_Ready_Dataset.csv*` 从原始 CSV 逐字节重建（仅限 dev 仓库——2026-09-16 起发行包不带原始 CSV，见上 Addendum）。

---

## Decision 6: 打包三课（PyInstaller 冻结运行时）

1. **pickle 动态引用对静态分析不可见**：生产模型是 `sklearn.pipeline.Pipeline[FeatureBuilder, LabelDecodedEstimator(XGBClassifier)]`，unpickle 时动态 import `sklearn.pipeline` —— PyInstaller 静态分析看不到，Overlay EXE 曾因此缺失该模块（v1 预览包 Overlay AI 区永久空白的直接原因）。同类模块（`src.model.features` / `src.model.label_decode` / `src.model.production_backend` / `src.core.backup_chain`）一律显式进双 spec hiddenimports。**规则：凡是 pickle 会引用的模块，必须在打包面显式声明。**
2. **xgboost 3.x 冻结两件套**：本环境 PyInstaller 6.21 无 xgboost hook，`xgboost.dll`（54.3MB，注意名为 `xgboost.dll` 非 `libxgboost.dll`）不会被自动收集，需显式 binaries；xgboost 3.x 在 import 时读取包内 `VERSION` 文件，缺失即 `FileNotFoundError` 崩溃，需显式 datas。均已固化进 spec 注释。
3. **`--selftest` 门禁取代存活式冒烟**：旧"存活 10s"冒烟永远测不到模型加载失败（加载点在游戏附着后/失败被静默吞噬）。`--selftest` 在真实 EXE 进程执行"路径解析 → 模型加载 → 一次 predict → exit 0/1"（import 链与生产完全一致），`build_exe.ps1` 第 7 步自动跑双 EXE selftest，任一失败即构建失败；Overlay 特意以 CWD=TEMP 运行以覆盖"frozen 路径依赖 CWD"场景。**实现陷阱**：PowerShell `& exe` 不等待 GUI 子系统进程，`$LASTEXITCODE` 是陈旧值 → 假阳性 PASS，必须 `Start-Process -Wait -PassThru` 取真实退出码。

配套的冻结可观测性修复（Overlay hotfix）：`src/app/config.py` 新增 `resolve_runtime_path()` 统一 frozen 路径解析（frozen+相对路径 → 基于 `sys.executable` 目录）；模型加载失败 `logger.error`（含 traceback）；UI 未加载时显示橙色"⚠ AI 模型未加载"（Nova 预警优先级更高）——**AI 区不再可能无提示空白**。

---

## Rejected Alternatives

| 方案 | 拒绝理由 |
|------|----------|
| 采纳 Run A | 全部可比指标次于 Run B；macro_top3 49.82% 长尾小类回退 ~5pp |
| 维持基线（拒绝 G5a 超标） | 放弃 +5.94pp 效果收益换 122MB 一次性加载增量，与用户裁决不符 |
| lgbm 次优回退补测 | 无现成导出产物，CV 差距 ~4.4pp，holdout G1 大概率仅人工评审区 |
| TrainingService 抽象层（P5.4 已拒） | 沿用结论：顺序函数调用不需要服务抽象 |
| OMP 环境变量限线程（训练期） | Decision 2 根因：运行时被 nthread=-1 覆盖，无效 |
| 部署侧 OMP 上限（推理期） | Run B pickle 内嵌 n_jobs=1，天然满足，无需改动 |

---

## Consequences

- **正面**：实战口径 top3 硬过滤 58.81% → 65.37%；一键训练几秒完成（fit ~1.8s）且单线程无 CPU 尖峰；模型体积 19.05MB → 7.46MB；数据集/模型具备三层回滚与静默数据丢失防护；冻结包有可自动门禁的自检入口。
- **代价**：启动加载 RSS 增量 122MB（一次性，用户裁决接受）；发行包 ~155MB（v1.1.0 125.7MB + xgboost.dll 增量）；FLAML 复现链的两个隐藏行为（稀有类增广、shuffle）必须永久镜像在 production_backend 中，升级 FLAML 版本时需重新核对。
- **不变量**：`--train` legacy 路径、Overlay 双进程架构（ADR-P5.2）、P4 core 接口、ActionPredictor 对外契约均未变。

---

## Implementation Summary

| 提交 | 内容 |
|------|------|
| 5646cba..52b5e96 | P0–P5：实验依赖、共享数据集模块、四指标 benchmark、FLAML 训练 CLI（--n-jobs）、零 flaml 导出 |
| 59b11c5 / 6ebbbc6 | Run B 采纳（adopt_model.py CLI + 门禁校验） |
| 928fd12 | 双 spec 打包 xgboost 运行时（P7） |
| 03bfebe / 2e3cf30 | production_backend 模块 + `--pipeline` 路由切换 |
| 623af7c / 8d50d61 / 9c23bdb | Overlay hotfix（可观测性 + frozen 路径）+ selftest 门禁 |
| 8d2d6fc / 8eefff2 / 8982b6e / 87ff68a / fa6545e | v3 数据安全：两代备份链、合并语义、训练守门、训练日志、factory model + 原始 CSV 随包 |

测试：581（v1.1.0）→ **766**（v1.2.0），全量通过。

## Known Debt / Follow-ups（本轮不动）

1. **sha256 工具三处副本**：`scripts/adopt_model.py` / `scripts/benchmark_model.py` / `scripts/train_automl.py` 各自实现 `sha256_file`（正式实现已在 `src/core/backup_chain.py`）→ 统一改为 import。
2. **selftest helper 双实现**：`overlay.py _selftest()` 与 `launch.py` 内联逻辑各自维护 → 提取共享模块。
3. 版本号无常量定义（体现在 README/包名/CHANGELOG 文本）→ 可考虑引入单一 `__version__`。
4. 推送与 GitHub Release：用户未授权，待裁决。

## Next Steps

1. ✅ v1.2.0 正式发行包（本 ADR 所属 P8 收尾）
2. ✅ 合并回 main（--no-ff，保留 feature 分支）
3. ⬜ push / GitHub Release（用户裁决后）
4. ⬜ 用户进游戏长线实测（对照离线指标）
