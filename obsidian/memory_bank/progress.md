# Progress — BlackDragon

> Status source: `Refactoring_roadmap.md`

## Phase Overview

| Phase  | Name                           | Status         | Key Deliverables                                                                    | Tag    |
| ------ | ------------------------------ | -------------- | ----------------------------------------------------------------------------------- | ------ |
| **P1** | 项目优化 (Project Standardization) | **Complete**   | README, .gitignore, requirements.txt, directory structure                           | v0.1.0 |
| **P2** | P0 修复 (Critical Fixes)         | **Complete**   | Logging, unified actions.py, centralized offsets.py, posture FSM, bare except sweep | v0.2.0 |
| P3     | 测试体系 (Test Safety Net)         | **Complete**   | 182 tests (60% coverage), GitHub Actions CI                                         | v0.3.0 |
| P4     | 架构重构 (Architecture Refactor)   | **Complete**   | src/core/, src/data/, src/model/, src/ui/, main.py                                  | —      |
| P5     | 控制中心 (Dashboard + Overlay)     | **Complete**   | Dashboard, Bootstrap, Dual-Process, PyInstaller EXE, Training Pipeline        | v1.1.0 |
| **P6.1** | **AutoML 模型迁移 (Model Migration)** | **Complete** | FLAML Run B XGBoost adoption, one-click retrain, data merge + backup chain, selftest gate | v1.2.0 |
| P6     | 模型工程化 (Model Engineering)     | Planned        | Model versioning, incremental learning, GitHub Release                         | —      |

---

## P6.1 — AutoML Model Migration (Complete ✅, v1.2.0)

**Experiment ✅, Run B adoption ✅, one-click integration ✅, overlay hotfix ✅, data safety ✅, release ✅**

### Experiment & Adoption
- [x] P0–P5 experiment infra: requirements-experiment.txt (flaml 2.6.0), shared dataset module + source_session provenance, four-metric benchmark CLI, holdout cache
- [x] P6 candidate search: Run A (6 features) / Run B (12 derived features), both xgboost; G1–G8 gate matrix
- [x] Run B attempt1 heap-crash root cause: FLAML `n_jobs=-1` → xgboost `nthread=-1` runtime-overrides OMP env vars → `--n-jobs` injection point fix
- [x] G5a attribution (two experiments + cross-candidate): booster deserialization one-shot cost → user Tier 2 acceptance (122MB)
- [x] Adoption via `scripts/adopt_model.py` (gated CLI + sidecar); production sha256 `ed3db5f8…`

### One-click Pipeline & Data Safety
- [x] `src/model/production_backend.py` — deterministic Run B retrain (auto_augment mirror, shuffle(1), n_jobs=1); `--pipeline` routed, `--train` legacy kept
- [x] `src/core/backup_chain.py` — two-generation chain (.bak/.bak2) + same-sha skip, shared by dataset & model writes
- [x] Cleaner merge semantics — absent sessions preserved from existing dataset; full CSV set = byte-identical rebuild
- [x] Training gates (warn-only: rows <50% prev / holdout <100 / classes −20%) + sidecar gate_warnings + train_*.log tee (last 10)
- [x] `models/factory_model.pkl` immutable rollback copy + raw combat CSVs bundled in release

### Overlay Hotfix & Selftest
- [x] RC1/RC2/RC-B fixes: `resolve_runtime_path()` frozen path resolution, load-failure logging, orange "⚠ AI 模型未加载" hint, `sklearn.pipeline` hiddenimport
- [x] `--selftest` on launch.py / overlay.py / both EXEs; build_exe.ps1 step 7 hard gate (Overlay @TEMP)

### Release (v1.2.0)
- [x] ADR-P6.1 written; CHANGELOG v1.2.0 (+v1.1.0 backfill); README updated (metrics / training / rollback / selftest)
- [x] `Fatalis-Prediction-v1.2.0-windows.zip` (G6 ≤300MB PASS, ~155MB)
- [x] 766 tests passed (581 → 766, +185); merged to main --no-ff; feature branch kept; **not pushed** (pending user decision)

---

## P5 — Control Center (Complete ✅)

**P5 Dashboard ✅, P5.1 Bootstrap ✅, P5.2 Overlay Experiment ✅, P5.3 Dual-Process ✅, P5.4 Training Pipeline ✅, Frozen EXE ✅**

### P5.3 — Dual-Process Overlay
- [x] Revert P5.2 experimental code — restore `src/ui/overlay.py` to standalone design
- [x] Clean `AppController` — remove in-process OverlayUI lifecycle
- [x] Create `overlay.py` — standalone overlay process entry
- [x] Rewrite `launch.py` — dual-process launcher (spawns overlay subprocess)
- [x] Dashboard UX: overlay subprocess start/stop button; StatusBar shows process status
- [x] 532 tests + 100% overlay.py coverage → rebased to 541

