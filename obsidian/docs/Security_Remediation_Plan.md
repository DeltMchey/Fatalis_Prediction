# BlackDragon 安全修复优化计划（P5.5 Security Hardening）

> **关联文档**: [Security_Audit_Report.md](./Security_Audit_Report.md)（2026-08-24 全量安全审查，15 项发现）
> **编制依据**: memory bank（projectbrief / productContext / systemPatterns / techContext / activeContext / progress / changelog）+ 审查发现
> **日期**: 2026-08-24

---

## 0. 与项目现状的对齐（读 memory bank 后的编制决策）

| 决策点 | 结论 | 依据 |
|--------|------|------|
| 阶段定位 | **P5.5 Security Hardening**，插在 P5.4 与 P6 之间 | progress.md 阶段表（P1–P5 Complete，P6 Planned）；插入式编号不打乱既有规划 |
| 版本号 | **v1.1.3**（P1 项随后 v1.1.4） | changelog.md 已用 v1.1.1/v1.1.2 标记训练管线修复，安全修复延续 patch 序列 |
| H1 拆分 | v1.1.3 做 **SHA-256 完整性校验**；LightGBM 原生格式迁移**留给 P6** | P6 = 模型工程化（版本管理）。格式迁移会破坏 .pkl/.bak/发布包兼容，与版本管理一并做只破坏一次 |
| 零 diff 约束 | H1 触及 `src/model/predictor.py`（P4 core）→ 新建 **ADR-P5.5** 显式解除 | activeContext 反复强调 "P4 core 零 diff"；决策须留 ADR（延续 ADR-P5.2/5.3/5.4 链） |
| 工作流 | 每项修复 = 实现 + 新增测试 + memory bank 更新 + CHANGELOG + 必要时重建 EXE | changelog.md 各条目的固定结构（Completed/API/Design Decisions/Metrics/Review） |
| 测试命令 | `MPLBACKEND=Agg pytest tests/ -q`（本机 Tcl/Tk 损坏，TkAgg 偶发失败） | changelog.md 2026-08-03 Known Environment Issue |
| 基线 | 581 tests / 100% pass / 94% coverage——**所有修复后不低于此基线** | activeContext Current Test Metrics |

---

## 1. 总体分期

| 期 | 版本 | 内容 | 预估工作量 | 风险 |
|----|------|------|-----------|------|
| **P0** | v1.1.3 | H1(SHA-256) + H2(配置校验) + M4(cleaner 容错) + L5(.gitignore) | 10–14 人时 | 中（触及 P4 core 与打包链） |
| **P1** | v1.1.4 | M1(日志脱敏) + M2/M3+I3(CI 加固) + L3/L4(日志轮转/有界队列) | 6–8 人时 | 低–中 |
| **P2** | 随 P6 | H1 第二阶段(原生模型格式+版本管理) + I1/I2/L1/L2/I4 | 并入 P6 规划 | — |

依赖关系：P0 四项任务相互独立可并行（H1 是最长链）；P1 各项独立；P2 不阻塞前两期。

---

## 2. P0 — v1.1.3 详细任务

### 任务 1：H1 模型完整性校验（SHA-256 sidecar）⚠️ 最长链

**方案对比**（审查报告已列，此处为最终决策）：

| 方案 | 内容 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | `.pkl` 旁挂 `.sha256` 校验文件 | 兼容现有 .pkl/.bak/发布包；改动小 | 首次安装需信任分发包 | ✅ **v1.1.3 采用** |
| B | 改 LightGBM 原生文本格式 | 彻底消除 pickle 执行面 | 破坏 .bak 兼容、发布包全换、双进程加载逻辑重写 | ✅ **P6 采用**（与模型版本管理合并） |
| C | Authenticode/代码签名 | 最强 | 个人项目成本高 | ❌ 放弃 |

**涉及文件**：
- `src/model/predictor.py` — `__init__` 加载前校验（P4 core，需 ADR-P5.5）
- `train_lgbm.py` — `joblib.dump()` 后生成 `models/fatalis_ai_model.pkl.sha256`；`.bak` 备份时同步生成 `.bak.sha256`
- `build/BlackDragon.spec` + `build/BlackDragonOverlay.spec` — datas 增加 sidecar 打包
- `scripts/build_exe.ps1` — surfacing 步骤复制 sidecar
- `ai_engine.py`（legacy）— 同步加校验或 docstring 声明 legacy 不受保护（推荐前者，5 行）

