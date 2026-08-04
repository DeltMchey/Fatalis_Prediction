# Release Commit Plan — BlackDragon v1.0.0

- **Date**: 2026-08-04
- **Branch**: master
- **HEAD**: `d055717 docs: complete legacy documentation migration`
- **Plan**: 3 commits for v1.0.0 release

---

## 1. Current Git State

| Category | Files | Notes |
|----------|:---:|------|
| Staged (rename) | 2 | `TEST_COVERAGE_MAP.md`, `TEST_PRIORITY_LIST.md` → `archive/` |
| Modified (unstaged) | 14 | Frozen fixes, tests, MB, README, config |
| Untracked (new) | ~20 | Build specs, scripts, docs, release files |

---

## 2. Commit Plan

### Commit 1: `feat: implement PyInstaller frozen runtime support and UX improvements`

**Scope**: All frozen runtime fixes, PyInstaller build system, dashboard UX enhancements, test additions.

```bash
# -- Frozen runtime fixes --
git add launch.py                                  # --train flag, frozen bootstrap gate, UTF-8 stdout
git add src/app/controller.py                      # data_dir frozen-aware, start_training/start_overlay frozen branches
git add src/dashboard/main_window.py                # combat records + training data display
git add train_lgbm.py                              # os.makedirs("models", exist_ok=True)

# -- PyInstaller build system (new files) --
git add build/BlackDragon.spec                      # Dashboard EXE spec
git add build/BlackDragonOverlay.spec               # Overlay EXE spec
git add scripts/build_exe.ps1                       # One-click build script

# -- Config --
git add .gitignore                                  # build/ + dist/ ignore rules

# -- Tests --
git add tests/test_app_controller.py                # FrozenPath tests, frozen training flag
git add tests/test_launch.py                        # TrainMode tests
git add tests/test_dashboard.py                     # TestRefreshCsvList updates

# Commit message:
git commit -m "feat: implement PyInstaller frozen runtime support and UX improvements

Frozen Runtime:
- controller: data_dir exe-relative path resolution
- controller: start_training/start_overlay frozen-mode subprocess spawn
- launch.py: --train flag for subprocess entry + UTF-8 stdout reconfigure
- train_lgbm.py: os.makedirs('models', exist_ok=True) for frozen model save

Build System:
- build/BlackDragon.spec — Dashboard EXE (hidden imports, datas, excludes)
- build/BlackDragonOverlay.spec — Overlay EXE (smaller bundle, excludes dashboard)
- scripts/build_exe.ps1 — one-click build (test → clean → build → merge → surface)
- .gitignore: build artifacts + dist/ added

Dashboard UX:
- Combat records display: battle_record_count + empty-state hint
- Training data status: ML_Ready_Dataset.csv present/missing indicator

Tests: 541 → 551 (+10: frozen paths, training mode, dashboard UI)"
```

**Files**: 11 (7 modified + 4 new)
**Build artifacts excluded**: `build/BlackDragon/`, `build/BlackDragonOverlay/` (git-ignored since they contain `.toc`/`.pyz`/`.exe` temp files)

---

### Commit 2: `docs: add v1.0 release documentation and PyInstaller guides`

**Scope**: All release-related documentation (audits, guides, runtime reports, analysis), Memory Bank updates, README polish.

```bash
# -- Release audits & reports --
git add obsidian/docs/Final_Release_Audit.md
git add obsidian/docs/Frozen_Fix_Review.md
git add obsidian/docs/Frozen_Model_Lifecycle_Audit.md
git add obsidian/docs/Frozen_Runtime_Bug_Report.md
git add obsidian/docs/Frozen_Training_Data_Analysis.md
git add obsidian/docs/Release_Candidate_Runtime_Test.md
git add obsidian/docs/Release_Readiness_Audit.md

# -- PyInstaller docs --
git add obsidian/docs/PyInstaller_Build_Guide.md
git add obsidian/docs/PyInstaller_Packaging_Architecture.md
git add obsidian/docs/PyInstaller_Packaging_Research.md
git add obsidian/docs/PyInstaller_Review.md

# -- Repository planning docs --
git add obsidian/docs/Repository_Migration_Plan.md
git add obsidian/docs/Repository_Structure_Proposal.md

# -- Future roadmap (v1.1) --
git add obsidian/docs/Training_Pipeline_Integration_Analysis.md

# -- README + Memory Bank --
git add README.md                                    # Updated badges (551 tests), entry points, structure, roadmap
git add obsidian/memory_bank/activeContext.md         # Updated to v1.0 RC
git add obsidian/memory_bank/changelog.md             # v1.0 RC entry
git add obsidian/memory_bank/progress.md              # Updated to v1.0 RC

git commit -m "docs: add v1.0 release documentation and PyInstaller guides

Release Audits:
- Final Release Audit (0 Must Fix, 2 Should Fix → resolved)
- Release Readiness Audit (repository, license, sensitive data, packaging)
- Release Candidate Runtime Test (6/6 scenarios passed)
- Frozen Bug Reports & Fix Reviews (4 bug reports, 2 fix reviews)
- Frozen Model Lifecycle Audit (train → save → load → predict closed loop)
- Training Data Analysis (Option D — hybrid bundled + user-replaceable)

PyInstaller Docs:
- Packaging Research (component compatibility: DPG, pymem, LightGBM, numpy)
- Packaging Architecture (two-EXE split, spec design, post-build merge)
- Build Guide (dev environment, commands, resources, troubleshooting)
- Spec Review (hidden imports verification, build readiness)

Repository:
- Repository Structure Proposal (20→12 items root cleanup)
- Repository Migration Plan (14+5+3 file moves, import impact)
- Training Pipeline Integration Analysis (v1.1 roadmap)

README: badges 541→551, entry points table, dual-process architecture section
Memory Bank: activeContext, changelog, progress synced to v1.0 RC"
```

