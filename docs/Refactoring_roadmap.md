# BlackDragon 分阶段重构路线图

> 最后更新：2026-06-07
> 目标：从单体脚本到可发布的 GitHub 开源项目，每阶段保持可运行

---

## 总览

```
P1 ──► P2 ──► P3 ──► P4 ──► P5
项目       P0      测试     架构     模型
优化      修复     体系     重构     工程化
(2天)    (3天)   (3天)   (5天)   (4天)
  │        │       │       │       │
  │ 低风险  │ 消除   │ 安全网 │ 解耦   │ 工业化
  │ 基础化  │ 核心债 │        │       │
  ▼        ▼       ▼       ▼       ▼
 可运行   可运行   可运行   可运行   可运行 ──► 🚀 GitHub Release
```

**核心原则**：
- 每阶段结束，`python ai_engine.py` 必须能启动并与游戏正常交互
- 先建立安全网（日志、测试），再做高风险改动
- 每次改动控制在 2-3 个文件，避免大规模重写
- 每个 Phase 结束打一个 git tag

---

## P1：项目优化（2 天）— 低风险基建

> **目标**：在不改动任何核心逻辑的前提下，建立项目基础设施，为后续工作铺路。
> **原则**：纯增量操作，不改一行现有代码逻辑。

### 修改清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `README.md` | 项目介绍、安装说明、使用指南、目录结构 |
| 新建 | `.gitignore` | 忽略 `.venv/`, `__pycache__/`, `*.csv`, `*.pkl`, `.idea/` |
| 新建 | `requirements.txt` | 锁定依赖版本：`pymem`, `dearpygui`, `lightgbm`, `scikit-learn`, `pandas`, `numpy`, `matplotlib`, `joblib` |
| 新建 | `CHANGELOG.md` | 版本记录 |
| 新建 | `archive/` 目录 | 将 `mod.py` 移入，添加废弃说明 |
| 新建 | `data/` 目录 | 将 `fatalis_combat_data_*.csv`、`ML_Ready_Dataset.csv` 移入 |
| 新建 | `models/` 目录 | 将 `fatalis_ai_model.pkl`、`feature_importance.png` 移入 |
| 新建 | `docs/` 目录 | 将 `出招表.txt`、`招式表2.0.txt`、`Project_map.md`、`Tech_debt.md` 移入 |
| 修改 | `ai_engine.py` L156 | 模型路径：`"fatalis_ai_model.pkl"` → `"models/fatalis_ai_model.pkl"` |
| 修改 | `ai_engine.py` L103 | CSV 输出路径加 `data/` 前缀 |
| 修改 | `data_cleaner.py` L8 | glob 路径加 `data/` 前缀 |
| 修改 | `data_cleaner.py` L125 | CSV 输出路径加 `data/` 前缀 |
| 修改 | `data_upgrade.py` L8 | glob 路径加 `data/` 前缀 |
| 修改 | `train_lgbm.py` L14 | CSV 路径加 `data/` 前缀 |
| 修改 | `train_lgbm.py` L64 | 模型路径加 `models/` 前缀 |
| 修改 | `train_lgbm.py` L78 | 图片路径加 `models/` 前缀 |
| 新建 | `tests/manual_checklist.md` | 手工验证清单（此时还不写代码测试） |

### 风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| 路径变更导致模块找不到文件 | 🟢 极低 | 统一使用相对路径，本地逐项验证 |
| `mod.py` 被移除后有人依赖 | 🟢 极低 | 移入 `archive/` 而非删除，README 注明 |

### 预计工作量

| 工作项 | 耗时 |
|--------|------|
| README + .gitignore + requirements.txt | 3h |
| 目录重组 + 路径修改 | 2h |
| CHANGELOG + 文档整理 | 1h |
| 手工验证 | 2h |
| **合计** | **8h (2天)** |

### 验证方法

```bash
# 1. 确认目录结构
ls -la
# 预期输出：README.md, requirements.txt, .gitignore, ai_engine.py,
#          data_cleaner.py, data_upgrade.py, train_lgbm.py, enrage.py,
#          data/, models/, docs/, archive/, tests/

# 2. 确认数据管线
cd data/ && ls fatalis_combat_data_*.csv | wc -l  # 应 > 0
python data_cleaner.py                              # 应输出 "✅ V4.5 ... 有效样本: N 条"
python train_lgbm.py                                # 应输出 "🏆 绝对准确率: XX%" "🌟 Top-3 命中率: XX%"

# 3. 确认主程序启动（无需游戏，检查 import 和 UI 初始化不报错）
python -c "import ai_engine; print('✅ 模块加载成功')"

# 4. 确认 gitignore 生效
git status  # 不应出现 .venv/, __pycache__/, *.csv, *.pkl
```

### P1 完成标志

- [ ] `README.md` 包含安装步骤、使用方法、项目结构说明
- [ ] `.gitignore` 忽略所有生成文件和虚拟环境
- [ ] `requirements.txt` 可复现环境
- [ ] `git init` 后 `git status` 干净（仅源代码和文档）
- [ ] `python data_cleaner.py && python train_lgbm.py` 正常运行
- [ ] `python ai_engine.py` 能启动 UI 窗口（游戏未开时显示 "未找到游戏进程"）
- [ ] Git tag: `v0.1.0-project-init`

---

## P2：P0 修复（3 天）— 消除核心债

