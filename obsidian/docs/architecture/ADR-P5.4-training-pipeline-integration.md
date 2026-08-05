# ADR-P5.4: Automated Training Pipeline Integration

- **Date**: 2026-08-05
- **Revised**: 2026-08-05 — 移除 `data_upgrade.py` 依赖；Pipeline 从 3 步骤简化为 2 步骤
- **Status**: Decided (revised)
- **Author**: Architect

> **Revision Note**: 原始设计包含 `data_upgrade` → `data_cleaner` → `train_lgbm` 三步骤。因用户数据格式已固定为 v2（含 `phase`/`is_enraged` 列），不再需要运行时数据升级。`data_upgrade.py` 保留为独立工具脚本，但**不纳入自动化 pipeline**。
>
> **Related Analysis**: 详细技术调研见 [[../Training_Pipeline_Integration_Analysis|Training Pipeline Integration Analysis]]。

---

## Context

### Current State

BlackDragon v1.0.0 的训练流程需要用户手动执行两个独立步骤：

```
[Manual step 1] python data_cleaner.py    ← 用户手动运行
    ↓
data/ML_Ready_Dataset.csv                 ← 必须存在才能进行步骤 2
[Manual step 2] python train_lgbm.py      ← 用户手动运行 或点击 Dashboard "开始训练"
    ↓
models/fatalis_ai_model.pkl
```

Dashboard 的「开始训练」按钮绕过了 `data_cleaner.py`，仅触发 `train_lgbm.py`。

### Target State

将两个步骤整合为一条自动化 Pipeline，用户点击一次按钮即可完成：

```
Dashboard "开始训练" 按钮
    ↓
data_cleaner.py      ← 从原始录像重新生成 ML_Ready_Dataset.csv
    ↓
train_lgbm.py        ← 训练模型 → models/fatalis_ai_model.pkl
```

> **从原设计中移除**: `data_upgrade.py`。原因：用户数据格式已固定为 v2（含 `phase`/`is_enraged` 列）。若未来需要升级旧格式 CSV，`data_upgrade.py` 仍可作为独立工具手动运行。

### Why Now

- v1.0.0 已发布且稳定（551 tests passed，PyInstaller frozen runtime 已验证）
- 训练流程是用户体验的最后一块缺失拼图
- 现有 `--train` flag + subprocess 基础设施已证明可靠，扩展风险低

---

## Constraints

| # | Constraint | Source |
|---|-----------|--------|
| C1 | 不修改 P4 core: `src/core/`、`src/model/`、`src/data/`、`main.py` | ADR-P5.2 延续 |
| C2 | PyInstaller frozen EXE 必须支持 Pipeline（`BlackDragon.exe --pipeline`） | v1.0.0 交付约束 |
| C3 | 保持 `--train` 单独训练模式（向后兼容） | 用户场景 |
| C4 | 不修改 Overlay 子进程（`BlackDragonOverlay.exe`）——训练是 Dashboard 功能 | ADR-P5.2 进程隔离 |
| C5 | Dashboard UI 不新增控件——PIPE 输出捕获机制已满足进度展示需求 | 最小改动原则 |
| C6 | TrainingPanel 不引入复杂度增长（状态机、进度条等推至 v1.2） | MVP 约束 |

---

## Analysis: Three Design Options

完整对比分析见 `Training_Pipeline_Integration_Analysis.md` §2。此处摘要：

### Option A: Inline Pipeline via `--pipeline` Flag（推荐）

```python
# launch.py main()
if "--pipeline" in sys.argv:
    from data_cleaner import clean_combat_data
    from train_lgbm import train_fatalis_ai
    clean_combat_data()
    train_fatalis_ai()
    return
```

| Pro | Con |
|-----|-----|
| 最小改动：1 新 flag + 1 hidden import | 两脚本跑在同一进程——任一步骤失败则全部中止 |
| 复用现有 PIPE 输出捕获机制 | 不能精细取消（cancel 终止整个子进程） |
| 与 `--overlay` / `--train` 模式一致 | |
| 后退成本极低（flag 名回退即可） | |

### Option B: TrainingService（新抽象层）

