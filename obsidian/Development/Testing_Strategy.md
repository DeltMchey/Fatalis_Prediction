---
title: Testing Strategy
tags:
  - testing
  - pytest
  - coverage
  - CI
created: 2026-08-04
updated: 2026-09-16
---

# Testing Strategy — BlackDragon v1.2

> 当前测试体系（v1.2.0 状态：**766 passed**，36 个测试文件）。历史版本见 `docs/legacy/development-v0/`。

## 1. 测试金字塔

```
         ┌────────┐
         │ E2E    │  ← --selftest 真机自检（构建门禁）+ 游戏内手动 checklist
        ┌┤────────┤┐
        ││ 集成   ││  ← data_cleaner / data_upgrade / train_lgbm / production_backend / entry points / AutoML 工具链
        │├────────┤│
        ││ 单元   ││  ← P4 模块 + v1.2.0 新模块（backup_chain / features / label_decode / dataset）
        └┴────────┴┘
```

## 2. 当前指标

| 指标 | 值 |
|------|-----|
| 总测试数 | **766 passed**（36 个测试文件，v1.2.0） |
| 通过率 | 100%（`MPLBACKEND=Agg`；v1.1.0 581 → v1.2.0 766，+185） |
| 总体覆盖率 | 86%（v1.2.0，据 [[memory_bank/changelog|Changelog]]；新增实验/工具链模块摊薄，P4 core 仍 100%；P5.3 时期为 94%） |
| 全量 pytest | `build_exe.ps1` 第 2 步构建门禁（构建前必须全绿） |
| `--selftest` 门禁 | `build_exe.ps1` 第 7 步：双 EXE 真实加载 + 推理自检，任一失败即构建失败（Overlay 以 CWD=TEMP 运行覆盖 frozen 路径） |
| CI workflow | `.github/workflows/test.yml`（Windows + Ubuntu, Python 3.11/3.12） |

> 覆盖率口径：P5.3 时期 94% → v1.2.0 86%（新增实验/工具链模块摊薄；P4 core 维持 100%，据 [[memory_bank/changelog|Changelog]]）。

## 3. 测试文件映射

| 测试文件 | 目标 |
|----------|------|
| test_infrastructure.py | fixtures, config, discovery, CI |
| test_actions.py | ACTION_DB, ACTION_MAPPING, phase/posture sets |
| test_offsets.py | GameOffsets dataclass, 字段值, 不可变性 |
| test_logging.py | setup_logging, FileHandler |
| test_math_logic.py | calc_distance_2d, calc_relative_angle, select_top_k |
| test_phase_filter.py | filter_probs_by_phase/posture, renormalize |
| test_nova.py | evaluate_nova |
| test_data_upgrade.py | phase/enrage backfill, column order |
| test_data_cleaner.py | ETL: mapping, FSM, filtering, corrupted CSV, 合并语义 |
| test_train_lgbm.py | legacy LightGBM 路径 smoke |
| test_state_tracker.py | CombatStateTracker 全方法 |
| test_memory_reader.py | MemoryReader 指针链/读取 |
| test_predictor.py | ActionPredictor 加载/预测/过滤 |
| test_recorder.py | CombatRecorder 门控/录制/生命周期 |
| test_overlay.py | OverlayUI 状态/显示/DPG 生命周期 |
| test_app_config.py | AppConfig 默认值/持久化 |
| test_app_controller.py | AppController 生命周期/子进程 |
| test_game_service.py | GameService 检测/附着/分离 |
| test_bootstrap_checker.py | DependencyChecker 检查/安装 |
| test_dashboard.py | Dashboard UI 组件/回调 |
| test_launch.py | launch.py 结构 + auto_start + `--pipeline`/`--train` 路由 |
| test_overlay_entry.py | overlay.py 组装 + 重试循环 |
| test_main_integration.py | main.py composition root |
| **test_backup_chain.py** | 原子提升 / 两代备份链 / same-sha 跳过（v1.2.0） |
| **test_features.py** | FeatureBuilder 12 列派生 / fit-transform 防泄漏（v1.2.0） |
| **test_dataset_split.py** | load_ml_dataset / 分层切分（v1.2.0） |
| **test_production_backend.py** | Run B 重训链 / 守门 / sidecar（v1.2.0） |
| **test_train_automl.py** | FLAML CLI（--n-jobs 注入）/ 参数域（v1.2.0） |
| **test_automl_metric.py** | AutoML 搜索口径 top3 指标（v1.2.0） |
| **test_model_export.py** | 零 flaml 导出 / pickle 契约（v1.2.0） |
| **test_adopt_model.py** | 采纳门槛校验 / 轮换 / sidecar（v1.2.0） |
| **test_benchmark_model.py** | 四指标 benchmark 口径（v1.2.0） |

## 4. Mock 策略

| 组件 | 策略 |
|------|------|
| MemoryReader | `MagicMock(spec=MemoryReader)`（无 pymem 依赖） |
| ActionPredictor | `MagicMock(spec=ActionPredictor)`（无模型依赖） |
| CombatStateTracker | **真实实例**（纯逻辑） |
| DPG | `patch("src.ui.overlay.dpg")` / `patch("src.dashboard.*.dpg")`（不启动真实窗口） |
| pymem | 跨平台 stub 预装 + 函数级 monkeypatch |
| AppController | `MagicMock`（Dashboard 测试） |
| subprocess.Popen | `monkeypatch`（子进程测试） |

## 5. 跨平台策略

- **Windows**：真实环境（pymem/dearpygui 已装）
- **Linux CI**：模块级预装 stub（`pymem`, `dearpygui`）→ import 成功
- 结构约束测试（AST）：验证模块无 `pymem` 模块级 import、无模块级可变状态
- `MPLBACKEND=Agg`：规避本机 Tcl/Tk 损坏导致的 matplotlib 回退（已知环境问题）

## 6. 运行命令

```bash
# 全量测试
MPLBACKEND=Agg pytest tests/ -q

# 覆盖率
MPLBACKEND=Agg pytest tests/ -q --cov=src --cov=overlay --cov=launch --cov-report=term

# 单模块
MPLBACKEND=Agg pytest tests/test_state_tracker.py -q
```

## 7. 已知环境问题

| 问题 | 影响 | 规避 |
|------|------|------|
| 本机 Tcl/Tk `init.tcl` 缺失 | matplotlib 间歇回退 TkAgg → test_train_lgbm 偶发失败 | 始终 `MPLBACKEND=Agg` |
| DPG/GLFW 无法在 CI 渲染 | 真窗口测试不可能 | 全部 DPG 调用 mock |

## 8. 未来改进

- [x] ~~E2E 真机自检~~ → v1.2.0 已落地 `--selftest`（双 EXE 真实加载 + 推理，构建硬门禁）；游戏内手动 checklist 仍待补
- [ ] 进程级集成测试（launch.py 真实 spawn + 存活断言）
- [x] ~~特征消融回归测试~~ → P6 Run A/B 对照已完成（派生特征 50.71% gain）
- [ ] selftest helper 双实现去重（ADR-P6.1 follow-up：`overlay.py _selftest()` 与 `launch.py` 内联逻辑提取共享模块）