### P5.3 Auto-Start (ADR-P5.3)
- [x] `auto_start_overlay: bool = True` — launch.py gates on config
- [x] `auto_record: bool = True` — config-driven recording default
- [x] Overlay retry loop: `_find_game_process()` waits for game (60×2s)

### PyInstaller Frozen Support
- [x] Build specs: `build/BlackDragon.spec` + `build/BlackDragonOverlay.spec`
- [x] `scripts/build_exe.ps1` — one-click build (test → clean → build → merge)
- [x] Frozen path fixes: `controller.data_dir` (exe-relative), `start_training` cwd, `start_overlay` sibling exe
- [x] Model surfacing: `_internal/models/` → `dist/BlackDragon/models/`
- [x] Data surfacing: `_internal/data/` → `dist/BlackDragon/data/`
- [x] Training data: `data/ML_Ready_Dataset.csv` bundled + surfaced
- [x] UTF-8 fix: stdout reconfigure for emoji output in frozen `--train`
- [x] Training model save: `os.makedirs("models", exist_ok=True)`

### P5.4 — Training Pipeline Integration
- [x] `--pipeline` flag in `launch.py` — one-click `data_cleaner` → `train_lgbm`
- [x] `controller.start_training()` uses `--pipeline` (frozen: `[exe, --pipeline]`, dev: `[python, launch.py, --pipeline]`)
- [x] Unknown action defense: cleaner filters labels not in `ACTION_DB` + trainer secondary detection
- [x] `stratify=y` with small-dataset fallback (prevent LightGBM "unseen labels" crash)
- [x] NaN / non-numeric label warnings
- [x] Frozen EXE support: `data_cleaner` hidden import in `build/BlackDragon.spec`
- [x] 581 tests (569 baseline + 12 new); `pytest tests/ -q` all pass
- [x] ADR-P5.4 documented (Decision: Option A — `--pipeline` flag)
- [x] Frozen regression test: `BlackDragon.exe --pipeline` exit 0 (rebuild verified)
- [x] README updated: 581 tests badge, `--pipeline` entry point, pipeline workflow, frozen section

### Dashboard UX (P5.3 → v1.0)
- [x] Combat records display: `战斗记录: N 个` (not "CSV 文件")
- [x] Training data status: `训练数据: ML_Ready_Dataset.csv ✓` / `未找到`
- [x] Empty state hints: `暂无战斗记录（开始游戏录制后自动生成）`

### Release Engineering
- [x] `README.md` updated (P5.3 / 556 tests / 94% / entry points)
- [x] `LICENSE` (MIT), `CONTRIBUTING.md`, `SECURITY.md` added
- [x] Legacy markers on `main.py` + `ai_engine.py`
- [x] `obsidian/docs/legacy/` migration (15 files archived, `git mv`)
- [x] Repository cleanup: `TEST_COVERAGE_MAP.md`, `TEST_PRIORITY_LIST.md` → archive
- [x] RC test: 6/6 scenarios passed (install / dashboard / overlay / data / model / training)
- [x] Final Release Audit: 0 Must Fix, 2 Should Fix (resolved)
- [x] Knowledge Base v1.0 (50 active docs + 13 audit/build docs)

## Current State Summary

- **Phase**: P6.1 — v1.2.0 (AutoML Model Migration, experiment closed)
- **Project runs**: Yes — `python launch.py` (Dev) / `python launch.py --pipeline` (one-click Run B retrain, seconds) / `BlackDragon.exe` (Frozen, ~155MB zip / 286MB unpacked)
- **Tests**: **766** (100% pass rate); overall coverage **86%** (P4 core 100%)
- **Production model**: XGBoost pipeline (AutoML Run B) — top1 32.58% / top3_raw 66.19% / top3_filtered 65.37%; 7.46MB; single-threaded inference
- **P6.1 modules**: `src/model/production_backend.py`, `src/core/backup_chain.py`, `src/model/{dataset,features,label_decode,mlp_learner}.py`, `scripts/{train_automl,benchmark_model,export_model,adopt_model}.py`
- **Root entries**: `launch.py` (primary), `overlay.py` (secondary), `main.py` (legacy), `ai_engine.py` (legacy)
- **Build**: `build/BlackDragon.spec`, `build/BlackDragonOverlay.spec`, `scripts/build_exe.ps1` (selftest hard gate in step 7)
- **Rollback**: factory_model.pkl (shipped) / .bak / .bak2; dataset rebuild from bundled raw CSVs
- **ADR**: ADR-P5.2 (dual-process), ADR-P5.3 (auto-start), ADR-P5.4 (training pipeline), ADR-P6.1 (AutoML migration)
- **Pending**: push + GitHub Release (user decision)
