# Knowledge Base Content Review — BlackDragon v1.0

- **Date**: 2026-08-04
- **Reviewer**: Reviewer (code audit role)
- **Scope**: 14 new/rewritten markdown files in `obsidian/`（Step 1 of KB v1.0）
- **Method**: Cross-reference each doc against actual source code (`src/`, `launch.py`, `overlay.py`, tests), git HEAD, and memory bank

---

## 1. Overall Assessment

| 维度 | 评级 | 说明 |
|------|:---:|------|
| **Architecture accuracy** | 🟡 基本准确, 3 处错误 | 进程拓扑正确；shutdown 顺序 + Mermaid 图有误；Overlay 推理链路描述有歧义 |
| **Module/API accuracy** | 🟢 准确 | 所有 API 签名、方法名、字段名均与源码一致 |
| **P5.2 failure recording** | 🟢 准确 | 三种失败方案正确记录，GLFW main-thread 限制正确描述 |
| **Lifecycle / Data Flow** | 🟡 1 处错误 | shutdown 顺序与实际代码不一致 |
| **Memory Bank conflict** | 🟢 无冲突 | 测试数、覆盖率、阶段日期均与 changelog.md/progress.md 一致 |
| **Source code consistency** | 🟢 一致 | 类名、文件名、入口点均与源码匹配 |
| **Outdated descriptions** | 🟢 无 | 所有描述反映 P5.3 auto-start 当前状态，无 P3/P4 残留 |

**结论**：文档整体质量高，核心架构事实（进程分拆、模块职责、数据流）100% 准确。发现 **3 个需修复的错误**（Mermaid 引用空节点、shutdown 顺序、推理链路描述），3 个次要问题。

---

## 2. 逐文件审计

### 2.1 `Index.md` — 🟢 通过

| 检查项 | 结果 |
|--------|:---:|
| 入口点与 `launch.py`/`overlay.py`/`main.py`/`ai_engine.py` 一致 | ✅ |
| 技术栈与 `requirements.txt` + `techContext.md` 一致 | ✅ |
| 导航链接全部指向新建文件（14 个链接） | ✅ |
| 不自维护状态数据（符合设计 P6 原则） | ✅ |

### 2.2 `Architecture/System_Architecture.md` — 🟡 1 处错误

| 检查项 | 结果 |
|--------|:---:|
| 双进程描述：Dashboard Process + Overlay Process | ✅ 准确（ADR-P5.2 一致） |
| ASCII 图流程：`launch.py → Config → Controller → [auto_start_overlay] → GameService → Dashboard.run()` | ✅ 准确（`launch.py` main() 一致） |
| Overlay 进程流程：`AppConfig.load() → _find_game_process() → P4 modules → OverlayUI.run()` | ✅ 准确（`overlay.py` main() 一致） |
| 双进程原因（GLFW main-thread 限制） | ✅ 准确（ADR-P5.2） |
| 外部依赖列表 | ✅ 完整 |
| Legacy 入口说明 | ✅ 准确 |
| 目录映射表：`src/ui/` 标为 "Overlay" 进程 | ⚠️ `fonts.py` 被 Dashboard 和 Overlay **双进程使用**（`Dashboard.run()` 中调用 `setup_cjk_font()`），标注应为"双进程"或注明"overlay.py 由两个进程共享" |
| **Mermaid 图：`CTRL -->\|start_overlay / stop_overlay\| P2`** | 🔴 **错误**：`P2` 节点未在 Mermaid 中定义（Overlay 子图中只有 `OV`/`OVUI`/`REC2`/`P4B`）。目标应为 `OV[overlay.py]`。此边在 Obsidian 渲染后会指向空节点 |

### 2.3 `Architecture/Module_Design.md` — 🟢 通过

