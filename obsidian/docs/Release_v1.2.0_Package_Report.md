# Release Package Report — BlackDragon v1.2.0

- **Date**: 2026-09-16 16:42
- **Scope**: v1.2.0 release packaging — clean build → selftest gate → package → verify → SHA256
- **Predecessor**: `Release_v1.1.0_Package_Report.md`（格式与流程参照）

> **修订（2026-09-16，用户裁决）**：发行包 `data/` 不再附带 19 个原始战斗 CSV，只保留清洗后的 `ML_Ready_Dataset.csv`（`build_exe.ps1` 原 5e 步打包逻辑移除，commit 见 `fa6545e` 的反转）。本文档内容清单与 SHA256 已按重新打包后的发行物更新；取舍（放弃"数据集从零重建"，重训安全由 F1 合并语义保障）详见 `ADR-P6.1` F2 决策 Addendum。

---

## 1. 环境与版本

| 项目 | 值 |
|------|-----|
| Git HEAD（构建时） | `cb71d91`（docs(memory-bank): update six files for v1.2.0 closure；分支 `feature/automl-experiment`） |
| Git status | 文档变更已全部提交；`release/`、`dist/`、`models/*.pkl` 均 gitignored |
| Python | 3.12.6 (venv) |
| PyInstaller | 6.21.0 |
| 测试基线 | **766 passed**（构建门禁内置全量 pytest，91.1s；修订重打包门禁为 767 项，含发行包形态边界测试，exit 0） |

## 2. 打包流程

### 2.1 清理 + 重建（`scripts/build_exe.ps1 -Clean`，BUILD_EXIT=0）

| 步骤 | 结果 |
|------|:---:|
| [2/7] pytest 全量 766 passed | ✅ |
| [3/7] 清理旧 build/dist | ✅ |
| [4/7] BlackDragon.exe（Dashboard，含 xgboost 运行时 + production_backend + backup_chain hiddenimports） | ✅ |
| [5/7] BlackDragonOverlay.exe（含 sklearn.pipeline 动态引用） | ✅ |
| [6/7] 合并 + surface：数据集 / 运行时模型 / **factory_model.pkl（缺失即构建失败）**（修订：原始 CSV 不再随包） | ✅ |
| [7/7] 双 EXE `--selftest` 硬门禁：Dashboard @项目根 exit 0；**Overlay @TEMP exit 0**（frozen 路径解析 CWD 无关验证） | ✅ |

### 2.2 组装发布包

```
release/Fatalis-Prediction-v1.2.0-windows/    ← 组装目录（staging，1480 个文件；修订：不含原始 CSV）
release/Fatalis-Prediction-v1.2.0-windows.zip ← 压缩包（正式发行物）
```

组装 = `dist/BlackDragon/*` + `LICENSE` + `README.txt`（v1.2.0 正式版：模型指标对比、一键训练语义、摘要行/告警、三层回滚、--selftest）+ `models/fatalis_ai_model.pkl.meta.json`（sidecar：采信来源 / sha / 门槛 / 回滚程序；包内模型 sha 与 sidecar `model_sha256` 一致）。

> 注：sidecar 为组装步骤手工补入（spec datas 未收集 meta.json，v3 预览包同样如此；已列入 follow-up 建议）。selftest 冒烟在 zip 封口后执行，包内无运行残留（`blackdragon.log` 已确认不在 zip 内）。

## 3. Zip 验证

| 检查项 | 结果 | 证据 |
|--------|:---:|------|
| `BlackDragon.exe` | ✅ | 21,688,800 B → 修订重打包后见第 4 节新 sha |
| `BlackDragonOverlay.exe` | ✅ | 21,643,103 B → 修订重打包后见第 4 节新 sha |
| `_internal/`（含 xgboost.dll + VERSION） | ✅ | 1480 个文件总计（zip 条目 1509，含目录） |
| `data/ML_Ready_Dataset.csv` | ✅ | 186,483 B（sha `3e5ed34d…295fda6c`，与实验口径一致） |
| `models/fatalis_ai_model.pkl` | ✅ | 7,824,436 B（sha `ed3db5f8…ce65b5f` = 采纳物，与仓库生产模型逐位一致） |
| `models/factory_model.pkl` | ✅ | 7,824,436 B（sha 同上——出厂即 Run B） |
| `models/fatalis_ai_model.pkl.meta.json` | ✅ | 2,095 B |
| `LICENSE` / `README.txt` | ✅ | 1,068 B / 5,646 B |

