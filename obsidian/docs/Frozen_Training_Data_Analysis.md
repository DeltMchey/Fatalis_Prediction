# Frozen Mode — Training Data Path Analysis

- **Date**: 2026-08-04
- **Analyst**: Analysis (read-only)
- **Scope**: `train_lgbm.py`, `data_cleaner.py`, `data_upgrade.py`, PyInstaller spec

---

## 1. Root Cause

### 1.1 Data Flow (Dev Mode)

```
CombatRecorder                         data_cleaner.py                   train_lgbm.py
     │                                       │                                │
     │  写入 raw CSVs                         │  读取 raw CSVs                  │  读取 processed
     ▼                                       ▼                                ▼
data/fatalis_combat_data_*.csv  ─────────  data/ML_Ready_Dataset.csv  ──────  models/fatalis_ai_model.pkl
    (19 files, ~11 MB)                      (85.8 KB)                         (17.6 MB)
```

**开发模式下完整工作流**:
```bash
# 1. 录制战斗数据（BlackDragon 运行时自动）
#    → data/fatalis_combat_data_*.csv

# 2. 清洗数据（用户手动运行）
python data_cleaner.py
#    → data/ML_Ready_Dataset.csv

# 3. 训练模型（用户手动运行）
python train_lgbm.py
#    → models/fatalis_ai_model.pkl
```

### 1.2 Frozen Mode — What Exists

| Component | In EXE? | Location |
|-----------|:---:|------|
| `launch.py` (Dashboard) | ✅ | `BlackDragon.exe` |
| `overlay.py` (Overlay) | ✅ | `BlackDragonOverlay.exe` |
| `models/fatalis_ai_model.pkl` | ✅ | Bundled via `--datas` → `_internal/models/` |
| `models/feature_importance.png` | ❌ | Not bundled |
| `data/ML_Ready_Dataset.csv` | ❌ | **Not bundled** ← root cause |
| `data/fatalis_combat_data_*.csv` | N/A | Generated at runtime by CombatRecorder |
| `data_cleaner.py` | ❌ | Not bundled in any exe |
| `data_upgrade.py` | ❌ | Not bundled in any exe |
| `train_lgbm.py` | ✅ (partial) | `train_fatalis_ai()` callable via `--train` flag |

### 1.3 Gap Analysis

```
训练模式执行链:

controller.start_training()
    ↓
spawn BlackDragon.exe --train  (cwd=<exe_dir>)
    ↓
launch.py → "--train" in sys.argv
    ↓
train_lgbm.train_fatalis_ai()
    ↓
pd.read_csv("data/ML_Ready_Dataset.csv")  ← 硬编码相对路径
    ↓
❌ FileNotFound — exe 目录无 data/
```

**三处硬编码路径**（均不感知 frozen 环境）:

| 文件:行 | 路径 | 用途 |
|---------|------|------|
| `train_lgbm.py:18` | `"data/ML_Ready_Dataset.csv"` | 读取训练集 |
| `train_lgbm.py:70` | `"models/fatalis_ai_model.pkl"` | 写入训练好的模型 |
| `train_lgbm.py:84` | `"models/feature_importance.png"` | 写入特征重要性图 |

**仅 `models/fatalis_ai_model.pkl` 被 PyInstaller 打包**（作为推理依赖）。`data/ML_Ready_Dataset.csv` 不在 spec 的 `datas` 中——PyInstaller 不会收集它。

---

## 2. Solution Analysis

### 2.1 Option A: Bundle ML_Ready_Dataset.csv in EXE

```
PyInstaller datas += ("data/ML_Ready_Dataset.csv", "data")
Release package: BlackDragon.exe + data/ML_Ready_Dataset.csv (可选外部放置)
```

| Pro | Con |
|-----|-----|
| 下载后训练立即可用 | 数据集是"开发团队录制"的，用户无法用自己的数据替换（除非 rebuild） |
| 85.8 KB — 体积忽略不计 | 数据集过时问题——用户录制更多 hunts 后无法重新训练 |
| 实现简单（+1 行 spec） | |

### 2.2 Option B: Auto-Generate on First Run

```
用户录制 hunts → raw CSVs
  → 首次点击"训练"时:
    1. 运行 data_cleaner.py (需要 --clean flag)
    2. 运行 data_upgrade.py (需要 --upgrade flag)
    3. 运行 train_lgbm.py (已有 --train flag)
```

| Pro | Con |
|-----|-----|
| 用户用自己的数据训练 | 需要增加 2 个 exe flag (`--clean`, `--upgrade`) |
| 数据永远是最新的 | `data_cleaner.py` / `data_upgrade.py` 需要纳入 PyInstaller build |
| | 实现复杂度高——相当于打包完整工具链 |

### 2.3 Option C: Training Requires Manual Dataset Preparation

