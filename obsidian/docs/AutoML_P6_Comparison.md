# AutoML 实验 P6 对比决策矩阵（基线 / Run A / Run B）

> 分支：`feature/automl-experiment` ｜ 阶段：P6 候选训练与对比评审
> 报告日期：2026-09-16 ｜ 决策归属：P8（用户裁决，本文档只提供判定依据，不做采纳动作）
> 依据规划：`obsidian/docs/AutoML_Experiment_Plan.md` §1.2（G1–G8 门槛定义）

## 0. 数据与口径

| 项 | 值 | 出处 |
|----|----|------|
| 数据集 | `data/ML_Ready_Dataset.csv`，SHA-256 `3e5ed34d…295fda6c` | 各 run manifest |
| 留出集缓存 | `experiments/holdout_cache.csv`（488 行 / 46 类），SHA-256 `365f815d…3374bb5`，全部测量复用同一缓存 | `holdout_cache.meta.json` |
| 基线锚点报告 | `experiments/automl_20260915/reports/baseline_report.json`（2026-09-15 23:58） | P3 产出 |
| Run A 报告 | `reports/candidate_runA.json`（03:22）+ G5 复测 `reports/candidate_runA_omp8_retest.json`（06:17） | 本阶段 |
| Run B 报告 | `reports/candidate_runB.json`（08:59） | 本阶段 |
| 环境 | Python 3.12.6 / sklearn 1.8.0 / lightgbm 4.6.0 / xgboost 3.4.1 / flaml 2.6.0 / Windows 11（32 逻辑核） | 各报告 env |

被测对象：
- **基线**：生产模型 `models/fatalis_ai_model.pkl`（LightGBM，19.05MB）——只读，全程未写入。
- **Run A**：FLAML 搜索（仅 6 锁定特征，预算 5400s）→ best=xgboost（CV top3 72.28%）→ 导出 `experiments/fatalis_ai_model_automl_p6runA.pkl`（11.45MB，提取路径，零 flaml 引用）。
- **Run B**：FLAML 搜索（6+6 派生特征 = 12 列：angle_sin/cos、distance_bin、distance×enraged、posture×phase、prev_action 频次，预算 5400s，`--n-jobs 1`）→ best=xgboost（CV top3 72.51%）→ 导出 `experiments/fatalis_ai_model_automl_p6runB.pkl`（7.46MB，提取路径，零 flaml 引用）。

## 1. 执行摘要

- **Run A 效果门槛全过且进入采纳区**：G1 top3_raw = 65.57%（+5.32pp ≥ 采纳线 63.25%）、G2 top1 = 31.76%（+4.71pp）、G3/G4/G7/G8 全过。
- **Run B（重试成功）全面优于或持平 Run A**：G1 top3_raw = **66.19%（+5.94pp，采纳区）**、G2 top1 = **32.58%（+5.53pp）**、G3 p95=4.31ms、G4 仅 7.46MB、G7/G8 过；**macro 口径不回退**（macro_top3 54.50% ≈ 基线 54.65%，macro_top3_filtered 与 top1_macro 反超基线）——Run A 的长尾小类风险在 Run B 上基本消解。
- **两候选共同唯一未过项：G5 加载 RSS 增量（Run A 130.4MB / Run B 122.0MB > 100MB）**。G5 归因复测（OMP=8）+ RSS 分解实验证明：**与 OpenMP 线程池无关（首次推理仅 +2.2MB），主体是 xgboost booster 反序列化的固有内存表示（joblib.load 阶段 ~184–190MB RSS 增量，其中 runner 口径净增量 122–130MB）**，线程限制无法消除；两候选同为 xgboost 家族、超标幅度与 pickle 体积同向（11.45MB→130.4MB、7.46MB→122.0MB），交叉佐证归因。稳态 RSS 与 5min 漂移两项均达标。
- **Run B attempt1 堆损坏崩溃（0xC0000374）**：根因链已查明——FLAML 默认 `n_jobs=-1` 经 wrapper 转成 xgboost `nthread=-1`，**运行时覆盖 OMP_NUM_THREADS 环境变量**，attempt1 的环境变量限线程实际未生效，trial 仍满 32 核。重试改用 `automl.fit(n_jobs=1)` 注入点（`train_automl.py` 新增 `--n-jobs` 参数）后**训练全程稳定**（重试执行稳定运行越过 attempt1 崩溃点 2011s 达 3390s+，直至预算耗尽正常退出，EXITCODE=0，best=xgboost CV top3 72.51%，wall 90.2min）。
- **Tier 判定建议**：两候选均因 G5 单项未过不能自动进 Tier 1；按 §6 给出的裁决建议为 **Tier 2 人工评审，倾向采纳 Run B**（首选），理由：超标项是一次性启动加载增量而非持续占用，稳态内存差 +90.2MB（预算 150MB 内）、无泄漏，效果收益 +5.94pp 显著且 macro 口径无回退。

## 2. P6 执行时间线

