# BlackDragon(黑龙招式预测)

> AI-assisted hunting overlay for **Monster Hunter World** — predicts Fatalis's next attack in real-time.

[![Phase](https://img.shields.io/badge/phase-P6%20AutoML%20Migration-blue)](#roadmap)
[![Tests](https://img.shields.io/badge/tests-766%20passed-brightgreen)](#roadmap)
[![Coverage](https://img.shields.io/badge/coverage-86%25-brightgreen)](#roadmap)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## What It Does

BlackDragon reads Monster Hunter World process memory in real-time, runs a trained XGBoost pipeline (AutoML-selected, v1.2.0) to predict Fatalis's next attack, and displays the Top-3 predictions as a transparent in-game overlay.

| Feature | Description |
|---------|-------------|
| **Real-time prediction** | XGBoost multiclass pipeline (~46 action classes, 12 engineered features), inference every 0.5s |
| **Transparent overlay** | dearpygui window (420×350), top-right corner, click-through |
| **Game-rule filtering** | Phase/posture constraints ensure predictions are physically possible |
| **Nova warning** | HP-threshold-based alert for Fatalis's ultimate attack (飞天火) |
| **Combat recording** | Real-time CSV logging (~10 rows/sec) for model training |
| **Control panel** | Dashboard UI for managing overlay, recording, training, and real-time logs |

## Requirements

- **Windows** only (uses Win32 API and `pymem` for process memory)
- **Monster Hunter World** running (`MonsterHunterWorld.exe`)
- **Python 3.11+** with virtual environment
- **Chinese font**: `msyh.ttc` (Microsoft YaHei) — included with Windows

## Quick Start

```bash
# 1. Clone and enter the project
git clone <repo-url> && cd BlackDragon

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Train the model (one-time, uses included CSV data)
#    Option A: 一键 pipeline（推荐）— 数据清洗 + Run B XGBoost 配置重训（几秒完成）
python launch.py --pipeline
#    Option B: 手动两步 — 可单独调参 debug（legacy LightGBM 路径）
# python data_cleaner.py
# python train_lgbm.py

# 5. Launch the game, enter a Fatalis quest, then run:
python launch.py            # P5.3 Dashboard + Overlay 双进程（推荐）
# python overlay.py         # 仅 Overlay 进程
# python main.py            # P4 legacy 单进程入口
# python ai_engine.py       # Legacy God Class
```

## Entry Points

| Command | Description | Status |
|---------|-------------|:---:|
| `python launch.py` | **Dashboard + Overlay** 双进程启动器（自动启动覆盖层） | ✅ Recommended |
| `python launch.py --pipeline` | **一键数据清洗 + Run B XGBoost 训练**（合并录制数据，几秒完成） | ✅ v1.2 |
| `python overlay.py` | 独立 Overlay 进程入口（透明覆盖层） | ✅ |
| `python launch.py --selftest` / `python overlay.py --selftest` | 自检：路径解析 → 模型加载 → 一次推理 → exit 0/1 | ✅ v1.2 |
| `python main.py` | P4 单进程 overlay 入口 | ⚠️ Legacy |
| `python ai_engine.py` | God Class 单体脚本 | ⚠️ Legacy |

### CLI Tools

| Command | Description |
|---------|-------------|
| `python launch.py --pipeline` | **一键训练**：`data_cleaner`（合并语义）→ `src/model/production_backend.py`（Run B XGBoost 胜出配置；v1.2，Dashboard 按钮背后逻辑） |
| `python data_cleaner.py` | ETL: raw CSV → ML-ready dataset（清洗+提纯；不在场的会话行从现有数据集保留） |
| `python train_lgbm.py` | Legacy LightGBM training script（`--train` 路径，保留向后兼容） |
| `python data_upgrade.py` | Backfill phase/enrage columns in old CSVs（独立工具，不纳入 pipeline） |

### Pipeline Workflow

```
录制数据 (fatalis_combat_data_*.csv)
    │
    ▼
data_cleaner.py   ← ACTION_MAPPING → Posture FSM → 提纯（合并语义：缺席会话保留）
    │
    ▼
ML_Ready_Dataset.csv
    │
    ▼
production_backend.py  ← Run B 胜出配置 XGBoost（190 树，12 派生特征，n_jobs=1）
    │
    ▼
fatalis_ai_model.pkl + feature_importance.png + .meta.json（sidecar）
```

`launch.py --pipeline` 和 Dashboard「模型训练」按钮均执行上述完整流程。未知动作（未在 `ACTION_DB` 定义）将在清洗阶段过滤并输出 warning。训练完成后输出数据摘要行（本次 vs 上代会话/行/类），数据可疑缩水（行数 < 上代 50%、holdout < 100 行、类数降 ≥ 20%）时输出 ⚠ 告警并记入 sidecar；每次训练完整日志写入 `models/train_YYYYMMDD_HHMMSS.log`（保留最近 10 份）。

### Model Rollback（三层）

| 层级 | 文件 | 用途 |
|------|------|------|
| 出厂模型 | `models/factory_model.pkl` | 随发行包分发的不可变副本，训练永不触碰——任意时刻拷贝覆盖 `fatalis_ai_model.pkl` 即回到出厂状态 |
| 上一代 | `models/fatalis_ai_model.pkl.bak` | 最近一次变更训练前的模型 |
| 上上代 | `models/fatalis_ai_model.pkl.bak2` | 再上一次（两代轮换链） |

数据集同理（`ML_Ready_Dataset.csv.bak` / `.bak2`）。自 v1.2.0 起发行包仅附带清洗后的 `ML_Ready_Dataset.csv`，原始战斗 CSV 不随包（2026-09-16 用户裁决）：重训安全由清洗合并语义保障——不在场的会话行从现有数据集保留，单场录制无法替换出厂数据集。同数据重复训练产生逐位相同的模型，不会推进备份链（same-sha skip）。

## Documentation

Full knowledge base: [`obsidian/Index.md`](obsidian/Index.md)

Architecture overview: [`obsidian/Architecture/System_Architecture.md`](obsidian/Architecture/System_Architecture.md)

Architecture decision records: [`obsidian/docs/architecture/`](obsidian/docs/architecture/)

## Project Structure

```
BlackDragon/
├── launch.py               # P5.3 双进程入口（推荐；含 --pipeline / --selftest）
├── overlay.py              # P5.3 Overlay 独立进程入口（含 --selftest）
├── main.py                 # P4 legacy 单进程入口
├── ai_engine.py            # Legacy God Class
│
├── src/                    # 源码
│   ├── core/               #   CombatStateTracker + MemoryReader + backup_chain（两代备份链）
│   ├── model/              #   ActionPredictor + production_backend（Run B 训练后端）+ features/label_decode/dataset
│   ├── data/               #   CombatRecorder（CSV 录制 daemon）
│   ├── ui/                 #   OverlayUI + shared CJK font
│   ├── app/                #   AppController / AppConfig / GameService
│   ├── dashboard/          #   Dashboard UI（控制中心）
│   ├── bootstrap/          #   DependencyChecker（启动检查）
│   └── config/             #   动作数据库 + 内存偏移量（单一数据源）
│
├── data_cleaner.py         # ETL: raw CSV → ML-ready dataset（合并语义）
├── train_lgbm.py           # Legacy LightGBM training script（--train 路径）
├── data_upgrade.py         # Backfill phase/enrage columns in old CSVs
│
├── data/                   # Combat recording CSVs (git-ignored)
├── models/                 # Trained artifacts (git-ignored；factory_model.pkl 随发行包分发)
├── archive/                # Deprecated files + legacy closure reports
├── obsidian/               # Knowledge base + project documentation
├── tests/                  # Test suite (pytest + coverage, 766 tests)
├── requirements.txt
├── CHANGELOG.md
└── .gitignore
```

## How It Works

```
Game Memory ──► pymem (MemoryReader)
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
  Recorder       StateMachine    AI Predictor
  (CSV daemon)   (CombatState)   (ActionPredictor)
    │                               │
    ▼                               ▼
  data/*.csv                    Top-3 Overlay
    │                         (OverlayUI DPG)
    ▼
  data_cleaner.py
    │
    ▼
  production_backend.py → models/fatalis_ai_model.pkl
```

1. **Read memory** — `MemoryReader` (pymem) reads `MonsterHunterWorld.exe` process memory
2. **State machine** — `CombatStateTracker` computes posture, phase, enrage, distance, angle
3. **ML prediction** — `ActionPredictor` runs the XGBoost pipeline `predict_proba()` (6 input features, 12 engineered inside the pipeline)
4. **Hard filter** — Phase/posture constraints zero out impossible actions → renormalize
5. **Display** — Top-3 predictions shown on transparent overlay

### Key Innovation: Two-Layer Prediction

```
ML probabilities → Phase filter → Posture filter → Renormalize → Top-3
```

Pure ML can output physically impossible predictions. The hard filter guarantees legitimacy.

### Architecture: Dual-Process (P5.3)

BlackDragon v1.0 uses two independent Python processes:
- **Dashboard Process** (`launch.py`) — control center with GameService, AppController, DPG UI
- **Overlay Process** (`overlay.py`) — transparent game overlay with independent DPG context

This solves the DPG 2.x / GLFW main-thread limitation. See [`obsidian/Architecture/System_Architecture.md`](obsidian/Architecture/System_Architecture.md) for full architecture documentation.

### Frozen EXE (PyInstaller)

BlackDragon v1.2 supports standalone EXE deployment via PyInstaller:

| Command | Description |
|---------|-------------|
| `BlackDragon.exe` | Dashboard + Overlay 双进程（等同于 `python launch.py`） |
| `BlackDragon.exe --pipeline` | **冷冻环境一键训练**（等同于 `python launch.py --pipeline`） |
| `BlackDragon.exe --selftest` / `BlackDragonOverlay.exe --selftest` | **自检诊断**：路径解析 → 模型加载 → 一次推理 → 退出码 0/1（详情写 `blackdragon.log`） |

Build: `.\scripts\build_exe.ps1 -Clean` → produces `dist/BlackDragon/` (two EXEs, ~286 MB unpacked; release zip ~155 MB).
Both EXEs include embedded Python runtime + dependencies (incl. xgboost runtime); no Python installation required on target machine.
The build itself runs both EXEs' `--selftest` as a hard gate — a build that cannot load and run the model fails.

模型加载异常不再静默：Overlay 显示橙色「⚠ AI 模型未加载」提示，`blackdragon.log` 记录完整 traceback，`--selftest` 可在无游戏环境下快速定谳。

## Known Limitations

- Single monster only (Fatalis, zone 417)
- Memory offsets tied to a specific MHW build — game updates may break them
- No multi-player tracking, no weapon-type-specific predictions
- Single XGBoost pipeline (no ensemble); model trained for one MHW build's move set

## Roadmap

| Phase | Name | Status |
|-------|------|:---:|
| P1 | Project Standardization | ✅ Done |
| P2 | Critical Fixes | ✅ Done |
| P3 | Test Safety Net (182 tests, 60% coverage, CI) | ✅ Done |
| P4 | Architecture Refactor (5 modules extracted) | ✅ Done |
| P5 | Control Center (Dashboard + Bootstrap + GameService) | ✅ Done |
| P5.1 | Bootstrap + Game-less Startup | ✅ Done |
| P5.2 | Overlay Integration Experiment (deferred → ADR-P5.2) | ✅ Done |
| P5.3 | Dual-Process Overlay Architecture (556 tests, 94% coverage) | ✅ Done |
| P5.4 | Training Pipeline Integration — one-click clean+train, unknown-action defense, frozen support (581 tests) | ✅ Done |
| **P6.1** | **AutoML Model Migration** — FLAML Run B XGBoost adopted, one-click retrain, data merge + backup chain, selftest gate (766 tests, v1.2.0) | ✅ Done |
| P6 | Model Engineering (versioning, incremental learning) | 📋 Future |

See [`obsidian/Development/Development_Roadmap.md`](obsidian/Development/Development_Roadmap.md) for detailed roadmap. Historical roadmap: [`obsidian/docs/legacy/Refactoring_roadmap.md`](obsidian/docs/legacy/Refactoring_roadmap.md).

## Documentation

Full knowledge base: [`obsidian/Index.md`](obsidian/Index.md)

## License

MIT — see [LICENSE](LICENSE)