**关键设计**：
```
校验逻辑（predictor.__init__）:
  1. sidecar 存在 → sha256(模型文件) 与 sidecar 比对；不匹配 → _model=None + logger.error("模型完整性校验失败")
  2. sidecar 缺失（旧模型/用户自训练）→ logger.warning + 自动生成 sidecar（首次信任）
     —— 首次信任的残余风险在 README/SECURITY.md 明示：请仅对来源可靠的模型放行
  3. Dashboard/Overlay 状态栏已有"模型: 未加载"指示，拒载天然可见
```

**测试**：`tests/test_predictor.py` +4（校验通过加载 / 篡改拒载 / 缺失 sidecar 首次生成+warning / 空模型文件拒载）；`tests/test_train_lgbm.py` +1（训练后 sidecar 存在且匹配）
**验收标准**：修改模型任一字节后启动 Dashboard/Overlay → 拒绝加载、日志含"完整性校验失败"、UI 显示未加载；正常训练 → 校验闭环通过
**回归风险**：frozen 模式 sidecar 未 surfacing 会导致每次启动走"首次信任"——spec/ps1 必须同步改并重建 EXE 验证
**工作量**：6–8 人时（含 EXE 重建验证）

### 任务 2：H2 配置字段校验（白名单 + 类型断言）

**涉及文件**：`src/app/config.py`（load 增加校验层）；`tests/test_app_config.py`

**字段校验规则表**（实现清单）：

| 字段 | 类型 | 规则 | 非法时 |
|------|------|------|--------|
| `model_path` | str | 相对路径、以 `models/` 开头、不含 `..` 与盘符 | 回退默认 |
| `data_dir` | str | 相对路径、不含 `..` 与盘符 | 回退默认 |
| `dataset_path` | str | 以 `data/` 开头的相对路径 | 回退默认 |
| `overlay_script` | str | **白名单 {"overlay.py"}** | 回退默认 |
| `training_script` | str | **白名单 {"train_lgbm.py"}** | 回退默认 |
| `auto_record` / `auto_start_overlay` | bool | `isinstance(x, bool)` | 回退默认 |
| `overlay_opacity` | float | 0.0 ≤ x ≤ 1.0 | 回退默认 |
| `prediction_interval` | float | 0.1 ≤ x ≤ 10.0 | 回退默认 |

所有回退均 `logger.warning("配置字段非法: %s=%r，使用默认值", ...)`。校验通过后 `overlay_script` 白名单使 controller.py:248 的 `subprocess` 汇点风险消除（controller 无需改动）。

**测试**：`tests/test_app_config.py` +8~10（每类规则 1 例 + 混合合法/非法 + 原子保存不受影响）
**验收标准**：篡改 `blackdragon_config.json` 的 `overlay_script` 为任意路径 → 启动后实际仍执行 `overlay.py`，日志有 warning
**回归风险**：低——现有测试全部使用合法值；`tests/test_app_controller.py` 的 frozen/dev cmd 断言不受影响
**工作量**：2–3 人时

### 任务 3：M4 data_cleaner 行级容错

**涉及文件**：`data_cleaner.py`；`tests/test_data_cleaner.py`

**改动点**：
1. 文件级 try/except 扩展：`read_csv` 后校验必需列（`distance`/`relative_angle`/`action_id`）存在，缺列跳过该文件并告警；
2. 行循环包裹 try/except——坏行跳过、计数、结束时汇总 `⚠️ 跳过 N 个坏行`；
3. `int(row['action_id'])` 改 `pd.to_numeric(errors='coerce')`（与 train_lgbm.py v1.1.2 做法对齐）。

**测试**：`tests/test_data_cleaner.py` +4（坏行跳过不中断 / 缺必需列整文件跳过 / 非数值 action_id 过滤 / 全坏文件优雅返回）
**验收标准**：在现有 19 个 CSV 中混入一个含垃圾行的文件 → `--pipeline` 全流程完成且输出跳过统计
**回归风险**：低——仅增加防御路径，正常数据路径逐行等价
**工作量**：2–3 人时

### 任务 4：L5 .gitignore 补配置文件

`.gitignore` 增加 `blackdragon_config.json`（及 `*.json.tmp` 若未覆盖）。5 分钟，零风险。

### P0 收尾清单（沿用 changelog.md 固定结构）