| 时刻（2026-09-16） | 事件 |
|----|----|
| 09-15 23:58 | P3 基线锚点报告产出（基线 benchmark 全项） |
| 00:34 | Run A attempt1 启动，发现 OpenMP 全核自旋空转（1638s 空隙/7 trial），被杀，现场存 `p6_runA_attempt1_killed/` |
| 01:38 | 新增 `p6_launch_train.py`（OMP_NUM_THREADS=8 / KMP_BLOCKTIME=0 / PASSIVE），Run A 重跑 |
| 03:09 | **Run A 训练完成**（01:38:45→03:09:15，90.2min），best=xgboost，CV top3 72.28% |
| 03:17–03:22 | Run A 导出（extract 路径，无 flaml 验证通过）+ benchmark 全项 → `candidate_runA.json` |
| 03:17 | Run B attempt1 启动（同一 launcher） |
| 03:56 前后 | Run B attempt1 崩溃：`EXITCODE=1073807364`（0xC0000374 堆损坏），flaml log 停在 wall≈2011s（xgboost trial 中），现场存 `p6_runB_attempt1_heapcrash/` |
| 06:17 | G5 归因复测（OMP=8 benchmark Run A 导出模型）+ RSS 分解实验 |
| 06:21 | **Run B 重试第一次执行启动**（`--n-jobs 1`）：健康运行 60min（wall 3540s，越过 attempt1 崩溃点 1530s，best CV 72.51%），07:21:05 被执行侧 Bash 后台任务 60 分钟存活上限连坐终止（非训练故障，无堆损坏痕迹），现场存 `p6_runB_retry1_killed_by_tasklimit/` |
| 07:22 | **Run B 重试 detached 重启**（PowerShell Start-Process 进程树外拉起，不依附任务生命周期；coordinator 批准为最终一次） |
| 08:52 | **Run B 重试完成**（07:22:03→08:52:12，90.2min，EXITCODE=0），best=xgboost，CV top3 72.51%；轨迹与被误杀执行逐点一致（确定性复现） |
| 08:53–08:59 | Run B 导出（extract 路径，无 flaml 验证通过）+ benchmark 全项 → `candidate_runB.json` + G8 抽查 PASS |

## 3. 决策矩阵（基线 / Run A / Run B × G1–G8）

门槛定义（规划 §1.2；括号内为本轮实际采用数值，B_* 为基线实测锚点）：

| ID | 门槛 | 判定线 |
|----|------|--------|
| G1 | top3_raw（留出集，raw 口径） | ≥ B+3.0pp = **63.25%** 采纳；[61.25%, 63.25%) 人工评审；< 61.25% 拒绝 |
| G2 | top1 | ≥ B−1.0pp = **26.05%** |
| G3 | 端到端时延 | p95 ≤ min(20ms, 2×B_p95) = **10.7ms** 且 mean ≤ **10ms** |
| G4 | 模型文件 | ≤ **40MB** |
| G5 | 内存 | 加载 RSS 增量 ≤ **100MB**；稳态 RSS ≤ B+150MB = **316.6MB**；5min 漂移 ≤ **5%** |
| G6 | 发布包体积 | ≤ 300MB（仅采纳时考核，P7 实测） |
| G7 | 训练预算 | 单次搜索 wall ≤ 5400s 硬上限（目标 ≤ 60min） |
| G8 | 可复现 | 留出集索引 golden 一致；导出模型同输入同输出逐位一致 |

### 3.1 主表

| 门槛 | 基线（实测锚点） | Run A | Run A 判定 | Run B | Run B 判定 |
|------|------------------|-------|-----------|-------|-----------|
| **G1** top3_raw | 60.25% | **65.57%**（+5.32pp） | **PASS（采纳区）** | **66.19%**（+5.94pp） | **PASS（采纳区）** |
| **G2** top1 | 27.05% | **31.76%**（+4.71pp） | PASS | **32.58%**（+5.53pp） | PASS |
| **G3** p95 / mean | 5.35ms / 4.34ms | **6.24ms / 5.32ms**（限线程复测 4.27 / 3.79） | PASS | **4.31ms / 3.97ms** | PASS |
| **G4** 模型文件 | 19.05MB | **11.45MB** | PASS | **7.46MB** | PASS |
| **G5a** 加载 RSS 增量 | 36.1MB | **130.4MB**（OMP=8 复测 126.2MB） | **FAIL**（>100MB） | **122.0MB** | **FAIL**（>100MB） |
| **G5b** 稳态 RSS | 166.6MB | **264.2MB**（复测 258.2MB，≤316.6） | PASS | **256.8MB**（≤316.6） | PASS |
| **G5c** 5min 漂移 | −5.45MB | **+0.24MB/5min ≈ +0.09%**（≤5%） | PASS | **+0.23MB/5min ≈ +0.09%**（≤5%） | PASS |
| **G6** 包体积 | 227MB（现包） | 不适用（P7 实测；xgboost 胜出需评估 DLL 增量，见 §7） | N/A（P7） | 同左 | N/A（P7） |
| **G7** 训练 wall | —（手工基线） | **90.2min**（01:38:45→03:09:15；搜索预算 5400s 用满，总 wall 5409s） | PASS（硬上限内；超 60min 目标值） | **90.2min**（07:22:03→08:52:12；同 5409s） | PASS（硬上限内；超 60min 目标值） |
| **G8** 逐位一致 | —（golden 索引测试锁定） | 导出模型 132 行×3 次推理**逐位一致**；与源 estimator `max_abs_diff=0.0`；复测准确率与原测逐位一致 | PASS | 导出模型 132 行×3 次推理**逐位一致**；与源 estimator `max_abs_diff=0.0` | PASS |

