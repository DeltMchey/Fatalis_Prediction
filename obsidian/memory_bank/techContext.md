# Tech Context — BlackDragon

## Technology Stack

| Category | Technology | Version |
|----------|-----------|---------|
| Language | Python | 3.12.6 |
| Game memory reading | `pymem` | 1.14.0 |
| GUI / Overlay | `dearpygui` | 2.3 |
| ML model (production, v1.2) | `xgboost` | 3.4.1 |
| ML framework (legacy `--train`) | `lightgbm` | 4.6.0 |
| ML utilities | `scikit-learn` | 1.8.0 |
| AutoML search (experiment-only) | `flaml` | 2.6.0 |
| Data processing | `pandas`, `numpy` | 3.0.2, 2.4.4 |
| Visualization | `matplotlib` | 3.10.9 |
| Model persistence | `joblib` | 1.5.3 |
| Window management | `ctypes` (Win32 API) | Windows SDK |
| Concurrency | `threading` | stdlib |
| Packaging | `pyinstaller` | 6.21.0 |

> Experiment-only deps (`flaml`, `psutil`) live in `requirements-experiment.txt` and never enter the EXE runtime. `xgboost` + `scipy` (transitive) entered `requirements.txt` with the Run B adoption (ADR-P6.1).

## Environment Constraints

- **Platform**: Windows only (Win32 API for transparent overlay, pymem for process memory)
- **Game process**: `MonsterHunterWorld.exe` must be running
- **Python**: 3.x with virtual environment (`.venv/`)
- **Font**: `C:/Windows/Fonts/msyh.ttc` (Microsoft YaHei) required for Chinese text
- **IDE**: PyCharm (`.idea/` directory present)

## Memory Layout (Hardcoded Offsets)

### Base Addresses (module-relative)
```
Player Base:  0x050139A0
Monster Base: 0x051238C8
Zone Base:    0x0500ECA0
```

### Monster Entity Chain
```
[0x698] → [i * 0x8] → [0x138] → [0]  (iterate up to 10 slots)
```

### Monster Data Offsets
```
Position (float×3):    +0x160
Rotation (quat×4):     +0x170
HP Base:               +0x7670
  HP Max:              +0x60
  HP Current:          +0x64
Action ID (int32):     +0x6278
Enrage Struct:         +0x1BE30
  Enrage Timer:        +0x24
  Enrage Max:          +0x28
```

### Player Data Chain
```
[0x50] → [0xC0] → [0x670] → position (float×3)
```

### Zone Detection
```
[0xAED0] → zone_id (int32), 417 = Fatalis arena
```

**Critical**: These offsets are specific to one MHW build version. Game updates invalidate them. Currently hardcoded in 3 files — known tech debt #1.

## File Inventory

### Source Code — src/ (P4/P5/P6.1 modular architecture)
| File | Purpose |
|------|---------|
| `src/core/state_tracker.py` | CombatStateTracker — pure battle state FSM |
| `src/core/memory_reader.py` | MemoryReader — all pymem memory reads |
| `src/core/backup_chain.py` | Two-generation backup chain (`.bak`/`.bak2`) + same-sha skip — shared promotion primitive for dataset/model writes (P6.1) |
| `src/model/predictor.py` | ActionPredictor — XGBoost pipeline load + inference |
| `src/model/production_backend.py` | One-click Run B training backend — deterministic reproduction (FLAML auto_augment mirror + shuffle(1), `n_jobs=1`) (P6.1) |
| `src/model/dataset.py` | Shared dataset loading + session provenance (P6.1) |
| `src/model/features.py` | FeatureBuilder — 6→12 derived features inside the pipeline (P6.1) |
| `src/model/label_decode.py` | LabelDecodedEstimator — label-encoded wrapper restoring action IDs (P6.1) |
| `src/model/mlp_learner.py` | FLAML custom MLP learner (experiment-only, not in EXE) |
| `src/data/recorder.py` | CombatRecorder — CSV recording daemon |
| `src/ui/overlay.py` | OverlayUI — transparent DPG overlay |
| `src/ui/fonts.py` | Shared CJK font loading |
| `src/app/config.py` | AppConfig — JSON settings persistence + `resolve_runtime_path()` frozen path resolution |
| `src/app/controller.py` | AppController — lifecycle coordinator + training log tee (`models/train_*.log`, last 10) |
| `src/app/game_service.py` | GameService — background game detection |
| `src/dashboard/*.py` | Dashboard control center (main_window, status_bar, log_view, training_panel) |
| `src/bootstrap/checker.py` | DependencyChecker — env check |
| `src/config/actions.py` / `offsets.py` | Single source of truth for actions + memory offsets |

### Root Entry Points
| File | Purpose |
|------|---------|
| `launch.py` | P5.3 Dashboard + Overlay dual-process launcher (recommended; `--pipeline` / `--train` / `--selftest`) |
| `overlay.py` | Standalone Overlay process entry (`--selftest`) |
| `main.py` | Legacy P4 single-process entry |
| `ai_engine.py` | Legacy God Class (reference only) |
| `data_cleaner.py` / `data_upgrade.py` / `train_lgbm.py` | Offline data pipeline CLI tools (`train_lgbm.py` = legacy `--train` path; cleaner has merge semantics) |