| Pro | Con |
|-----|-----|
| 架构清晰，每步独立可测试 | 改动最大：新模块 + Controller 重构 |
| 步骤间可取消 | 过度工程——两个函数的流水线不需要完整服务抽象 |

### Option C: 分步 Subprocess Pipeline

| Pro | Con |
|-----|-----|
| 每步独立失败 | 需要 `--clean` flag + 2 次子进程启动 |
| | 输出切换 + 错误传播复杂度 |

---

## Decision

### Decision 1: 采用 Option A — `--pipeline` flag（2 步骤：clean → train）

**核心方案**：在 `launch.py` 中新增 `--pipeline` flag，顺序调用 `clean_combat_data()` → `train_fatalis_ai()`。

**Controller 变更**：

```python
# src/app/controller.py — start_training()
def start_training(self) -> bool:
    if self.is_training:
        return False
    try:
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--pipeline"]
            popen_kwargs = {"cwd": os.path.dirname(sys.executable)}
        else:
            cmd = [sys.executable, "launch.py", "--pipeline"]
            popen_kwargs = {}
        self._training_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            **popen_kwargs,
        )
    except Exception:
        logger.error("启动训练失败", exc_info=True)
        return False
    # ... training_thread + queue 不变 ...
```

**launch.py 新 flag handler**：

```python
# launch.py main()
if "--pipeline" in sys.argv:
    sys.argv.remove("--pipeline")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    from data_cleaner import clean_combat_data
    from train_lgbm import train_fatalis_ai
    clean_combat_data()
    train_fatalis_ai()
    return
```

**选择理由**：

| 评估维度 | 结论 |
|----------|------|
| 实现工作量 | 🟢 极低：~15 行，4 个文件 |
| Frozen EXE 兼容性 | 🟢 已验证模式（与 `--train`、`--overlay` 一致） |
| 测试影响 | 🟢 ~8 新增测试，0 破坏性变更 |
| UI 影响 | 🟢 无（PIPE 捕获机制不变） |
| 数据安全 | 🟢 **改善** —— 无原地 CSV 修改风险（upgrade 步骤已移除） |
| 架构一致性 | 🟢 高（遵循已有 flag 模式） |

### Decision 2: 对写过操作实施备份保护

> **Revised**: 备份目标从 3 个减少为 2 个（移除 `data_upgrade.py`）。

| 脚本 | 被覆盖对象 | 备份方式 |
|------|-----------|----------|
| `data_cleaner.py` | `data/ML_Ready_Dataset.csv` | 若文件已存在，重命名为 `data/ML_Ready_Dataset.csv.bak` |
| `train_lgbm.py` | `models/fatalis_ai_model.pkl` | 若文件已存在，重命名为 `models/fatalis_ai_model.pkl.bak` |

**不阻塞 v1.1 发布**——备份是安全增强，可在 Pipeline 核心流程跑通后追加。

### Decision 3: 保留 `--train` 单独模式（向后兼容）

`launch.py` 中现有 `--train` handler **不删除、不修改**。

Dashboard 的 Pipeline 按钮覆盖主流场景（一键全流程），`--train` 为兜底选项（高级用户手动清洗后直接训练）。

### Decision 4: TrainingPanel UI 不做阶段性改造

当前 TrainingPanel 设计已完美适配 Pipeline：

- **状态行**：`"训练状态: 进行中"` / `"训练状态: 空闲"` — 含义不变
- **输出面板**：PIPE 捕获 30 行滚动缓冲区 — 两个脚本的 `print()` 输出自然流入，用户看到：
  ```
  ✅ V4.5 纯粹观测流(含起手映射)数据提纯完成！有效样本: Y 条
  🚀 正在训练 LightGBM (V4.5 纯粹观测流)...
  🏆 绝对准确率 (Accuracy): Z%
  ```
- **取消按钮**：`proc.terminate()` 终止整个 Pipeline——粗粒度但 MVP 可接受

阶段性进度条（`[1/2] 数据清洗中...` → `[2/2] 训练中...`）推迟至 v1.2。

---

## Rejected Alternatives

### Rejected: Option B — TrainingService 抽象层