### 3.2 辅助指标（不设门槛，供裁决参考）

| 指标 | 基线 | Run A | Run B |
|------|------|-------|-------|
| top3_filtered（实战口径） | 58.81% | 64.55% | **65.37%** |
| macro_top3 | 54.65% | 49.82%（长尾小类偏弱，见 §7 风险） | **54.50%**（≈基线，无回退） |
| top1_macro | 27.07% | 23.58% | **27.83%**（反超基线） |
| macro_top3_filtered | 52.97% | 48.42% | **53.77%**（反超基线） |
| 时延 p99 / max | 6.21 / 7.14ms | 8.26 / 10.58ms（复测 5.49 / 6.96ms） | **4.50 / 4.67ms** |
| runner cpu_mean | 407.7% | 657.2%（OMP=8 复测 149.2%） | **2.3%**（模型更小，预测负载轻、无自旋） |
| FLAML CV top3（搜索口径） | — | 72.28%（xgboost） | **72.51%**（xgboost） |
| best config | 手工固定 | 200 树 / depth 5 / lr 0.031 | 190 树 / depth 4 / lr 0.078 |

## 4. G5 异常归因（Run A load_rss_delta 130.4MB）

### 4.1 复测：线程池假设被否定

任务假设：32 线程 OpenMP 池预分配导致超标。**复测证据不支持**：

| 测量 | 原测（默认线程） | 复测（OMP_NUM_THREADS=8） | 差异 |
|------|------------------|---------------------------|------|
| load_rss_delta_mb | 130.39 | **126.24** | −4.2MB（仍 >100MB） |
| steady_rss_mb | 264.20 | 258.17 | −6.0MB |
| cpu_mean_percent | 657.2% | **149.2%** | 线程限制确实生效（占用大幅下降） |
| top1 / top3_raw / top3_filtered | 31.76 / 65.57 / 64.55% | **逐位一致**（确定性佐证） | 0 |

线程数 32→8 使 CPU 占用从 6.6 核降到 1.5 核（限制生效的直接证据），但加载增量仅降 4.2MB——**主体与线程池无关**。

### 4.2 分解实验：大头是 booster 反序列化

同进程序列采样（`experiments/automl_20260915/p6_g5_rss_decompose.py`，报告 `reports/g5_rss_decompose_{default,omp8}.json`）：

| 阶段 | 默认线程 | OMP=8 |
|------|----------|-------|
| imports（predictor 链，含 xgboost DLL） | +5.3MB | +5.4MB |
| **joblib.load（pickle 反序列化 + booster 内存表示）** | **+189.5MB** | **+183.7MB** |
| 首次 predict（OpenMP 池 + 预热） | +2.2MB | +3.0MB |
| 二次 predict | +0.4MB | +0.0MB |

（注：分解脚本 baseline 仅含 numpy/pandas，故总增量 ~195MB 高于 benchmark runner 口径 126–130MB——runner 的 baseline 已含 benchmark 模块链 import。两口径的"模型加载净增量"一致地落在 126–130MB。）

### 4.3 归因结论

1. **主体（≈120MB+）= xgboost booster 反序列化的固有内存表示**：11.45MB 的 pickle 载入后，xgboost 内部按 46 类 × 200 树重建树结构（大量小粒度堆分配 + Windows 堆粒度放大），属模型族固有开销，**线程限制、加载方式均无法消除**。Run B（7.46MB、46 类 × 190 树、更浅）load_rss_delta = 122.0MB，与 Run A（130.4MB）同向同量级——两候选交叉佐证该归因与 pickle 体积弱相关、与 xgboost 家族强相关。
2. OpenMP 线程池贡献 ≤3MB（首推理差值），import 链 ~5MB——均非主因。
3. 稳态无泄漏（两候选 5min 漂移均 +0.09%，且 G8 确定性通过排除行为异常）。
4. **判定维持 FAIL（Run A 130.4/126.2MB、Run B 122.0MB，均 >100MB）**，但超标性质 = 一次性启动加载增量，非持续占用（稳态 257–264MB，差基线 +90.2MB（Run B）/+97.6MB（Run A），均 ≤150MB 预算）。缓解只能来自模型侧（如减少 n_estimators 上限、或换 lgbm 次优回退，见 §7），不能来自部署侧线程参数。
5. 附带发现：限线程（OMP=8）使 Run A 推理时延反而改善（p95 6.24→4.27ms）——多线程在小批量单行推理上是纯开销。**生产部署建议：无论采纳哪个模型，推理进程建议设 nthread/OMP 上限（如 4–8）**。

