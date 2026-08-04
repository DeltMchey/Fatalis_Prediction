# ADR-P5.3: Auto-Start and Recording Default Behavior

- **Date**: 2026-08-04
- **Status**: Decided
- **Author**: Architect

---

## Context

P5.3 双进程架构已实现（ADR-P5.2 decision → implementation）。当前启动行为：

```
launch.py
  ├─ bootstrap
  ├─ controller.start_overlay()           ← 无条件 spawn overlay.py
  ├─ GameService.start()                  ← 后台轮询游戏进程
  └─ Dashboard.run()

overlay.py（子进程）
  ├─ pymem.Pymem("MonsterHunterWorld.exe") ← 立即连接；未找到 → 退出
  ├─ MemoryReader / StateTracker / Predictor / Recorder
  ├─ recorder.start()
  └─ OverlayUI.run()
```

**问题**：
1. `launch.py` 无条件启动 overlay 子进程（L43），但 overlay 子进程连接游戏可能早于游戏启动 → overlay 进程立即退出（`"未找到游戏进程"`）→ 用户必须手动重新点击 Dashboard 按钮
2. 游戏附着后，录制默认开启（`CombatStateTracker(is_recording=True)`），但该行为是硬编码的，无法通过配置关闭
3. `AppConfig.auto_start_overlay`（default `False`）字段已定义但从未被消费（死配置）

**需求变更**：
1. Dashboard 自动启动 Overlay 子进程（无用户干预）
2. Overlay 连接游戏后自动进入工作状态（recording 启动 + DPG 循环运行）
3. 默认开启数据录制模式
4. 用户仍然可以通过 Dashboard 手动关闭 Overlay 和 Recording

---

## Constraints

| # | Constraint | Source |
|---|-----------|--------|
| C1 | 不修改 P4 core: `src/core/`, `src/model/`, `src/data/`, `main.py` | 用户要求 |
| C2 | 保持 P5.3 双进程架构（不恢复进程内 Overlay）| 用户要求 |
| C3 | 不引入新的全局状态 | 用户要求 |
| C4 | Overlay 子进程必须能**独立启动**（`python overlay.py` 仍可用）| 架构约束 |
| C5 | `test_default_auto_start_overlay_false` 测试约束 `auto_start_overlay` 默认值不可改 | 测试合约 |

---

## Analysis: Current Flow

### 时序图（现状）

```
Time ──────────────────────────────────────────────────►

launch.py        [start_overlay]────────[Dashboard event loop]──────[shutdown]
                       │                         │
overlay.py       [connect game]                    │
                  ✗ game not found                 │
                  exit(1)                          │
                                                   │
GameService                         [poll...detect game]
                                   [attach_game → recorder.start]
                                                   
User action                         [click "启动覆盖层" button]
                                   [overlay.py restarted ✓]
```

**问题根因**：`launch.py` 在 GameService 检测到游戏**之前**就启动了 overlay 子进程。

### 录制默认值现状

| 位置 | 调用 | 默认 |
|------|------|------|
| `controller.attach_game` (L97) | `CombatStateTracker(is_recording=True)` | 硬编码 `True` |
| `overlay.py` main (L57) | `CombatStateTracker(is_recording=True)` | 硬编码 `True` |

两个进程各有一个独立的 StateTracker 实例。Dashboard 进程的录制状态通过 `controller.is_recording` 查询，Overlay 进程的录制状态在其 GUI checkbox 中显示（但受限于 WS_EX_TRANSPARENT，该 checkbox 不可点击——用户只能通过 Dashboard 控制录制）。

---

## Design Options

### 选项 A：Overlay 子进程添加游戏重试循环（推荐）

在 `overlay.py` main() 中将 `pymem.Pymem("MonsterHunterWorld.exe")` 包裹为重试循环（类似 GameService 的轮询逻辑），最多等待 N 秒。

**改动范围**：
- `overlay.py` — 添加重试逻辑（~15 行）
- `src/app/config.py` — 添加 `auto_record: bool = True` 字段
- `src/app/controller.py` — `attach_game` 中 `is_recording=config.auto_record`
- 仅此三处

**时序**：
```
launch.py        [start_overlay]────[Dashboard event loop]──────────[shutdown]
                       │
overlay.py       [retry connect...]
                  ...polling...
                              [game appears] → [connect ✓] → [recording ✓] → [UI ✓]
```