> **目标**：修复 Tech_debt.md 中标记为 P0 的 3 项核心问题，不改架构。
> **原则**：每个修复在独立的 commit 中，可单独回滚。

### 修改清单

#### Step 2.1：异常日志化（Tech_debt #3）— 0.5 天

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `src/__init__.py` | 包初始化 |
| 新建 | `src/logging_config.py` | 统一日志配置：`blackdragon.log` 文件 + 控制台 |
| 修改 | `ai_engine.py:146-147` | `except: pass` → `except Exception: logger.warning(...)` |
| 修改 | `ai_engine.py:309-310` | `except: pass` → `except Exception: logger.error(...)` |
| 修改 | `ai_engine.py:158-159` | 模型加载失败打印 → `logger.error(...)` |
| 修改 | `ai_engine.py:169` | 字体加载异常 → `logger.warning(...)` |
| 修改 | `ai_engine.py:320-321` | 进程连接失败 → `logger.error(...)` |

**验证**：故意制造异常（模型文件不存在、游戏未开），检查 `blackdragon.log` 是否记录。

#### Step 2.2：统一 ACTION_MAPPING（Tech_debt #2）— 1 天

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `src/config/__init__.py` | |
| 新建 | `src/config/actions.py` | 唯一数据源：`ACTION_DB`, `ACTION_MAPPING`, 所有招式分类集合 |
| 修改 | `ai_engine.py` L17-69 | 删除 ACTION_DB/ACTION_MAPPING/P1_ONLY_IDS 等，改为 `from src.config.actions import ...` |
| 修改 | `data_cleaner.py` L15-51 | 删除 ACTION_MAPPING/MINOR_AND_PASSIVE 等，改为 import |
| 删除 | `data_cleaner.py` 重复定义 | 整段替换 |
| 修改 | `enrage.py` | 无需改动（不引用这些常量） |

**关键动作**：对比 `ai_engine.py` 和 `data_cleaner.py` 的映射表，合并为**并集**，确保不丢失任何映射。

```python
# src/config/actions.py 结构示意
"""黑龙动作数据库 — 项目唯一数据源"""

ACTION_DB: dict[int, str] = {
    306: "等待", 307: "等待", ...
}

ACTION_MAPPING: dict[int, int] = {
    # 龙车
    38: 37, 39: 37, 40: 37,
    50: 49, 51: 49, 52: 49,
    # 连咬（含 data_cleaner.py 独有的 57:53）
    54: 53, 55: 53, 56: 53, 57: 53,
    # ... 完整合并
}

# 招式分类（用作物理过滤和训练排除）
P1_ONLY_IDS: set[int]
P2_PLUS_IDS: set[int]
P3_ONLY_IDS: set[int]
DOWN_IDS: set[int]
SCRIPTED_IDS: set[int]
MINOR_AND_PASSIVE: set[int]
```

**验证**：运行 `python data_cleaner.py` 和 `python train_lgbm.py`，确保准确率不降（允许轻微波动）。启动 `ai_engine.py` 确认动作名显示正常。

#### Step 2.3：偏移量配置化（Tech_debt #1）— 1.5 天

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `src/config/offsets.py` | 所有内存偏移量集中定义（dataclass） |
| 修改 | `ai_engine.py:81-99` | `get_ptr()` 和 `find_monster()` 使用 `offsets` 对象而非硬编码 |
| 修改 | `ai_engine.py:110-144` | `data_logger_thread` 使用配置对象 |
| 修改 | `ai_engine.py:209-248` | `update_logic` 使用配置对象 |
| 修改 | `ai_engine.py:323` | 基址计算使用配置对象 |
| 修改 | `enrage.py:37,41` | 基址和扫描范围使用配置对象 |
| 新建 | `docs/offsets_guide.md` | 偏移量含义说明 + 游戏更新后修改指南 |

```python
# src/config/offsets.py
from dataclasses import dataclass

@dataclass(frozen=True)
class GameOffsets:
    # ── 基址（模块内偏移）──
    PLAYER_BASE: int = 0x050139A0
    MONSTER_BASE: int = 0x051238C8
    ZONE_BASE: int = 0x0500ECA0

    # ── 怪物实例链 ──
    MONSTER_LIST_FIRST: int = 0x698
    MONSTER_LIST_STRIDE: int = 0x8
    MONSTER_LIST_NEXT: int = 0x138
    MONSTER_LIST_TERMINAL: int = 0

    # ── 怪物属性 ──
    MONSTER_HP_BASE: int = 0x7670
    HP_MAX: int = 0x60
    HP_CURRENT: int = 0x64
    MONSTER_COORDS: int = 0x160
    MONSTER_QUAT: int = 0x170
    MONSTER_ACTION_ID: int = 0x6278

    # ── 发怒结构体 ──
    ENRAGE_STRUCT: int = 0x1BE30
    ENRAGE_TIMER: int = 0x24
    ENRAGE_MAX: int = 0x28

    # ── 玩家链 ──
    PLAYER_CHAIN_1: int = 0x50
    PLAYER_CHAIN_2: int = 0xC0
    PLAYER_COORDS: int = 0x670

    # ── 区域 ──
    ZONE_OFFSET: int = 0xAED0
    ZONE_FATALIS: int = 417

    # ── 战斗参数 ──
    MONSTER_MAX_SLOTS: int = 10
    MONSTER_MIN_HP: float = 500.0
    NOVA_THRESHOLDS: tuple = (0.78, 0.50, 0.41, 0.26, 0.06)

OFFSETS = GameOffsets()
```