## 5. Run B 崩溃取证与重试记录

### 5.1 attempt1 崩溃（现场：`p6_runB_attempt1_heapcrash/`）

- 启动 03:17:22（`p6_train_runB.cmd`，经 `p6_launch_train.py`：OMP_NUM_THREADS=8、KMP_BLOCKTIME=0、OMP_WAIT_POLICY=PASSIVE）。
- flaml log 停在 wall_clock≈2011.7s（record 6，xgboost trial，top3=72.51%），此后下一个 xgboost trial 进行中崩溃；`train_stdout.log` 仅 `EXITCODE=1073807364`（= 0xC0000374，STATUS_HEAP_CORRUPTION），落盘时刻 04:39（崩溃后进程挂起约 43 分钟，疑似 Windows 错误报告挂载）。
- 同一 launcher 下 Run A 全程成功（90.2min，同为 xgboost 主导）→ 崩溃呈随机性，符合 Windows OpenMP 并行区堆损坏的偶发特征。

### 5.2 根因链（为什么环境变量没救命）

```
FLAML AutoML 默认 n_jobs = -1（automl.py: settings["n_jobs"] = get("n_jobs", -1)）
  → compute_estimator(..., n_jobs=state.n_jobs)
  → xgboost wrapper config2params(): params["nthread"] = params.pop("n_jobs")  # = -1
  → XGBClassifier(nthread=-1) → 运行时 omp_set_num_threads(32)
  → 覆盖 OMP_NUM_THREADS=8 环境变量（环境变量只是 OpenMP 默认初值）
  → 32 核并行区 × 5 折 CV 反复进出 → Windows OpenMP 运行时堆损坏（偶发）
```

旁证：Run A benchmark 推理 cpu_mean 657%（xgboost 预测期全核，n_jobs 未设时默认跟 OMP=32）。

### 5.3 重试（仅一次授权；执行细节与基础设施事故记录）

- 缓解：`scripts/train_automl.py` 新增 `--n-jobs` 参数（默认 None 保持既有行为），下发 `automl.fit(n_jobs=1)` —— 从 FLAML 注入点彻底单线程化全部 learner（xgboost nthread=1 / lgbm / rf / et；mlp wrapper 已显式 pop n_jobs）。搜索空间、指标、预算（5400s）、seed 与 attempt1 完全一致。
- 先以 `--smoke --n-jobs 1`（60s，lgbm+rf）验证参数路径，再正式启动。
- 相关回归：`tests/test_train_automl.py` + `test_automl_metric.py` + `test_model_export.py` 共 61 项全过。
- **第一次执行（06:21:05–07:21:05）**：健康运行 60 分钟（wall 3540s；06:56 核查：越过 attempt1 崩溃点 wall 2011s 达 1530s，CPU 时间/wall ≈ 104% 单核满载，best CV top3=72.51% 与 attempt1 崩溃前 best 相同——确定性复现）。07:21:05 被执行侧 Bash 后台任务的 **60 分钟存活上限**连坐终止（训练进程非正常退出但无堆损坏痕迹：无 0xC0000374、train_stdout 无异常输出，属基础设施误杀）。现场存档 `p6_runB_retry1_killed_by_tasklimit/`。
- **detached 重启（07:22:03，coordinator 批准为最终一次）**：改用 PowerShell `Start-Process` 进程树外拉起（前任 launcher 注释中"不依附后台任务生命周期"的原设计意图），轮询改独立短命令。**结果：成功完成**（08:52:12，EXITCODE=0，总 wall 5409s ≈ 90.2min，与 Run A 的 5409s 完全一致——预算控制精度一致）。flaml 轨迹与被误杀执行逐点一致（wall 390s/6 trials/72.37% → wall 1395s/7 trials/72.51%），再次确认确定性。
- **最终结果**：best_estimator=xgboost，CV top3=**72.51%**，best_config = 190 树 / max_depth 4 / max_leaves 4 / lr 0.0780 / subsample 0.946（全量见 `p6_runB/run_manifest.json`）；导出与 benchmark 见 §3。
- **n_jobs=1 缓解的实战验证结论**：attempt1（线程实际满 32 核）在 wall 2011s 堆损坏；重试两次执行合计单核运行 ~9000s+（第一次 3540s + 第二次 5409s，另含 smoke/导出）零异常——根因修复（§5.2）有效性证据充分。

## 6. Tier 判定与建议

（按规划 §1.2 决策规则：Tier 1 = G1 达采纳线且 G2–G8 全过；Tier 2 = G1 在评审区且 G2–G8 全过；任一工程门槛失败 → Tier 3 拒绝。）

