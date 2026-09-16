# Release Package Report — BlackDragon v1.2.0

- **Date**: 2026-09-16 16:42
- **Scope**: v1.2.0 release packaging — clean build → selftest gate → package → verify → SHA256
- **Predecessor**: `Release_v1.1.0_Package_Report.md`（格式与流程参照）

---

## 1. 环境与版本

| 项目 | 值 |
|------|-----|
| Git HEAD（构建时） | `cb71d91`（docs(memory-bank): update six files for v1.2.0 closure；分支 `feature/automl-experiment`） |
| Git status | 文档变更已全部提交；`release/`、`dist/`、`models/*.pkl` 均 gitignored |
| Python | 3.12.6 (venv) |
| PyInstaller | 6.21.0 |
| 测试基线 | **766 passed**（构建门禁内置全量 pytest，91.1s） |

## 2. 打包流程

### 2.1 清理 + 重建（`scripts/build_exe.ps1 -Clean`，BUILD_EXIT=0）

| 步骤 | 结果 |
|------|:---:|
| [2/7] pytest 全量 766 passed | ✅ |
| [3/7] 清理旧 build/dist | ✅ |
| [4/7] BlackDragon.exe（Dashboard，含 xgboost 运行时 + production_backend + backup_chain hiddenimports） | ✅ |
| [5/7] BlackDragonOverlay.exe（含 sklearn.pipeline 动态引用） | ✅ |
| [6/7] 合并 + surface：数据集 / 19 个原始战斗 CSV / 运行时模型 / **factory_model.pkl（缺失即构建失败）** | ✅ |
| [7/7] 双 EXE `--selftest` 硬门禁：Dashboard @项目根 exit 0；**Overlay @TEMP exit 0**（frozen 路径解析 CWD 无关验证） | ✅ |

### 2.2 组装发布包

```
release/Fatalis-Prediction-v1.2.0-windows/    ← 组装目录（staging，1499 个文件）
release/Fatalis-Prediction-v1.2.0-windows.zip ← 压缩包（正式发行物）
```

组装 = `dist/BlackDragon/*` + `LICENSE` + `README.txt`（v1.2.0 正式版：模型指标对比、一键训练语义、摘要行/告警、三层回滚、--selftest）+ `models/fatalis_ai_model.pkl.meta.json`（sidecar：采信来源 / sha / 门槛 / 回滚程序；包内模型 sha 与 sidecar `model_sha256` 一致）。

> 注：sidecar 为组装步骤手工补入（spec datas 未收集 meta.json，v3 预览包同样如此；已列入 follow-up 建议）。selftest 冒烟在 zip 封口后执行，包内无运行残留（`blackdragon.log` 已确认不在 zip 内）。

## 3. Zip 验证

| 检查项 | 结果 | 证据 |
|--------|:---:|------|
| `BlackDragon.exe` | ✅ | 21,688,800 B |
| `BlackDragonOverlay.exe` | ✅ | 21,643,103 B |
| `_internal/`（含 xgboost.dll + VERSION） | ✅ | 1499 个文件总计 |
| `data/ML_Ready_Dataset.csv` | ✅ | 186,483 B（sha `3e5ed34d…295fda6c`，与实验口径一致） |
| `data/fatalis_combat_data_*.csv` | ✅ | 19 个（数据集重建保险） |
| `models/fatalis_ai_model.pkl` | ✅ | 7,824,436 B（sha `ed3db5f8…ce65b5f` = 采纳物，与仓库生产模型逐位一致） |
| `models/factory_model.pkl` | ✅ | 7,824,436 B（sha 同上——出厂即 Run B） |
| `models/fatalis_ai_model.pkl.meta.json` | ✅ | 2,095 B |
| `LICENSE` / `README.txt` | ✅ | 1,068 B / 5,646 B |

### 包内 EXE selftest 冒烟（发行包本体，非 dist）

```
release/Fatalis-Prediction-v1.2.0-windows/BlackDragon.exe        --selftest  → exit 0
release/Fatalis-Prediction-v1.2.0-windows/BlackDragonOverlay.exe --selftest  → exit 0 (CWD=TEMP)
```

## 4. G6 与 SHA256

| 项 | 值 |
|----|-----|
| **G6 包体积门槛（≤300MB）** | **PASS** — 166,854,511 B = **159.1 MiB**（v1.1.0 125.7MB，增量 +33.1MB ≈ xgboost.dll 压缩后体积） |
| zip SHA256 | `9b7f929e490413203a0b20f59f718bdd0d0e78eb6a35e21febc9d6c9ce2ad17a` |
| `BlackDragon.exe` | `3f739394c8d823ddf9db549d5cccab5557a80e6dc4aa9dae47c5808529c288a9` |
| `BlackDragonOverlay.exe` | `95b375f58fed0841ca9f9def46db9514b4de783a1992b2adb12de715648b71c2` |
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
| 发布包组装（1499 文件，含 factory model + 19 原始 CSV + sidecar） | ✅ |
| zip 创建 159.1 MiB（G6 ≤300MB） | ✅ PASS |
| 包内双 EXE selftest | ✅ exit 0 / exit 0 |
| SHA256 清单 + 红线 sha 复核 | ✅ 全部一致 |

**结论: PASS** — `Fatalis-Prediction-v1.2.0-windows.zip` 满足发布要求。

**建议下一步**（均待用户裁决，本轮不执行）:
1. `git push origin main` + `git tag -a v1.2.0`
2. 上传 zip 到 GitHub Release（附 SHA256）
3. 用户进游戏长线实测（对照离线指标 top3_filtered 65.37%）