**优点**：
- 改动最小（仅 overlay.py + config 一行）
- `launch.py` 无条件启动语义保留（与 ADR-P5.2 "Launch both" 一致）
- `python overlay.py` 独立运行也更健壮（可先启 overlay 再开游戏）
- Dashboard 按钮作为"重新启动"机制仍有效
- 不需要跨进程协调

**缺点**：
- 重试期间 overlay 进程占用内存（~50MB DPG + Python runtime）
- 重试超时后进程退出，用户仍需手动重启

**参数建议**：
```python
_RETRY_INTERVAL = 2.0   # 秒
_MAX_RETRIES = 60       # 最多等 2 分钟
```

---

### 选项 B：延迟 Overlay 启动到游戏附着时

将 overlay 子进程的启动从 `launch.py` 移至 `AppController.attach_game()`（游戏检测成功后）。

**改动范围**：
- `launch.py` — 移除 `controller.start_overlay()` 调用
- `src/app/controller.py` — `attach_game` 末尾添加 `self.start_overlay()`
- `src/app/config.py` — 同上

**时序**：
```
launch.py        [Dashboard event loop]────────────────────[shutdown]

GameService      [poll...detect game]
                 [attach_game]
                 [start_overlay] ← 此时 game 已在运行
                                    │
overlay.py                         [connect ✓] → [recording ✓] → [UI ✓]
```

**优点**：
- 精确时序：overlay 只在游戏已确认运行时启动，不会"空跑"
- `launch.py` 恢复纯 Dashboard 启动（职责单一）
- 无内存浪费

**缺点**：
- `launch.py` 语义改变：不再 "Launch both"（与 ADR-P5.2 Step 4 冲突）
- `attach_game` 添加 UI 子进程管理职责（混合数据模块初始化 + UI 进程管理）
- `python overlay.py` 独立运行时仍需直接连接游戏（无变化）
- 游戏 crash 后 re-attach 可能重复启动 overlay（需去重逻辑）
- 修改范围更大（launch.py 语义 + controller 职责 + test_launch.py 结构测试）

---

### 选项 C：两者结合（A + B）

- `launch.py`：仅在 `config.auto_start_overlay` 为 True 时启动 overlay
- `controller.attach_game`：每次游戏附着成功后确保 overlay 运行（`if not is_overlay_running: start_overlay()`）
- `overlay.py`：添加重试循环

**优点**：最健壮——无论何种场景 overlay 都能最终启动。
**缺点**：改动最大，多重触发点增加调试复杂度。

---

## Recommendation

**推荐选项 A**。

理由：
1. **改动最小** — 仅 1 个核心文件（`overlay.py`）需要行为变更；config 新增 1 个字段；controller 1 行修改
2. **保持 ADR-P5.2 语义** — `launch.py` "Launch both" 不变；`overlay.py` 变得更健壮而非变更架构
3. **独立运行友好** — `python overlay.py` 单独使用场景也受益于重试逻辑
4. **后退成本低** — 若重试逻辑不适合，回退仅涉及 `overlay.py`
5. **满足全部需求**：
   - ✅ Dashboard 自动启动 Overlay（launch.py 无条件 spawn → overlay 等待游戏 → 自动进入工作状态）
   - ✅ Overlay 连接后自动工作（recording 启动 + DPG 循环）
   - ✅ 默认录制（`auto_record=True` 配置驱动）
   - ✅ 用户手动关闭（Dashboard 按钮不变）

---

## Decision

### Decision 1: overlay.py 添加游戏连接重试循环

`overlay.py` main() 中，游戏进程连接 (`pymem.Pymem`) 失败时不立即退出，而是以轮询方式重试。

**参数**：
```python
_RETRY_INTERVAL = 2.0   # 重试间隔（秒）
_MAX_RETRIES = 60       # 最大重试次数（总计 2 分钟）
```

重试循环结束后仍失败 → 输出 `"等待超时，未找到游戏进程"` → 退出。

此决策满足需求 1（自动启动）和需求 2（自动进入工作状态）。

### Decision 2: 新增 `auto_record` 配置项

`AppConfig` 新增字段：

```python
auto_record: bool = True    # 默认开启录制模式
```

**消费点**：
- `AppController.attach_game()`: `CombatStateTracker(is_recording=self._config.auto_record)` — Dashboard 进程的录制默认状态
- `overlay.py`: 保持硬编码 `is_recording=True`（Overlay 进程始终录制——它是战斗 UI 模式；独立进程不访问 Dashboard 的 AppConfig）

**理由**：
- Dashboard 进程的录制应可配置——用户可能希望在游戏附着后默认不录制（节省 I/O）
- Overlay 进程的录制始终开启——它是专门的战斗数据显示界面
- 两个进程录制独立（ADR-P5.2 设计），互不干扰