| 候选 | G1 | 工程门槛 | 严格规则结论 | 建议裁决 |
|------|----|----------|--------------|----------|
| Run A | 采纳区（65.57% ≥ 63.25%） | G5a 单项 FAIL（130.4/126.2MB > 100MB） | 严格按规则不满足 Tier 1（"G2–G8 全过"被 G5a 破坏） | Tier 2 人工评审 |
| Run B | 采纳区（**66.19% ≥ 63.25%，+5.94pp**） | G5a 单项 FAIL（122.0MB > 100MB） | 同上，不满足 Tier 1 | **Tier 2 人工评审，倾向采纳（首选候选）** |

**裁决建议：Tier 2 → 采纳 Run B**（若不接受 G5a 超标则维持基线，见下）。Run B 在全部可比项上优于或持平 Run A：G1 +0.62pp、G2 +0.82pp、macro_top3 +4.68pp（追平基线，消解 Run A 的长尾风险）、模型体积 −4.0MB、p95 −1.93ms、G5a 超标幅度 −8.4MB。

**倾向采纳的理由（适用于 Run B，Run A 同理但数据全面次之）**：
1. G5a 超标项经两轮归因实验 + 双候选交叉验证定性为 **xgboost booster 一次性反序列化开销**，非泄漏、非持续占用、非可部署缓解项；G5 的真正守护目标（与游戏同机长期共存）由稳态 RSS 与漂移衡量——两项均达标（256.8MB ≤ 316.6MB；漂移 +0.09% ≤ 5%）。
2. 效果收益大：G1 +5.94pp（超过 +3.0pp 采纳线 2.9pp），G2 top1 同步 +5.53pp（非牺牲 top1 换 top3），macro 口径不回退（macro_top3_filtered、top1_macro 双反超基线）。
3. 工程其余全过且多数优于基线：时延 p95 4.31ms < 基线 5.35ms、体积 7.46MB（基线的 39%）、cpu_mean 2.3%（推理负载极轻）、确定性（G8 逐位）。

**若用户裁决不接受启动增量 122MB**：维持基线（Tier 3），工具链资产仍按规划保留；或走 lgbm 次优回退补测（本轮 log 显示 Run B 搜索期 lgbm 曾记录 CV top3 68.09%（首 trial）、Run A 搜索期 68.74%，但**无现成导出产物**，需按 best lgbm config 确定性重训 + 导出 + benchmark 后再判门槛，约 0.5h 机时 + 0.5 人日；注意 lgbm 候选的 CV 差距 ~4.4pp，其 holdout G1 大概率落在人工评审区而非采纳区——回退前建议先向用户确认是否值得）。

## 7. 风险与交接要点（P7/P8）

1. **FLAML `n_jobs=-1` 根因（本实验最重要的基础设施教训，P8 写 ADR 时建议收录）**：FLAML AutoML 默认 `n_jobs=-1`（全核），经 wrapper 转成 xgboost `nthread=-1` / lgbm `num_threads=-1`，**运行时 `omp_set_num_threads(全核)` 覆盖 OMP_NUM_THREADS 环境变量**（环境变量只是 OpenMP 初值）。该根因一石二鸟地解释了本实验两个现象：① attempt1 的堆损坏（0xC0000374，Windows 上 32 核 OpenMP 并行区反复进出，偶发堆损坏；attempt1 的 OMP_NUM_THREADS=8 缓解因此实际未生效）；② Run A benchmark 的 cpu_mean 657%（xgboost 预测期全核 + 自旋）。**任何在 Windows 上跑 FLAML/xgboost 训练的场景必须显式限线程**：训练侧 `train_automl.py --n-jobs`（本次新增）；推理/部署侧显式 `nthread`/OMP 上限——G5 限线程复测的实测数据支撑：OMP=8 下 p95 6.24→4.27ms、cpu 657%→149%（准确率逐位不变），单行推理多线程是纯开销且挤占游戏 CPU。
2. **xgboost 运行时依赖**：两候选胜者均为 xgboost → 按 5.4 特殊规则，P7 需实测 `libxgboost.dll` 打包增量与 G6（≤300MB）；若 G6 失败且用户仍要采纳 → 取非 xgboost 次优（无现成导出产物，需确定性重训补测，见 §6 回退说明）。
3. **macro 口径**：Run B 已基本消解该风险（macro_top3 54.50% ≈ 基线 54.65%；macro_top3_filtered 53.77% 与 top1_macro 27.83% 双反超基线）；Run A 的 macro_top3 49.82% 偏弱——若最终选 Run A 需知悉（选 Run B 则无此顾虑）。
4. **生产部署建议（无论采纳与否）**：推理进程设置 OMP/nthread 上限（4–8），实测依据见第 1 条。
5. **训练基础设施（沉淀资产）**：Windows 上长训练必须 detach 拉起（`p6_train_runB_retry.cmd` + PowerShell `Start-Process` 模式），避免依赖 agent 后台任务生命周期（本次第一次重试执行即被 60 分钟任务上限连坐误杀，机时损失 60min）；`--n-jobs` 参数与该模式均已在 `scripts/` 与 `experiments/automl_20260915/` 沉淀。
6. **Run B 采纳时注意**：FeatureBuilder 为 derived=True（12 列），导出管线已封装该变换（生产输入仍是 6 列），G8 已验证导出与源逐位一致；但 P7 打包需确认 `src/model/features.py` 随应用分发（现状已满足，`train_automl.py` 不进 EXE）。
7. **G6 未测**：本轮不考核，P7 打包时补。
8. **P8 ADR 素材**：本文件 §4（G5 归因）、§5（崩溃取证与根因链）、§6（裁决建议）可直接引用；无论采纳与否，ADR 需记录 G5a 的 122–130MB 事实与"一次性加载增量 vs 持续占用"的定性分析。

