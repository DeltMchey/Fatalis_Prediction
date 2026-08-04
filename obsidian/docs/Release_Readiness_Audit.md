# BlackDragon v1.0 — GitHub Release Readiness Audit

- **Date**: 2026-08-04
- **Auditor**: Release Engineer + Software Architect
- **Scope**: Full repository (source, docs, data, tests, configuration)
- **Status**: `541 tests passed` | `git HEAD: d055717`

---

## 1. Repository Structure Review

### 1.1 Root-Level Scripts

| File | Lines | Purpose | Verdict |
|------|:---:|---------|:---:|
| `launch.py` | 60 | P5.3 Dashboard + Overlay 双进程入口（**推荐**） | ✅ KEEP — primary entry |
| `overlay.py` | 83 | P5.3 Overlay 独立进程入口 | ✅ KEEP — secondary entry |
| `main.py` | 85 | P4 单进程 overlay（legacy） | 🟡 KEEP + mark as `# LEGACY` |
| `ai_engine.py` | 484 | God Class — P3 测试兼容入口 | 🟡 KEEP + mark as `# LEGACY` |
| `data_cleaner.py` | 130 | ETL: raw CSV → ML dataset | ✅ KEEP — CLI tool |
| `data_upgrade.py` | 76 | Backfill phase/enrage in old CSVs | ✅ KEEP — CLI tool |
| `train_lgbm.py` | 82 | LightGBM training | ✅ KEEP — CLI tool |

**Recommendation**: 不建议创建 `scripts/` 目录。当前根目录脚本数（7 个 `.py`）适中，且均为顶级入口（entry point / CLI tool）。移动到 `scripts/` 会：
- 破坏用户习惯（README 中 `python launch.py` 变为 `python scripts/launch.py`）
- 增加 import 路径复杂度（`src/` 已在 `sys.path` 中有 `pytest.ini` 的 `pythonpath = .` 支持）
- 违反"不移动文件"约束

**legacy 标记建议**：在 `main.py` 和 `ai_engine.py` 的 module docstring 第一行加 `# LEGACY` 标记，与 `launch.py` 的 `# 推荐` 形成对比。不改变代码逻辑。

### 1.2 obsidian/ 文档仓库

| 子目录 | 文件数 | 状态 |
|--------|:---:|------|
| `Architecture/` | 5 | ✅ v1.0 KB 活跃 |
| `AI_Model/` | 6 | ✅ v1.0 KB + 原详细文档 |
| `Game_Reverse/` | 6 | ✅ v1.0 KB + 原详细文档 |
| `Development/` | 3 | ✅ v1.0 KB 活跃 |
| `memory_bank/` | 7 | ✅ AI agent context |
| `docs/` | 12+2 txt | ✅ ADR + research + audit reports |
| `docs/legacy/` | 16 | ✅ 历史归档（已 git mv） |

---

## 2. GitHub Open Source Readiness

### 2.1 Essential Files Checklist