**验证**：启动 `ai_engine.py`，进游戏验证所有数据显示正常（动作名、HP%、距离、角度、发怒状态、Nova 预警）。

### 风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| ACTION_MAPPING 合并时遗漏条目 | 🟡 中 | diff 对比后取并集；运行 data_cleaner + train 验证准确率 |
| 偏移量重构引入引用错误 | 🟡 中 | 逐函数替换，每替换一个函数就启动验证一次 |
| 日志文件权限/编码问题 | 🟢 低 | 使用 `encoding='utf-8'`，捕获文件写入异常 |

### 预计工作量

| 工作项 | 耗时 |
|--------|------|
| 2.1 异常日志化 | 3h |
| 2.2 ACTION_MAPPING 统一 | 6h |
| 2.3 偏移量配置化 | 8h |
| 验证 + 修 bug | 3h |
| **合计** | **20h (3天)** |

### P2 完成标志

- [ ] 所有 `except: pass` 替换为日志记录
- [ ] `blackdragon.log` 正常生成
- [ ] `ACTION_MAPPING` 只有 `src/config/actions.py` 一处定义
- [ ] `ai_engine.py`、`data_cleaner.py` 均 import 自 `src.config.actions`
- [ ] 所有内存偏移量在 `src/config/offsets.py` 中
- [ ] `python data_cleaner.py && python train_lgbm.py` 输出准确率与 P1 基线一致（误差 ±1%）
- [ ] `python ai_engine.py` 进游戏运行 5 分钟无异常日志
- [ ] Git tag: `v0.2.0-p0-fixes`

---

## P3：测试体系（3 天）— 建立安全网

> **目标**：为核心逻辑建立测试覆盖，确保 P4 大规模重构时有安全网。
> **原则**：只测纯逻辑（不依赖游戏进程），不写集成测试（此时还没有模块化）。

### 修改清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `requirements-dev.txt` | `pytest`, `pytest-cov`, `pytest-mock` |
| 新建 | `tests/__init__.py` | |
| 新建 | `tests/test_actions.py` | 测试 `ACTION_MAPPING` 的正确性和一致性 |
| 新建 | `tests/test_posture_fsm.py` | 测试姿态状态机 |
| 新建 | `tests/test_phase_filter.py` | 测试阶段/姿态物理过滤规则 |
| 新建 | `tests/test_nova.py` | 测试 Nova 血线阈值逻辑 |
| 新建 | `tests/test_data_cleaner.py` | 测试数据清洗核心逻辑 |
| 新建 | `tests/conftest.py` | 共享 fixtures（构造 mock 数据） |
| 新建 | `.github/workflows/test.yml` | GitHub Actions CI：每次 push 跑 pytest |
| 新建 | `setup.cfg` | pytest 配置（最小覆盖率 60%） |

### 测试范围

```
测试金字塔
    ┌──────┐
    │  E2E  │  ← P5 补
    ├──────┤
    │ 集成  │  ← P4 补（模块间交互）
    ├──────┤
    │ 单元  │  ← P3 集中建设 ← 本阶段
    └──────┘
```

#### tests/test_actions.py

```python
"""测试动作映射的正确性"""
import pytest
from src.config.actions import ACTION_MAPPING, P1_ONLY_IDS, P2_PLUS_IDS, P3_ONLY_IDS

class TestActionMapping:
    def test_dragon_charge_maps_to_base(self):
        """龙车所有帧映射到基础 ID"""
        assert ACTION_MAPPING.get(38) == 37
        assert ACTION_MAPPING.get(39) == 37
        assert ACTION_MAPPING.get(40) == 37

    def test_bite_combo_maps_to_base(self):
        """连咬所有帧映射到基础 ID"""
        assert ACTION_MAPPING.get(54) == 53
        assert ACTION_MAPPING.get(55) == 53
        assert ACTION_MAPPING.get(56) == 53
        assert ACTION_MAPPING.get(57) in (53, None)  # 57 可能未定义

    def test_no_circular_mapping(self):
        """无循环映射: A→B→C 链条中 C 不应映射到 A"""
        for src, dst in ACTION_MAPPING.items():
            chain = [src]
            current = dst
            while current in ACTION_MAPPING:
                assert current not in chain, f"循环映射: {chain} → {current}"
                chain.append(current)
                current = ACTION_MAPPING[current]

    def test_phase_sets_disjoint(self):
        """阶段专属招式集合应互斥"""
        overlap_12 = P1_ONLY_IDS & P2_PLUS_IDS
        overlap_13 = P1_ONLY_IDS & P3_ONLY_IDS
        overlap_23 = P2_PLUS_IDS & P3_ONLY_IDS
        assert not overlap_12, f"P1∩P2: {overlap_12}"
        assert not overlap_13, f"P1∩P3: {overlap_13}"
        assert not overlap_23, f"P2∩P3: {overlap_23}"

    def test_all_mapped_targets_exist_in_db(self):
        """所有映射目标 ID 在 ACTION_DB 中有名称"""
        from src.config.actions import ACTION_DB
        for dst in set(ACTION_MAPPING.values()):
            assert dst in ACTION_DB, f"映射目标 {dst} 不在 ACTION_DB 中"
```