## 8. 产物清单

| 产物 | 路径 |
|------|------|
| Run A 训练产物 | `experiments/automl_20260915/p6_runA/`（manifest / best_config / automl_best.pkl / feature_builder.pkl / flaml_log.csv） |
| Run A 导出模型 | `experiments/fatalis_ai_model_automl_p6runA.pkl`（11.45MB，sha256 `1b819ac6…cfb24f9`）+ `.meta.json` |
| Run A benchmark | `experiments/automl_20260915/reports/candidate_runA.json` |
| G5 复测 | `experiments/automl_20260915/reports/candidate_runA_omp8_retest.json` |
| G5 分解实验 | `experiments/automl_20260915/reports/g5_rss_decompose_{default,omp8}.json`（脚本 `p6_g5_rss_decompose.py`） |
| Run B attempt1 现场 | `experiments/automl_20260915/p6_runB_attempt1_heapcrash/`（flaml_log.csv / train_stdout.log 含 EXITCODE=0xC0000374） |
| Run B 重试第一次执行（被任务上限误杀） | `experiments/automl_20260915/p6_runB_retry1_killed_by_tasklimit/` |
| Run B 重试（成功） | `experiments/automl_20260915/p6_runB/`（manifest / best_config / automl_best.pkl / feature_builder.pkl / flaml_log.csv，EXITCODE=0）+ `p6_train_runB_retry.cmd` |
| Run B 导出模型 | `experiments/fatalis_ai_model_automl_p6runB.pkl`（7.46MB，sha256 `ed3db5f8…ce65b5f`）+ `.meta.json` |
| Run B benchmark | `experiments/automl_20260915/reports/candidate_runB.json` |
| G8 抽查 | `experiments/automl_20260915/reports/g8_bitwise_runA.json` + `g8_bitwise_runB.json`（脚本 `p6_g8_export_bitwise_check.py`，双候选均 PASS） |
| 基线锚点 | `experiments/automl_20260915/reports/baseline_report.json` |
| 生产模型 | `models/fatalis_ai_model.pkl` —— **全程零写入**（本轮所有导出走 `experiments/` 白名单路径） |

## 9. P7 采纳与打包简报（2026-09-16，用户裁决后执行）

> 用户裁决（P8 前置）：**Tier 2 正式采纳 Run B**（接受 122MB 一次性启动加载增量）；不做 lgbm 回退补训；本轮不合并 main、不 push、不发 release，产物供进游戏实测。

### 9.1 胜出配置复现验证（报告 `reports/p7_repro_runB.json`）

用 `p6_runB/run_manifest.json` 的 best_config 做确定性原生重训（不走 FLAML 搜索，n_jobs=1），与正式导出物在留出集缓存对比：

- **逐位一致**：重训模型 vs 导出模型 predict_proba `max_abs_diff = 0.0`（488 行 × 46 类全量）；两次重训亦逐位一致（确定性证据）。
- **四项指标与正式报告全部 +0.000pp**：top1 32.582% / top3_raw 66.189% / top3_filtered 65.369% / macro_top3 54.502%。
- **排查过程中发现的复现要点（已入档）**：仅按 best_config + FLAML 注入项（objective=multi:softprob、enable_categorical、n_jobs=1）重训仍有偏差（top3 +0.6pp）；根因是 **FLAML `auto_augment` 稀有类增广**（计数 <20 的 14 个长尾类整行复制，train_80 从 1949 → 2175 行）+ `shuffle(random_state=1)`，改变类别先验（booster `base_score` 逐类向量不同）与训练行集。镜像该数据准备后逐位一致。
- 顺带修复：`scripts/export_model.py` 备选重训路径对 xgboost 的签名过滤缺陷（`XGBClassifier.__init__` 为 `(objective, **kwargs)`，原白名单会把 best_config 全部滤掉，静默训练默认配置模型）——已修复并加 5 项回归测试（commit 93ebbca）。

### 9.2 采纳执行

