# Changelog — BlackDragon Memory Bank

> 记录每个阶段的完成事件，与根目录 `CHANGELOG.md`（版本发布记录）互补。

---

### 2026-09-16 — P6.1 AutoML 模型迁移全程：FLAML 选型 → Run B 采纳 → 一键接入 → hotfix → v1.2.0 发版

#### Phase
P6.1 AutoML Model Migration — v1.2.0 ✅（分支 `feature/automl-experiment`，4149ede..fa6545e 约 24 commits，已合并 main）

#### Completed（里程碑时间线）
- **P0–P2 实验基建**：`requirements-experiment.txt`（flaml 2.6.0 钉版，运行时零新增依赖原则）；共享数据集模块 + 会话溯源（source_session）；统一四指标 benchmark CLI（top1 / top3_raw / top3_filtered / macro_top3）；留出集缓存（488 行 / 46 类）
- **P3 基线锚点**：生产 LightGBM 基线全项实测（top3_raw 60.25%、top3_filtered 58.81%、p95 5.35ms、19.05MB）
- **P4–P5 训练与导出**：FLAML 训练 CLI（`scripts/train_automl.py`，预算 5400s）+ 零 flaml 运行时导出（提取路径：确定性重训复现 + 独立导出物）
- **P6 候选对比**：Run A（6 特征 xgboost，top3 65.57%）/ Run B（12 派生特征 xgboost，top3 66.19%）；**Run B attempt1 堆损坏（0xC0000374）根因查明**：FLAML 默认 `n_jobs=-1` 经 wrapper 转 xgboost `nthread=-1`，运行时 `omp_set_num_threads` 覆盖 OMP 环境变量 → 新增 `--n-jobs` 注入点（`automl.fit(n_jobs=1)`）后训练全程稳定（教训入 ADR-P6.1 Decision 2）
- **G5a 归因**：加载 RSS 增量 122MB（Run B）主体为 xgboost booster 反序列化固有开销（线程限制无法消除，两轮实验 + 双候选交叉验证）——**用户 Tier 2 裁决接受**（一次性启动增量，稳态 256.8MB ≤ 316.6MB 预算）
- **P7 采纳**：`scripts/adopt_model.py` 显式采纳 CLI（门槛校验 + .bak 轮换 + 加载复核 + sidecar）；Run B xgboost 成为生产模型（sha256 `ed3db5f8…ce65b5f`，7.46MB）；双 spec 打包 xgboost 运行时（xgboost.dll 显式 binaries + VERSION datas，PyInstaller 6.21 无 hook）
- **P8 一键管线接入**：新模块 `src/model/production_backend.py`（Run B 胜出配置确定性复现：分层切分 42 → FeatureBuilder 仅 fit train_80 → FLAML auto_augment 镜像 + shuffle(1) → XGBClassifier n_jobs=1 → Pipeline）；`--pipeline` 路由切换，`--train` 保留 legacy
- **Overlay 静默失败 hotfix（RC1/RC2/RC-B）**：`resolve_runtime_path()` 统一 frozen 路径解析；加载失败 logger.error + UI 橙色「⚠ AI 模型未加载」；Overlay spec 补 `sklearn.pipeline`（pickle 动态引用）；`--selftest` 永久诊断入口 + build_exe.ps1 第 7 步双 EXE selftest 硬门禁（取代存活式冒烟）
- **v3 数据安全**：`src/core/backup_chain.py` 两代备份链（.bak/.bak2 + same-sha skip）；data_cleaner 合并语义（缺席会话行保留，全量 CSV = 逐字节一致）；训练守门（摘要行 + 破坏性变更告警入 sidecar，只警告不阻塞）；训练日志 tee（train_*.log 保留 10 份）；factory_model.pkl + 原始 CSV 随包（三层回滚）
- **v1.2.0 正式发版**：版本号、CHANGELOG、README、ADR-P6.1、正式发行包 `Fatalis-Prediction-v1.2.0-windows.zip`（G6 ≤300MB PASS）、memory bank 更新、合并 main（--no-ff）

