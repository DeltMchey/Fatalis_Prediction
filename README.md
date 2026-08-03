# BlackDragon (黑龙)

> AI-assisted hunting overlay for **Monster Hunter World** — predicts Fatalis's next attack in real-time.

[![Phase](https://img.shields.io/badge/phase-P4%20Architecture%20Refactor-green)](#roadmap)
[![Tests](https://img.shields.io/badge/tests-385%20passed-brightgreen)](#roadmap)
[![Coverage](https://img.shields.io/badge/coverage-72%25-brightgreen)](#roadmap)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## What It Does

BlackDragon reads Monster Hunter World process memory in real-time, runs a trained LightGBM model to predict Fatalis's next attack, and displays the Top-3 predictions as a transparent in-game overlay.

| Feature | Description |
|---------|-------------|
| **Real-time prediction** | LightGBM multiclass classifier (~40-60 action classes), inference every 0.5s |
| **Transparent overlay** | dearpygui window (420×350), top-right corner, click-through |
| **Game-rule filtering** | Phase/posture constraints ensure predictions are physically possible |
| **Nova warning** | HP-threshold-based alert for Fatalis's ultimate attack (飞天火) |
| **Combat recording** | Real-time CSV logging (~10 rows/sec) for model training |

## Requirements

- **Windows** only (uses Win32 API and `pymem` for process memory)
- **Monster Hunter World** running (`MonsterHunterWorld.exe`)
- **Python 3.x** with virtual environment
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
python data_cleaner.py
python train_lgbm.py

# 5. Launch the game, enter a Fatalis quest, then run:
python main.py            # P4+ 推荐入口（组合 5 个模块）
# python ai_engine.py     # legacy fallback（God Class，保留作参考）
```

## Project Structure

```
BlackDragon/
├── main.py               # P4+ composition root（推荐入口）
├── ai_engine.py          # legacy God Class（保留：P3 测试兼容 + fallback）
├── src/                  # P4 架构模块
│   ├── core/
│   │   ├── state_tracker.py    # CombatStateTracker — 共享战斗状态
│   │   └── memory_reader.py    # MemoryReader — 唯一游戏内存读取入口
│   ├── model/
│   │   └── predictor.py        # ActionPredictor — AI 预测管线
│   ├── data/
│   │   └── recorder.py         # CombatRecorder — 录制 daemon 线程
│   ├── ui/
│   │   └── overlay.py          # OverlayUI — DearPyGui 覆盖层
│   ├── config/                 # 动作数据库 + 内存偏移量（单一数据源）
│   └── logging_config.py
│
├── data_cleaner.py       # ETL: raw CSV → ML-ready dataset
├── train_lgbm.py         # LightGBM training script
├── data_upgrade.py       # Backfill phase/enrage columns in old CSVs
│
├── data/                 # Combat recording CSVs (git-ignored)
│   └── ML_Ready_Dataset.csv       (cleaned transition pairs)
├── models/               # Trained artifacts (git-ignored)
│   ├── fatalis_ai_model.pkl
│   └── feature_importance.png
├── archive/              # Deprecated files + legacy closure reports
├── obsidian/             # Memory bank + project documentation
├── tests/                # Test suite (16 files, 385 tests, pytest + coverage)
├── requirements.txt
├── CHANGELOG.md
└── .gitignore
```

## How It Works

```
Game Memory ──► ai_engine.py (live)
                    │
                    ├──► data/*.csv ──► data_cleaner.py ──► data/ML_Ready_Dataset.csv
                    │                                              │
                    │                                              ▼
                    │                                      train_lgbm.py
                    │                                              │
                    │                                              ▼
                    │                                      models/*.pkl
                    │                                              │
                    └────────────────────────────── joblib.load() ◄┘
                                                       │
                                                  AI Inference
                                                       │
                                                  Top-3 Overlay
```

1. **Read memory** — `pymem` reads MonsterHunterWorld.exe process memory directly
2. **State machine** — Computes posture, phase, enrage, distance, angle from raw memory
3. **ML prediction** — LightGBM `predict_proba()` on 6 features → probability distribution
4. **Hard filter** — Phase/posture constraints zero out impossible actions → renormalize
5. **Display** — Top-3 predictions shown on transparent overlay

### Key Innovation: Two-Layer Prediction

```
ML probabilities → Phase filter → Posture filter → Renormalize → Top-3
```

Pure ML can output physically impossible predictions. The hard filter guarantees legitimacy.

## Known Limitations

- Single monster only (Fatalis, zone 417)
- Memory offsets tied to a specific MHW build — game updates may break them
- No multi-player tracking, no weapon-type-specific predictions
- Single LightGBM model (no ensemble)

## Roadmap

| Phase | Name | Status |
|-------|------|--------|
| P1 | Project Standardization | ✅ Done |
| P2 | Critical Fixes (logging, offset centralization) | ✅ Done |
| P3 | Test Safety Net (182 tests, 60% coverage, CI) | ✅ Done |
| P4 | Architecture Refactor (modular src/, 385 tests) | ✅ Done |
| P5 | Model Engineering (versioning, incremental learning) | Planned |

See [`docs/Refactoring_roadmap.md`](docs/Refactoring_roadmap.md) for details.

## License

MIT