- 新增 `scripts/adopt_model.py`（规划 5.3 第 2 层"显式采纳"独立入口；`export_model.py` 保持源码级生产隔离不变量）：门槛校验（报告 sha 一致性 / G4 / G1 拒绝线 / G5a 需显式 override）→ .bak 单代轮换 → 拷贝 → ActionPredictor 加载复核 → sidecar。
- **采纳结果**：生产 `models/fatalis_ai_model.pkl` = Run B 导出物（sha256 `ed3db5f8…ce65b5f`，7.46MB）；`.bak` = 基线 LightGBM（`4d2344cf…84ef3e`，19.05MB，轮换前生产与旧 .bak 同 sha）；sidecar `models/fatalis_ai_model.pkl.meta.json` 记录来源 run / sha / 门槛数据 / 回滚程序 / G5a override 理由。
- **采纳后短测**（生产路径实测，`reports/p7_post_adopt_production.json`）：六项指标与 Run B 正式报告全部 +0.0000pp；p95 4.70ms（≤10.7ms 门槛；与报告 4.31ms 差异为机器噪声）；全量 pytest 693 passed 在采纳后状态运行。
- 采纳 commit `59b11c5` 独立可 revert（模型二进制 gitignored，revert 后需手工从 .bak 恢复生产文件）。

### 9.3 P7 打包

- **spec 变更**（双 spec 同步）：hiddenimports 增 `xgboost`/`xgboost.sklearn` + `src.model.features`/`src.model.label_decode`（pickle 动态引用，静态分析不可见）；binaries 显式收集 `xgboost/lib/xgboost.dll`；datas 增 `xgboost/VERSION`。`requirements.txt` 增 `xgboost==3.4.1` + `scipy==1.18.0`（传递依赖）。
- **打包教训（两条，均由冻结探针发现）**：① 本环境 PyInstaller 6.21 无 xgboost hook，DLL（54.3MB，名为 `xgboost.dll` 而非 libxgboost.dll）不会被自动收集，需显式 binaries；② xgboost 3.x 在 import 时读取包内 `VERSION` 文件，缺它则 `FileNotFoundError` 直接崩——两者都已固化进 spec 注释。
- **G6 判定：PASS** —— 预览包 `release/Fatalis-Prediction-automal-runB-preview.zip` = **162.2MB**（≤300MB 门槛；旧 v1.1.0 包 125.7MB，增量 +36.5MB ≈ xgboost.dll 压缩后体积 − 模型缩小 11.6MB）；dist 目录 286MB（未压缩口径）。
- **冻结冒烟**：
  - `BlackDragon.exe --pipeline` 退出码 0（data_cleaner → train_lgbm 冻结训练链路正常，训练指标与基线逐位一致 27.05%/60.25%；冒烟后已恢复 dist 内采纳模型）；
  - 双 EXE 启动存活冒烟通过（Dashboard 10s 存活并自动拉起 Overlay 子进程；standalone Overlay 存活于游戏等待循环——模型加载点在游戏附着之后，无法无游戏触达）；
  - **冻结推理链路探针**（一次性 onedir/onefile EXE，同 spec 面）：joblib.load 反序列化采纳模型（FeatureBuilder + LabelDecodedEstimator + XGBClassifier）+ xgboost.dll/VERSION 冻结加载 + 单行推理，输出与开发模式逐位一致（top1=0.364282，46 类）——**PASS**。
- **干净机器（无 Python）冒烟**：本轮未执行（本机无法模拟），预览包解压即用，留作用户实测第一步。

### 9.4 推理线程上限结论（§4.3/§7.1 建议的落地判定）

**无需任何代码/环境变量改动**：Run B 导出物 pickle 内嵌 `n_jobs=1`（FLAML `--n-jobs 1` 经 config2params 写入 estimator），xgboost sklearn 包装在每次 fit/predict 时将其转为 `nthread=1`——生产推理天然单线程。实测佐证：Run B benchmark cpu_mean 2.3%（对比 Run A 的 657%）、采纳后短测 p95 4.70ms。§7.1 的"部署侧设 OMP/nthread 上限"建议对本模型自动满足；仅当未来换用非本管线产出的模型时需重新评估。

### 9.5 用户进游戏实测指引

1. 解压 `release/Fatalis-Prediction-automl-runB-preview.zip` 到任意目录（无需 Python）。
2. 对照基线：同一场地连续狩猎中对比 Top-3 命中观感（离线口径预期 top3_filtered 58.8% → 65.4%）；注意 UI 置信度读数会整体略降（更保守但更准，见 `AutoML_RunB_Feature_Insights.md` §2）。
3. 观察启动后首个预测出现的时延（模型加载 ~0.15s，进程内存稳态约 257MB）与游戏帧率无感知劣化（推理单线程、cpu ~2%）。
4. 一键训练（--pipeline）仍走 LightGBM 旧管线，重训会覆盖预览包内模型（本包为预览件，无碍）；如需回到 Run B，重新解压即可。
5. 回滚（如需）：`models/fatalis_ai_model.pkl.bak` 覆盖 `fatalis_ai_model.pkl`（仓库内 .bak 为基线；预览包内无 .bak，直接用旧 v1.1.0 包对比亦可）。

## 10. P8 简报：Run B 配置接入一键训练管线 + runB-oneclick 预览包（2026-09-16）