**拒绝理由**：两个顺序函数调用不需要完整服务抽象。新增模块 + Controller 重构 + 步骤状态机 = 过度工程。若 v1.2 确实需要步骤级控制，届时再提取不迟。

### Rejected: Option C — 分步 Subprocess 启动

**拒绝理由**：两次子进程启动 + 输出切换 + 错误传播复杂度，远超一个进程内的顺序调用价值。

### Rejected: 修改 Dashboard UI 添加"清洗数据"单独按钮

**拒绝理由**：与一键完成目标相悖——仍需要两步操作（点"清洗" → 等完成 → 点"训练"）。

### Rejected: 将 `data_upgrade` 纳入 Pipeline（原设计）

**方案**：Original ADR-P5.4 Decision 1 包含 `upgrade_old_csv_files()` → `clean_combat_data()` → `train_fatalis_ai()` 三步骤。

**拒绝理由（修订时）**：
1. **不再需要**：用户数据格式已固定为 v2（含 `phase`/`is_enraged` 列），无旧格式 CSV 需运行时升级
2. **数据安全风险**：`upgrade_old_csv_files()` 原地修改原始 CSV（🔴 High risk），移除后消除此风险
3. **简化设计**：Pipeline 从 3 步骤降为 2 步骤——减少 hidden import（只需 `data_cleaner`）、减少测试目标、减少错误面
4. **保留独立工具**：`data_upgrade.py` 仍可用于手动升级历史数据（独立工具模式，不自动执行）

---

## Consequences

### 正面影响（含修订增益）

| 影响 | 说明 |
|------|------|
| 🟢 用户体验提升 | 从"手动两步"变为"一键完成" |
| 🟢 数据时效性保证 | 每次训练前自动从最新录像重新清洗 |
| 🟢 **数据安全改善** | 移除 upgrade 步骤 → 消除原地 CSV 修改风险（原 🔴 High risk） |
| 🟢 **实现更简单** | 代码从 ~30 行降为 ~15 行；hidden import 从 2 个降为 1 个 |
| 🟢 架构一致性 | `--pipeline` 遵循已有 flag 模式 |
| 🟢 零 UI 变更 | 无需修改 DPG widget |
| 🟢 低风险部署 | 可立即回退至 `--train` 模式 |

### 需关注的影响

| 影响 | 缓解 |
|------|------|
| 🟡 子进程生命周期变长 | ~35-60s（c/t ~30s 仅训练）。MVP 可接受 |
| 🟡 Frozen EXE 体积 | `data_cleaner` 新增到 hidden imports。**实际增量 0 MB**（pandas 已在 EXE 中） |
| 🟢 ~~原 `data_upgrade` 原地修改风险~~ | **已消除** |

### 不变模块（零 diff 保证）

| 模块 | 原因 |
|------|------|
| `src/core/`、`src/model/`、`src/data/` | P4 core — C1 约束 |
| `src/ui/overlay.py` | Overlay 不参与训练 |
| `src/dashboard/` (全部 4 个文件) | PIPE 捕获逻辑不变 |
| `src/app/game_service.py` | 游戏检测不变 |
| `src/bootstrap/checker.py` | 环境检查不变 |
| `src/config/actions.py`、`src/config/offsets.py` | 坐标/动作数据库不变 |
| `build/BlackDragonOverlay.spec` | Overlay EXE 不需要训练模块 |
| `scripts/build_exe.ps1` | 已有 ML_Ready_Dataset.csv 处理 |
| `data_upgrade.py` | 保留为独立工具，不修改 |

---

## Implementation

### 涉及模块（修订后）

#### 修改文件（4 个，核心变更）

| # | 文件 | 变更内容 | 行数 |
|---|------|----------|:---:|
| 1 | `launch.py` | 新增 `--pipeline` flag handler：`clean_combat_data()` → `train_fatalis_ai()` | +10 |
| 2 | `src/app/controller.py` | `start_training()` 中 `"--train"` → `"--pipeline"`（frozen）；`"train_lgbm.py"` → `"launch.py" "--pipeline"`（dev） | ~6 |
| 3 | `build/BlackDragon.spec` | hiddenimports 新增 `'data_cleaner'`（仅此一项） | +1 |

