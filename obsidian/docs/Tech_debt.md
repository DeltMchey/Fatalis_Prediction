# BlackDragon 技术债清单

> 最后更新：2026-06-07

---

## 目录

1. [评估维度说明](#评估维度说明)
2. [🔴 高风险 (4项)](#-高风险)
3. [🟡 中风险 (5项)](#-中风险)
4. [🟢 低风险 (5项)](#-低风险)
5. [修复路线图](#修复路线图)

---

## 评估维度说明

| 维度 | 定义 | 等级 |
|------|------|------|
| **严重程度** | 对系统正确性/稳定性/安全性的影响 | 🔴高 🟡中 🟢低 |
| **修复收益** | 修复后带来的价值（可维护性提升、bug 减少、扩展性增强） | ★★★ 重大 ★★ 显著 ★ 有限 |
| **修复成本** | 预估工作量（人时） | 💰💰💰 高(>8h) 💰💰 中(3-8h) 💰 低(<3h) |
| **优先级** | 综合排序：P0 > P1 > P2 > P3 | P0 立即 / P1 短期 / P2 中期 / P3 长期 |

---

## 🔴 高风险

### #1 魔法数字硬编码 — 内存偏移量散落各处

| 属性 | 内容 |
|------|------|
| **位置** | `ai_engine.py` L67, L83-98, L110-144, L209-248 等；`enrage.py` L41；`mod.py` L67-86 |
| **严重程度** | 🔴 高 |
| **修复收益** | ★★★ 重大 — 游戏更新时只需改一处配置文件 |
| **修复成本** | 💰💰 中 (4-6h) |
| **优先级** | **P0** |

#### 问题描述

所有内存偏移量以魔法数字形式硬编码在源码中：

```python
# ai_engine.py 中的典型硬编码:
ptr = get_ptr(pm, base, [0x698, i * 0x8, 0x138, 0])      # 怪物实例链
hp = pm.read_longlong(ptr + 0x7670)                        # HP 指针偏移
action_id = pm.read_int(monster + 0x6278)                  # 动作 ID 偏移
enrage_timer = self.pm.read_float(monster + 0x1BE30 + 0x24) # 发怒秒表

PLAYER, MONSTER, ZONE = base + 0x050139A0, base + 0x051238C8, base + 0x0500ECA0
```

**影响**：游戏每次版本更新（即使是小补丁），基址和偏移量可能全部失效，需要手动在 3 个文件中逐一查找替换。

#### 修复方案

```python
# src/config/offsets.py (新文件)
from dataclasses import dataclass

@dataclass(frozen=True)
class GameOffsets:
    # 基址
    PLAYER_BASE:  int = 0x050139A0
    MONSTER_BASE: int = 0x051238C8
    ZONE_BASE:    int = 0x0500ECA0

    # 怪物实例链
    MONSTER_LIST:       list = (0x698, 0x8, 0x138, 0)
    MONSTER_HP_OFFSET:  int = 0x7670
    HP_MAX_OFFSET:      int = 0x60
    HP_CURRENT_OFFSET:  int = 0x64

    # 怪物数据
    MONSTER_COORDS:     int = 0x160
    MONSTER_QUAT:      int = 0x170
    MONSTER_ACTION_ID:  int = 0x6278

    # 发怒结构
    ENRAGE_STRUCT:      int = 0x1BE30
    ENRAGE_TIMER:       int = 0x24
    ENRAGE_MAX:         int = 0x28

    # 玩家数据
    PLAYER_CHAIN:       list = (0x50, 0xC0, 0x670)

    # 区域
    ZONE_OFFSET:        list = (0xAED0,)
    ZONE_TARGET:        int = 417   # 虚黑城
```

---

### #2 ACTION_MAPPING 三处重复定义

| 属性 | 内容 |
|------|------|
| **位置** | `ai_engine.py:48-60`, `data_cleaner.py:15-45`, `mod.py:60-175`（隐式） |
| **严重程度** | 🔴 高 |
| **修复收益** | ★★★ 重大 — 消除数据不一致 bug，修改只需一处 |
| **修复成本** | 💰💰 中 (3-5h) |
| **优先级** | **P0** |

#### 问题描述

动作合并映射字典在三个文件中各自维护，已出现细微差异：

```python
# data_cleaner.py 有，但 ai_engine.py 缺失的映射:
57: 53,    # 连咬第5帧 (ai_engine.py 的 ACTION_MAPPING 没有 57)
80: 79,    # 大咬第2帧
119: 129,  # 蓄力火 趴→立

# ai_engine.py 有，但 data_cleaner.py 缺失的:
34: 33,    # 拍地
36: 35,    # 扫地
```

**影响**：
- 训练数据使用了一种映射，推理时使用了另一种映射 → 模型学到的招式分布与运行时不一致 → 预测精度下降
- 新增动作映射需要人工同步三处

#### 修复方案

```python
# src/config/actions.py (唯一数据源)
"""动作数据库 — 项目中唯一的数据源"""

# 动作 ID → 名称
ACTION_DB: dict[int, str] = {
    306: "等待", 307: "等待", 308: "等待",
    # ... 完整映射
}

# 动作合并映射 (动画帧 → 起手帧 Base ID)
ACTION_MAPPING: dict[int, int] = {
    # 龙车
    38: 37, 39: 37, 40: 37,
    50: 49, 51: 49, 52: 49,
    # 连咬
    54: 53, 55: 53, 56: 53, 57: 53,
    69: 68, 70: 68, 71: 68, 72: 68,
    # ... 完整且唯一的映射
}

# 阶段专属招式
P1_ONLY_IDS:  set[int] = {37, 38, 39, 40, 53, 54, 55, 56, 146, 147, 148, 137}
P2_PLUS_IDS:  set[int] = {129, 119, 121, 122, 138, 49, 50, 51, 52, 68, 69, 70, 71, 72, 149, 150, 151, 81, 82, 83}
P3_ONLY_IDS:  set[int] = {100, 101, 98, 99, 155, 156, 134, 208, 209, 210, 214, 211, 213, 215, 212, 216}

# ... 其他分类集合
```

所有模块统一 `from src.config.actions import ACTION_MAPPING`

---

### #3 静默异常吞噬 — 无日志的数据丢失和 UI 故障

| 属性 | 内容 |
|------|------|
| **位置** | `ai_engine.py:146-147`, `ai_engine.py:309-310`；`mod.py:236`, `mod.py:200-202` |
| **严重程度** | 🔴 高 |
| **修复收益** | ★★★ 重大 — 可观测性从 0 到 1，能发现隐藏 bug |
| **修复成本** | 💰 低 (1-2h) |
| **优先级** | **P0** |

#### 问题描述

```python
# ai_engine.py:146-147 — 录制线程
except:
    pass    # 任何异常静默丢弃！录制中断无感知

# ai_engine.py:309-310 — UI 刷新循环
except:
    pass    # 渲染异常静默！预测失败无提示
```

**影响**：
- 录制线程崩溃 → 整场战斗数据丢失 → 用户毫无察觉
- 模型推理异常 → 预测区空白 → 用户以为 AI 坏了，难以排查
- 无法收集线上错误，改进依赖"偶然看到"

#### 修复方案

```python
import logging
import traceback

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('blackdragon.log', encoding='utf-8'),
        logging.StreamHandler()  # 可选：控制台同时输出
    ]
)
logger = logging.getLogger(__name__)

# 替换 except: pass
except Exception:
    logger.warning(f"录制线程异常:\n{traceback.format_exc()}")

except Exception:
    logger.error(f"UI 刷新异常:\n{traceback.format_exc()}")
```

---

### #4 God Class — ai_engine.py 承担 5 种职责

| 属性 | 内容 |
|------|------|
| **位置** | `ai_engine.py` 全文件，尤其是 `Ultimate_Radar_UI` 类 |
| **严重程度** | 🔴 高 (架构级) |
| **修复收益** | ★★★ 重大 — 可测试性、可维护性飞跃 |
| **修复成本** | 💰💰💰 高 (8-12h) |
| **优先级** | **P1** |

#### 问题描述

`ai_engine.py` (328 行) 和 `Ultimate_Radar_UI` 类同时承担：

| 职责 | 行范围 | 说明 |
|------|--------|------|
| 内存读取 | L81-99, L209-211 | `get_ptr()`, `find_monster()` |
| 状态机 | L218-258, L282-293 | phase/posture/enrage/nova |
| CSV 录制 | L102-148 | `data_logger_thread()` |
| AI 推理 | L268-305 | `predict_proba()` + 物理过滤 |
| UI 渲染 | L161-186, L260-310 | dearpygui 窗口 + 文本更新 |

**影响**：
- 无法对任何单一职责写单元测试
- 修改任一职责有牵一发动全身的风险
- 新人理解代码需要通读 328 行
- 无法复用：换个 UI 框架需要重写整个文件

#### 修复方案

```
src/
├── core/
│   ├── memory_reader.py    # MemoryReader 类：封装所有 pymem 操作
│   └── state_tracker.py    # StateTracker 类：phase/posture/enrage/nova
├── data/
│   └── recorder.py          # CombatRecorder 类：CSV 录制
├── model/
│   └── predictor.py         # ActionPredictor 类：加载模型 + 推理 + 过滤
├── ui/
│   └── overlay.py           # OverlayUI 类：dearpygui 窗口管理
└── main.py                  # 组装各模块，启动线程和 UI 循环
```

---

## 🟡 中风险

### #5 全局可变状态 — 多线程无保护

| 属性 | 内容 |
|------|------|
| **位置** | `ai_engine.py:72-78` |
| **严重程度** | 🟡 中 |
| **修复收益** | ★★ 显著 — 消除潜在竞态条件，数据一致性保证 |
| **修复成本** | 💰 低 (1-2h) |
| **优先级** | **P1** |

#### 问题描述

```python
shared_state = {
    'action_id': -1, 'posture': 1, 'phase': 1, 'is_enraged': 0,
    'is_recording': True, 'nova_warning': False, 'hp_initialized': False,
    'triggered_novas': set()
}
lock = threading.Lock()
action_buffer = deque(maxlen=100)
```

- `action_buffer` 有 `lock` 保护（仅在 `data_logger_thread` 写入和 `update_logic` 读取时）
- 但 `shared_state` 的读写**没有任何锁保护**
- 录制线程写入 `shared_state['phase']`，UI 线程同时读写 `shared_state['phase']`
- Python GIL 使得 dict 赋值本身不会崩溃，但逻辑一致性无法保证（读到中间状态的 phase+posture 组合）

#### 修复方案

```python
import threading
from contextlib import contextmanager

class CombatState:
    """线程安全的战斗状态容器"""

    def __init__(self):
        self._lock = threading.RLock()
        self._action_id = -1
        self._posture = 1
        self._phase = 1
        self._is_enraged = 0
        self._is_recording = True
        self._nova_warning = False
        self._hp_initialized = False
        self._triggered_novas: set[float] = set()

    @contextmanager
    def atomic(self):
        """获取原子操作上下文"""
        with self._lock:
            yield self

    # 属性访问器带锁
    @property
    def phase(self): return self._phase
    @phase.setter
    def phase(self, val):
        with self._lock: self._phase = val
    # ... 其余属性同理
```

---

### #6 无模型版本管理

| 属性 | 内容 |
|------|------|
| **位置** | `ai_engine.py:156`；`train_lgbm.py:64` |
| **严重程度** | 🟡 中 |
| **修复收益** | ★★ 显著 — 支持模型回滚、A/B 对比、版本追溯 |
| **修复成本** | 💰 低 (1-2h) |
| **优先级** | **P1** |

#### 问题描述

```python
# 训练：固定文件名
joblib.dump(model, "fatalis_ai_model.pkl")

# 推理：固定文件名
self.ai_model = joblib.load("fatalis_ai_model.pkl")
```

- 每次训练覆盖旧模型 → 无法回滚
- 不知道当前模型用哪批数据、什么时间训练的
- 无法 A/B 对比新旧模型效果

#### 修复方案

```python
# 训练时
from datetime import datetime
import json

version = datetime.now().strftime("%Y%m%d_%H%M%S")
model_name = f"fatalis_ai_v{version}.pkl"
joblib.dump(model, f"models/{model_name}")

# 同时保存元数据
metadata = {
    "version": version,
    "accuracy": accuracy_score(y_test, y_pred),
    "top3_accuracy": top3_accuracy,
    "features": feature_cols,
    "n_samples": len(df),
    "hyperparams": {"num_leaves": 63, "max_depth": 7, ...}
}
with open(f"models/{model_name}.meta.json", "w") as f:
    json.dump(metadata, f, indent=2)

# 推理时
import os, json
models_dir = "models"
latest = sorted(os.listdir(models_dir))[-1] if os.listdir(models_dir) else None
```

---

### #7 无增量学习能力

| 属性 | 内容 |
|------|------|
| **位置** | `train_lgbm.py` |
| **严重程度** | 🟡 中 |
| **修复收益** | ★★ 显著 — 积累数据越多模型越好，训练时间不线性增长 |
| **修复成本** | 💰💰 中 (3-4h) |
| **优先级** | **P2** |

#### 问题描述

每次训练从零开始加载全部历史数据重新训练。随着录制文件越来越多：
- 训练时间线性增长
- 无法利用已有模型权重

LightGBM 原生支持 `init_model` 参数实现增量训练：

```python
# 首次训练
model.fit(X_train, y_train, ...)
joblib.dump(model, "models/fatalis_base.pkl")

# 增量训练（有新数据时）
old_model = joblib.load("models/fatalis_base.pkl")
model.fit(
    X_new, y_new,
    init_model=old_model,  # ← 关键：从旧模型继续
    n_estimators=50,        # 只加少量树
    ...
)
```

---

### #8 数据格式无版本标识

| 属性 | 内容 |
|------|------|
| **位置** | 所有 CSV 文件 |
| **严重程度** | 🟡 中 |
| **修复收益** | ★★ 显著 — 消除数据兼容性猜测，自动化升级/降级 |
| **修复成本** | 💰 低 (1-2h) |
| **优先级** | **P2** |

#### 问题描述

原始 CSV 和清洗后的 CSV 都没有 schema version 标识。`data_upgrade.py` 通过试探列名判断是否是旧格式：

```python
if 'phase' in df.columns and 'is_enraged' in df.columns:
    continue  # 猜测是新版本
```

随着字段增加（如未来可能增加 `player_weapon`, `party_size`），版本兼容性将成为噩梦。

#### 修复方案

```python
# CSV 第一行增加 header 注释（或使用单独的 schema 文件）
# 或使用 Parquet 格式（自带 schema）

# 方案 A：增加 schema_version 列
SCHEMA_VERSION = "3.0"

# 录制时
csv.writer(f).writerow([...])  # 新的一列在最前：schema_version

# 加载时
df = pd.read_csv(file)
if 'schema_version' not in df.columns:
    # V1/V2 旧数据 → 需要升级
    ...
```

---

### #9 缺少特征重要性分析和模型解释

| 属性 | 内容 |
|------|------|
| **位置** | `train_lgbm.py:67-78` |
| **严重程度** | 🟡 中 |
| **修复收益** | ★ 有限 — 帮助理解模型，但不是功能必须 |
| **修复成本** | 💰 低 (1-2h) |
| **优先级** | **P2** |

#### 问题描述

当前只输出特征重要性条形图，但：
- 未分析每个招式最重要的特征是什么（如龙车主要看距离，火球主要看角度）
- 未评估特征间的交互效应
- 未尝试特征消融（去掉某个特征看看准确率下降多少）

#### 修复方案

```python
# 按招式分析 Top 重要特征
for action_id in top_actions:
    subset = X_test[y_test == action_id]
    shap_values = explainer(subset)
    ...

# 特征消融实验
for feature in feature_cols:
    X_reduced = X.drop(columns=[feature])
    acc = train_and_evaluate(X_reduced, y)
    print(f"Without {feature}: accuracy drops by {baseline_acc - acc:.2f}%")
```

---

## 🟢 低风险

### #10 mod.py 废弃代码残留

| 属性 | 内容 |
|------|------|
| **位置** | `mod.py` 全文件 (248 行) |
| **严重程度** | 🟢 低 |
| **修复收益** | ★ 有限 — 减少混淆，降低新人学习成本 |
| **修复成本** | 💰 低 (<1h) |
| **优先级** | **P3** |

`mod.py` 是 `ai_engine.py` 的前身，功能已被完全覆盖（无 AI、无录制、无发怒检测）。保留仅用于历史参考。建议移到 `archive/` 目录或添加明确的废弃注释。

---

### #11 中文/Emoji 混合注释

| 属性 | 内容 |
|------|------|
| **位置** | 全项目 |
| **严重程度** | 🟢 低 |
| **修复收益** | ★ 有限 — 提高国际化可读性 |
| **修复成本** | 💰💰 中 (2-3h) |
| **优先级** | **P3** |

代码中混用中文注释、英文变量名、Emoji 前缀（🌟、✅、⚠️）。对于中文开发者无障碍，但不规范。建议逐步统一为英文注释（变量名已经是英文）。

---

### #12 零单元测试

| 属性 | 内容 |
|------|------|
| **位置** | 全项目 |
| **严重程度** | 🟢 低（当前规模小） |
| **修复收益** | ★★ 显著 — 重构安全网，减少回归 bug |
| **修复成本** | 💰💰💰 高 (>8h，随重构逐步补充) |
| **优先级** | **P3** |

当前零测试。好消息是核心逻辑（状态机、动作映射、物理过滤）是纯函数/数据结构操作，无需游戏环境即可测试。建议在 P0/P1 重构过程中同步补测试。

```python
# 可无游戏环境测试的核心逻辑:
def test_action_mapping():
    assert ACTION_MAPPING.get(38) == 37  # 龙车帧映射
    assert ACTION_MAPPING.get(54) == 53  # 连咬帧映射
    assert 57 not in ACTION_MAPPING or ACTION_MAPPING[57] == 53

def test_posture_fsm():
    tracker = PostureStateMachine()
    tracker.update(115)  # 俯冲 → 站立
    assert tracker.posture == 1
    tracker.update(138)  # 孕吐 → 趴下
    assert tracker.posture == 0

def test_phase_filter():
    probs = np.ones(100) / 100
    filtered = apply_phase_filter(probs, phase=2, classes=np.arange(100))
    assert filtered[37] == 0.0  # P1 龙车在 P2 概率应为 0
    assert filtered[137] == 0.0  # P1 孕吐在 P2 概率应为 0
```

---

### #13 录制的 CSV 无压缩

| 属性 | 内容 |
|------|------|
| **位置** | `ai_engine.py:102-148` |
| **严重程度** | 🟢 低 |
| **修复收益** | ★ 有限 — 节省磁盘空间 |
| **修复成本** | 💰 低 (<1h) |
| **优先级** | **P3** |

当前 17 个 CSV 约 11MB，长期录制会线性增长。建议：录制时直接写入 gzip 压缩 CSV，或定期归档为 Parquet 格式。

---

### #14 悬浮窗参数硬编码

| 属性 | 内容 |
|------|------|
| **位置** | `ai_engine.py:171-172, 185-186` |
| **严重程度** | 🟢 低 |
| **修复收益** | ★ 有限 — 用户可自定义窗口属性 |
| **修复成本** | 💰 低 (<1h) |
| **优先级** | **P3** |

窗口大小 (420×350)、位置（右上角偏移 440）、透明度、字体路径均硬编码。建议提为配置文件，支持用户自定义。

---

## 修复路线图

```
Phase 1: P0 紧急 (1-2 天)
─────────────────────────
□ #3  异常日志化 ──────── 立即修复，成本最低收益最大
□ #1  偏移量配置化 ────── 创建 offsets.py
□ #2  ACTION_MAPPING 统一 创建 actions.py 唯一数据源

Phase 2: P1 短期 (3-5 天)
─────────────────────────
□ #4  God Class 拆解 ──── 拆为 MemoryReader / StateTracker / Predictor / OverlayUI
□ #5  线程安全改造 ────── CombatState 类 + RLock
□ #6  模型版本管理 ────── 文件名 + metadata.json

Phase 3: P2 中期 (1-2 周)
─────────────────────────
□ #7  增量学习 ────────── LightGBM init_model
□ #8  数据版本标识 ────── CSV schema version
□ #9  特征分析深化 ────── SHAP + 消融实验

Phase 4: P3 长期 (持续)
─────────────────────────
□ #10 清理 mod.py
□ #11 注释规范化
□ #12 补充单元测试
□ #13 CSV 压缩
□ #14 UI 参数配置化
```

### 投入产出比最高的 3 项

| 排名 | 编号 | 问题 | 成本 | 收益 | 理由 |
|------|------|------|------|------|------|
| 🥇 | #3 | 异常日志化 | 1-2h | ★★★ | 成本极低，立即暴露所有隐藏 bug |
| 🥈 | #2 | ACTION_MAPPING 统一 | 3-5h | ★★★ | 消除数据不一致 bug，直接影响模型精度 |
| 🥉 | #1 | 偏移量配置化 | 4-6h | ★★★ | 游戏更新时 5 分钟修复 vs 逐行查找 |
