# Repository Structure Proposal — BlackDragon v1.0

- **Date**: 2026-08-04
- **Author**: Release Engineer
- **Scope**: Root directory cleanup for GitHub release
- **Status**: Proposed — no files modified

---

## 1. Current State: Root Directory Audit

### 1.1 File Inventory (20 items)

```
BlackDragon/                          
├── .coverage                  ⚠️ temp data (git-ignored, should not be committed)
├── .coveragerc                ✅ coverage config — keep
├── .gitignore                 ✅ git rules — keep
├── pytest.ini                 ✅ test config — keep
├── requirements.txt           ✅ dependencies — keep
├── README.md                  ✅ project intro — keep
├── LICENSE                    ✅ license — keep
├── CHANGELOG.md               ✅ version history — keep
├── CONTRIBUTING.md            ✅ contribution guide — keep
├── SECURITY.md                ✅ security policy — keep
├── TEST_COVERAGE_MAP.md       ❌ P3 artifact, outdated — archive
├── TEST_PRIORITY_LIST.md      ❌ P3 artifact, outdated — archive
├── blackdragon.log            ❌ runtime log (git-ignored) — clean
│
├── launch.py                  ✅ P5.3 primary entry point — MUST keep
├── overlay.py                 ✅ P5.3 secondary entry point — keep
│
├── ai_engine.py               ⚠️ LEGACY God Class (488 lines) — move
├── main.py                    ⚠️ LEGACY P4 entry (88 lines) — move
│
├── data_cleaner.py            ⚠️ CLI tool (ETL) — candidate: scripts/
├── data_upgrade.py            ⚠️ CLI tool (CSV upgrade) — candidate: scripts/
└── train_lgbm.py              ⚠️ CLI tool (ML training) — candidate: scripts/
```

### 1.2 Problem Summary

| Problem | Files | Impact |
|---------|-------|--------|
| **Root clutter** | 20 files — hard to find the important ones | New user sees 7 `.py` files, doesn't know which to run |
| **Legacy confusion** | `ai_engine.py` / `main.py` next to `launch.py` | User may run wrong entry point, get outdated behavior |
| **CLI tools interleaved** | `data_cleaner.py` / `train_lgbm.py` with entry points | README `python launch.py` is buried among scripts |
| **Stale artifacts** | `TEST_COVERAGE_MAP.md` / `TEST_PRIORITY_LIST.md` | P3-era docs, outdated (ref: `tests/manual_checklist.md` at 541 tests, not 385) |
| **Unclean working tree** | `.coverage` / `blackdragon.log` | Temporary files should not be in repo |

---

## 2. Design Goals

| Goal | Description |
|------|-------------|
| **5-second understanding** | New user reads root → immediately sees `launch.py` and `README.md` |
| **One command to run** | `pip install -r requirements.txt && python launch.py` |
| **No dead ends** | Every root file is either essential or obviously categorized |
| **GitHub standards** | `README.md`, `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md` all visible |
| **No import breakage** | Moving files must not break `from src.config import ...` imports |

---

## 3. Proposed Structure

### 3.1 New Root Directory (14 files → 12 files)

```
BlackDragon/                          
├── README.md                  ✅ project intro
├── LICENSE                    ✅ license
├── CHANGELOG.md               ✅ version history
├── CONTRIBUTING.md            ✅ contribution guide
├── SECURITY.md                ✅ security policy
│
├── requirements.txt           ✅ dependencies
├── pytest.ini                 ✅ test config
├── .coveragerc                ✅ coverage config
├── .gitignore                 ✅ git rules
│
├── launch.py                  ✅ primary entry — `python launch.py`
├── overlay.py                 ✅ secondary entry — `python overlay.py`
│
├── scripts/                   ★ CLI tools (moved)
│   ├── data_cleaner.py        # ETL pipeline
│   ├── data_upgrade.py        # CSV backfill
│   └── train_lgbm.py          # Model training
│
├── archive/                   ★ Legacy entries (moved here)
│   ├── ai_engine.py           # LEGACY God Class
│   ├── main.py                # LEGACY P4 entry
│   ├── enrage.py              # (already present)
│   ├── mod.py                 # (already present)
│   └── legacy_reports/        # (already present)
│
├── src/                       [unchanged — P4/P5 modules]
├── tests/                     [unchanged — 25 test files]
└── obsidian/                  [unchanged — knowledge base]
```

