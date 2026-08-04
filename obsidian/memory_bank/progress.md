# Progress — BlackDragon

> Status source: `Refactoring_roadmap.md`

## Phase Overview

| Phase  | Name                           | Status         | Key Deliverables                                                                    | Tag    |
| ------ | ------------------------------ | -------------- | ----------------------------------------------------------------------------------- | ------ |
| **P1** | 项目优化 (Project Standardization) | **Complete**   | README, .gitignore, requirements.txt, directory structure                           | v0.1.0 |
| **P2** | P0 修复 (Critical Fixes)         | **Complete**   | Logging, unified actions.py, centralized offsets.py, posture FSM, bare except sweep | v0.2.0 |
| P3     | 测试体系 (Test Safety Net)         | **Complete**   | 182 tests (60% coverage), GitHub Actions CI                                         | v0.3.0 |
| P4     | 架构重构 (Architecture Refactor)   | **Complete**   | src/core/, src/data/, src/model/, src/ui/, main.py                                  | —      |
| P5     | 控制中心 (Dashboard + Overlay)     | **Complete**   | Dashboard, Bootstrap, Dual-Process, PyInstaller EXE                                 | —      |
| P6     | 模型工程化 (Model Engineering)     | Planned        | Model versioning, incremental learning, GitHub Release v1.0.0                       | —      |

---

## P5 — Control Center (Complete ✅)

**P5 Dashboard ✅, P5.1 Bootstrap ✅, P5.2 Overlay Experiment ✅, P5.3 Dual-Process ✅, Frozen EXE ✅**

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

### Dashboard UX (P5.3 → v1.0)
- [x] Combat records display: `战斗记录: N 个` (not "CSV 文件")
- [x] Training data status: `训练数据: ML_Ready_Dataset.csv ✓` / `未找到`
- [x] Empty state hints: `暂无战斗记录（开始游戏录制后自动生成）`

### Release Engineering
- [x] `README.md` updated (P5.3 / 551 tests / 94% / entry points)
- [x] `LICENSE` (MIT), `CONTRIBUTING.md`, `SECURITY.md` added
- [x] Legacy markers on `main.py` + `ai_engine.py`
- [x] `obsidian/docs/legacy/` migration (15 files archived, `git mv`)
- [x] Repository cleanup: `TEST_COVERAGE_MAP.md`, `TEST_PRIORITY_LIST.md` → archive
- [x] RC test: 6/6 scenarios passed (install / dashboard / overlay / data / model / training)
- [x] Final Release Audit: 0 Must Fix, 2 Should Fix (resolved)
- [x] Knowledge Base v1.0 (50 active docs + 13 audit/build docs)

## Current State Summary

- **Phase**: P5.3 — v1.0 Release Candidate (Dual-Process Overlay + Frozen EXE)
- **Project runs**: Yes — `python launch.py` (Dev) / `BlackDragon.exe` (Frozen, 227 MB package)
- **Tests**: **551** (27 test files, 100% pass rate)
- **Coverage**: **94%** overall; P4 core 100%; Dashboard components 85-98%
- **P5 modules**: `src/app/` (controller, config, game_service), `src/dashboard/`, `src/bootstrap/`, `src/ui/fonts.py`
- **Root entries**: `launch.py` (primary), `overlay.py` (secondary), `main.py` (legacy), `ai_engine.py` (legacy)
- **Build**: `build/BlackDragon.spec`, `build/BlackDragonOverlay.spec`, `scripts/build_exe.ps1`
- **P4 core status**: `src/core/`, `src/model/`, `src/data/` — **zero diff** since P4.6
- **KB v1.0**: 50 active docs + 16 legacy + 13 audit/build docs
- **ADR**: ADR-P5.2 (dual-process), ADR-P5.3 (auto-start + recording)