#### API
- `python launch.py --pipeline` — 一键训练改为 Run B 后端（`clean_combat_data() → train_runb_backend()`）
- `python launch.py --train` — legacy LightGBM 路径（不变）
- `--selftest`（launch.py / overlay.py / 双 EXE）— 自检诊断入口
- `BlackDragon.exe --pipeline` — 冻结一键训练（几秒完成、单线程）

#### Design Decisions
- Run B 采纳（vs Run A）：四指标全面占优 + macro 无回退 + 体积更小 + p95 更低（ADR-P6.1 Decision 1）
- G5a 122MB 超标：用户 Tier 2 裁决接受，理由固化于 sidecar g5a_override_reason（ADR-P6.1 Decision 3）
- FLAML 训练必须注入点限线程（n_jobs=1），OMP 环境变量无效（ADR-P6.1 Decision 2）
- factory_model.pkl 刻意不用 .bak 命名（出厂与上一版本不共享轮换槽位）
- pickle 引用模块（sklearn.pipeline / features / label_decode / production_backend / backup_chain）必须显式进 hiddenimports（打包三课，ADR-P6.1 Decision 6）

#### Metrics
- 留出集四指标：top1 27.05→**32.58%**、top3_raw 60.25→**66.19%**、top3_filtered 58.81→**65.37%**、macro_top3 54.65→54.50%（无回退）
- 模型 19.05→**7.46MB**；p95 5.35→**4.31ms**；推理 cpu 407.7→**2.3%**；加载 RSS 增量 +122MB（一次性，裁决接受）
- Tests: 581 → **766**（+185：automl 训练/导出/采纳/production_backend/backup_chain/合并语义/守门/selftest/路径解析/UI 提示等），全量通过；总覆盖率 86%（新增实验模块摊薄，P4 core 仍 100%）
- 发行包：~155MB zip（G6 PASS）

#### Review
- ADR：`obsidian/docs/architecture/ADR-P6.1-automl-model-migration.md`；全程记录：`obsidian/docs/AutoML_P6_Comparison.md` §1–§11
- 已知债务（未处理）：sha256 工具三处副本（scripts/ 三个 CLI vs backup_chain 正式实现）、selftest helper 双实现（overlay.py / launch.py）
- 未 push、未发 GitHub Release（用户裁决后执行）

---

### 2026-08-05 — Stratify Small-Dataset Fallback + Label Data Quality (v1.1.2)

#### Phase
P5.4 Training Pipeline — Regression Fix ✅

#### Completed
- **修复 stratify 极小数据集回归风险**（审查 Must Fix）
  - `train_lgbm.py`: `train_test_split` 前计算 `_n_samples` / `_n_classes` / `_test_size_samples`
  - `test_size_samples >= n_classes` → 保持 `stratify=y`（正常数据 2000+ samples / 40~50 classes 不变）
  - `test_size_samples < n_classes` → 降级 `stratify=None` + warning
    `⚠️ Dataset too small for stratified split: test samples=X, classes=Y. Fallback to non-stratified split.`
  - 修复前: sklearn 抛 `ValueError: test_size should be greater or equal to number of classes`
- **NaN label warning**（审查 Should Fix A）
  - `Removed N rows with empty labels.` — 不再静默丢弃
- **非数值 label 安全转换**（审查 Should Fix B）
  - `pd.to_numeric(errors='coerce')` 将 `'37'→37`、`'abc'→NaN` → 过滤 + warning
  - 修复测试暴露的隐藏 bug: 手工编辑 CSV 后整列变 object dtype，原 `int(v)` 会误杀全部数值 label

#### API
- 无公共 API 变化；`train_fatalis_ai()` 签名不变

#### Design Decisions
- 正常数据（2000+ / 40~50 classes）路径完全不变——仍用 stratify
- 降级仅发生在极小数据集，输出明确 warning（非静默 catch）
- 保持: `src/core/` 零 diff、`src/data/recorder.py` 零 diff、模型格式不变、predictor 不变

#### Metrics
- Tests: 577 → **581**（+4 net: small-dataset fallback 2 + NaN warning 1 + non-numeric warning 1）
- 全部通过: `pytest tests/ -q` → 581 passed