#### tests/test_posture_fsm.py

```python
"""测试姿态状态机"""
import pytest
from src.config.actions import ACTION_DB, ACTION_MAPPING

# 从 ai_engine 提取状态机逻辑为独立函数（P2 后的代码已 importable）
class PostureTracker:
    """姿态追踪器（从 ai_engine.py 提取的纯逻辑）"""
    def __init__(self):
        self.posture = 1  # 初始站立
        self.last_action = -1

    def update(self, action_id: int) -> int:
        """根据动作更新姿态，返回新的 posture"""
        if action_id != self.last_action and action_id != -1:
            if action_id in {115, 116, 121, 122, 129, 119, 98, 99, 68, 69, 70, 71, 72,
                             149, 150, 151, 32, 19, 197, 219, 222}:
                self.posture = 1
            elif action_id in {138, 49, 50, 51, 52, 73, 30, 74, 75}:
                self.posture = 0
            elif action_id in {107, 108, 167, 179}:
                self.posture = 2
            self.last_action = action_id
        return self.posture


class TestPostureFSM:
    def test_initial_posture_is_standing(self):
        tracker = PostureTracker()
        assert tracker.posture == 1

    def test_dive_sets_standing(self):
        """俯冲(115) → 站立"""
        tracker = PostureTracker()
        tracker.update(115)
        assert tracker.posture == 1

    def test_vomit_sets_prone(self):
        """孕吐(138) → 趴下"""
        tracker = PostureTracker()
        tracker.update(138)
        assert tracker.posture == 0

    def test_jump_sets_flying(self):
        """跳投(107) → 飞行"""
        tracker = PostureTracker()
        tracker.update(107)
        assert tracker.posture == 2

    def test_same_action_no_change(self):
        """同一招式重复不改变姿态"""
        tracker = PostureTracker()
        tracker.update(115)  # → 站立
        tracker.update(115)  # 重复同一招式
        assert tracker.posture == 1  # 仍站立

    def test_transition_chain(self):
        """姿态切换链路: 站立→趴下→站立"""
        tracker = PostureTracker()
        assert tracker.posture == 1   # 初始站立
        tracker.update(30)            # 趴下 → 0
        assert tracker.posture == 0
        tracker.update(32)            # 站起 → 1
        assert tracker.posture == 1
```

#### tests/test_phase_filter.py

```python
"""测试 AI 推理的物理过滤规则"""
import numpy as np
import pytest
from src.config.actions import P1_ONLY_IDS, P2_PLUS_IDS, P3_ONLY_IDS

# 从 ai_engine.py 提取过滤函数
def apply_phase_posture_filter(probs: np.ndarray, classes: np.ndarray,
                                phase: int, posture: int) -> np.ndarray:
    """应用阶段 + 姿态物理过滤（纯函数，无副作用）"""
    probs = probs.copy()

    # 站立姿态的趴下招式排除
    STANDING_EXCLUDE = {129, 119, 98, 99, 68, 69, 70, 71, 72,
                        149, 150, 151, 152, 153, 93}
    # 趴下姿态的站立招式排除
    PRONE_EXCLUDE = {138, 49, 50, 51, 52, 73, 107, 108, 136, 88,
                     91, 92, 94, 95, 96, 97, 100, 101, 137, 154,
                     155, 156, 37, 38, 39, 40, 131, 132, 133,
                     140, 141, 142, 135, 134, 81, 82, 83}

    for i, class_id in enumerate(classes):
        if phase > 1 and class_id in P1_ONLY_IDS: probs[i] = 0.0
        if phase < 2 and class_id in P2_PLUS_IDS: probs[i] = 0.0
        if phase < 3 and class_id in P3_ONLY_IDS: probs[i] = 0.0
        if posture == 1 and class_id in STANDING_EXCLUDE: probs[i] = 0.0
        elif posture == 0 and class_id in PRONE_EXCLUDE: probs[i] = 0.0

    total = probs.sum()
    if total > 0:
        probs /= total
    return probs


class TestPhaseFilter:
    def test_p1_actions_blocked_in_p2(self):
        """P1 专属招式在 P2 概率为 0"""
        classes = np.array([37, 53, 146, 137, 88, 129])  # 前4个P1专属
        probs = np.ones(6) / 6
        result = apply_phase_posture_filter(probs, classes, phase=2, posture=1)
        assert result[0] == 0.0  # P1 龙车
        assert result[1] == 0.0  # P1 连咬
        assert result[2] == 0.0  # P1 后撤
        assert result[3] == 0.0  # P1 孕吐
        assert result[4] > 0.0   # 单火球不受影响

    def test_p2_actions_blocked_in_p1(self):
        """P2 才有的招式在 P1 概率为 0"""
        classes = np.array([129, 121, 81, 37])
        probs = np.ones(4) / 4
        result = apply_phase_posture_filter(probs, classes, phase=1, posture=1)
        assert result[0] == 0.0  # P2 蓄力火
        assert result[1] == 0.0  # P2 飞天俯冲
        assert result[2] == 0.0  # P2 吐痰
        assert result[3] > 0.0   # P1 龙车保留

    def test_p3_actions_blocked_in_p2(self):
        """P3 专属招式在 P2 概率为 0"""
        classes = np.array([155, 134, 208, 88])
        probs = np.ones(4) / 4
        result = apply_phase_posture_filter(probs, classes, phase=2, posture=1)
        assert result[0] == 0.0  # P3 360扫火
        assert result[1] == 0.0  # P3 左右火
        assert result[2] == 0.0  # P3 捕食

    def test_renormalization(self):
        """过滤后概率重归一化，和为 1"""
        classes = np.array([37, 88, 91])  # 37 是 P1 only
        probs = np.array([0.3, 0.3, 0.4])
        result = apply_phase_posture_filter(probs, classes, phase=2, posture=1)
        assert abs(result.sum() - 1.0) < 1e-9

    def test_all_zero_handled(self):
        """全过滤后不除零"""
        classes = np.array([37, 53, 146])  # 全是 P1 only
        probs = np.ones(3) / 3
        result = apply_phase_posture_filter(probs, classes, phase=2, posture=1)
        assert result.sum() == 0.0  # 不崩溃，全零
```

