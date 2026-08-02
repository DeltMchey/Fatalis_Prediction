# Tech Context — BlackDragon

## Technology Stack

| Category | Technology | Version (if known) |
|----------|-----------|-------------------|
| Language | Python 3 | Current unknown |
| Game memory reading | `pymem` | Current unknown |
| GUI / Overlay | `dearpygui` | Current unknown |
| ML framework | `lightgbm` | Current unknown |
| ML utilities | `scikit-learn` | Current unknown |
| Data processing | `pandas`, `numpy` | Current unknown |
| Visualization | `matplotlib` | Current unknown |
| Model persistence | `joblib` | Current unknown |
| Window management | `ctypes` (Win32 API) | Windows SDK |
| Concurrency | `threading` | stdlib |

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

### Source Code (6 files)
| File | Lines | Purpose |
|------|-------|---------|
| `ai_engine.py` | 328 | Main program: memory read + state machine + recording + AI inference + UI |
| `data_cleaner.py` | 130 | ETL: raw CSV → ML-ready dataset |
| `data_upgrade.py` | 76 | Backfill phase/enrage columns in old CSVs |
| `train_lgbm.py` | 82 | LightGBM training script |
| `enrage.py` | 82 | Memory scanner for reverse-engineering enrage struct |
| `mod.py` | 248 | Deprecated simpler overlay (no AI, no recording) |

### Data Assets
| File | Size | Description |
|------|------|-------------|
| `fatalis_combat_data_*.csv` (×17) | ~11 MB total | Raw recorded combat sessions |
| `ML_Ready_Dataset.csv` | ~88 KB | Cleaned transition pairs for training |
| `fatalis_ai_model.pkl` | ~18 MB | Trained LightGBM model |

### Reference Documents
| File | Description |
|------|-------------|
| `出招表.txt` | Action ID → name mapping v1 |
| `招式表2.0.txt` | Action ID → name mapping v2 (with phase/posture annotations) |

## Dependencies (requirements.txt)

Current unknown — no `requirements.txt` exists yet. Dependencies inferred from imports:
```
pymem
dearpygui
lightgbm
scikit-learn
pandas
numpy
matplotlib
joblib
```

## Build / Run

```bash
# Data pipeline
python data_cleaner.py    # Produces ML_Ready_Dataset.csv
python train_lgbm.py      # Produces fatalis_ai_model.pkl + feature_importance.png

# Main program (requires game running)
python ai_engine.py       # Launches transparent overlay

# Diagnostic tool (requires game running)
python enrage.py          # Live memory scanner for enrage struct
```

No build system, no package configuration, no CI/CD.