| 检查项 | 结果 |
|--------|:---:|
| `src/` 目录树与实际文件列表一致 | ✅ |
| CombatStateTracker API（8 methods）— 签名准确 | ✅（cross-referenced with `inspect.getsource`） |
| MemoryReader API（9 methods）— `follow_pointer_chain` / `check_zone` / `read_enrage_state` 等存在 | ✅（verified in source） |
| ActionPredictor API — `predict` 签名 + 4 static methods + `is_loaded` | ✅ |
| CombatRecorder API — `start`/`stop`/`run` + CSV 8 列 | ✅ |
| OverlayUI — `run()` 唯一入口，P4.5 standalone 设计 | ✅ |
| AppConfig 9 字段 + 默认值 | ✅（verified with `dataclasses.fields(AppConfig)`） |
| AppController API — 9 methods + 7 properties | ✅ |
| 依赖 DAG（Mermaid） | ✅ 方向正确 |
| 测试映射表 | ⚠️ 仅列出 14 行，遗漏 P3 测试文件（`test_infrastructure`, `test_math_logic`, `test_phase_filter`, `test_nova`, `test_data_upgrade`, `test_data_cleaner`, `test_train_lgbm`, `test_fonts` = 142 tests）。Testing_Strategy.md 有完整清单。Module_Design 可注明"仅模块级测试——完整清单见 Testing_Strategy" |

### 2.4 `Architecture/Process_Architecture.md` — 🟡 2 处错误

| 检查项 | 结果 |
|--------|:---:|
| P5.2 三种方案失败表 | ✅ 与 ADR-P5.2 一致 |
| 启动时序 Mermaid（`launch.py` → `controller.start_overlay()` → `overlay.py`） | ✅ 准确 |
| Overlay 连接时序 Mermaid（`_find_game_process()` 重试循环） | ✅ 准确 |
| Dashboard 线程模型（Main / GameService / Recorder / Training reader / 子进程 ×2） | ✅ 准确 |
| Overlay 线程模型（Main / Recorder） | ✅ 准确 |
| 生命周期状态机图（Bootstrap → Config → SpawnOverlay → DashboardReady → Attached → Shutdown） | ✅ 逻辑正确 |
| **attach_game 步骤**（`MemoryReader → CombatStateTracker(is_recording=config.auto_record) → ActionPredictor → deque+Lock → CombatRecorder → recorder.start()`） | ✅ 准确（`controller.attach_game()` 源码一致） |
| detach_game | ✅ `recorder.stop()` 不终止 overlay ✅ |
| **shutdown 顺序：`1.recorder.stop() 2.overlay.terminate() 3.training.terminate() 4.game_service.stop()`** | 🔴 **顺序错误**：`launch.py` 的 `finally` 块为 `game_service.stop(); controller.shutdown()`。实际执行顺序是 `game_service.stop()` **先于** `controller.shutdown()`（shutdown 内依次 recorder → overlay → training）。文档将 `game_service.stop()` 放在第 4 步，颠倒了顺序 |
| 跨进程状态同步表（5 行）| ✅ 准确（ADR-P5.2 一致） |
| 关键约束（P4 core 零修改 / 不恢复进程内 Overlay / 无全局状态）| ✅ 准确 |

### 2.5 `Architecture/Data_Flow.md` — 🟢 通过

| 检查项 | 结果 |
|--------|:---:|
| 全链路 Mermaid（在线双进程 + 离线独立脚本）| ✅ 逻辑正确 |
| CSV 8 列格式 | ✅ 与 `CombatRecorder._COLUMNS` 一致 |
| 推理路径数据转换表 | ✅ 准确 |
| 清洗管线步骤 | ✅ 与 `data_cleaner.py` 逻辑一致 |
| 训练超参数 | ✅ 与 `train_lgbm.py` 一致 |
| Config 数据流（双进程各自 `AppConfig.load()`） | ✅ 准确 |

### 2.6 `Architecture/ADR_Index.md` — 🟡 1 处微妙不符

| 检查项 | 结果 |
|--------|:---:|
| ADR-P5.2 日期 (2026-08-03)、Status (Decided)、Summary | ✅ 与 ADR 元数据一致 |
| ADR-P5.3 日期 (2026-08-04)、Summary | ✅ 准确 |
| **ADR-P5.3 Status: "Decided"** | ⚠️ ADR 文件元数据仍为 `Status: Proposed`。实现虽已完成，但 ADR 文件未更新状态。Index 中标注 "Decided" 反映事实但与实际 ADR 文件不一致 |

### 2.7 `AI_Model/Training_Pipeline.md` — 🟢 通过