1. 新建 `obsidian/docs/architecture/ADR-P5.5-security-hardening.md`（决策：SHA-256 方案、P4 core 解除零 diff 的范围仅限 predictor 加载路径、B 方案归入 P6）
2. `pytest tests/ -q` 全绿（预计 581 → ~596）
3. 更新 memory bank：activeContext（Current Phase → P5.5）、progress（阶段表插行）、changelog（v1.1.3 条目：Completed/API/Design Decisions/Metrics/Review）
4. 根 `CHANGELOG.md` + README badge（tests 数）
5. `.\scripts\build_exe.ps1 -Clean` 重建 EXE，frozen 验证：模型校验闭环 + `--pipeline` 退出码 0
6. tag `v1.1.3` + release zip

---

## 3. P1 — v1.1.4 详细任务

### 任务 5：M1+L3 日志脱敏 + 轮转（合并实施）

**涉及文件**：`src/logging_config.py`；`tests/test_logging.py`（11 个测试需同步更新——有断言绑定 `FileHandler("blackdragon.log")`）

**设计**（保守方案，兼容 dev 测试）：
- **文件位置**：dev 模式维持 CWD（测试兼容）；frozen 模式写 `%APPDATA%/BlackDragon/blackdragon.log`（`sys.frozen` 判断，与项目 frozen 惯例一致）
- **轮转**：`RotatingFileHandler(maxBytes=1MB, backupCount=3, encoding="utf-8")`（解决 L3）
- **脱敏**：自定义 `logging.Filter` 将 record 中的 `Path.home()` 与项目根前缀替换为 `~` / `<app>`——traceback 文本经 `record.getMessage()` 后处理

**测试**：test_logging.py 更新断言 +3（轮转配置 / 脱敏生效 / frozen 路径分支）
**工作量**：3–4 人时 | **风险**：中（动全局日志初始化，全测试回归确认）

### 任务 6：M2+M3+I3 CI 加固（零代码回归）

`.github/workflows/test.yml`：
1. 三个 action 固定 commit SHA（M2）；
2. 顶层 `permissions: contents: read`（M2）;
3. `pip install -r requirements.txt` 替换裸包名安装；pytest/pytest-cov 固定版本（M3）；
4. 新增 `pip-audit` 步骤（I3，失败仅 warn 不阻塞，首轮观察）。

**验收**：CI 双矩阵（ubuntu/windows × 3.11/3.12）全绿。**工作量**：1–2 人时

### 任务 7：L4 有界日志队列

`src/logging_config.py`：`_log_queue = queue.Queue(maxsize=1000)`，QueueHandler 满时丢弃（logging 内建 `enqueue` 失败即弃）；或仅 Dashboard 进程挂载 QueueHandler。**工作量**：1 人时

---

## 4. P2 — 并入 P6（模型工程化）的任务

| 项 | 内容 | 与 P6 的结合点 |
|----|------|----------------|
| H1-B | LightGBM 原生格式 `model.booster_.save_model()` + `lgb.Booster(model_file=)` | P6 模型版本管理的存储层——版本目录 + 每版 checksum 天然包含 |
| I2 | overlay.py 改用 `config.model_path` | 随版本管理统一模型寻址 |
| I1 | SECURITY.md 占位符链接 | 需用户提供真实 GitHub repo 地址（**阻塞项：等待输入**） |
| L1 | FindWindowW 后校验窗口属主 PID | 独立小改进 |
| L2 | DependencyChecker 安装前列出包清单强化确认 | 独立小改进 |
| I4 | 附着时校验游戏进程路径 | 可选纵深防御 |

---

## 5. 里程碑总览

```
v1.1.2 (现状, 581 tests)
  └─ P0 (P5.5): H1-SHA256 + H2 + M4 + L5 ──── ADR-P5.5 + 重建 EXE + tag v1.1.3
  └─ P1: M1 + M2/M3 + L3/L4 ──────────────── tag v1.1.4
  └─ P6 (模型工程化): H1-B + I2 + 版本管理 … ─ tag v1.2.0 / v2.0
```

## 6. 待用户决策的开放项

1. **SECURITY.md 真实仓库地址**（I1，纯文本替换，随时可做）；
2. **P0 是否与 P1 合并为单版本 v1.1.3**（工作量 +6 人时，发布节奏更省）——默认分两版；
3. H1 首次信任策略（缺失 sidecar 自动生成 vs 强制拒载）——本计划默认前者（兼容旧 .bak 与现有分发包），若项目定位更偏向"绝不容忍未校验模型"可改后者。