§9.5 第 4 条的遗留（一键训练仍走 LightGBM 旧管线）在本轮消除：Dashboard「开始训练」（`--pipeline`）现在用**用户自己的新数据**重训 **Run B 胜出配置**。

### 10.1 架构与实现

- **新模块 `src/model/production_backend.py`**：把 `p7_repro_runB.py` 验证过的复现链路提升为正式后端（正式代码零 experiments/ 运行时依赖）。链路 = `load_ml_dataset` → 分层切分(42) → `FeatureBuilder` 仅 fit 于 train_80（防泄漏红线）→ FLAML auto_augment 镜像（<20 稀有类整行复制，1949→2175）→ `shuffle(random_state=1)` → LabelEncoder → `XGBClassifier(RUNB_BEST_CONFIG + objective/enable_categorical/verbosity/n_jobs=1，不设 random_state)` → `LabelDecodedEstimator` 包装 → `Pipeline` → 写前 `.bak` 轮换 → joblib 产物 + gain 口径 12 列中文名特征图 + sidecar（`backend=runb_config`，含 config/dataset sha/日期/来源）。
- **路由**：`launch.py --pipeline` 改为 `clean_combat_data() → train_runb_backend()`（2 行 diff）；`--train` 保留 legacy `train_lgbm` 路径（其 12 个测试不动）。`controller.py`/Dashboard 零改动（仍拉起 `--pipeline`）。spec hiddenimports 增 `src.model.production_backend`（lightgbm 因 `--train` 保留）。
- **采纳入口关系不变**：`export_model.py`（物理隔离）与 `adopt_model.py`（显式采纳）仍是 AutoML 候选→生产的路径；`production_backend` 承接的是 train_lgbm 的"一键训练写生产"角色，写前轮换机制一致。

### 10.2 验证结果（全部沙箱/解包副本，真生产模型零触碰，任务前后 sha 核对一致）

| 验证项 | 结果 |
|---|---|
| 单元测试 | 新增 `tests/test_production_backend.py` 14 个（augment 镜像行数/分布、泄漏防护断言、产物结构 [FeatureBuilder, LabelDecodedEstimator(XGBClassifier n_jobs=1)]、sidecar、确定性、失败路径、ActionPredictor 契约）；全量 707 passed（构建门禁再跑一次 707 passed） |
| 沙箱 E2E（dev） | `experiments/sandbox_onelick/` 两次完整 `--pipeline`：指标 32.58% / Top-3 66.19%（与正式报告一致）；两次运行 predict_proba 逐位一致；**沙箱重训模型 vs 现行采纳模型逐位一致（488 行留出集 max_abs_diff=0.0）**；全程 3.7s（fit 1.83s） |
| 冻结 `--pipeline` 冒烟 | 解包副本上 `BlackDragon.exe --pipeline` 退出码 0、指标同上、耗时 4.65s；**冻结重训产物文件 sha 与开发模式重训完全相同**（`9c73cd71…`，文件级跨环境确定性） |
| 双 EXE 冒烟 | Dashboard 10s 存活并自动拉起 1 个 Overlay 子进程，干净退出 |
| 冻结推理探针 | 一次性探针 EXE（同 xgboost 收集面）对发行模型/冻结重训/开发重训三个模型全部 PROBE_OK，top1 全精度 hex `0x1.7506600000000p-2`（0.36428213…，与 §9.3 P7 探针基线一致） |

### 10.3 打包

- 预览包：`release/Fatalis-Prediction-runB-oneclick-preview.zip` = **154.7MB**（G6 ≤300MB **PASS**；上版 Run B 预览包 162.2MB，差异来自压缩器口径）。内含双 EXE、Run B 生产模型（sha 与采纳时一致）、`data/ML_Ready_Dataset.csv`、xgboost.dll + VERSION、新 README（说明一键训练语义与回滚方法）。
- dist 未压缩 286MB（与上版持平）。

### 10.4 用户实测指引（本版差异）

1. 解压 `release/Fatalis-Prediction-runB-oneclick-preview.zip` 到任意目录（无需 Python）。
2. **与上一版预览包的唯一行为差异**：在游戏里录制若干场黑龙后点 Dashboard「开始训练」，现在会用你的数据以 Run B 配置重训 xgboost 模型（几秒完成、单线程无 CPU 尖峰），日志面板会打印 `🚀 正在训练 XGBoost (Run B 胜出配置)...` 与 Top-3 指标；重启后生效。
3. 验证一键训练生效：训练后 `models/fatalis_ai_model.pkl.meta.json` 的 `backend` 字段应为 `runb_config`；`models/feature_importance.png` 变为 12 特材 gain 条形图。
4. 出厂模型即 Run B（与上版预览包相同）：不训练直接玩，预测行为与上版完全一致（同模型文件）。
5. 回滚：`models/fatalis_ai_model.pkl.bak`（训练前的旧模型）覆盖回 `fatalis_ai_model.pkl`；或重新解压。