### 3.2 Files to Remove / Clean

| File | Reason | Action |
|------|--------|--------|
| `blackdragon.log` | Runtime log — git-ignored, accidentally tracked | Remove, verify `.gitignore` |
| `.coverage` | pytest temp data — git-ignored | Remove, verify `.gitignore` |
| `TEST_COVERAGE_MAP.md` | P3 artifact — outdated (385 tests) | Move to `archive/legacy_reports/` |
| `TEST_PRIORITY_LIST.md` | P3 artifact — outdated | Move to `archive/legacy_reports/` |

### 3.3 After Cleanup

```
$ ls BlackDragon/
CHANGELOG.md   CONTRIBUTING.md  LICENSE   README.md   SECURITY.md
.coveragerc    .gitignore       pytest.ini  requirements.txt
launch.py      overlay.py
archive/       scripts/        src/       tests/     obsidian/
```

12 items in root. All `.py` files are entry points. All `.md` / config files are self-explanatory.

---

## 4. Migration Plan

### 4.1 File Moves

| # | Source | Destination | Risk | Import Fix Needed? |
|---|--------|-------------|:---:|:---:|
| 1 | `ai_engine.py` | `archive/ai_engine.py` | Low | No — never imported by src/ |
| 2 | `main.py` | `archive/main.py` | Low | No — never imported by src/ |
| 3 | `data_cleaner.py` | `scripts/data_cleaner.py` | Medium | Yes — needs `sys.path` fix |
| 4 | `data_upgrade.py` | `scripts/data_upgrade.py` | Medium | Yes — needs `sys.path` fix |
| 5 | `train_lgbm.py` | `scripts/train_lgbm.py` | Medium | Yes — needs `sys.path` fix |
| 6 | `TEST_COVERAGE_MAP.md` | `archive/legacy_reports/TEST_COVERAGE_MAP.md` | None | N/A |
| 7 | `TEST_PRIORITY_LIST.md` | `archive/legacy_reports/TEST_PRIORITY_LIST.md` | None | N/A |
| 8 | `.coverage` | Delete | None | N/A |
| 9 | `blackdragon.log` | Delete | None | N/A |

### 4.2 Import Fix for scripts/

`data_cleaner.py`, `data_upgrade.py`, `train_lgbm.py` all use:

```python
from src.config.actions import ...
from src.config.offsets import ...
```

When run from project root (`python data_cleaner.py`), `sys.path[0]` = `''` (cwd), so `import src.config` works.

After moving to `scripts/`:
- `python scripts/data_cleaner.py` → `sys.path[0]` = `scripts/` → `import src.config` **FAILS** (looks for `scripts/src/config/...`)

**Fix**: Add a path-bootstrapping block at the top of each script:

```python
# scripts/data_cleaner.py (add at top, before other imports)
import sys, os
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

This ensures `scripts/data_cleaner.py` can still import `src.config.actions` when run from any working directory.

**Alternative**: Use `python -m scripts.data_cleaner` (module run) — but this requires users to know `-m` flag and is less intuitive than `python scripts/data_cleaner.py`.

### 4.3 README Updates Required

After migration:

```bash
# Before (current):
python data_cleaner.py
python train_lgbm.py

