# Changelog

All notable changes to the BlackDragon project.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.1.0-project-init] — 2026-06-22

### Added

- `.gitignore` — excludes `.venv/`, `__pycache__/`, `data/*.csv`, `models/*.pkl`, `models/*.png`, `.idea/`
- `requirements.txt` — pinned dependency versions (dearpygui, lightgbm, pymem, etc.)
- `README.md` — project overview, install guide, usage, directory structure
- `CHANGELOG.md` — this file
- `data/` directory — all combat recording CSVs moved here
- `models/` directory — trained model (`.pkl`) and feature importance plot (`.png`) moved here
- `archive/` directory — deprecated `mod.py` moved here
- `tests/` directory — `manual_checklist.md` for manual verification
- `archive/README.md` — explains archive purpose

### Changed

- Updated file paths in `ai_engine.py` (CSV output → `data/`, model load → `models/`)
- Updated file paths in `data_cleaner.py` (CSV glob + output → `data/`)
- Updated file paths in `train_lgbm.py` (dataset → `data/`, model + plot → `models/`)
- Updated file paths in `data_upgrade.py` (CSV glob → `data/`)
- Moved `出招表.txt` and `招式表2.0.txt` to `docs/`

### Verified

- `python data_cleaner.py` processes all 17 CSV files → 2447 valid samples
- `python train_lgbm.py` trains successfully (Top-3 accuracy: 56.17%)
- All imports resolve correctly
- All file paths point to correct new locations

---

## Prior Versions

No version history exists before v0.1.0. The project was previously an unversioned monolithic script.