### 风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| 提取测试逻辑时意外修改行为 | 🟡 中 | 先写测试、再提取函数（TDD 反向操作: 复制原代码→写测试→确认通过→替换原代码） |
| 姿态状态机测试覆盖不完备 | 🟢 低 | 列出所有边界招式，逐项添加测试用例 |
| CI 环境无 dearpygui/pymem | 🟢 低 | 单元测试不 import 这些库，CI 配置跳过需要 GUI 的测试 |

### 预计工作量

| 工作项 | 耗时 |
|--------|------|
| 提取可测试函数（PostureTracker, apply_filter） | 3h |
| test_actions.py | 2h |
| test_posture_fsm.py | 3h |
| test_phase_filter.py | 3h |
| test_nova.py + test_data_cleaner.py | 3h |
| CI 配置 (GitHub Actions) | 2h |
| 验证 + 提升覆盖率 | 2h |
| **合计** | **18h (3天)** |

### P3 完成标志

- [ ] `pytest` 运行全部测试且绿色
- [ ] 测试覆盖率 ≥ 60%（`pytest --cov=src --cov-report=term`）
- [ ] 核心逻辑（actions.py, posture FSM, filter）覆盖率 ≥ 90%
- [ ] `.github/workflows/test.yml` 配置完成，push 自动触发
- [ ] `tests/manual_checklist.md` 更新为自动化测试索引
- [ ] P2 的功能全部保持正常
- [ ] Git tag: `v0.3.0-test-safety-net`

---

## P4：架构重构（5 天）— 解耦 God Class

> **目标**：将 `ai_engine.py` 拆解为独立模块，但外部行为完全不变。
> **原则**：每次只拆一个职责，拆完验证通过再拆下一个。

### 拆分顺序（由外到内，由简到繁）

```
ai_engine.py (当前 328 行)
    │
    ├── Step 4.1: 拆出 StateTracker    (状态机逻辑)       → src/core/state_tracker.py
    ├── Step 4.2: 拆出 MemoryReader    (内存读取层)       → src/core/memory_reader.py
    ├── Step 4.3: 拆出 CombatRecorder  (CSV 录制)         → src/data/recorder.py
    ├── Step 4.4: 拆出 ActionPredictor (AI 推理)          → src/model/predictor.py
    ├── Step 4.5: 拆出 OverlayUI       (悬浮窗)           → src/ui/overlay.py
    └── Step 4.6: 组装 main.py         (入口 + 线程管理)  → main.py

每一步后: python main.py 验证 (或 python ai_engine.py 如果仍在原位)
```

### 修改清单