（修订：原清单中 `data/fatalis_combat_data_*.csv` ×19 一项已随 2026-09-16 用户裁决移除——发行包只附带清洗数据集，见文首修订说明。）

### 包内 EXE selftest 冒烟（发行包本体，非 dist）

```
release/Fatalis-Prediction-v1.2.0-windows/BlackDragon.exe        --selftest  → exit 0
release/Fatalis-Prediction-v1.2.0-windows/BlackDragonOverlay.exe --selftest  → exit 0 (CWD=TEMP)
```

## 4. G6 与 SHA256

| 项 | 值 |
|----|-----|
| **G6 包体积门槛（≤300MB）** | **PASS** — 修订重打包后 164,214,645 B = **156.6 MiB**（初版 159.1 MiB，减 19 个原始 CSV 后 -2.5 MiB；v1.1.0 125.7MB） |
| zip SHA256 | `fab5b5de2d65867e1aa97c25464a5910111690af783014287147aa89fe213a82`（修订重打包） |
| `BlackDragon.exe` | `4f4386dd270a44e66e8235474213546db27e3dab07292383a749353528433f42`（PyInstaller 非逐字节确定，重建后变化属预期） |
| `BlackDragonOverlay.exe` | `e472f8d574a469604c3127fe072bd7855e6801c20b394dd2ad44a060673e2bc3`（同上） |
| `models/fatalis_ai_model.pkl`（包内） | `ed3db5f81f9720cda3f6a07bd314cc95fa60413e9c434d438f65387f0ce65b5f` |
| `models/factory_model.pkl`（包内） | `ed3db5f81f9720cda3f6a07bd314cc95fa60413e9c434d438f65387f0ce65b5f` |
| `data/ML_Ready_Dataset.csv`（包内） | `3e5ed34d9a2e77b38e686044b166f4cdc4d2e0ec852085d03bace09e295fda6c` |

**红线复核（仓库 `models/`，构建前后一致）**：`fatalis_ai_model.pkl` = `ed3db5f8…ce65b5f` ✅；`.bak` = `4d2344cf…84ef3e` ✅；`factory_model.pkl` = `ed3db5f8…ce65b5f` ✅（全程零触碰）。

## 5. 已知注意事项

| # | 事项 | 说明 |
|---|------|------|
| 1 | Zip 路径分隔符为 `\` | PowerShell 5.1 `Compress-Archive` 惯例，与 v1.0.0/v1.1.0 一致。Windows Explorer 解压正常；跨平台解压工具需注意。非阻塞。 |
| 2 | sidecar 未进 spec datas | `fatalis_ai_model.pkl.meta.json` 为组装步骤手工补入；spec 未收集（v3 预览包同样）。follow-up：spec datas + build 脚本 surface 自动化。 |
| 3 | `release/` 目录已 gitignore | zip 与 staging 不入版本控制。 |
| 4 | 干净机器（无 Python）冒烟 | 本机无法模拟；包内双 EXE selftest exit 0 已覆盖"frozen import 链 + 模型加载 + 推理"路径，用户实测第一步建议跑 `--selftest`。 |

## 6. 结论

| 验证项 | 结果 |
|--------|:---:|
| 清理重建（766 tests 门禁） | ✅ |
| 双 EXE selftest 构建门禁（含 Overlay @TEMP） | ✅ |
| 发布包组装（1480 文件，含 factory model + sidecar；修订：不含原始 CSV） | ✅ |
| zip 创建 156.6 MiB（G6 ≤300MB） | ✅ PASS |
| 包内双 EXE selftest | ✅ exit 0 / exit 0 |
| SHA256 清单 + 红线 sha 复核 | ✅ 全部一致 |

**结论: PASS** — `Fatalis-Prediction-v1.2.0-windows.zip` 满足发布要求。

**建议下一步**（均待用户裁决，本轮不执行）:
1. `git push origin main` + `git tag -a v1.2.0`
2. 上传 zip 到 GitHub Release（附 SHA256）
3. 用户进游戏长线实测（对照离线指标 top3_filtered 65.37%）
