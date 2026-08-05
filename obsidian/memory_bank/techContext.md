# Tech Context — BlackDragon

## Technology Stack

| Category | Technology | Version |
|----------|-----------|---------|
| Language | Python | 3.12.6 |
| Game memory reading | `pymem` | 1.14.0 |
| GUI / Overlay | `dearpygui` | 2.3 |
| ML framework | `lightgbm` | 4.6.0 |
| ML utilities | `scikit-learn` | 1.8.0 |
| Data processing | `pandas`, `numpy` | 3.0.2, 2.4.4 |
| Visualization | `matplotlib` | 3.10.9 |
| Model persistence | `joblib` | 1.5.3 |
| Window management | `ctypes` (Win32 API) | Windows SDK |
| Concurrency | `threading` | stdlib |
| Packaging | `pyinstaller` | 6.21.0 |

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

### Source Code — src/ (P4/P5 modular architecture)
| File | Purpose |
|------|---------|
| `src/core/state_tracker.py` | CombatStateTracker — pure battle state FSM |
| `src/core/memory_reader.py` | MemoryReader — all pymem memory reads |
| `src/model/predictor.py` | ActionPredictor — LightGBM load + inference |
| `src/data/recorder.py` | CombatRecorder — CSV recording daemon |
| `src/ui/overlay.py` | OverlayUI — transparent DPG overlay |
| `src/ui/fonts.py` | Shared CJK font loading |
| `src/app/config.py` | AppConfig — JSON settings persistence |
| `src/app/controller.py` | AppController — lifecycle coordinator |
| `src/app/game_service.py` | GameService — background game detection |
| `src/dashboard/*.py` | Dashboard control center (main_window, status_bar, log_view, training_panel) |
| `src/bootstrap/checker.py` | DependencyChecker — env check |
| `src/config/actions.py` / `offsets.py` | Single source of truth for actions + memory offsets |

### Root Entry Points
| File | Purpose |
|------|---------|
| `launch.py` | P5.3 Dashboard + Overlay dual-process launcher (recommended) |
| `overlay.py` | Standalone Overlay process entry |
| `main.py` | Legacy P4 single-process entry |
| `ai_engine.py` | Legacy God Class (reference only) |
| `data_cleaner.py` / `data_upgrade.py` / `train_lgbm.py` | Offline data pipeline CLI tools |

### Build System
| File | Purpose |
|------|---------|
| `build/BlackDragon.spec` | PyInstaller spec — Dashboard EXE |
| `build/BlackDragonOverlay.spec` | PyInstaller spec — Overlay EXE |
| `scripts/build_exe.ps1` | One-click build (test → build → merge → surface) |

### Data Assets
| File | Size | Description |
|------|------|-------------|
| `fatalis_combat_data_*.csv` (×19) | ~11 MB total | Raw recorded combat sessions |
| `ML_Ready_Dataset.csv` | ~86 KB | Cleaned transition pairs for training |
| `fatalis_ai_model.pkl` | ~18 MB | Trained LightGBM model |

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
```

## Build / Run

```bash
# Development mode (requires game running for full functionality)
python launch.py          # Dashboard + Overlay dual-process (recommended)
python overlay.py         # Overlay process only
python main.py            # Legacy P4 single-process

# Offline data pipeline
python data_cleaner.py    # Produces ML_Ready_Dataset.csv
python train_lgbm.py      # Produces fatalis_ai_model.pkl + feature_importance.png

# PyInstaller EXE build
.\scripts\build_exe.ps1 -Clean
# → dist/BlackDragon/BlackDragon.exe + BlackDragonOverlay.exe
# → release/BlackDragon-v1.1.0-windows.zip

# Tests
MPLBACKEND=Agg pytest tests/ -q   # 581 tests, 94% coverage
```

CI/CD: `.github/workflows/test.yml` (Windows + Ubuntu, Python 3.11/3.12)

## Frozen Runtime (PyInstaller)

- Two EXEs in one directory: `BlackDragon.exe` + `BlackDragonOverlay.exe`
- Each EXE bundles Python runtime + dependencies in `_internal/`
- Runtime data (data/ + models/) surfaced next to EXE (exe-relative paths)
- Frozen path resolution: `sys.executable`-based (`<exe_dir>/data`, `<exe_dir>/models`)
- Frozen subprocess spawn: `--pipeline` / `--train` / `--overlay` flag mode; `cwd=<exe_dir>`
- UTF-8 stdout fix: `sys.stdout.reconfigure(encoding="utf-8")` for emoji output