| 检查项 | 结果 |
|--------|:---:|
| 管线图、数据采集参数、清洗步骤 | ✅ 与旧 AI_Pipeline / Training_Process 一致 |
| 超参数表 10 行 | ✅ 与 `train_lgbm.py` 一致 |
| 评估指标（Accuracy, Top-3 56.17%） | ✅ 与 Model_Evaluation.md 一致 |

### 2.8 `AI_Model/Inference_System.md` — 🟡 1 处错误

| 检查项 | 结果 |
|--------|:---:|
| 模型规格、两层预测架构、6 维特征、推理性能 | ✅ 准确 |
| **§8: "Overlay 进程: GameService 附着 → P4 模块 → OverlayUI.update_logic() → predict()"** | 🔴 **错误**：`GameService` 运行在**Dashboard 进程**（非 Overlay 进程）。Overlay 进程通过 `overlay.py` main() 中的 `_find_game_process()` **自行**连接游戏，不依赖 GameService。应改为 "`overlay.py` → `_find_game_process()` → P4 模块" 或引用 Process_Architecture 的 Overlay 连接时序图 |

### 2.9 `Game_Reverse/Memory_Architecture.md` — 🟢 通过

| 检查项 | 结果 |
|--------|:---:|
| 3 基址 + 指针链 + 怪物布局 | ✅ 与 `offsets.py` 一致 |
| MemoryReader 9 方法表 | ✅ 与源码一致 |
| 健壮性设计表 | ✅ 准确 |

### 2.10 `Game_Reverse/Combat_State.md` — 🟢 通过

| 检查项 | 结果 |
|--------|:---:|
| ACTION_DB (144) + ACTION_MAPPING (54) | ✅ 与 `actions.py` 一致 |
| 姿态 FSM 5 态 + 触发集合 | ✅ 准确 |
| 阶段系统 + P1_ONLY/P2_PLUS/P3_ONLY 过滤规则 | ✅ 准确 |
| 发怒硬件检测原理 + Nova 5 阈值 + 重置动作 | ✅ 准确 |
| §8 实现映射表 | ✅ 引用正确 |

### 2.11 `Development/Development_Roadmap.md` — 🟢 次要标注

| 检查项 | 结果 |
|--------|:---:|
| 阶段完成日期与 `changelog.md` 一致 | ✅ |
| 指标表（P3→P5.3-auto 测试数/覆盖率） | ✅ |
| **P5 行标为 "Dashboard + Overlay"** | ⚠️ P5 (2026-08-03) 实际完成的是 Dashboard + Bootstrap + GameService（无 Overlay 集成）。Overlay 在 P5.3 (2026-08-04) 才最终完成。建议 P5 改为 "Dashboard + Bootstrap" 或 "控制中心" |

### 2.12 `Development/Release_History.md` — 🟢 通过

| 检查项 | 结果 |
|--------|:---:|
| 版本日期、tag、测试数/覆盖率 | ✅ 与 `changelog.md` 一致 |
| 测试数量演进 5 行 | ✅ |
| 架构里程碑 3 行 | ✅ |

### 2.13 `Development/Testing_Strategy.md` — 🟢 通过

| 检查项 | 结果 |
|--------|:---:|
| 测试文件映射（22 文件完整清单） | ✅ 完整（含 P3 文件） |
| Mock 策略表 | ✅ 准确 |
| 跨平台策略 | ✅ 准确 |
| 已知环境问题（Tcl/Tk） | ✅ 准确 |
| 总测试数 541 / 覆盖率 94% | ✅（pytest 确认） |

### 2.14 `docs/legacy/README.md` — 🟢 通过

| 检查项 | 结果 |
|--------|:---:|
| 归档来源映射表 | ✅ 与旧文件结构一致 |
| 权威文档对照表 | ✅ |

---

## 3. 检查清单逐项回复

### Architecture 文档是否准确反映以下组件？

| 组件 | System_Architecture | Module_Design | Process_Architecture | 状态 |
|------|:---:|:---:|:---:|:---:|
| Dashboard process | ✅ | ✅ | ✅ | 准确 |
| Overlay process | ✅ | ✅ | ✅ | 准确 |
| AppController | ✅ (Mermaid diagram) | ✅ (full API + properties) | ✅ (attach/detach/shutdown) | 准确 |
| GameService | ✅ | ✅ | ✅ | 准确 |
| MemoryReader | ✅ | ✅ (9 methods) | — | 准确 |
| StateTracker | ✅ | ✅ (8 methods) | — | 准确 |
| CombatRecorder | ✅ | ✅ (3 methods + CSV) | ✅ (daemon lifecycle) | 准确 |
| ActionPredictor | ✅ | ✅ (5 methods + is_loaded) | — | 准确 |

