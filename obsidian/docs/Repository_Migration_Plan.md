# Repository Migration Plan — BlackDragon v1.0

- **Date**: 2026-08-04
- **Author**: Release Engineer
- **Source**: `obsidian/docs/Repository_Structure_Proposal.md`
- **Status**: Proposed — no files modified

---

## Executive Summary

当前根目录 20 个文件，迁移目标 12 个。但迁移有 **重大测试影响**：5 个 `.py` 文件被 7 个测试文件导入（140 tests），任何移动都会破坏测试。

因此本计划提供 **两份方案**：保守方案（零测试影响）和完整方案（需更新测试 import）。

---

## 1. Test Impact Analysis (Blocking Factor)

### 1.1 Import Dependency Map

| Root File | Imported By | Tests | Can Move? |
|-----------|-------------|:---:|:---:|
| `ai_engine.py` | `test_math_logic.py`, `test_phase_filter.py`, `test_nova.py` | **85** | 🔴 Blocked |
| `main.py` | `test_main_integration.py` | **20** | 🔴 Blocked |
| `data_cleaner.py` | `test_data_cleaner.py` | **19** | 🔴 Blocked |
| `data_upgrade.py` | `test_data_upgrade.py` | **11** | 🔴 Blocked |
| `train_lgbm.py` | `test_train_lgbm.py` | **5** | 🔴 Blocked |
| `launch.py` | `test_launch.py` | 11 | ✅ Stays in root |
| `overlay.py` | `test_overlay_entry.py` | 24 | ✅ Stays in root |

> **结论**: 140/541 tests (26%) 直接依赖根目录 `.py` 文件的当前路径。约束 `不修改 tests/` 意味着这些文件无法通过 `git mv` 移动。

### 1.2 CLI Runner Impact

| File | Import Path | After Migration | Fix Needed |
|------|-------------|-----------------|:---:|
| `data_cleaner.py` | `from src.config.actions import ...` | `scripts/data_cleaner.py` → `sys.path[0]` = `scripts/` | `sys.path.insert(0, ...)` |
| `data_upgrade.py` | same pattern | same | same |
| `train_lgbm.py` | `from src.logging_config import ...` | same | same |

### 1.3 CI Impact

`.github/workflows/test.yml` does NOT invoke training scripts directly. It calls `pytest --cov` which discovers tests via `testpaths = tests` in `pytest.ini`. Moving `.py` files themselves would break test imports, but the CI pipeline already handles this scenario (stub modules for pymem/dpg on Linux). Test import path updates would auto-resolve.

---

## 2. Plan A: Conservative Migration（推荐 — 零测试影响）

### 2.1 Scope

仅移动**无测试依赖**的文件。不影响 541 tests。

### 2.2 Migration Table

| # | Source | Destination | Method | Risk |
|---|--------|-------------|--------|:---:|
| 1 | `TEST_COVERAGE_MAP.md` | `archive/legacy_reports/TEST_COVERAGE_MAP.md` | `git mv` | None |
| 2 | `TEST_PRIORITY_LIST.md` | `archive/legacy_reports/TEST_PRIORITY_LIST.md` | `git mv` | None |
| 3 | `.coverage` | Delete | `rm` | None (git-ignored, temp data) |
| 4 | `blackdragon.log` | Delete + `.gitignore` verify | `rm` | None (git-ignored) |

### 2.3 Files NOT Moved (Reason)

| File | Reason for Keeping at Root |
|------|---------------------------|
| `ai_engine.py` | Imported by 3 test files (85 tests) |
| `main.py` | Imported by `test_main_integration.py` (20 tests) |
| `data_cleaner.py` | Imported by `test_data_cleaner.py` (19 tests) |
| `data_upgrade.py` | Imported by `test_data_upgrade.py` (11 tests) |
| `train_lgbm.py` | Imported by `test_train_lgbm.py` (5 tests) |
| `launch.py` | Primary entry point |
| `overlay.py` | Secondary entry point |