# After:
python scripts/data_cleaner.py
python scripts/train_lgbm.py
```

Entry Points table in README would update to reflect new script locations.

### 4.4 test_launch.py Impact

`tests/test_launch.py` performs AST-level structural checks on `launch.py` (e.g., "no module-level import pymem"). These tests import the `launch` module directly. Since `launch.py` stays in root, tests are unaffected.

`tests/test_main_integration.py` imports `main` module directly. If `main.py` moves to `archive/`, this import breaks. **Fix**: `git mv main.py archive/main.py` — the test's `from main import main` would need to become `from archive.main import main`, or the test could be updated to use `sys.path.insert`.

### 4.5 Obsidian Links

Obsidian wikilinks referencing `[[main.py]]` or `[[ai_engine.py]]` — these are unlikely (no such links found in the KB audit). Memory bank references `ai_engine.py` by name in text, not as a wikilink target. No link breakage expected.

---

## 5. Risk Analysis

### 🔴 High Risk

| # | Risk | Mitigation |
|---|------|-----------|
| R1 | Moving `main.py` breaks `tests/test_main_integration.py` (20 tests import `from main import main`) | Update test import to `from archive.main import main` + verify all 20 tests pass |
| R2 | Moving CLI tools breaks user muscle memory (`python data_cleaner.py` → `python scripts/data_cleaner.py`) | README update is the authoritative doc; CHANGELOG notes the migration |

### 🟡 Medium Risk

| # | Risk | Mitigation |
|---|------|-----------|
| R3 | `sys.path` insertion in scripts may have edge cases (PyInstaller, subprocess, etc.) | Test on clean clone after migration |
| R4 | CI workflow references `python train_lgbm.py` — needs path update | Update `.github/workflows/test.yml` if it invokes training directly |

### 🟢 Low Risk

| # | Risk | Mitigation |
|---|------|-----------|
| R5 | Someone has `ai_engine.py` bookmarked — link break | Legacy files are in `archive/` with clear README |
| R6 | User confusion — "where did main.py go?" | README Entry Points table clearly states legacy status + location |

---

## 6. Recommendation

### Decision: ✅ RECOMMEND EXECUTION (after review)

The migration reduces root file count from 20 to 12, eliminates legacy confusion, and achieves professional open-source standards. All risks are manageable with documented mitigations.

### Recommended Execution Order

1. Create `scripts/` directory
2. Move `data_cleaner.py`, `data_upgrade.py`, `train_lgbm.py` → `scripts/`
   - Add `sys.path` bootstrap to each (3 × 3-line addition)
3. Move `ai_engine.py`, `main.py` → `archive/`
4. Move `TEST_COVERAGE_MAP.md`, `TEST_PRIORITY_LIST.md` → `archive/legacy_reports/`
5. Remove `.coverage`, `blackdragon.log` (gitignored, cleanup only)
6. Update `tests/test_main_integration.py` import path
7. Update `README.md` (CLI tools paths + Entry Points table)
8. Run `MPLBACKEND=Agg pytest tests/ -q` — verify 541 tests
9. Commit as single `chore: reorganize repository structure for v1.0 release`

### Files NOT Touched

| Path | Reason |
|------|--------|
| `src/` | Core architecture — frozen |
| `tests/` | Test suite — unchanged (except main import path) |
| `obsidian/` | Knowledge base — unchanged |
| `pytest.ini`, `.coveragerc`, `.gitignore` | Config files — unchanged |
| `data/`, `models/` | User data — gitignored, untouched |

---

## Appendix: Before/After Comparison

### Before

```
$ ls
ai_engine.py  data_upgrade.py  main.py       requirements.txt
blackdragon.log  launch.py     overlay.py    TEST_COVERAGE_MAP.md
CHANGELOG.md  LICENSE          pytest.ini    TEST_PRIORITY_LIST.md
CONTRIBUTING.md  .coveragerc   README.md     train_lgbm.py
data_cleaner.py  .gitignore    SECURITY.md   .coverage
```

20 items, 7 `.py` files — unclear which is the entry point.

### After

```
$ ls
CHANGELOG.md   CONTRIBUTING.md  LICENSE   README.md   SECURITY.md
.coveragerc    .gitignore       pytest.ini  requirements.txt
launch.py      overlay.py
archive/       scripts/        src/       tests/     obsidian/
```

12 items, 2 `.py` files — `launch.py` obviously the entry point. Clean, professional.