#### Review
- 待 reviewer 审查；需重建 EXE 使 frozen `--pipeline` 生效

---

### 2026-08-05 — Training Pipeline Bug Fix: Unknown Action Labels (v1.1.1)

#### Phase
P5.4 Training Pipeline — Bug Fix ✅

#### Completed
- **修复训练崩溃**: `ValueError: y contains previously unseen labels: [np.int64(117)]`
  - 根因: 原始 CSV 含未在 `ACTION_DB` 中定义的动作（如 117）→ 通过清洗成为 `next_action` label → `train_test_split` 无序分层时将稀有类全放入 test → LightGBM 4.6.0 LabelEncoder "unseen labels" 崩溃
  - **方案 A（清洗阶段）**: `data_cleaner.py` 过滤未在 `ACTION_DB` 中定义的 target_action，收集 `unknown_targets` 并输出 warning（具体 action_id）
  - **方案 B（训练阶段）**: `train_lgbm.py` 训练前检测未知 label，输出具体 ID + 过滤；丢弃 NaN label；空数据集优雅停止（不覆盖旧模型）
  - **防御性**: `train_test_split` 添加 `stratify=y`——保证每个 >=3 的类在 train/test 中都有实例，杜绝稀有类全入 test 的崩溃机制
  - 无 catch Exception 兜底——显式处理未知动作

#### API
- 无公共 API 变化；`train_fatalis_ai()` / `clean_combat_data()` 签名不变
- 新增 warning 输出（stdout + logger.warning）

#### Design Decisions
- 未知动作 = 不在 `ACTION_DB` 中定义的动作 ID（如 117, 118）
- 双阶段防御: cleaner 源头过滤（主）+ trainer 二次检测（兜底，防手工构造数据集）
- `stratify=y` 修复根因机制（无序分层），非只处理 117 单例
- 保持: `src/core/` 零 diff、`src/data/recorder.py` 零 diff、pipeline 架构不变、模型 .pkl 格式兼容

#### Metrics
- Tests: 569 → **577**（+8 net: cleaner unknown-filter 4 + trainer invalid-label 3 + pipeline graceful 1）
- 全部通过: `pytest tests/ -q` → 577 passed

#### Review
- 待 reviewer 审查；涉及数据管道脚本需重建 EXE（frozen `--pipeline` 已含 `data_cleaner` hidden import）

---

### 2026-08-05 — P5.4 Training Pipeline Integration (v1.1)

#### Phase
P5 Control Center (控制中心) — Training Pipeline ✅

#### Completed
- **`--pipeline` 一键训练流程**（ADR-P5.4：data_cleaner → train_lgbm，2 步骤）
  - `launch.py`: 新增 `--pipeline` flag handler——`clean_combat_data()` → `train_fatalis_ai()`；`--train` 保留向后兼容
  - `src/app/controller.py`: `start_training()` 改为 `--pipeline`（冻结模式 `[exe, --pipeline]`，开发模式 `[python, launch.py, --pipeline]`）；TrainingPanel PIPE 捕获不变
  - `build/BlackDragon.spec`: hiddenimports 新增 `'data_cleaner'`（`data_upgrade` 不纳入——数据格式已固定）
- **数据安全增强**
  - `data_cleaner.py`: 写入前备份 `ML_Ready_Dataset.csv` → `.bak`
  - `train_lgbm.py`: 显式检查输入数据集存在（clean 失败时停止）+ 写入前备份 `fatalis_ai_model.pkl` → `.bak`（训练失败不覆盖旧模型）
- **`data_upgrade.py` 处置**: 不修改、不删除——保留为独立工具（`python data_upgrade.py` 手动升级历史数据），不纳入 pipeline
- **设计文档修订**: `Training_Pipeline_Integration_Analysis.md` + `ADR-P5.4` 更新为 2 步骤 pipeline（移除 data_upgrade 依赖）

#### API
- `BlackDragon.exe --pipeline`（frozen）/ `python launch.py --pipeline`（dev）— 一键清洗 + 训练
- `--train` — 仅训练（向后兼容，不变）
- Dashboard「模型训练」按钮 → `--pipeline` 全流程