### 2.4 After Migration (Conservative)

```
BlackDragon/
├── README.md         CONTRIBUTING.md    SECURITY.md
├── LICENSE           CHANGELOG.md
├── requirements.txt  pytest.ini         .coveragerc     .gitignore
├── launch.py         overlay.py
├── ai_engine.py      main.py                          ← stays (test dependency)
├── data_cleaner.py   data_upgrade.py   train_lgbm.py  ← stays (test dependency)
├── src/              tests/            archive/        obsidian/
```

根目录: **16 files**（从 20 减少到 16，减少 4 个临时/过期文件）

**优势**:
- 零测试破坏 ✅
- 零 src 修改 ✅
- 零 test 修改 ✅
- 约束完全满足 ✅

**劣势**:
- 仍保留 5 个 `.py` 在根目录（未达到理想的 12-item root）
- `ai_engine.py` / `main.py` 仍在根目录可能与 `launch.py` 混淆

### 2.5 Mitigation for Remaining Clutter

在 README 中通过清晰的 Entry Points 表格区分：

```markdown
## Entry Points

### Runtime（直接使用）
| Command | Description |
| `python launch.py` | Dashboard + Overlay 双进程（推荐） |
| `python overlay.py` | 独立 Overlay 进程 |

### Training（模型训练）
| `python data_cleaner.py` | ... |
| `python train_lgbm.py` | ... |

### Legacy（历史参考，不再维护）
| `python main.py` | P4 单进程架构 |
| `python ai_engine.py` | God Class |
```

---

## 3. Plan B: Full Migration（需放宽约束）

### 3.1 Scope

移动所有 5 个可迁移 `.py` 文件 + 清洁临时文件。需更新 7 个测试文件的 import 路径。

### 3.2 Migration Table

| # | Source | Destination | Test Impact |
|---|--------|-------------|-------------|
| 1 | `ai_engine.py` | `archive/ai_engine.py` | 3 文件 (85 tests) import 更新 |
| 2 | `main.py` | `archive/main.py` | 1 文件 (20 tests) import 更新 |
| 3 | `data_cleaner.py` | `scripts/data_cleaner.py` | 1 文件 (19 tests) + `sys.path` 引导 |
| 4 | `data_upgrade.py` | `scripts/data_upgrade.py` | 1 文件 (11 tests) + `sys.path` 引导 |
| 5 | `train_lgbm.py` | `scripts/train_lgbm.py` | 1 文件 (5 tests) + `sys.path` 引导 |
| 6 | `TEST_COVERAGE_MAP.md` | `archive/legacy_reports/` | None |
| 7 | `TEST_PRIORITY_LIST.md` | `archive/legacy_reports/` | None |
| 8 | `.coverage` | Delete | None |
| 9 | `blackdragon.log` | Delete | None |

### 3.3 Test Import Updates Required

| Test File | Old Import | New Import | Tests |
|-----------|-----------|-----------|:---:|
| `test_math_logic.py` | `from ai_engine import ...` | `from archive.ai_engine import ...` | 27 |
| `test_phase_filter.py` | `from ai_engine import ...` | `from archive.ai_engine import ...` | 32 |
| `test_nova.py` | `from ai_engine import evaluate_nova` | `from archive.ai_engine import evaluate_nova` | 26 |
| `test_main_integration.py` | `from main import main` | `from archive.main import main` | 20 |
| `test_data_cleaner.py` | `import data_cleaner` | `import scripts.data_cleaner` | 19 |
| `test_data_upgrade.py` | `import data_upgrade` | `import scripts.data_upgrade` | 11 |
| `test_train_lgbm.py` | `import train_lgbm` | `import scripts.train_lgbm` | 5 |

**Total test files changed**: 7 (import path only, no logic change)

### 3.4 CLI Script Fix

每份移到 `scripts/` 的脚本顶部添加 3 行路径引导：