### Experiment / Adoption CLIs (P6.1)
| File | Purpose |
|------|---------|
| `scripts/train_automl.py` | FLAML search CLI (budget, `--n-jobs` injection point, `--smoke`) |
| `scripts/benchmark_model.py` | Unified four-metric benchmark (top1 / top3_raw / top3_filtered / macro_top3 + gates) |
| `scripts/export_model.py` | Zero-flaml export (extract path, physical isolation from production) |
| `scripts/adopt_model.py` | Explicit adoption CLI (gate validation → .bak rotation → copy → load check → sidecar) |

### Build System
| File | Purpose |
|------|---------|
| `build/BlackDragon.spec` | PyInstaller spec — Dashboard EXE (xgboost.dll binaries + VERSION datas + factory_model.pkl + pickle-ref hiddenimports) |
| `build/BlackDragonOverlay.spec` | PyInstaller spec — Overlay EXE (incl. `sklearn.pipeline` dynamic pickle reference) |
| `scripts/build_exe.ps1` | One-click build (test → build → merge → surface model/data/factory → **step 7: both EXEs `--selftest` hard gate**; raw CSVs NOT bundled since v1.2.0 per user ruling 2026-09-16) |

### Data Assets
| File | Size | Description |
|------|------|-------------|
| `fatalis_combat_data_*.csv` (×19) | ~11 MB total | Raw recorded combat sessions (NOT shipped since v1.2.0 — user ruling 2026-09-16; retrain safety guaranteed by cleaner merge semantics, historical sessions preserved from existing dataset) |
| `ML_Ready_Dataset.csv` | ~86 KB | Cleaned transition pairs for training (with `source_session` provenance) |
| `fatalis_ai_model.pkl` | ~7.5 MB | Production model — XGBoost pipeline `Pipeline[FeatureBuilder, LabelDecodedEstimator(XGBClassifier)]` (AutoML Run B) |
| `factory_model.pkl` | ~7.5 MB | Immutable shipped-model copy (rollback target; never touched by training/rotation) |
| `fatalis_ai_model.pkl.bak` / `.bak2` | — | Two-generation retrain backup chain |
| `fatalis_ai_model.pkl.meta.json` | — | Sidecar: adoption/training provenance, gates, data summary, rollback info |

### Reference Documents
| File | Description |
|------|-------------|
| `出招表.txt` | Action ID → name mapping v1 |
| `招式表2.0.txt` | Action ID → name mapping v2 (with phase/posture annotations) |

## Dependencies (requirements.txt)

All pinned in `requirements.txt`:
```
dearpygui==2.3
joblib==1.5.3
lightgbm==4.6.0
matplotlib==3.10.9
numpy==2.4.4
pandas==3.0.2
Pymem==1.14.0
scikit-learn==1.8.0
scipy==1.18.0
xgboost==3.4.1
```

## Build / Run

```bash
# Development mode (requires game running for full functionality)
python launch.py          # Dashboard + Overlay dual-process (recommended)
python overlay.py         # Overlay process only
python main.py            # Legacy P4 single-process

# Offline data pipeline
python data_cleaner.py    # Produces ML_Ready_Dataset.csv (merge semantics)
python train_lgbm.py      # Legacy LightGBM path (--train)

# One-click Run B retrain (v1.2): clean+merge → XGBoost winning config, seconds
python launch.py --pipeline

# Self-test diagnostic (path resolution → model load → one predict → exit 0/1)
python launch.py --selftest
python overlay.py --selftest

# PyInstaller EXE build
.\scripts\build_exe.ps1 -Clean
# → dist/BlackDragon/BlackDragon.exe + BlackDragonOverlay.exe
# → release/Fatalis-Prediction-v1.2.0-windows.zip (step 7 selftest gate)

# Tests
MPLBACKEND=Agg pytest tests/ -q   # 766 tests, 86% coverage
```

CI/CD: `.github/workflows/test.yml` (Windows + Ubuntu, Python 3.11/3.12)

## Frozen Runtime (PyInstaller)

- Two EXEs in one directory: `BlackDragon.exe` + `BlackDragonOverlay.exe`
- Each EXE bundles Python runtime + dependencies in `_internal/` (incl. `xgboost.dll` — explicit binaries, PyInstaller 6.21 has no xgboost hook — and `xgboost/VERSION` datas, required at import)
- Runtime data (data/ + models/ + factory_model.pkl + raw combat CSVs) surfaced next to EXE (exe-relative paths via `resolve_runtime_path()`)
- Frozen path resolution: `sys.executable`-based; CWD-independent (verified by selftest @TEMP)
- Frozen subprocess spawn: `--pipeline` / `--train` / `--overlay` flag mode; `cwd=<exe_dir>`
- UTF-8 stdout fix: `sys.stdout.reconfigure(encoding="utf-8")` for emoji output
- `--selftest` mode (both EXEs): path resolution → model load → one predict → exit 0/1; wired as a build hard gate (`build_exe.ps1` step 7, `Start-Process -Wait -PassThru` for real GUI-process exit codes)
- Pickle dynamic references (`sklearn.pipeline`, `src.model.features/label_decode/production_backend`, `src.core.backup_chain`) declared as explicit hiddenimports — static analysis cannot see them (ADR-P6.1 Decision 6)