#### Design Decisions
- 双进程架构保持（P5.3 / ADR-P5.2）——pipeline 仍是 Dashboard 单子进程，Overlay 不受影响
- 不修改 P4 core（`src/core/`、`src/model/`、`src/data/recorder.py`）— 零 diff
- TrainingPanel UI 零变更——PIPE 捕获自然显示两步骤输出
- 数据安全：备份优先于覆盖（`.bak` 策略），训练失败不破坏旧模型

#### Metrics
- Tests: 559 → **569**（+10 net：新增 `tests/test_training_pipeline.py` 10 tests；修改 controller 2 个 frozen 断言 + launch +3）
- 覆盖: pipeline 调用顺序、frozen/dev 命令、clean 失败优雅、train 失败不覆盖旧模型
- P4 core 零 diff；Overlay 架构零 diff

#### Review
- 待 reviewer 审查；需重建 EXE（spec 已修改）使 frozen `--pipeline` 生效

---

### 2026-08-04 — PyInstaller Frozen Support + v1.0 Release Candidate

#### Phase
P5 Control Center (控制中心) — PyInstaller + RC ✅

#### Completed
- **PyInstaller 打包支持** — 双 EXE (`BlackDragon.exe` + `BlackDragonOverlay.exe`) 通过 `--onedir` COLLECT 构建
  - `build/BlackDragon.spec` + `build/BlackDragonOverlay.spec` — hidden imports (dearpygui, lightgbm, sklearn, pymem, src/*)
  - `scripts/build_exe.ps1` — 一键构建 (test → clean → build → merge → surface data/model)
  - Surfacing: `_internal/models/` → `dist/BlackDragon/models/` (bundled model); `_internal/data/` → `dist/BlackDragon/data/` (training dataset)
  - Frozen 路径修复: `controller.data_dir` frozen-aware; `start_training` cwd 固定到 exe 目录; `start_overlay` sibling exe spawn
  - UTF-8 编码修复: `--train` 冻 冻结启动 `sys.stdout.reconfigure(encoding="utf-8")`
  - `os.makedirs("models", exist_ok=True)` 在 `train_lgbm.py` 中确保模型输出目录存在

- **Runtime Bug Fixes**: CSV 路径 (bug #1), Training subprocess 复用 Dashboard (bug #2), Training data 缺失 #3), Model 首 首次加载 (bug #4)
- **RC Runtime Test**: 6/6 场景通过 (clean install / dashboard / overlay / data / model / training)
- **READY 更新**: LICENSE (MIT), CONTRIBUTING.md, SECURITY.md; README badges → 551 tests / 94%
- **KB v1.0**: 50 active docs + 16 legacy archived; 13 audit/build docs
- **ADR**: ADR-P5.3 status 更新为 Decided

#### Metrics
- Tests: 541 → **551** (+10 net: 7 frozen-path + dashboard UI)
- Coverage: 94% (unchanged)
- `dist/BlackDragon/` package: 227 MB (two EXEs + surfaced models/data)

#### Review
- RC tests all passed; release candidate ready

### 2026-08-04 — P5.3 Auto-Start + Recording Default (ADR-P5.3)

#### Phase
P5 Control Center (控制中心) — Auto-Start ✅

#### Completed
- **ADR-P5.3 方案 A 实施**（`obsidian/docs/architecture/ADR-P5.3-auto-start.md`）
  - `src/app/config.py`: `auto_start_overlay` 默认值 `False` → **`True`**；新增 `auto_record: bool = True`
  - `launch.py`: 启动覆盖层子进程改为 **`if config.auto_start_overlay: controller.start_overlay()`**（默认自动启动）
  - `overlay.py`: 读取共享 `AppConfig` 决定录制默认状态（`CombatStateTracker(is_recording=config.auto_record)`）；新增游戏连接**重试循环**（`_RETRY_INTERVAL=2.0`，`_MAX_RETRIES=60`）——Dashboard 启动可先于游戏，overlay 在游戏出现后自动进入工作状态
  - `src/app/controller.py`: `attach_game` 使用 `self._config.auto_record` 初始化录制状态
  - Dashboard 手动控制（start/stop overlay、toggle recording）**保持不变**

#### API
- `python launch.py` — 默认自动启动 Overlay 子进程 + Dashboard
- 配置项: `auto_start_overlay=True`（默认）、`auto_record=True`（默认），可通过 `blackdragon_config.json` 关闭

#### Design Decisions
- 双进程架构保持（P5.3 / ADR-P5.2）——overlay 仍是独立子进程，不恢复线程 Overlay
- overlay 重试循环使 launch 的"先启 overlay 后开游戏"场景无缝衔接
- 配置默认值遵循需求（auto-start + auto-record 均默认开启）；用户可显式关闭
- P4 core（`src/core/`、`src/model/`、`src/data/`、`main.py`）— **零 diff**

#### Metrics
- Tests: 532 → **541**（+9 net：新增 10，重命名 1）
- Coverage: 总体 **94%**（此前 93%）；`overlay.py` 100%；`launch.py` 36%→**86%**
- 新增测试：launch auto_start gating（3）、overlay retry（2）+ auto_record flow（2）、config defaults（2）、controller attach auto_record（2）

#### Review
- 待 reviewer 审查

### 2026-08-04 — P5.3 Dual-Process Architecture Complete

#### Phase
P5 Control Center (控制中心) — Dual-Process Overlay ✅

#### Completed
- **P5.3: Dashboard + Overlay 双进程架构** (per ADR-P5.2)
  - Reverted `src/ui/overlay.py` to P4.5 standalone design (removed P5.2 thread/queue/start/stop/show/hide command API) — `run()` is now the only lifecycle entry, blocking in the process's own main thread
  - Cleaned `AppController`: removed OverlayUI in-process lifecycle from attach_game/detach_game/shutdown; added **subprocess-based** overlay management (`start_overlay`/`stop_overlay`/`is_overlay_running`) — Dashboard launches `python overlay.py`
  - Added `overlay_script` config field (AppConfig, default `overlay.py`)
  - Created `overlay.py` — standalone overlay process entry (composition root, equivalent to main.py)
  - Rewrote `launch.py` — dual-process launcher: `controller.start_overlay()` (spawns overlay.py subprocess) + Dashboard
  - Dashboard UX: "启动覆盖层" button now launches/terminates the overlay **subprocess** (no more in-process toggle); StatusBar shows overlay process status (运行中/未启动)

#### API
- `python launch.py` — 双进程: Overlay 子进程 + Dashboard 控制中心（推荐）
- `python overlay.py` — 独立覆盖层进程
- `python main.py` — P4 standalone overlay (legacy)

#### Design Decisions
- GLFW main-thread 限制通过**进程级隔离**解决：每个进程有自己的 DPG context + 主线程
- `attach_game` 不再 import `src.ui.overlay`（dashboard 进程不创建 OverlayUI）
- `detach_game` 不终止覆盖层子进程（独立进程，用户手动关闭）
- Overlay 子进程 stdout/stderr 重定向到 DEVNULL（非交互进程）

#### Metrics
- Tests: 510 → **532** (+22 net: removed 8 P5.2 tests, added 30 P5.3 tests)
- `overlay.py` coverage: **100%**; `src/ui/overlay.py` coverage: **100%**; overall ~93%
- P4 core (`src/core/`, `src/model/`, `src/data/`) — **zero diff**
- `main.py` (P4.6) untouched

#### Review
- P5.3 implementation complete, all tests pass (MPLBACKEND=Agg)

### 2026-08-03 — P5.2 Overlay Integration Experiment (Deferred)

#### Phase
P5 Control Center (控制中心) — Experimental

#### Attempted
- **P5.2: Overlay Integration** — Three approaches tested to integrate transparent overlay with Dashboard
  - Solution A: Single DPG context + `create_viewport()` multi-viewport → widgets render only on primary viewport
  - Solution B: Overlay daemon thread + own DPG context → GLFW crash (non-main thread window creation)
  - Solution C: OverlayService + cross-thread `queue.Queue` commands → same GLFW violation
- Experiment saved as commit `6952114` (30 files, 510 tests)
- ADR written: `obsidian/docs/architecture/ADR-P5.2-overlay-process.md`

#### Root Cause
`dearpygui==2.3` uses GLFW as windowing backend. GLFW requires all `glfwCreateWindow()` calls on the main thread. DPG 2.x cannot run two windowed contexts simultaneously in one process.

#### Decision
Dual-process architecture: Dashboard and Overlay as separate Python processes. Each has its own DPG context on its own main thread. Overlay integration deferred to next iteration.

#### Metrics
- Tests: 510 (all pass, P4 core unchanged)
- Mock tests pass; real DPG on Windows fails at overlay thread creation
### 2026-08-03 — P4 Step 6 Complete + v0.5.0 Cleanup

#### Phase
P4 Architecture Refactoring (架构重构) — Complete ✅

#### Completed
- **P4.6: Integration**
  - Created `main.py` — application composition root (~85 lines)
  - Created `tests/test_main_integration.py` — 20 tests, 100% pass
  - `ai_engine.py` left untouched — retained as legacy reference + P3 test-compat entry
  - `python main.py` = new recommended entry; `python ai_engine.py` = legacy fallback
  - 385 tests total, all pass (MPLBACKEND=Agg)

- **v0.5.0 Cleanup**
  - Moved `enrage.py` → `archive/` (research tool, no test deps)
  - Moved 8 P2/P3 closure reports → `archive/legacy_reports/`
  - Updated `README.md` (badges 385/72%, project structure tree, quick start, roadmap)
  - Updated `CHANGELOG.md` (v0.4.0 + v0.5.0 entries)
  - Updated `requirements.txt` (runtime vs test dep comments)
  - Fixed `test_main_integration.py` cross-platform import (stub pymem/dearpygui for Linux CI)

#### API
- `python main.py` — P4+ composition root (connects pymem → MemoryReader → StateTracker → Predictor → Recorder daemon → OverlayUI blocking)
- `python ai_engine.py` — legacy God Class (unchanged)

#### Design Decisions
- Zero-touch `ai_engine.py`: kept frozen for P3 test imports (85 tests) + fallback
- `main.py` is pure wiring — no business logic, no global mutable state (AST-verified)
- Shared instances (MemoryReader/StateTracker/buffer/lock) created once, injected by reference
- Linux CI cross-platform: stub modules pre-installed in sys.modules before `import main`

#### Metrics
- Tests: 365 → **385** (+20)
- `main.py` coverage: **100%**
- Overall coverage: **72%**
- P4 complete: all 6 steps done, 5 modules extracted, integration wired

#### Review
- P4.6 Review: **APPROVED** (0 blockers, 2 non-blocking suggestions)
### 2026-08-03 — P4 Step 5 Complete

#### Phase
P4 Architecture Refactoring (架构重构)

#### Completed
- **P4.5: OverlayUI Extraction**
  - Created `src/ui/__init__.py`
  - Created `src/ui/overlay.py` — `OverlayUI` class (289 lines)
  - Created `tests/test_overlay.py` — 41 tests, 100% pass
  - `overlay.py` achieves **100% branch coverage**
  - `ai_engine.py` / all 4 existing P4 modules left untouched — dual-track maintained

#### API
- `OverlayUI(memory_reader, state_tracker, predictor, action_buffer, action_lock)`
- `run()` — DPG event loop with try/finally for guaranteed destroy_context
- `_compute_frame()` — pure logic, 0 DPG calls, 1:1 order match with original update_logic
- `_apply_display()` — thin DPG layer (set_value / configure_item)
- `_setup_dpg()` — DPG context + font + window + viewport + Win32 ctypes transparent overlay
- `_compute_ai_display()` — nova warning / prediction throttle / ACTION_DB formatting
- `last_action` dropped — StateTracker owns posture FSM cursor

#### Design Decisions
- Constructor: only stores 5 injected deps — zero DPG/ctypes side effects → testable without real window
- `_compute_frame` structurally verified to contain no `dpg.` calls (regex test)
- Win32 ctypes isolated to `_apply_win32_overlay()` method body — `import src.ui.overlay` cross-platform safe
- AI prediction throttle (0.5s) kept in UI layer (`_last_ai_time`) — not a game logic concern
- DPG text/color updates separated from computation → `_compute_frame` returns dict, `_apply_display` applies
- CSV column display in state_text: no `posture` field (matching original)

#### Review
- P4 Step 5 Review: **APPROVED** — 0 blockers, 1 non-blocking observation (DPG configure_item order)

#### Metrics
- Tests: 324 → **365** (+41)
- overlay.py coverage: **100%**
- 5 of 6 modules extracted (StateTracker + MemoryReader + Predictor + Recorder + OverlayUI)
### 2026-08-03 — P4 Step 4 Complete

#### Phase
P4 Architecture Refactoring (架构重构)

#### Completed
- **P4.4: Recorder Extraction**
  - Created `src/data/__init__.py`
  - Created `src/data/recorder.py` — `CombatRecorder` class (216 lines)
  - Created `tests/test_recorder.py` — 34 tests, 100% pass
  - `recorder.py` achieves **100% branch coverage**
  - `ai_engine.py` / `state_tracker.py` / `memory_reader.py` left untouched — dual-track maintained

#### API
- `CombatRecorder(memory_reader, state_tracker, action_buffer, action_lock, data_dir="data")`
- Lifecycle: `start()` (daemon thread, idempotent) / `stop()` (explicit close) / `run()` (thread target, NEVER called directly)
- Gating: `_should_pause()` — `is_recording` off OR zone != Fatalis → 1s sleep
- Frame: `_record_frame()` — MemoryReader read → action_buffer append (with lock) → CSV row
- CSV format identical to original `data_logger_thread`: timestamp, hp_percent, phase, is_enraged, distance, relative_angle, posture, action_id

#### Design Decisions
- All memory reads via **MemoryReader** (no direct pymem / pm.read_*)
- All state reads via **CombatStateTracker** (no shared_state dict) — `is_recording` / `phase` / `posture` / `is_enraged`
- Action ID appended to shared `action_buffer` under `action_lock` (Recorder is producer, UI is consumer)
- D3: single-frame exception → `logger.warning` → sleep → continue (daemon stays alive); `stop()` is the only exit
- CSV file created lazily on first successful frame (nested data_dir auto-created)
- Column list single source of truth: `CombatRecorder._COLUMNS` (test imports it to avoid drift)

#### Review
- P4 Step 4 Review: **APPROVED** (SF-1: `_should_pause()` try/except coverage parity with legacy — fixed)
- SF-1 fix: `run()` try boundary moved up 3 lines to cover `_should_pause()` → defensive parity with original `data_logger_thread` exception scope

#### Metrics
Tests: 290 → **324** (+34)
recorder.py coverage: **100%**
4 of 6 modules extracted (StateTracker + MemoryReader + Predictor + Recorder)

#### Known Environment Issue (pre-existing, NOT a regression)
- This machine's Tcl/Tk install is broken (`init.tcl` missing), so matplotlib intermittently
  falls back to TkAgg backend → flaky `test_train_lgbm.py` failure on plain `pytest`
- Reproduced WITHOUT P4.4 changes (deselecting new recorder tests still fails)
- Workaround: `MPLBACKEND=Agg pytest` → full suite green (324/324)
## 2026-08-02 — P4 Step 3 Complete

### Phase
P4 Architecture Refactoring (架构重构)

### Completed
- **P4.3: Predictor Extraction**
  - Created `src/model/__init__.py`
  - Created `src/model/predictor.py` — `ActionPredictor` class (201 lines)
  - Created `tests/test_predictor.py` — 31 tests, 100% pass
  - `predictor.py` achieves **99% branch coverage** (1 missed: defensive `if col in columns`)
  - `ai_engine.py` left untouched — backward compat maintained

### API
- `ActionPredictor(model_path)` → `predict(6 features)` → `[(class_id, prob), ...]`
- 4 static methods migrated from P3.3: `filter_probs_by_phase`, `filter_probs_by_posture`, `renormalize_probs`, `select_top_k`
- 2 constants: `_POSTURE_STAND_EXCLUDE` (15 IDs), `_POSTURE_PRONE_EXCLUDE` (37 IDs)

### Design Decisions
- Dependencies: `joblib` + `pandas` + `numpy` + lazy `src.config.actions`
- No pymem / dearpygui / threading / StateTracker / MemoryReader
- Model load failure → `_model = None` → `predict()` returns `[]`
- Returns raw (class_id, prob) tuples — ACTION_DB display stays in caller (UI)
- Feature construction (6 columns, 4 categorical) 1:1 matching original `update_logic`

### Review
- P4 Step 3 Review: **APPROVED** (0 blocking, 2 non-blocking suggestions)

### Metrics
- Total tests: 259 → **290** (+31)
- Overall coverage: 68% → **72%**
- 3 of 6 modules extracted (StateTracker + MemoryReader + Predictor)

---

## 2026-08-02 — P4 Step 2 Complete

### Phase
P4 Architecture Refactoring (架构重构)

### Completed
- **P4.2: MemoryReader Extraction**
  - Created `src/core/memory_reader.py` — `MemoryReader` class (183 lines)
  - Created `tests/test_memory_reader.py` — 27 tests, 100% pass (mock pymem)
  - `memory_reader.py` achieves **100% branch coverage**
  - `ai_engine.py` left untouched — backward compat maintained

### Design Decisions
- Encapsulates all pymem process memory reads (9 public methods)
- Single dependency: `pymem` + `src.config.offsets`
- Zero business logic — returns raw data, no phase/enrage/posture/nova decisions
- Stateless beyond constructor (no cache, no mutable internal state) → thread-safe for multi-threaded use
- `check_zone` returns raw zone_id (no Fatalis=417 check) — business logic stays in caller
- `read_enrage_state` returns (0.0, 0.0) on failure → original fallback behavior preserved
- Not yet wired into ai_engine.py — dual-track status maintained

### Review
- P4 Step 2 Review: **APPROVED** (0 blocking, 3 non-blocking recommendations)

### Metrics
- Total tests: 232 → **259** (+27)
- Overall coverage: 64% → **68%**

---

## 2026-08-02 — P4 Step 1 Complete

### Phase
P4 Architecture Refactoring (架构重构)

### Completed
- **P4.1: StateTracker Extraction**
  - Created `src/core/__init__.py`
  - Created `src/core/state_tracker.py` — `CombatStateTracker` class (156 lines)
  - Created `tests/test_state_tracker.py` — 50 tests, 100% pass
  - `state_tracker.py` achieves **100% branch coverage**
  - `ai_engine.py` left untouched — backward compat maintained

### Design Decisions
- StateTracker encapsulates all shared_state dict semantics (7 state fields + 8 methods)
- Zero external dependencies: only `math` + `src.config.actions`
- `shared_state['action_id']` confirmed dead code — dropped
- `action_buffer` + `lock` deferred to P4 Step 4 (Recorder thread coordination)
- Not yet wired into ai_engine.py — standalone module for now

### Review
- P4 Step 1 Review: **APPROVED** (0 blocking, 3 non-blocking recommendations)

### Metrics
- Total tests: 182 → **232** (+50)
- Overall coverage: 60% → **64%**

---

## 2026-08-02 — P3 Complete

### Phase
P3 Test Safety Net (测试体系)

### Completed
- P3.1–P3.5: 182 tests, 60% coverage, GitHub Actions CI
- Tag: `v0.3.0-test-safety-net`

---

## 2026-06-25 — P2 Complete

### Phase
P2 Critical Fixes (P0 修复)

### Completed
- Logging, unified constants, posture FSM, bare except sweep
- Tag: `v0.2.0-p0-fixes`

---

## 2026-06-22 — P1 Complete

### Phase
P1 Project Standardization (项目优化)

### Completed
- README, .gitignore, requirements.txt, directory structure
- Tag: `v0.1.0-project-init`
