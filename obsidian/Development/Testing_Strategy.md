---
title: Testing Strategy
tags:
  - testing
  - pytest
  - coverage
  - CI
created: 2026-08-04
updated: 2026-08-04
---

# Testing Strategy — BlackDragon v1.0

> 当前测试体系（P5.3 auto-start 状态：541 tests, 94% coverage）。历史版本见 `docs/legacy/development-v0/`。

## 1. 测试金字塔

```
         ┌────────┐
         │ E2E    │  ← 未实现（真机游戏内测试，需手动 checklist）
        ┌┤────────┤┐
        ││ 集成   ││  ← data_cleaner / data_upgrade / train_lgbm / entry points
        │├────────┤│
        ││ 单元   ││  ← P4 模块（state_tracker / memory_reader / predictor / recorder / overlay）
        └┴────────┴┘
```

## 2. 当前指标

| 指标 | 值 |
|------|-----|
| 总测试数 | **541**（22 个测试文件） |
| 通过率 | 100%（`MPLBACKEND=Agg`） |
| 总体覆盖率 | **94%** |
| P4 core（state_tracker/memory_reader/recorder） | 100% |
| predictor | 99% |
| overlay.py / src/ui/overlay.py | 100% |
| config 模块 | 100% (3/3) |
| data 管线模块 | 100% (3/3) |
| CI workflow | `.github/workflows/test.yml`（Windows + Ubuntu, Python 3.11/3.12） |

## 3. 测试文件映射

| 测试文件 | 数量 | 目标 |
|----------|:---:|------|
| test_infrastructure.py | 17 | fixtures, config, discovery, CI |
| test_actions.py | 20 | ACTION_DB, ACTION_MAPPING, phase/posture sets |
| test_offsets.py | 14 | GameOffsets dataclass, 字段值, 不可变性 |
| test_logging.py | 11 | setup_logging, FileHandler |
| test_math_logic.py | 27 | calc_distance_2d, calc_relative_angle, select_top_k |
| test_phase_filter.py | 32 | filter_probs_by_phase/posture, renormalize |
| test_nova.py | 26 | evaluate_nova |
| test_data_upgrade.py | 11 | phase/enrage backfill, column order |
| test_data_cleaner.py | 19 | ETL: mapping, FSM, filtering, corrupted CSV |
| test_train_lgbm.py | 5 | mini training, model output, rare class filter |
| test_state_tracker.py | 50 | CombatStateTracker 全方法 |
| test_memory_reader.py | 27 | MemoryReader 指针链/读取 |
| test_predictor.py | 31 | ActionPredictor 加载/预测/过滤 |
| test_recorder.py | 34 | CombatRecorder 门控/录制/生命周期 |
| test_overlay.py | 41 | OverlayUI 状态/显示/DPG 生命周期 |
| test_app_config.py | 12 | AppConfig 默认值/持久化 |
| test_app_controller.py | 40 | AppController 生命周期/子进程 |
| test_game_service.py | 12 | GameService 检测/附着/分离 |
| test_bootstrap_checker.py | 26 | DependencyChecker 检查/安装 |
| test_dashboard.py | 25 | Dashboard UI 组件/回调 |
| test_launch.py | 11 | launch.py 结构 + auto_start 行为 |
| test_overlay_entry.py | 24 | overlay.py 组装 + 重试循环 |
| test_main_integration.py | 20 | main.py composition root |

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

- [ ] E2E 真机手动 checklist（游戏内验证双进程 + 覆盖层）
- [ ] 进程级集成测试（launch.py 真实 spawn + 存活断言）
- [ ] 特征消融回归测试（P6）