#### 修改文件（2 个，数据安全增强）

| # | 文件 | 变更内容 | 行数 |
|---|------|----------|:---:|
| 4 | `data_cleaner.py` | `clean_combat_data()` 中如 `ML_Ready_Dataset.csv` 存在，先 rename 为 `.bak` | +3 |
| 5 | `train_lgbm.py` | `train_fatalis_ai()` 中如 `fatalis_ai_model.pkl` 存在，先 rename 为 `.bak` | +3 |

#### 新增文件（1 个，测试）

| # | 文件 | 内容 | 行数 |
|---|------|------|:---:|
| 6 | `tests/test_training_pipeline.py` | 6 个测试：pipeline flag 调用链、frozen/dev 命令正确性、取消行为、无数据场景等 | ~80 |

#### 测试修改（2 个，适配性调整）

| # | 文件 | 变更 |
|---|------|------|
| 7 | `tests/test_app_controller.py` | `test_start_training_frozen_uses_train_flag` → `test_start_training_frozen_uses_pipeline_flag` |
| 8 | `tests/test_launch.py` | 新增 `test_main_handles_pipeline_flag` |

### 文件变更对比（修订前 → 修订后）

| 指标 | 原始 v1 设计 | 修订后 v1.1 |
|------|:---:|:---:|
| 修改文件 | 4 core + 3 safety + 1 new test + 3 test mod = **10** | 3 core + 2 safety + 1 new test + 2 test mod = **8** |
| 代码行数 | ~130 | ~80 |
| Hidden imports | `data_cleaner`, `data_upgrade` (2) | `data_cleaner` (1) |
| 🔴 High risks | 1 (upgrade in-place write) | **0** |
| Pipeline 步骤 | 3 | 2 |
| 新增测试 | ~12 | ~8 |

### 测试预期

```
Baseline:       551 tests
Pipeline 新增:   +8 tests（test_training_pipeline.py: 6 + controller: 1 + launch: 1）
修改适配:         1 rename（controller test）
破坏性变更:       0
───────────────
Target:         ~559 tests
```

### 实施顺序

```
Phase 1 — Core:  launch.py flag → controller.py → spec hidden import
Phase 2 — Safety: backup-before-write in data_cleaner/train_lgbm
Phase 3 — Tests:  test_training_pipeline.py + test adaptations
Phase 4 — Build:  pyinstaller build/BlackDragon.spec --clean → 验证 --pipeline
Phase 5 — RC:     真机验证：录制数据 → 点击 "开始训练" → 模型更新 → Overlay 使用新模型
```

### 回滚方案

| 场景 | 操作 |
|------|------|
| Pipeline 功能问题 | `controller.py` 中 `"--pipeline"` 改回 `"--train"` |
| Frozen EXE import 失败 | 注释 spec 中新增的 `'data_cleaner'` hidden import，重建 |
| 数据丢失 | 从 `data/ML_Ready_Dataset.csv.bak` 或 `models/fatalis_ai_model.pkl.bak` 恢复 |
| 完整回退至 v1.0 | `git revert` 本次所有 commits；重建 EXE |

### `data_upgrade.py` 处置

**保留文件，不修改。** 其作为独立工具继续存在：

```bash
# 手动升级历史数据（非自动化流程）
python data_upgrade.py
```

现有 `tests/test_data_upgrade.py` 的 13 个测试不受影响——它们测试的是独立工具的升级逻辑，与 pipeline 无关。

---

## Next Steps

1. ✅ 前置分析完成：`Training_Pipeline_Integration_Analysis.md`（已修订）
2. ✅ ADR 记录完成：当前文档（ADR-P5.4，已修订）
3. ✅ 修订更新：移除 `data_upgrade` 依赖，Pipeline 2 步骤
4. ⬜ 更新 ADR Index（`obsidian/Architecture/ADR_Index.md`）— 反映 ADR-P5.4 修订
5. ⬜ 实现 Phase 1：`launch.py` → `controller.py` → `spec`
6. ⬜ 实现 Phase 2：backup-before-write（2 个脚本）
7. ⬜ 实现 Phase 3：测试
8. ⬜ 重建 EXE + 真机验证