```python
# scripts/data_cleaner.py (line 1-3, before all other imports)
import sys, os
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

### 3.5 After Migration (Full)

```
BlackDragon/
├── README.md         CONTRIBUTING.md    SECURITY.md
├── LICENSE           CHANGELOG.md
├── requirements.txt  pytest.ini         .coveragerc     .gitignore
├── launch.py         overlay.py
├── scripts/                              ← CLI tools
│   ├── data_cleaner.py
│   ├── data_upgrade.py
│   └── train_lgbm.py
├── archive/                              ← legacy entries
│   ├── ai_engine.py
│   ├── main.py
│   ├── enrage.py
│   ├── mod.py
│   └── legacy_reports/
├── src/              tests/              obsidian/
```

根目录: **12 files** ✅

### 3.6 Constraint Relaxation Required

| Constraint | Original | Relaxed To | Reason |
|-----------|----------|-----------|--------|
| 不修改 tests/ | No changes | Import path updates only | 7 files, 0 logic changes, 0 assertion changes |
| 不修改 src/ | No changes | No changes | ✅ Fully respected |
| launch/overlay usage | Unchanged | Unchanged | ✅ Fully respected |

> **重要**: 测试 import 路径更新属于 **模块引用调整（refactoring）**，不影响测试逻辑。所有 140 tests 的断言、fixture、mock 策略完全不变。

---

## 4. Rollback Plan

### 4.1 Conservative Migration (Plan A)

回滚成本: **极低** — 仅移动 4 个非代码文件。

```bash
# Undo:
git mv archive/legacy_reports/TEST_COVERAGE_MAP.md TEST_COVERAGE_MAP.md
git mv archive/legacy_reports/TEST_PRIORITY_LIST.md TEST_PRIORITY_LIST.md
# .coverage and blackdragon.log are git-ignored — no recovery needed
```

### 4.2 Full Migration (Plan B)

回滚成本: **中等** — 需 revert 7 test imports + 5 file moves。

```bash
git revert <commit-hash>
# OR:
git mv archive/ai_engine.py ai_engine.py
git mv archive/main.py main.py
git mv scripts/data_cleaner.py data_cleaner.py
git mv scripts/data_upgrade.py data_upgrade.py
git mv scripts/train_lgbm.py train_lgbm.py
# Revert test imports (7 files)
MPLBACKEND=Agg pytest tests/ -q  # verify 541
```

### 4.3 README Updates

两种方案均需更新 README。如果从 Plan B 回滚到 Plan A，需恢复旧路径。建议在 `CHANGELOG.md` 中记录迁移日期和回滚 commit。

---

## 5. Recommendation

### ✅ Execute Plan A (Conservative) Immediately — 零风险

- 清洁 4 个临时/过期文件
- 零测试影响
- 根目录从 20 → 16 items
- 可在任何时机执行，不阻塞 release

### 📋 Defer Plan B (Full) to Post-Release

- 需放宽 "不修改 tests/" 约束
- 需 architect + reviewer 审批 test import 更新
- Executable as follow-up PR after v1.0 tag
- Benefit: 12-item root, professional open-source standard

### Execution Order for Plan A

```
1. git rm .coverage blackdragon.log           (remove temp files)
2. git mv TEST_COVERAGE_MAP.md archive/legacy_reports/
3. git mv TEST_PRIORITY_LIST.md archive/legacy_reports/
4. MPLBACKEND=Agg pytest tests/ -q             (verify 541)
5. git commit -m "chore: clean root directory for v1.0 release"
```

### Files Untouched (Both Plans)

| Path | Reason |
|------|--------|
| `src/` | Core architecture — frozen |
| `tests/` | Test suite (Plan A: zero changes) |
| `obsidian/` | Knowledge base — frozen |
| `launch.py` / `overlay.py` | Primary entry points — frozen |
| `pytest.ini` / `.coveragerc` / `.gitignore` | Config files — frozen |
| `README.md` / `LICENSE` / `CONTRIBUTING.md` / `SECURITY.md` | Release docs — frozen |