#### Step 4.1：拆出 StateTracker（1 天）

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `src/core/__init__.py` | |
| 新建 | `src/core/state_tracker.py` | `CombatState` 类：线程安全的状态容器 (Tech_debt #5) |
| 修改 | `ai_engine.py` | `shared_state` dict → `CombatState` 实例；状态更新逻辑迁移到 `CombatState` 方法 |

```python
# src/core/state_tracker.py
import threading
from contextlib import contextmanager
from src.config.actions import (
    ACTION_MAPPING, P1_ONLY_IDS, P2_PLUS_IDS, P3_ONLY_IDS,
    DOWN_IDS, SCRIPTED_IDS, MINOR_AND_PASSIVE
)
from src.config.offsets import OFFSETS

class CombatState:
    """线程安全的战斗状态容器，替代 shared_state dict"""

    def __init__(self):
        self._lock = threading.RLock()
        self._posture: int = 1
        self._phase: int = 1
        self._is_enraged: int = 0
        self._is_recording: bool = True
        self._nova_warning: bool = False
        self._hp_initialized: bool = False
        self._triggered_novas: set[float] = set()
        self._last_action: int = -1

    @contextmanager
    def atomic(self):
        """原子操作上下文"""
        with self._lock: yield

    # ── 属性访问器 ──
    @property
    def posture(self) -> int: return self._posture
    @property
    def phase(self) -> int: return self._phase
    @property
    def is_enraged(self) -> int: return self._is_enraged
    @property
    def nova_warning(self) -> bool: return self._nova_warning

    # ── 状态更新方法 ──
    def update_phase(self, hp_percent: float):
        """根据 HP 百分比推导战斗阶段"""
        if hp_percent > OFFSETS.NOVA_THRESHOLDS[0]:
            self._phase = 1
        elif hp_percent > OFFSETS.NOVA_THRESHOLDS[1]:
            self._phase = 2
        else:
            self._phase = 3

    def update_posture(self, action_id: int):
        """根据招式更新姿态"""
        if action_id != self._last_action and action_id != -1:
            if action_id in {115, 116, 121, 122, 129, 119, 98, 99,
                             68, 69, 70, 71, 72, 149, 150, 151,
                             32, 19, 197, 219, 222}:
                self._posture = 1
            elif action_id in {138, 49, 50, 51, 52, 73, 30, 74, 75}:
                self._posture = 0
            elif action_id in {107, 108, 167, 179}:
                self._posture = 2
            elif action_id in DOWN_IDS:
                self._posture = 3
            elif action_id in SCRIPTED_IDS:
                self._posture = 4

    def update_enrage(self, timer: float, max_val: float):
        """硬件级发怒检测"""
        self._is_enraged = 1 if (0.0 < timer < max_val) else 0

    def check_nova(self, hp_percent: float, action_id: int) -> bool:
        """检查飞天火血线预警"""
        if not self._hp_initialized:
            for t in OFFSETS.NOVA_THRESHOLDS:
                if hp_percent <= t: self._triggered_novas.add(t)
            self._hp_initialized = True

        for t in OFFSETS.NOVA_THRESHOLDS:
            if hp_percent <= t and t not in self._triggered_novas:
                self._triggered_novas.add(t)
                self._nova_warning = True

        if action_id in {197, 167, 179}:
            self._nova_warning = False

        return self._nova_warning

    def reset(self):
        """回城时重置所有状态"""
        with self._lock:
            self._posture = 1
            self._phase = 1
            self._is_enraged = 0
            self._hp_initialized = False
            self._nova_warning = False
            self._triggered_novas.clear()
            self._last_action = -1
```

#### Step 4.2：拆出 MemoryReader（1 天）

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `src/core/memory_reader.py` | 封装 pymem 操作：`get_ptr()`, `find_monster()`, `read_player()`, `read_monster()` |

```python
# src/core/memory_reader.py
import pymem
import pymem.process
from dataclasses import dataclass
from typing import Optional
from src.config.offsets import OFFSETS

@dataclass
class PlayerData:
    x: float; y: float; z: float

@dataclass
class MonsterData:
    ptr: int
    x: float; y: float; z: float
    quat: tuple[float,float,float,float]
    hp_percent: float
    action_id: int
    enrage_timer: float
    enrage_max: float

class MemoryReader:
    def __init__(self, process_name: str = "MonsterHunterWorld.exe"):
        self.pm = pymem.Pymem(process_name)
        self.base = pymem.process.module_from_name(
            self.pm.process_handle, process_name
        ).lpBaseOfDll

    def _get_ptr(self, base: int, offsets: list[int]) -> int:
        """多级指针解引用"""
        ...

    def find_monster(self) -> Optional[int]:
        """遍历怪物槽位，返回黑龙实例指针"""
        ...

    def read_player(self) -> Optional[PlayerData]:
        """读取玩家坐标"""
        ...

    def read_monster(self, ptr: int) -> MonsterData:
        """读取怪物完整数据"""
        ...

    def read_zone(self) -> int:
        """读取当前区域 ID"""
        ...
```

#### Step 4.3-4.5：拆出 Recorder、Predictor、Overlay（1.5 天）

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `src/data/__init__.py` | |
| 新建 | `src/data/recorder.py` | `CombatRecorder` 类：CSV 写入线程 (Tech_debt #13: 加 gzip 选项) |
| 新建 | `src/model/__init__.py` | |
| 新建 | `src/model/predictor.py` | `ActionPredictor` 类：模型加载 + 推理 + 物理过滤 (Tech_debt #6: 模型版本管理) |
| 新建 | `src/ui/__init__.py` | |
| 新建 | `src/ui/overlay.py` | `OverlayUI` 类：dearpygui 窗口管理 (Tech_debt #14: 配置化) |

#### Step 4.6：组装 main.py（1 天）

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `main.py` | 新入口：组装各模块、启动线程、运行 UI 循环 |
| 保留 | `ai_engine.py` | 改为 `from main import main` 保持向后兼容 |
| 新建 | `src/config/settings.py` | 应用级配置：窗口大小/位置/颜色/透明度/推理间隔 (Tech_debt #14) |

```python
# main.py
"""BlackDragon 主入口"""
from src.core.memory_reader import MemoryReader
from src.core.state_tracker import CombatState
from src.data.recorder import CombatRecorder
from src.model.predictor import ActionPredictor
from src.ui.overlay import OverlayUI
import threading

def main():
    # 1. 连接游戏
    reader = MemoryReader()

    # 2. 初始化状态
    state = CombatState()

    # 3. 加载模型
    predictor = ActionPredictor()

    # 4. 启动录制线程
    recorder = CombatRecorder(state, reader)
    recorder_thread = threading.Thread(target=recorder.run, daemon=True)
    recorder_thread.start()

    # 5. 启动 UI（占用主线程）
    ui = OverlayUI(reader, state, predictor)
    ui.run()

if __name__ == "__main__":
    main()
```

### 风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| 拆分后模块间接口不匹配 | 🟡 中 | 每拆一个模块，立即在游戏中验证（至少运行 3 分钟） |
| 性能回退（多一层函数调用） | 🟢 低 | pymem 调用本身是瓶颈（~0.1ms），Python 函数调用开销可忽略 |
| 线程模型变更引入竞态 | 🟡 中 | CombatState 在 P3 已有测试，P4 只改封装不改逻辑 |
| 拆分过程中断项目能运行 | 🟢 低 | 保留 `ai_engine.py` 完整副本，渐进式替换 |

### 预计工作量

| 工作项 | 耗时 |
|--------|------|
| 4.1 拆出 StateTracker | 6h |
| 4.2 拆出 MemoryReader | 6h |
| 4.3 拆出 CombatRecorder | 3h |
| 4.4 拆出 ActionPredictor | 4h |
| 4.5 拆出 OverlayUI | 4h |
| 4.6 组装 main.py + 配置化 | 6h |
| 验证 + 修 bug | 4h |
| **合计** | **33h (5天)** |

### P4 完成标志

- [ ] `ai_engine.py` 代码量从 328 行降至 < 20 行（仅保留向后兼容的 import）
- [ ] `main.py` 作为新入口，功能与旧 `ai_engine.py` 完全一致
- [ ] `src/core/`, `src/data/`, `src/model/`, `src/ui/` 各有独立模块
- [ ] 所有 P3 测试继续通过
- [ ] 新增模块的单元测试（`tests/test_memory_reader.py` 用 mock，`tests/test_predictor.py` 用 mock 模型）
- [ ] 进游戏实战验证 10 分钟：动作显示、AI 预测、Nova 预警、CSV 录制全正常
- [ ] Git tag: `v0.4.0-architecture-refactor`

---

## P5：模型工程化（4 天）— 工业级完善

> **目标**：模型训练工业化，项目达到 GitHub 发布标准。
> **原则**：增量改进，不破坏现有管线。

### 修改清单

#### Step 5.1：模型版本管理 + 元数据（1 天）

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `src/model/predictor.py` | 支持加载指定版本模型 / 自动加载最新 |
| 新建 | `src/model/trainer.py` | 从 `train_lgbm.py` 重构：版本化输出 + 元数据 |
| 新建 | `src/model/metadata.py` | 模型元数据 dataclass |
| 修改 | `train_lgbm.py` | 改为调用 `src/model/trainer.py`（不重复实现） |
| 新建 | `scripts/train.sh` | 一键训练脚本（Windows: `scripts/train.bat`） |

```python
# src/model/metadata.py
@dataclass
class ModelMetadata:
    version: str              # "20260607_143022"
    accuracy: float           # 0.7234
    top3_accuracy: float      # 0.8912
    features: list[str]       # ['distance', 'relative_angle', ...]
    n_samples: int            # 4521
    n_classes: int            # 47
    hyperparams: dict         # {'num_leaves': 63, ...}
    training_data_hash: str   # SHA256 of ML_Ready_Dataset.csv
    created_at: str           # ISO timestamp
```

#### Step 5.2：增量学习（Tech_debt #7）— 1 天

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `src/model/trainer.py` | 增加 `incremental_train()` 方法 |
| 新建 | `tests/test_incremental.py` | 增量训练不退化测试 |

#### Step 5.3：数据版本管理（Tech_debt #8）— 0.5 天

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `src/data/recorder.py` | CSV header 加 `schema_version` 列 |
| 修改 | `data_cleaner.py` | 按 schema_version 自动选择清洗逻辑 |
| 修改 | `data_upgrade.py` | 支持多版本迁移路径 |

#### Step 5.4：文档与发布（1 天）

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `CONTRIBUTING.md` | 贡献指南 |
| 新建 | `docs/installation.md` | 详细安装说明（含虚拟环境、字体配置） |
| 新建 | `docs/usage.md` | 使用教程（截图 + 说明） |
| 新建 | `docs/model_training.md` | 模型训练指南 |
| 新建 | `docs/memory_reverse_engineering.md` | 内存逆向方法（供社区贡献偏移量更新） |
| 新建 | `LICENSE` | MIT License |
| 完善 | `README.md` | 补徽章 (CI passing, Python version, license) + GIF 演示 |

#### Step 5.5：CI/CD 完善（0.5 天）

| 操作 | 文件 | 说明 |
|------|------|------|
| 新建 | `.github/workflows/lint.yml` | ruff 代码检查 |
| 修改 | `.github/workflows/test.yml` | 添加覆盖率报告 + badge |
| 新建 | `.github/workflows/release.yml` | tag 推送自动创建 GitHub Release |

### 最终项目结构

```
D:\BlackDragon/
├── main.py                     # 主入口
├── ai_engine.py                # 向后兼容 (import main)
├── data_cleaner.py             # 数据清洗 (import src.data)
├── data_upgrade.py             # 数据升级 (import src.data)
├── train_lgbm.py               # 模型训练 (import src.model)
├── enrage.py                   # 内存扫描器
│
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE                     # MIT
├── requirements.txt
├── requirements-dev.txt
├── setup.cfg
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── logging_config.py       # 统一日志
│   ├── config/
│   │   ├── __init__.py
│   │   ├── actions.py          # 动作数据库 (唯一数据源)
│   │   ├── offsets.py          # 内存偏移量
│   │   └── settings.py         # 应用配置 (窗口/路径/阈值)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── memory_reader.py    # 游戏内存读取
│   │   └── state_tracker.py    # 战斗状态机
│   ├── data/
│   │   ├── __init__.py
│   │   ├── recorder.py         # CSV 录制
│   │   ├── cleaner.py          # 数据清洗逻辑
│   │   └── upgrade.py          # 数据升级逻辑
│   ├── model/
│   │   ├── __init__.py
│   │   ├── predictor.py        # AI 推理
│   │   ├── trainer.py          # 模型训练
│   │   └── metadata.py         # 模型元数据
│   └── ui/
│       ├── __init__.py
│       └── overlay.py          # 悬浮窗 UI
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_actions.py         # 动作映射测试
│   ├── test_posture_fsm.py     # 姿态状态机测试
│   ├── test_phase_filter.py    # 物理过滤测试
│   ├── test_nova.py            # Nova 预警测试
│   ├── test_state_tracker.py   # CombatState 测试
│   ├── test_predictor.py       # ActionPredictor mock 测试
│   ├── test_incremental.py     # 增量训练测试
│   └── manual_checklist.md
│
├── scripts/
│   ├── train.bat               # 一键训练
│   └── train.sh
│
├── archive/
│   └── mod.py                  # 旧版悬浮窗
│
├── docs/
│   ├── installation.md
│   ├── usage.md
│   ├── model_training.md
│   ├── memory_reverse_engineering.md
│   ├── offsets_guide.md
│   ├── Project_map.md
│   └── Tech_debt.md
│
├── data/
│   ├── fatalis_combat_data_*.csv
│   └── ML_Ready_Dataset.csv
│
├── models/
│   ├── fatalis_ai_v20260607_143022.pkl
│   ├── fatalis_ai_v20260607_143022.meta.json
│   └── feature_importance.png
│
└── .github/
    └── workflows/
        ├── test.yml
        ├── lint.yml
        └── release.yml
```

### 风险

| 风险 | 等级 | 缓解 |
|------|------|------|
| 增量训练导致模型退化 | 🟡 中 | 写测试对比增量 vs 全量训练的准确率；保留全量训练选项 |
| schema_version 迁移路径不完整 | 🟢 低 | 在 P3 测试中覆盖所有历史数据版本的升级路径 |

### 预计工作量

| 工作项 | 耗时 |
|--------|------|
| 5.1 模型版本管理 | 6h |
| 5.2 增量学习 | 6h |
| 5.3 数据版本管理 | 3h |
| 5.4 文档与发布 | 6h |
| 5.5 CI/CD 完善 | 3h |
| **合计** | **24h (4天)** |

### P5 完成标志

- [ ] 模型训练输出带版本号和元数据 JSON
- [ ] 推理可指定版本或自动加载最佳模型
- [ ] 增量训练可用且准确率不低于全量训练的 95%
- [ ] CSV 含 `schema_version` 列，清洗代码按版本分发
- [ ] README 含 badge、GIF/截图、安装步骤
- [ ] GitHub Actions 三项 workflow 全部绿色
- [ ] CONTRIBUTING.md 和 docs/ 完整
- [ ] `git push` 到 GitHub，创建 v1.0.0 Release
- [ ] Git tag: `v1.0.0-github-release`

---

## 里程碑总表

| Phase | 名称 | 工作日 | 累计 | 关键产物 | Tag |
|-------|------|--------|------|----------|-----|
| P1 | 项目优化 | 2 | 2 | `README.md`, `.gitignore`, `requirements.txt`, 目录结构 | `v0.1.0` |
| P2 | P0 修复 | 3 | 5 | 日志系统, `src/config/actions.py`, `src/config/offsets.py` | `v0.2.0` |
| P3 | 测试体系 | 3 | 8 | 测试套件 (≥60% 覆盖), GitHub Actions CI | `v0.3.0` |
| P4 | 架构重构 | 5 | 13 | `src/core/`, `src/data/`, `src/model/`, `src/ui/`, `main.py` | `v0.4.0` |
| P5 | 模型工程化 | 4 | 17 | 模型版本管理, 增量学习, 完整文档, GitHub Release | `v1.0.0` |

**总预估**：17 个工作日（约 3.5 周），每个阶段产出可运行的项目。

## 投入产出比分析

```
影响 ▲
     │
  高 │              P2 ┌──────────┐
     │        ┌────────┤ 偏移量配置│
     │        │        │ 映射统一 │
     │  P1    │        │ 日志化   │
     │ ┌────┐ │        └──────────┘
     │ │基建│ │
  中 │ └────┘ │              P4 ┌──────────────┐
     │        │           ┌─────┤ God Class 拆解│
     │        │           │     │ 线程安全      │
     │        │           │     └──────────────┘
  低 │        │   P3      │             P5 ┌──────────────┐
     │        │  ┌──────┐ │        ┌───────┤ 模型版本管理  │
     │        │  │测试  │ │        │       │ 增量学习      │
     │        │  │体系  │ │        │       │ 文档/GitHub   │
     │        │  └──────┘ │        │       └──────────────┘
     └────────┴───────────┴────────┴─────────────────────────→ 时间
           1周          2周              3周             4周
```

P1-P2 是**基础设施投资**，成本低、收益立即可见。
P3 是**安全网建设**，为 P4 大规模重构提供信心。
P4 是**架构升级**，收益最高但依赖 P3 的测试保护。
P5 是**最后一公里**，让项目具备外部可用性。
