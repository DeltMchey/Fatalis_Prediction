# Fatalis Prediction (黑龙招式预测)

> AI-assisted hunting overlay for **Monster Hunter World** — predicts Fatalis's next attack in real-time.

[![Phase](https://img.shields.io/badge/phase-P5.3%20Dual--Process-blue)](#roadmap)
[![Tests](https://img.shields.io/badge/tests-556%20passed-brightgreen)](#roadmap)
[![Coverage](https://img.shields.io/badge/coverage-94%25-brightgreen)](#roadmap)
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
python data_cleaner.py
python train_lgbm.py

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
| `python overlay.py` | 独立 Overlay 进程入口（透明覆盖层） | ✅ |
| `python main.py` | P4 单进程 overlay 入口 | ⚠️ Legacy |
| `python ai_engine.py` | God Class 单体脚本 | ⚠️ Legacy |

### CLI Tools

| Command | Description |
|---------|-------------|
| `python data_cleaner.py` | ETL: raw CSV → ML-ready dataset |
| `python train_lgbm.py` | LightGBM training script |
| `python data_upgrade.py` | Backfill phase/enrage columns in old CSVs |

## Documentation

Full knowledge base: [`obsidian/Index.md`](obsidian/Index.md)

Architecture overview: [`obsidian/Architecture/System_Architecture.md`](obsidian/Architecture/System_Architecture.md)

Architecture decision records: [`obsidian/docs/architecture/`](obsidian/docs/architecture/)

## Project Structure

```
BlackDragon/
├── launch.py               # P5.3 双进程入口（推荐）
├── overlay.py              # P5.3 Overlay 独立进程入口
├── main.py                 # P4 legacy 单进程入口
├── ai_engine.py            # Legacy God Class
│
├── src/                    # 源码
│   ├── core/               #   CombatStateTracker + MemoryReader
│   ├── model/              #   ActionPredictor（AI 推理管线）
│   ├── data/               #   CombatRecorder（CSV 录制 daemon）
│   ├── ui/                 #   OverlayUI + shared CJK font
│   ├── app/                #   AppController / AppConfig / GameService
│   ├── dashboard/          #   Dashboard UI（控制中心）
│   ├── bootstrap/          #   DependencyChecker（启动检查）
│   └── config/             #   动作数据库 + 内存偏移量（单一数据源）
│
├── data_cleaner.py         # ETL: raw CSV → ML-ready dataset
├── train_lgbm.py           # LightGBM training script
├── data_upgrade.py         # Backfill phase/enrage columns in old CSVs
│
├── data/                   # Combat recording CSVs (git-ignored)
├── models/                 # Trained artifacts (git-ignored)
├── archive/                # Deprecated files + legacy closure reports
├── obsidian/               # Knowledge base + project documentation
├── tests/                  # Test suite (26 files, 556 tests, pytest + coverage)
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
  train_lgbm.py → models/fatalis_ai_model.pkl
```

1. **Read memory** — `MemoryReader` (pymem) reads `MonsterHunterWorld.exe` process memory
2. **State machine** — `CombatStateTracker` computes posture, phase, enrage, distance, angle
3. **ML prediction** — `ActionPredictor` runs LightGBM `predict_proba()` on 6 features
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

## Known Limitations

- Single monster only (Fatalis, zone 417)
- Memory offsets tied to a specific MHW build — game updates may break them
- No multi-player tracking, no weapon-type-specific predictions
- Single LightGBM model (no ensemble)

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
| P6 | Model Engineering (versioning, incremental learning) | 📋 Future |

See [`obsidian/Development/Development_Roadmap.md`](obsidian/Development/Development_Roadmap.md) for detailed roadmap. Historical roadmap: [`obsidian/docs/legacy/Refactoring_roadmap.md`](obsidian/docs/legacy/Refactoring_roadmap.md).

## Documentation

Full knowledge base: [`obsidian/Index.md`](obsidian/Index.md)

## License

MIT — see [LICENSE](LICENSE)