| File | Status | Priority | Action |
|------|:---:|:---:|------|
| `README.md` | ⚠️ Needs update | 🔴 Must | 详见 §5 |
| `LICENSE` | ❌ Missing | 🔴 Must | 创建 MIT LICENSE 文件 |
| `.gitignore` | ✅ Complete | — | 正确排除 data/*.csv, models/*.pkl, *.log, .venv/ |
| `CONTRIBUTING.md` | ❌ Missing | 🟡 Should | 创建贡献指南（setup 步骤 + PR 流程） |
| `SECURITY.md` | ❌ Missing | 🟡 Should | 创建安全策略（报告漏洞渠道） |
| `CODE_OF_CONDUCT.md` | ❌ Missing | 🟢 Nice | Optional for small-team projects |
| `CHANGELOG.md` | ✅ Exists | — | 根目录 CHANGELOG.md（版本发布记录，非 memory_bank 版） |

### 2.2 LICENSE 说明

当前状态：
- `README.md` badge 标注 `![License](https://img.shields.io/badge/license-MIT-green)` — 声称 MIT
- 但仓库中**不存在 `LICENSE` 文件** → badge 引用 `LICENSE` 文件链接会 404

**必须创建** `LICENSE` 文件（含 MIT License 全文），或修正 badge 移除 license 声明。

### 2.3 Existing Files

| File | Content | Issue |
|------|---------|-------|
| `CHANGELOG.md` | 项目根版本记录 | ⚠️ 未确认与 memory_bank 的 changelog.md 内容一致性（预期不同：根目录 → 版本发布，memory_bank → 阶段事件） |

---

## 3. Sensitive Data Audit

### 3.1 Audit Results

| Path | Content | Sensitive? | Protected? |
|------|---------|:---:|:---:|
| `data/*.csv` (20 files, ~11MB) | 游戏战斗数据（timestamp, HP, action_id...） | ❌ 无个人数据 | ✅ `.gitignore` 排除 `data/*.csv` |
| `data/ML_Ready_Dataset.csv` | 清洗后的训练集（86KB） | ❌ 纯游戏特征 | ✅ `.gitignore` 排除 |
| `models/fatalis_ai_model.pkl` (17.6MB) | LightGBM 训练模型 | ❌ 无个人数据 | ✅ `.gitignore` 排除 |
| `models/feature_importance.png` | 特征重要性图 | ❌ 统计图 | ✅ `.gitignore` 排除 |
| `blackdragon.log` (434KB) | 运行日志 | ❌ 无密钥/凭据 | ✅ `.gitignore` 排除 `*.log` |
| `src/config/offsets.py` | 游戏内存偏移量（hex values） | ❌ 非敏感（固定游戏数据） | — |

### 3.2 .gitignore Verification

| Pattern | Covers | Status |
|---------|--------|:---:|
| `data/*.csv` | 19 场战斗录制 + ML_Ready_Dataset.csv | ✅ |
| `models/*.pkl` | fatalis_ai_model.pkl | ✅ |
| `models/*.png` | feature_importance.png | ✅ |
| `*.log` | blackdragon.log | ✅ |
| `.venv/` | Python virtualenv | ✅ |
| `__pycache__/`, `*.pyc` | Python bytecode | ✅ |
| `.idea/`, `.vscode/` | IDE files | ✅ |

**结论**: 无敏感数据泄露风险。gitignore 覆盖全面。

---

## 4. Python Packaging Review

### 4.1 requirements.txt

```
dearpygui==2.3          # GUI framework (Windows-only)
joblib==1.5.3           # Model serialization
lightgbm==4.6.0         # ML framework
matplotlib==3.10.9      # Visualization (feature importance)
numpy==2.4.4            # Numerical
pandas==3.0.2           # Data manipulation
Pymem==1.14.0           # Windows process memory reading
scikit-learn==1.8.0     # ML utilities
```

| Aspect | Assessment |
|--------|:---:|
| 版本锁定 | ✅ All pinned with `==` |
| 平台声明 | ✅ Commented as "Windows-only" |
| 测试依赖 | ⚠️ `pytest`, `pytest-cov` not listed (CI installs separately per comment) |
| Missing runtime deps | ❌ None (all 8 packages declared) |
| Missing build deps | N/A (pure Python, no build step) |

### 4.2 src/ Package Structure

```
src/
├── __init__.py           ✅
├── logging_config.py     ✅
├── config/               ✅ (actions.py, offsets.py, __init__.py)
├── core/                 ✅ (state_tracker.py, memory_reader.py, __init__.py)
├── model/                ✅ (predictor.py, __init__.py)
├── data/                 ✅ (recorder.py, __init__.py)
├── ui/                   ✅ (overlay.py, fonts.py, __init__.py)
├── app/                  ✅ (config.py, controller.py, game_service.py, __init__.py)
├── dashboard/            ✅ (main_window.py, status_bar.py, log_view.py, training_panel.py, __init__.py)
└── bootstrap/            ✅ (checker.py, __init__.py)
```

All packages have `__init__.py`. ✅

### 4.3 Run-from-Source Simulation

```
$ git clone <repo>
$ cd BlackDragon
$ python -m venv .venv
$ .venv\Scripts\activate
$ pip install -r requirements.txt

$ python launch.py
```

| Step | Status | Note |
|------|:---:|------|
| `git clone` | ✅ | Full repo with `src/` + entry points |
| `pip install -r requirements.txt` | ✅ | 8 packages, all pinned |
| `python launch.py` | Needs game | Dashboard launches even without game (GameService polls); overlay retries connection |

**Known failure mode**: `python launch.py` 在不满足 `Python >= 3.11` 的系统上会通过 `DependencyChecker.ensure()` 给用户友好提示并退出 ✅

**未实现的打包**：无 `setup.py` / `pyproject.toml` — 当前项目按"clone and run"模式设计，不提供 `pip install blackdragon`。对于 Windows-only 单机工具，这是合理的默认选择。如果未来想要 PyPI 发布，需补充。

---

## 5. Documentation Review

### 5.1 README.md Status — ⚠️ 严重过时

| Section | Current | Actual | Fix Required |
|---------|---------|--------|:---:|
| Badge: Phase | `P4 Architecture Refactor` | `P5.3 Dual-Process Overlay` | 🔴 Yes |
| Badge: Tests | `385 passed` | `541 passed` | 🔴 Yes |
| Badge: Coverage | `72%` | `94%` | 🔴 Yes |
| Badge: License | `MIT` (badge exists) | No LICENSE file | 🔴 Yes — must create LICENSE |
| Quick Start | `python main.py` as recommended | `python launch.py` as recommended | 🔴 Yes |
| Project Structure tree | Shows P4 only (no `app/`, `dashboard/`, `bootstrap/`, `ui/fonts.py`) | Must include P5 modules | 🔴 Yes |
| "How It Works" diagram | References `ai_engine.py` as central | References dual-process model | 🟡 Should update |
| Roadmap | P5 "Planned", P4 "Done" | P5 "Done", P6 "Planned" | 🟡 Should update |
| Roadmap link | `docs/Refactoring_roadmap.md` | File moved to `docs/legacy/` | 🟡 Update or remove link |
| Entry points | Lists `main.py`, `ai_engine.py` only | Missing `launch.py`, `overlay.py` | 🔴 Yes |
| License section | "MIT" | No LICENSE file | 🔴 Yes |

**Required additions to README**:
- [ ] Entry point table (launch.py / overlay.py / main.py / ai_engine.py)
- [ ] Architecture diagram (dual-process)
- [ ] Dashboard screenshot mention
- [ ] Link to obsidian/ Architecture/ docs
- [ ] Updated badges (541 tests, 94%, P5.3)

### 5.2 obsidian/ Documentation

| Option | Description | Verdict |
|--------|-------------|:---:|
| Option A | 保留在主仓库（当前） | ✅ **推荐** |
| Option B | 拆分为 `BlackDragon-Docs` 独立仓库 | ❌ Not recommended |

**Recommended: Option A — 保留在主仓库**

理由：
1. **单repo适合小团队** — BlackDragon 的源码和文档由同一批维护者管理。拆分会增加 PR 同步开销
2. **文档-代码紧密耦合** — ADR、Memory Bank、模块设计文档直接引用源码文件名和 API 签名。拆分后任何源码重命名都需要跨仓库 PR
3. **GitHub 原生支持单repo文档** — `obsidian/` 作为子目录存在，GitHub 直接渲染 `.md`，Obsidian 用户 clone 后即开即用
4. **无独立发布需求** — 文档不是独立产品（如独立文档站点），不需要独立 issue tracker 或 release cycle
5. **可选优化**: 在 README 中加入 `obsidian/Index.md` 的 permalink，使 web 用户也能浏览知识库入口

---

## 6. Release Checklist — BlackDragon v1.0

### 🔴 Must Complete Before Release

| # | Item | Verdict | Action |
|---|------|:---:|------|
| C1 | 541 tests pass | ✅ | Confirmed |
| C2 | `.gitignore` verified | ✅ | Full coverage |
| C3 | No sensitive data in repo | ✅ | Audit passed |
| C4 | `LICENSE` file created | ❌ | Create `LICENSE` with MIT full text |
| C5 | README updated | ❌ | Update badges, entry points, structure tree, roadmap |
| C6 | Remove stale license badge OR create LICENSE | ❌ | README badge `LICENSE` → 404 unless file exists |

### 🟡 Should Complete Before Release

| # | Item | Verdict | Action |
|---|------|:---:|------|
| C7 | `CONTRIBUTING.md` created | ❌ | Create with setup steps + PR guidelines |
| C8 | `SECURITY.md` created | ❌ | Create with vulnerability reporting channel |
| C9 | `README.md` entry point table | ❌ | Add table: launch.py / overlay.py / main.py / ai_engine.py |
| C10 | `README.md` architecture link | ❌ | Link to `obsidian/Architecture/System_Architecture.md` |
| C11 | Legacy files marked | ❌ | Add `# LEGACY` docstring to `main.py`, `ai_engine.py` |
| C12 | Roadmap link in README fixed | ❌ | Update or remove `docs/Refactoring_roadmap.md` reference |

### 🟢 Nice to Have

| # | Item | Verdict |
|---|------|:---:|
| C13 | `CODE_OF_CONDUCT.md` | Optional |
| C14 | GitHub Release notes drafted | After commit |
| C15 | `git tag v1.0.0` | After C1–C12 |
| C16 | `setup.py` / `pyproject.toml` for pip install | Deferred (clone-and-run model sufficient) |
| C17 | `.github/workflows/release.yml` | Deferred (CI test flow exists) |
| C18 | `README` screenshots / demo GIF | Enhances user adoption |

### Post-Release

| # | Item |
|---|------|
| 19 | Monitor GitHub Issues for first-user feedback |
| 20 | Archive `docs/legacy/` in release notes as "historical documentation" |
| 21 | Update `memory_bank/changelog.md` with `v1.0.0` entry |

---

## Appendix A: File Ownership Summary

| Category | Files | Managed by |
|----------|:---:|------------|
| Source | `src/`, `launch.py`, `overlay.py`, `main.py`, `ai_engine.py` | Coder |
| Tests | `tests/` (26 files) | Coder |
| Config | `pytest.ini`, `.coveragerc`, `.gitignore`, `requirements.txt` | Coder |
| Docs (active) | `obsidian/Architecture/`, `AI_Model/`, `Game_Reverse/`, `Development/` | Architect |
| Docs (MB) | `obsidian/memory_bank/` | Architect (active/progress) + Coder (changelog) |
| Docs (ADR) | `obsidian/docs/architecture/` | Architect |
| Docs (legacy) | `obsidian/docs/legacy/` | Nobody (time capsule) |
| Release | `README.md`, `LICENSE`, `CHANGELOG.md` | Architect / Coder |
| Data | `data/`, `models/` | User (git-ignored) |

## Appendix B: README Update Template

需要更新的 README 章节：

```markdown
[![Phase](https://img.shields.io/badge/phase-P5.3%20Dual--Process-blue)](#roadmap)
[![Tests](https://img.shields.io/badge/tests-541%20passed-brightgreen)](#roadmap)
[![Coverage](https://img.shields.io/badge/coverage-94%25-brightgreen)](#roadmap)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Quick Start
python launch.py            # P5.3 Dashboard + Overlay（推荐双进程入口）
python overlay.py           # 仅 Overlay 进程
python main.py              # P4 legacy 单进程入口
python ai_engine.py         # Legacy God Class

## Project Structure
├── launch.py               # P5.3 双进程入口（推荐）
├── overlay.py              # P5.3 Overlay 独立进程入口
├── main.py                 # P4 legacy
├── src/
│   ├── app/                # P5 — AppController, AppConfig, GameService
│   ├── dashboard/          # P5 — Dashboard UI
│   ├── bootstrap/          # P5.1 — DependencyChecker
│   ├── ui/                 # fonts.py (shared CJK font)
│   └── ...

## Documentation
→ obsidian/Index.md
```