此决策满足需求 3（默认录制）和需求 4（用户可手动关闭）。

### Decision 3: `auto_start_overlay` 保持现状，不在此阶段消费

`AppConfig.auto_start_overlay`（default `False`）**不在本次变更中消费**。

**理由**：
- 选项 A 中 launch.py 继续保持无条件启动 overlay（per ADR-P5.2 "Launch both"）
- `auto_start_overlay` 的未来语义应为：`True` → 启动时立即 spawn overlay（可能有重试但浪费资源）；`False` → 等待游戏检测后再 spawn。此优化涉及 attach_game 时序变更（类选项 B），需单独设计和测试
- C5 约束：测试预期 `default=False`，不可任意修改
- 保留此字段供后续 P5.4 迭代

### Decision 4: 不修改 GameService 或 Dashboard 的回调逻辑

- `GameService` 仅负责游戏检测 → `attach_game` / `detach_game`
- `Dashboard._on_frame` / `_refresh_button_states` / `_on_overlay_toggle` 不变
- 录制 checkbox 和覆盖层按钮的启用/禁用规则不变（`enabled=attached`）

---

## Rejected Alternatives

### Rejected: Make overlay.py read AppConfig for recording state

**方案**：overlay.py 读取 `blackdragon_config.json` 获取 `auto_record` 配置。

**拒绝理由**：
- Overlay 是独立进程——引入 `src.app.config` 依赖打破了进程隔离
- Overlay 的录制状态应始终为 True（它在战斗 UI 模式下运行）
- 用户通过 Dashboard checkbox 控制的是 Dashboard 进程的录制器，两者独立

### Rejected: Wire auto_start_overlay into launch.py now

**方案**：`launch.py` 中 `if config.auto_start_overlay: controller.start_overlay()`

**拒绝理由**：
- 与 ADR-P5.2 "Launch both" 语义冲突
- 默认 `False` → 默认不启动 overlay → 违背需求 1 "自动启动"
- 需要同步修改 `test_launch.py` 结构测试（增加变更范围）
- 此配置更适合控制"启动时立即启动 vs 等待游戏检测"，应在 attach_game 时序变更中一并处理

### Rejected: Auto-start from controller.attach_game

**方案**：`attach_game` 末尾调用 `self.start_overlay()`

**拒绝理由**：
- `attach_game` 设计为纯数据模块初始化（无 UI 进程管理）
- 游戏 crash 后 re-attach 可能重复启动 overlay（需要额外去重标志）
- overlay 重试循环（选项 A）解决了同样的时序问题，无需修改 attach_game 职责

---

## Impact Analysis

### 修改文件

| 文件 | 变更 | 类型 |
|------|------|------|
| `overlay.py` | 添加 pymem 连接重试循环 | 新增逻辑 |
| `src/app/config.py` | 添加 `auto_record: bool = True` | 新增字段 |
| `src/app/controller.py` | `attach_game` 中 `is_recording=config.auto_record` | 1 行修改 |

**总计：3 个文件，新增 ~15 行，修改 1 行。**

### 测试影响

| 文件 | 影响 |
|------|------|
| `tests/test_app_config.py` | 需新增 `test_default_auto_record_true` |
| `tests/test_app_controller.py` | `TestAttachGame.test_attach_game_creates_modules` 需验证 state_tracker 使用 config.auto_record |
| `tests/test_overlay_entry.py` | 需新增重试循环测试（mock pymem 连续失败 → 重试 N 次后退出）；现有测试需适配 |
| 其他测试 | 无影响 |

### 不修改的模块

- `src/core/` — P4 core，零 diff（C1）
- `src/model/` — P4 core，零 diff
- `src/data/` — P4 core，零 diff
- `main.py` — P4 core，零 diff
- `src/ui/overlay.py` — P5.3 已稳定，不修改
- `launch.py` — 语义保持，不修改
- `src/dashboard/` — UI 控件逻辑不变
- `src/app/game_service.py` — 游戏检测逻辑不变

---

## Next Steps

1. 实现 overlay.py 重试循环（`_RETRY_INTERVAL=2.0`, `_MAX_RETRIES=60`）
2. 添加/修改 AppConfig.auto_record 字段及测试
3. 修改 controller.attach_game 的 is_recording 参数
4. 更新 test_overlay_entry.py 覆盖重试和超时场景
5. 更新 changelog.md
6. 真机验证：先启 launch.py，后开游戏 → overlay 应自动出现
