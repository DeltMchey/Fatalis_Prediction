# Legacy Migration Review — BlackDragon v1.0

- **Date**: 2026-08-04
- **Reviewer**: Documentation Reviewer
- **Scope**: 16 staged files (legacy migration)
- **Method**: git diff --cached --name-status + Obsidian wikilink audit + file integrity checks

---

## 1. Execution Summary

| Check | Result |
|-------|:---:|
| git mv 使用 | ✅ 13/13 renames = `R100`（100% identical content） |
| git history 保持 | ✅ 13 个 rename + 2 个历史恢复（`65ac9e4` checkout） |
| 新版文档未覆盖 | ✅ `Architecture/` / `Development/` 均为 v1.0 新版本 |
| Memory Bank 未修改 | ✅ 零 diff |
| Source code 未触碰 | ✅ `src/` / `tests/` / `launch.py` / `overlay.py` 零 diff |

---

## 2. Detailed Findings

### 🔴 Must Fix (2)

| # | File | Line | Issue | Fix |
|---|------|:---:|-------|-----|
| MF-1 | `obsidian/Game_Reverse/Memory_Reading.md` | 188 | `[[../docs/offsets_guide|Offsets Guide]]` — `offsets_guide.md` 已迁移至 `docs/legacy/offsets_guide.md`，旧路径不存在。此文件为活跃文档（非 legacy），链接断裂。 | 改为 `[[docs/legacy/offsets_guide|Offsets Guide]]`（从 vault-root 路径）或移除链接并注明已归档 |
| MF-2 | `obsidian/Game_Reverse/Offset_System.md` | 163 | 同上——`[[../docs/offsets_guide|Offsets Guide]]` 指向已迁移文件 | 同上 |

**根因**：`offsets_guide.md` 从 `obsidian/docs/` 移动到 `obsidian/docs/legacy/`，但两个活跃 Game_Reverse 文档中的 `../docs/offsets_guide` 相对路径未同步更新。这两个文件不在本次迁移范围（未被移动），但其内部链接因迁移行为而失效。

**影响**：Obsidian 中点击这两个链接会打开空白页或提示"文件不存在"。

### 🟡 Should Fix (1)

| # | Issue | Detail |
|---|-------|--------|
| SF-1 | **Legacy 文档内部 wikilink 断裂** | 迁移后的 legacy 文档（如 `architecture-v0/System_Architecture.md:140` → `[[../docs/Tech_debt]]`）在 Obsidian 中无法解析——源路径已改变 |
| | **Acceptable reason** | Legacy README 明确声明"**不再维护**"，且约束"不修改旧文档内容"禁止修复。这些链接对历史追溯不构成实质性障碍 |
| | **Suggested action** | Legacy README 中已声明"不修改旧文档内容"，可在 README 中补充一条"Legacy 文档内部 wikilink 因迁移已失效"的免责说明 |

### 🟢 Nice to Have (1)

| # | Observation |
|---|-------------|
| NTH-1 | `Game_Reverse/Memory_Architecture.md:110` 已正确引用 `docs/legacy/offsets_guide.md` 新路径（该文件在 KB v1 创建时已预判迁移），可视为正确链接的范例 |

---

## 3. Passed Checks

### 3.1 git mv 使用

```
R100  obsidian/Architecture/AI_Pipeline.md → legacy/architecture-v0/AI_Pipeline.md
R100  obsidian/Architecture/Memory_Architecture.md → legacy/architecture-v0/Memory_Architecture.md
R100  obsidian/Development/CI_CD.md → legacy/development-v0/CI_CD.md
R100  obsidian/Development/Development_Log.md → legacy/development-v0/Development_Log.md
R100  obsidian/Development/Refactoring_Roadmap.md → legacy/development-v0/Refactoring_Roadmap.md
R100  obsidian/docs/* → legacy/* (8 files)
```

**13 个文件全部为 `R100`**（git 内置 rename detection 确认 100% 内容一致）✅

### 3.2 git history 保持