**Files**: 18 (16 new + 2 modified)

---

### Commit 3: `chore: add release boilerplate and archive legacy files`

**Scope**: GitHub release files (LICENSE, CONTRIBUTING, SECURITY), legacy markers, staged renames.

```bash
# -- Staged renames (from repository cleanup) --
# Already staged: TEST_COVERAGE_MAP.md → archive/legacy_reports/
# Already staged: TEST_PRIORITY_LIST.md → archive/legacy_reports/

# -- Legacy markers (comment-only changes, no logic modification) --
git add ai_engine.py                                # LEGACY comment (+4 lines)
git add main.py                                     # LEGACY ENTRY POINT comment (+3 lines)

# -- GitHub release boilerplate --
git add LICENSE                                     # MIT License (new)
git add CONTRIBUTING.md                             # Contribution guide (new)
git add SECURITY.md                                 # Security policy (new)

git commit -m "chore: add release boilerplate and archive legacy files

Release Files:
- LICENSE — MIT License (matching README badge)
- CONTRIBUTING.md — dev setup, test commands, PR process, architecture constraints
- SECURITY.md — vulnerability reporting, supported versions, security considerations

Legacy Markers:
- ai_engine.py: # LEGACY — superseded by src/ architecture
- main.py: # LEGACY ENTRY POINT — superseded by launch.py

Repository Cleanup:
- TEST_COVERAGE_MAP.md → archive/legacy_reports/
- TEST_PRIORITY_LIST.md → archive/legacy_reports/"
```

**Files**: 5 (2 modified + 3 new) + 2 staged renames

---

## 3. Special Checks

### 3.1 `Training_Pipeline_Integration_Analysis.md`

| Question | Answer |
|----------|--------|
| Should it go into v1.0? | **Yes** — it's an analysis document, not a code change. It serves as the design blueprint for v1.1 feature |
| Should it be in a separate branch? | No — committed to master as roadmap reference |
| Commit placement | Commit 2 (docs) |

### 3.2 `build/` Directory

| Path | Commit? | Reason |
|------|:---:|--------|
| `build/BlackDragon.spec` | ✅ Commit | Build recipe — needed for reproducible builds |
| `build/BlackDragonOverlay.spec` | ✅ Commit | Build recipe — needed for reproducible builds |
| `build/BlackDragon/` (subdirectory) | ❌ Ignore | Build artifacts (`.toc`, `.pyz`, `.exe`, `.pyc`) — gitignored |
| `build/BlackDragonOverlay/` (subdirectory) | ❌ Ignore | Same |
| `build/` other files | ❌ Ignore | All covered by `.gitignore` rules |
| `dist/` | ❌ Ignore | Build output — gitignored |
| `scripts/build_exe.ps1` | ✅ Commit | Build script |

**Verification**: `.gitignore` lines 18-20 correctly ignore `build/BlackDragon/`, `build/BlackDragonOverlay/`, `dist/`, `*.spec.bak`.

### 3.3 `ai_engine.py` and `main.py`

| File | Diff | Logic Change? | Commit? |
|------|------|:---:|:---:|
| `ai_engine.py` | +4 lines (LEGACY comment) | ❌ None | ✅ Commit 3 (chore) |
| `main.py` | +3 lines (LEGACY ENTRY POINT comment) | ❌ None | ✅ Commit 3 (chore) |

**Verdict**: Both are pure comment additions. Should go in the release commit (Commit 3) alongside other release housekeeping. They mark the items as legacy per the Release Readiness Audit (C11).

---

## 4. Commit Summary

| # | Message | Files | Type |
|:---:|------|:---:|------|
| 1 | `feat: implement PyInstaller frozen runtime support and UX improvements` | 11 | Feature |
| 2 | `docs: add v1.0 release documentation and PyInstaller guides` | 18 | Documentation |
| 3 | `chore: add release boilerplate and archive legacy files` | 7 | Chore |

**Total**: 36 files across 3 commits

### Files NOT Included (Correctly Ignored)

| Path | Reason |
|------|--------|
| `dist/` | Build output — gitignored |
| `build/BlackDragon/` | PyInstaller temp files — gitignored |
| `build/BlackDragonOverlay/` | PyInstaller temp files — gitignored |
| `obsidian/docs/Commit_Plan_Report.md` | Already committed (in prior KB commit) |
| `obsidian/docs/Legacy_Migration_Review.md` | Already committed |
| `obsidian/docs/Legacy_Migration_Final_Review.md` | Already committed |
| `obsidian/docs/Knowledge_Base_Audit.md` | Already committed |
| `obsidian/docs/Knowledge_Base_Content_Review.md` | Already committed |
| `obsidian/docs/Knowledge_Base_v1_Architecture.md` | Already committed |
| `obsidian/docs/Knowledge_Base_v1_Final_Review.md` | Already committed |

### Post-Commit Checklist

- [ ] `git log --oneline -3` shows the 3 commits
- [ ] 551 tests pass on HEAD
- [ ] `git tag v1.0.0` (after review approval)
- [ ] Push to remote
- [ ] Create GitHub Release with `dist/BlackDragon/` archive