### 是否正确记录 P5.2 失败？

| 失败场景 | System_Architecture | Process_Architecture | 状态 |
|----------|:---:|:---:|:---:|
| 单 context + `create_viewport()` 多视口失败 | ✅ | ✅ (方案 A 表) | 准确 |
| Thread Overlay 失败 | ✅ | ✅ (方案 B 表) | 准确 |
| GLFW main-thread 限制 | ✅ | ✅ (根因分析) | 准确 |
| OverlayService + queue 失败 | — | ✅ (方案 C 表) | 准确 |

### 是否遗漏？

| 项目 | 状态 | 位置 |
|------|:---:|------|
| ADR 索引 | ✅ | `Architecture/ADR_Index.md`（2 条） |
| 生命周期 | ✅ | `Architecture/Process_Architecture.md`（state machine + 2 sequence diagrams） |
| 数据流 | ✅ | `Architecture/Data_Flow.md`（online + offline + config） |

### 跨文档一致性

| 检查 | 结果 |
|------|:---:|
| 与 `memory_bank/changelog.md` 的日期/测试数/覆盖率冲突 | 无 |
| 与源码不一致（类名/方法名/文件名） | 无 |
| 过时描述（P3 God Class 残留） | 无——所有描述为当前 P5.3 状态 |

---

## 4. Findings Summary

### 🔴 Must Fix（3 项）

| # | 文件:行 | 问题 | 影响 |
|---|---------|------|------|
| 1 | `Architecture/System_Architecture.md:88` | Mermaid 图 `CTRL -->\|start_overlay / stop_overlay\| P2` — `P2` 节点未定义，目标应为 `OV[overlay.py]` | Obsidian 渲染后边指向空节点 |
| 2 | `Architecture/Process_Architecture.md:121-126` | shutdown 顺序：文档写 `1.recorder.stop() 2.overlay.terminate() 3.training.terminate() 4.game_service.stop()` — 实际 `launch.py` finally 中 `game_service.stop()` **先于** `controller.shutdown()` | 顺序颠倒 |
| 3 | `AI_Model/Inference_System.md:108-109` | "Overlay 进程: GameService 附着 → P4 模块" — `GameService` 在 Dashboard 进程，不在 Overlay 进程 | Overlay 推理链路描述有误 |

### 🟡 Should Fix（3 项）

| # | 文件:行 | 问题 | 建议 |
|---|---------|------|------|
| 4 | `Architecture/ADR_Index.md:20` | ADR-P5.3 Status 标注 "Decided" 但 ADR 文件元数据为 `Proposed` | 更新 ADR-P5.3 文件 Status 或 ADR_Index 中标注 `Proposed (implemented)` |
| 5 | `Development/Development_Roadmap.md:23` | P5 行标 "Dashboard + Overlay" — Overlay 在 P5.3 才完成 | 改为 "Dashboard + Bootstrap" |
| 6 | `Architecture/Module_Design.md:220-238` | 测试映射表遗漏 8 个 P3 测试文件（~142 tests） | 注明"仅模块级测试——完整清单见 Testing_Strategy.md" |

### 🟢 Nice to Have（3 项）

| # | 文件 | 问题 | 建议 |
|---|------|------|------|
| 7 | `Architecture/System_Architecture.md:138` | `src/ui/` 进程列标 "Overlay" — `fonts.py` 被两个进程使用 | 改为 "双进程 / Overlay (UI)" |
| 8 | `Architecture/Data_Flow.md:126` | `AppConfig.save()` 提及"设置变更时"——当前 Dashboard 代码未调用 `save()`（设计意图 vs 已实现） | 标注 `save()` 已定义但运行时未调用（未来功能） |
| 9 | `Architecture/Process_Architecture.md:100` | 状态机 "Config → SpawnOverlay: AppConfig.load()" — `AppConfig.load()` 更像是状态内步骤而非变迁触发器 | 细微调整 labels（不阻碍可读性） |