- 13 个 `git mv` rename — git 在 commit 时自动记录 rename 溯源 ✅
- 2 个"新文件"（`Data_Flow.md`、`System_Architecture.md` 旧版）— 从 `65ac9e4` checkout 后 `git mv` 到 legacy，git history 中旧内容位于 `65ac9e4` 及之前的 commit 中，可追溯 ✅

### 3.3 新版文档未覆盖

| 目录 | 文件数 | 版本 | 行数验证 |
|------|:---:|------|----------|
| `Architecture/` | 5 | v1.0 KB docs | 28-175 lines (new) |
| `Development/` | 3 | v1.0 KB docs | 41-85 lines (new) |
| `legacy/architecture-v0/` | 4 | P3-era old | 76-145 lines (old) |

`System_Architecture.md` 和 `Data_Flow.md` 在 `Architecture/` 中保留新版（86/104 lines），旧版（105/76 lines）正确位于 legacy ✅

### 3.4 legacy README 完整性

README 包含全部要求字段：

| 字段 | 覆盖 |
|------|:---:|
| 原路径 (`原路径`) | ✅ 原路径 → 新路径表 |
| 新路径 (`新路径`) | ✅ 同上 |
| 归档原因 (`归档原因`) | ✅ 每行理由 |
| 不再维护声明 | ✅ 顶部 `[!warning] 不再维护` callout |
| 权威文档对照 | ✅ 9 行对照表 |
| 非归档文件说明 | ✅ 底部说明保留文件（ADR/调研/出招表） |

### 3.5 Index.md 导航

Index.md 中 22 个 `[[wikilinks]]` 全部指向**活跃文档**路径：

| 链接指向 | 数量 | 状态 |
|----------|:---:|:---:|
| `memory_bank/*` | 6 | ✅ 文件未移动 |
| `Architecture/*` (new) | 5 | ✅ 新建 KB docs |
| `AI_Model/*` | 3 | ✅ 文件未移动 |
| `Game_Reverse/*` | 3 | ✅ 文件未移动 + 新建 docs |
| `Development/*` (new) | 3 | ✅ 新建 KB docs |
| `docs/*` (Knowledge_Base_*.md) | 2 | ✅ 未移动 |
| `docs/research/*` | 1 | ✅ 未移动 |

**零断裂链接** ✅

### 3.6 Memory Bank

```
git diff --cached --name-only -- obsidian/memory_bank/
→ (空输出)
```

Memory Bank 完全未触碰 ✅

---

## 4. Approval Status

### 🟡 **APPROVED with Conditions**

| 条件 | 说明 |
|------|------|
| **Before commit** | 必须修复 MF-1 / MF-2（两个 `offsets_guide` 断裂链接） |
| **After commit** | SF-1（legacy 内部断裂链接）不阻塞——已在 README 声明"不再维护" |
| NTH-1 | 可选 |

### 修复建议

MF-1 (`Memory_Reading.md:188`) 和 MF-2 (`Offset_System.md:163`) 均将 `[[../docs/offsets_guide|Offsets Guide]]` 替换为：

```markdown
`docs/legacy/offsets_guide.md`（已归档）
```

理由：
- 保留信息价值（告知读者 guide 存在）
- 避免断裂 wikilink
- 使用 backtick 引用而非 wikilink——legacy 路径不应作为活跃导航目标

### Summary Table

| 等级 | 数量 | 详情 |
|------|:---:|------|
| 🔴 Must Fix | **2** | 活跃文档断裂链接（MF-1, MF-2） |
| 🟡 Should Fix | **1** | Legacy 内部断裂链接（已文档化免责） |
| 🟢 Verified Pass | **15** | 13 renames + 2 history restores |
| 📝 README | **1** | 完整（原路径/新路径/归档原因/不再维护声明/权威对照） |

### Decision

**Conditionally Approved** — 修复 MF-1 + MF-2 后可安全 commit。legacy 内部断裂链接不阻塞（已文档化免责）。建议在与 MF fix 相同的 commit 中完成修复（均为 legacy migration 议题）。
