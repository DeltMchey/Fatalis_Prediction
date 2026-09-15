# Release Package Report — BlackDragon v1.1.0

- **Date**: 2026-08-05 18:52
- **Agent**: runner
- **Scope**: v1.1.0 release packaging — clean build → package → verify → SHA256

---

## 1. 环境与版本

| 项目 | 值 |
|------|-----|
| Git HEAD | `2e4f996` (docs: update v1.1.0 release documentation) |
| Git status | clean（无未提交变更） |
| Python | 3.12.6 (venv) |
| PyInstaller | 6.21.0 |
| 测试基线 | 581 passed |

---

## 2. 打包流程

### 2.1 检查 scripts/build_exe.ps1

脚本功能（`build_exe.ps1`）：
1. `[1/6]` 验证 PyInstaller
2. `[2/6]` 运行 pytest（`-Clean` 时也执行）
3. `[3/6]` 清理 build/dist 旧产物（仅 `-Clean`）
4. `[4/6]` 构建 `BlackDragon.exe`（Dashboard spec）
5. `[5/6]` 构建 `BlackDragonOverlay.exe`（Overlay spec）
6. `[6/6]` 合并 EXE + surface `data/ML_Ready_Dataset.csv` + `models/fatalis_ai_model.pkl`

**注意**: 脚本不创建 release zip —— zip 打包为独立步骤（本次手动执行）。

### 2.2 清理 + 重建

```
.\scripts\build_exe.ps1 -Clean   →   BUILD_EXIT=0
```

| 步骤 | 结果 |
|------|:---:|
| 清理旧 build/ dist/ | ✅ |
| pytest 581 passed | ✅ |
| BlackDragon.exe | ✅ |
| BlackDragonOverlay.exe | ✅ |
| data/ML_Ready_Dataset.csv surfaced | ✅ |
| models/fatalis_ai_model.pkl surfaced | ✅ |

### 2.3 创建发布包

```
release/Fatalis-Prediction-v1.1.0-windows/   ← 组装目录
release/Fatalis-Prediction-v1.1.0-windows.zip  ← 压缩包
```

组装：`dist/BlackDragon/*` + `LICENSE` + `README.txt`（v1.1.0 格式，含 pipeline 说明）

---

## 3. Zip 验证

### 3.1 文件清单

| 检查项 | 要求 | 结果 | 证据 |
|--------|:---:|:---:|------|
| `BlackDragon.exe` | ✅ | ✅ FOUND | 21,348,530 B |
| `BlackDragonOverlay.exe` | ✅ | ✅ FOUND | 21,323,593 B |
| `_internal/` | ✅ | ✅ FOUND | `_internal\python312.dll` 等 1450+ 条目 |
| `data/` | ✅ | ✅ FOUND | `data\ML_Ready_Dataset.csv` (88,708 B) |
| `models/` | ✅ | ✅ FOUND | `models\fatalis_ai_model.pkl` (19,976,868 B) |
| `LICENSE` | ✅ | ✅ FOUND | 1,068 B |
| `README.txt` | ✅ | ✅ FOUND | 2,924 B |

**总条目**: 1458 个

### 3.2 打包后冒烟测试

```
dist/BlackDragon/BlackDragon.exe --pipeline   →   SMOKE_EXIT=0
```

| 检查项 | 结果 |
|--------|:---:|
| frozen pipeline 退出码 | 0 |
| stderr 错误 | 空 |
| 无 Dashboard 弹出 | ✅（0 进程） |
| 无 Overlay 启动 | ✅ |

---

## 4. SHA256

```
Algorithm : SHA256
Hash      : 3C5CC31D0810C27AAA56BB8289A8A2719553A77637EC0F52036AC7F754DD629C
Path      : release\Fatalis-Prediction-v1.1.0-windows.zip
```

### 文件属性

| 属性 | 值 |
|------|-----|
| 文件名 | `Fatalis-Prediction-v1.1.0-windows.zip` |
| 大小 | 125,704,786 B (~120 MB) |
| 创建时间 | 2026-08-05 18:51:50 |
| SHA256 | `3C5CC31D0810C27AAA56BB8289A8A2719553A77637EC0F52036AC7F754DD629C` |

---

## 5. 已知注意事项

| # | 事项 | 说明 |
|---|------|------|
| 1 | **Zip 路径分隔符为 `\`** | PowerShell 5.1 `Compress-Archive` 使用反斜杠分隔符（非 ZIP 规范的前斜杠）。**与 v1.0.0 发布一致**（v1.0.0 zip 同样使用 `\`）。Windows Explorer / 内置解压可正常解压；跨平台工具（7-Zip on Linux）可能需注意。非阻塞，保持与 v1.0 一致。 |
| 2 | **无 `config/` 目录** | build 脚本注释提到 "copy dist/BlackDragon/ + models/ + config/"，但项目根无 `config/` 目录（配置通过 `blackdragon_config.json` 运行时生成）。v1.0.0 同样无此目录。非阻塞。 |
| 3 | **release/ 目录已 gitignore** | `release/` 在 `.gitignore` 中（`release/` 规则），zip 不会进入版本控制。 |

---

## 6. 结论

| 验证项 | 结果 |
|--------|:---:|
| 清理旧产物 | ✅ |
| 重建 EXE（581 tests） | ✅ |
| 发布包组装 | ✅ |
| zip 创建 | ✅ 125.7 MB |
| zip 内容验证（7 项） | ✅ 全部 FOUND |
| 冒烟测试（frozen --pipeline） | ✅ exit 0 |
| SHA256 | ✅ `3C5CC31D...629C` |

**结论: PASS** — `Fatalis-Prediction-v1.1.0-windows.zip` 满足发布要求。

**建议下一步**:
1. 上传 zip 到 GitHub Release（附 SHA256）
2. `git tag -a v1.1.0` + `git push --tags`
3. 发布说明引用 SHA256 供用户校验