```
用户需要:
  1. 从 GitHub 下载源码
  2. pip install requirements
  3. 手动运行 data_cleaner.py
  4. 将 ML_Ready_Dataset.csv 复制到 exe 目录
  5. 点击训练
```

| Pro | Con |
|-----|-----|
| 零代码改动 | 与 Python-free 分发理念完全相悖 |
| 用户自主控制数据 | "为什么 exe 还要装 Python？" |

### 2.4 Option D: Hybrid — Bundle Baseline + External Override（推荐）

```
Release package:
├── BlackDragon.exe
├── BlackDragonOverlay.exe
├── data/
│   └── ML_Ready_Dataset.csv    ← 预置基线数据集 (85.8 KB)
├── models/
│   └── (空 — 训练后填充)
└── config/
    └── (首次运行生成)

data_cleaner.py / data_upgrade.py:
  未来通过 --clean / --upgrade flag 在同一个 exe 中支持
  (作为 v1.1 功能——当前标记为 TODO)
```

**运行时**:
- 首次点击训练 → 使用预置 `data/ML_Ready_Dataset.csv`（85.8 KB）训练
- 用户录制 hunt → `CombatRecorder` 写入 `data/fatalis_combat_data_*.csv`
- 用户要重新训练 → 替换 `data/ML_Ready_Dataset.csv`（从源码环境运行 `data_cleaner.py` 生成的）→ 点击训练

| Pro | Con |
|-----|-----|
| 开箱即用 | 基线数据集可能过时（用户录制更多 hunts 后需手动更新） |
| 用户保留完全控制权 | |
| 体积增加可忽略 | |

---

## 3. Recommendation

### ✅ Option D — Hybrid

**理由**:
1. **最小改动** — 仅需在 spec 中添加 1 行 datas（`"data/ML_Ready_Dataset.csv"`）
2. **开箱即用** — 用户下载后立即可训练模型（无需 Python 环境）
3. **用户可控** — 数据集是外部文件，可随时替换为自己录制的 hunts 生成的
4. **与 cwd 修复兼容** — 训练从 exe 目录查找 `data/ML_Ready_Dataset.csv`，cwd 修复保证路径一致性

### 实施步骤（3 步）

| Step | Action | File |
|------|--------|------|
| 1 | 在 Dashboard spec 的 `datas` 中添加 `data/ML_Ready_Dataset.csv` | `build/BlackDragon.spec:19` |
| 2 | 在 `launch.py` `--train` 分支也设置 CWD 或使用 exe-relative 路径（当前 cwd 修复已生效） | Already done ✅ |
| 3 | Rebuild + 验证 `--train` 找到数据集 | `scripts/build_exe.ps1 -Clean` |

### 需要修改的文件

| 文件 | 变更 |
|------|------|
| `build/BlackDragon.spec` | `datas` 新增 `("data/ML_Ready_Dataset.csv", "data")` |
| 无需修改 | `train_lgbm.py`（硬编码路径已通过 cwd 修复适配） |
| 无需修改 | `launch.py`（cwd 修复已在 `--train` 分支生效） |
| 无需修改 | `src/app/controller.py`（cwd 修复已在 `start_training` frozen 分支生效） |

### 数据更新流程（用户视角）

```
录制 hunts
    ↓
data/fatalis_combat_data_*.csv  ← 自动生成
    ↓
[将 CSV 复制到源码环境]
    ↓
python data_cleaner.py          ← 在源码环境运行
    ↓
[将 ML_Ready_Dataset.csv 复制回 exe 目录]
    ↓
点击 Dashboard "开始训练"       ← 在 exe 中运行
    ↓
models/fatalis_ai_model.pkl     ← 训练完成，覆盖旧模型
```

### Future Work (v1.1)

- [ ] 添加 `BlackDragon.exe --clean` flag → 运行 `data_cleaner.py`
- [ ] 添加 `BlackDragon.exe --upgrade` flag → 运行 `data_upgrade.py`
- [ ] Dashboard 中"一键训练"按钮：clean → upgrade → train 流水线

---

## 4. Files Included in Analysis

| File | Read | Key Finding |
|------|:---:|------|
| `train_lgbm.py` | ✅ | L18: `pd.read_csv("data/ML_Ready_Dataset.csv")` — 硬编码相对路径 |
| `data_cleaner.py` | ✅ | L8: `glob.glob("data/fatalis_combat_data_*.csv")` — 硬编码相对；L96: writes `data/ML_Ready_Dataset.csv` |
| `data_upgrade.py` | ✅ | L8: `glob.glob("data/fatalis_combat_data_*.csv")` — 硬编码相对 |
| `src/app/config.py` | ✅ | L49: `dataset_path = "data/ML_Ready_Dataset.csv"` — config 有但 train_lgbm 不使用 |
| `build/BlackDragon.spec` | ✅ | `datas` 只包含 `models/fatalis_ai_model.pkl` — 不包含任何 `data/` 文件 |
