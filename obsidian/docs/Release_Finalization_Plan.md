# Release Finalization Plan — BlackDragon v1.0.0

- **Date**: 2026-08-04
- **Reviewer**: Final Release Review
- **Scope**: Post-commit analysis + hotfix integration

---

## 1. Current State

| Item | Status |
|------|:---:|
| v1.0.0 3 commits | ✅ At HEAD (a26e760) |
| overlay.py UTF-8 fix | ⚠️ Uncommitted (bug fix for release EXE) |
| test_overlay_entry.py UTF-8 tests | ⚠️ Uncommitted (+5 tests) |
| release/ directory | ⚠️ Untracked — NOT in .gitignore |
| 556 tests | ✅ Passing |
| release/BlackDragon-v1.0.0-windows.zip | ✅ Built (118.66 MB) |

---

## 2. Diff Analysis

### 2.1 overlay.py (+29 lines)

| Change | Classification |
|--------|:---:|
| `+ import sys` | Necessary for stdout reconfigure |
| `+ _ensure_utf8_stdio()` (17 lines) | Core fix — mirrors `launch.py --train` pattern |
| `+ _ensure_utf8_stdio()` call in `main()` (2 lines) | Invocation at earliest stage |

**Verdict**: ✅ **v1.0.0 hotfix** — runtime crash bug (UnicodeEncodeError in frozen Overlay EXE)

### 2.2 test_overlay_entry.py (~90 lines)

| Change | Classification |
|--------|:---:|
| 5 new tests in `TestUtf8Stdio` class | Regression safety net for the UTF-8 fix |

**Verdict**: ✅ **v1.0.0 hotfix companion** — ensures the fix is tested

---

## 3. release/ Directory

| Check | Finding |
|-------|---------|
| Is `release/` in .gitignore? | ❌ No |
| Is `release/` tracked by git? | ❌ No (untracked) |
| Zip size | 118.66 MB |
| Risk | Accidental `git add .` could commit the zip |

**Required**: Add `release/` to `.gitignore` immediately.

---

## 4. README / CHANGELOG / Memory Bank

| File | Current | Needs Update? |
|------|---------|:---:|
| `README.md` | Badge: `551 tests` | 🟡 Should be `556` (5 new UTF-8 tests) |
| `CHANGELOG.md` (root) | — | 🟡 No v1.0.0 entry |
| `obsidian/memory_bank/changelog.md` | Has v1.0.0 RC entry | 🟡 Should add final v1.0.0 release entry |

---

## 5. Finalization Plan

### Step 1: Hotfix Commit

```bash
git add overlay.py                         # UTF-8 fix
git add tests/test_overlay_entry.py        # UTF-8 tests
git add .gitignore                         # add release/ ignore rule

git commit -m "hotfix: add UTF-8 stdout reconfigure for overlay frozen EXE

Fixes UnicodeEncodeError in BlackDragonOverlay.exe when stdout is
redirected to PIPE (GBK encoding cannot encode emoji like \u2705).

- overlay.py: _ensure_utf8_stdio() helper (mirrors launch.py --train pattern)
- tests/test_overlay_entry.py: 5 new TestUtf8Stdio tests
- .gitignore: add release/ to prevent accidental zip commits"
```

**Files**: 3 (2 modified + 1 .gitignore update)
**Tests**: 551 → 556 (+5)

### Step 2: Update README badge

```bash
git add README.md  # 551 → 556
git commit -m "docs: update README test badge to 556 (v1.0.0 hotfix)"
```

### Step 3: Rebuild release zip (if needed)

If EXE was rebuilt after hotfix commit:
```bash
.\scripts\build_exe.ps1 -Clean
# Then repackage release zip
```

### Step 4: Git tag

```bash
git tag v1.0.0
```

### Step 5: GitHub Release

Upload `release/BlackDragon-v1.0.0-windows.zip` to GitHub Release.

---

## 6. Recommended Execution Order

| Step | Commands | Purpose |
|:---:|------|------|
| 1 | `git add overlay.py tests/test_overlay_entry.py .gitignore` + commit | Hotfix |
| 2 | `git add README.md` + commit (optional) | Polish |
| 3 | `git tag v1.0.0` | Tag |
| 4 | Upload zip to GitHub Release | Distribute |

---

## 7. Risk Assessment

| Risk | Severity | Notes |
|------|:---:|------|
| Overlay crash in release EXE | 🔴 Critical | Fixed by hotfix |
| release/ accidentally committed | 🟡 Medium | Fixed by .gitignore |
| README badge stale (551→556) | 🟢 Low | Cosmetic only |
| CHANGELOG without v1.0.0 entry | 🟢 Low | Can add in next release |

---

## 8. Decision

### ✅ Recommend: Execute Steps 1-4

The overlay UTF-8 fix is a runtime crash bug in the release EXE and must be included in v1.0.0. The other items (README badge, .gitignore) are low-risk polish included in the same hotfix commit.
