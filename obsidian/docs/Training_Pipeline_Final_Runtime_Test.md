# Training Pipeline Final Runtime Test

- **Date**: 2026-08-05
- **Agent**: runner
- **Scope**: v1.1.2 train_lgbm robustness fixes 回归验证（unit / dev / frozen）
- **Git**: `cfacada` + uncommitted v1.1.x changes

---

## 1. 测试环境

| 项目 | 值 |
|------|-----|
| OS | Windows (win32) |
| Python | 3.12.6 (venv) |
| pandas / lightgbm / sklearn / joblib | 3.0.2 / 4.6.0 / 1.8.0 / 1.5.3 |
| 项目根 data/ | **19** 个原始战斗 CSV |
| dist/BlackDragon/data/ | **20** 个原始战斗 CSV（含新 20260804_220153.csv 2.1MB） |
| dist/BlackDragon/BlackDragon.exe | 构建于 **2026-08-05 09:26**（**v1.1.2 修复前**） |

> **关键环境说明**: frozen EXE 构建时间早于 v1.1.2 源码修复。因此 frozen 测试实际执行的是**旧 train_lgbm 逻辑**——这对验证"是否需重建 EXE"至关重要。

---

## 2. Unit Test (pytest)

```
pytest tests/ -q   →   581 passed in 11.92s
```

| 指标 | 值 |
|------|-----|
| 收集 | 581 |
| 通过 | 581 |
| 失败 | 0 |
| 通过率 | 100% |

**结论: ✅ PASS** — v1.1.2 新增防御逻辑（stratify 降级 / NaN warning / 非数值 label）未破坏任何现有测试。

---

## 3. Development Pipeline (`python launch.py --pipeline`)

**命令**: `.venv\Scripts\python.exe -X utf8 launch.py --pipeline`
**退出码**: 0

### 阶段验证

| 阶段 | 结果 | 证据 |
|------|:---:|------|
| data_cleaner 运行 | ✅ | 处理 19 个 CSV → 提纯完成 |
| unknown action warning | ✅ 无触发 | 19 个根目录 CSV 无未知 action（无 "未知动作" 输出） |
| NaN / 非数值 warning | ✅ 无触发 | 数据干净 |
| Dataset too small | ✅ 无触发 | 2444 样本 / 51 类，远超阈值 |
| ML_Ready_Dataset.csv 生成 | ✅ | 88,708 B，2444 行 |
| train_lgbm 成功 | ✅ | Accuracy 27.05% |
| fatalis_ai_model.pkl 更新 | ✅ | 19,976,868 B（10:07:24） |
| .bak 文件生成 | ✅ | dataset.bak 90,511 B + model.bak 19,033,772 B |

### 记录指标

| 指标 | 值 |
|------|-----|
| 原始 CSV 数 | 19 |
| unknown action 数 | 0 |
| 清洗后样本数 | 2444 |
| 类别数 | 51 |
| Accuracy | **27.05%** |
| Top-3 | **60.25%** |
| 模型文件 | 19,976,868 B（46 classes） |

**结论: ✅ PASS** — 开发模式 pipeline 完整运行，防御逻辑正常（本次数据无触发项，未降级）。

---

## 4. Frozen Pipeline (`dist/BlackDragon/BlackDragon.exe --pipeline`)

**命令**: `Start-Process BlackDragon.exe -ArgumentList "--pipeline" -Wait -RedirectStandardOutput/Error`
**退出码**: **1（失败）**

### 阶段验证

| 检查项 | 结果 | 证据 |
|--------|:---:|------|
| 进入 pipeline mode | ✅ | 日志显示 cleaner 处理 20 CSV |
| 不启动 Dashboard | ✅ | 运行期间无 BlackDragon 窗口进程（0 个） |
| 不启动 Overlay | ✅ | 无 BlackDragonOverlay 进程 |
| hidden import 错误 | ✅ 无 | data_cleaner 正常从 PYZ 加载 |
| **train_lgbm 成功** | ❌ **失败** | 见下方错误 |

### 错误详情

```
Traceback (most recent call last):
  File "launch.py", line 58, in main
  File "train_lgbm.py", line 59, in train_fatalis_ai
  File "lightgbm\sklearn.py", line 1558, in fit
  File "sklearn\preprocessing\_label.py", line 144, in transform
  File "sklearn\utils\_encode.py", line 236, in _encode
ValueError: y contains previously unseen labels: [np.int64(117)]
```

### 原因分析

| 项 | 值 |
|----|-----|
| 根因 | **frozen EXE 是 v1.1.2 修复前的旧构建**（09:26） |
| 数据 | dist/data/ 20 个 CSV（含 117 未知动作） |
| 旧代码行为 | 无 unknown-label 过滤 + 无 stratify → 触发原始 bug |
| 旧模型保护 | ✅ 未覆盖——训练崩溃在保存前，旧 model.pkl 保持 7,880,916 B（可加载，44 classes） |
| cleaner 备份 | ✅ ML_Ready_Dataset.csv.bak 生成（cleaner 先运行，不受 train 崩溃影响） |

**结论: ❌ FAIL（预期）** — 旧 EXE 仍带原始 bug，**必须重建 EXE 才能让 frozen pipeline 使用修复后的 train_lgbm**。

---

## 5. 总结

| 测试 | 结果 | 说明 |
|------|:---:|------|
| Unit (581 tests) | ✅ PASS | 修复未破坏任何测试 |
| Dev pipeline | ✅ PASS | 完整运行，2444 样本 / 51 类 / Acc 27.05% / Top-3 60.25% |
| Frozen pipeline | ❌ FAIL | **旧 EXE 含原始 bug（unseen label 117）** |

### 是否需要重新 build exe？

**✅ 是——必须重建。**

- 当前 `dist/BlackDragon/BlackDragon.exe` 构建于 09:26，**不含** v1.1.1/v1.1.2 修复（unknown-label 过滤、stratify 降级、NaN/非数值处理）
- 重建后 frozen pipeline 才能正确过滤 action 117 等未知动作
- 重建命令: `.\scripts\build_exe.ps1 -Clean`

### 建议下一步

1. **重建 EXE** → 重新运行 frozen pipeline 验证（预期 PASS）
2. 重建后验证：`BlackDragon.exe --pipeline` 应输出 `⚠️ 检测到未知动作 label: [117]` 并完成训练
3. 若 117 是合法游戏动作，建议补充 `src/config/actions.py`（需领域知识）——当前过滤为安全默认

---

## runner 签名

- **结论**: Unit + Dev PASS；**Frozen FAIL（旧 EXE，需重建）**
- **建议下一步**: 重建 EXE → 复测 frozen pipeline → 确认 117 语义（补 ACTION_DB 或保持过滤）
