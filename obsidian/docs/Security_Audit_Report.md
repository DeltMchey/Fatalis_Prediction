# BlackDragon 安全审查报告

- **审查日期**: 2026-08-24
- **审查对象**: D:\Projects\BlackDragon（main 分支 @ 2e4f996）
- **审查方式**: 全仓库只读静态审查（不修改任何代码/配置），覆盖 OWASP Top 10 (2021)、CWE Top 25、依赖/CI/打包供应链与密钥暴露检查
- **审查范围**: 全部 Python 源码（含 legacy 入口）、配置文件、GitHub Actions、PyInstaller 打包脚本与 spec、git 全历史密钥扫描、运行时日志与数据目录

---

## 一、执行摘要

BlackDragon 是本地单机游戏辅助工具（读取 Monster Hunter World 进程内存 → 录制战斗数据 → LightGBM 训练/预测 → 透明覆盖层显示）。**无网络通信面、无账号/认证体系、无服务端组件**，因此传统 Web 类风险（注入、CSRF、SSRF、越权等）不适用。

总体结论：**核心内存读取与 UI 代码安全质量良好**——无命令注入（所有 `subprocess` 均为列表参数、无 `shell=True`）、无进程注入/写内存操作、无硬编码凭据、git 历史无密钥泄露、依赖全部精确固定版本、`train_lgbm.py` 对 CSV 输入已做较完善的防御性过滤。

主要风险集中在**本地文件信任边界**：模型文件（pickle）与配置文件（JSON）在加载时均无完整性/类型校验，二者组合可形成"被篡改或来自不可信来源的文件 → 启动即任意代码执行"的攻击链，对社区分发模型、配置包的场景构成真实威胁。其余为日志信息泄露、CI 供应链加固与数据容错类中低危问题。

| 严重级 | 数量 |
|--------|------|
| Critical | 0 |
| High | 2 |
| Medium | 4 |
| Low | 5 |
| Info | 4 |
| **合计** | **15** |

---

## 二、威胁模型

- **攻击者能力假设**：可替换/投放项目目录下的文件（共享机器上的其他用户、被恶意软件感染的进程、或用户主动下载的"社区模型/配置包"）；可创建同名窗口或同名进程。
- **不可行攻击面**：无网络输入 → 无远程利用路径；攻击者无法通过游戏进程内存数据控制程序流程（所有读取均异常包裹并返回默认值）。
- **工具设计固有风险**（已在 SECURITY.md 声明）：读取游戏进程内存、可被反作弊机制检测——属用途使然，不计为漏洞。

---

## 三、发现明细

### High（2）

#### H1 — 模型 pickle 反序列化无完整性校验，恶意模型文件可致启动即 RCE

- **位置**: `src/model/predictor.py:66`、`src/app/controller.py:102`、`overlay.py:109`、`ai_engine.py:328`（legacy）、`train_lgbm.py:137`、`build/BlackDragon.spec:19-21`
- **CWE**: CWE-502（不可信数据反序列化）
- **描述**: 应用在启动时（Dashboard 与 Overlay 两个进程均会）用 `joblib.load()` 加载 `models/fatalis_ai_model.pkl`，路径来自配置或硬编码。joblib/pickle 加载恶意文件可执行任意代码。模型文件随发布包分发（spec 将其打入 exe 包、build_exe.ps1 将其复制到 exe 旁），且**全程无任何完整性校验**（无签名、无 checksum）。`train_lgbm.py:137` 的 `joblib.dump()` 使模型成为自产自用的 pickle。攻击场景：用户下载他人分享/被篡改的模型文件放入 `models/`，或共享机器上其他用户替换该文件 → 下次启动即执行攻击者代码（与用户同权限）。
- **证据**: `predictor.py:66` `self._model = joblib.load(model_path)`；`train_lgbm.py:137` `joblib.dump(model, "models/fatalis_ai_model.pkl")`
- **修复建议**: ① 改用 LightGBM 原生格式（`model.booster_.save_model("models/fatalis_ai_model.txt")` 导出为文本/二进制 booster 格式，加载用 `lgb.Booster(model_file=...)`），彻底消除 pickle 执行面；② 若保留 pickle，发布时附带模型 SHA-256 并在加载前校验，失败则拒绝加载；③ 在 UI/文档中明确警告"不要加载来源不明的模型文件"。

#### H2 — 配置 JSON 无类型/取值校验，篡改 `overlay_script` 即可触发任意脚本执行

- **位置**: `src/app/config.py:64-70`、`src/app/controller.py:248-249`、调用链 `launch.py:80`
- **CWE**: CWE-15（配置错误）、CWE-94（代码生成控制不当）
- **描述**: `AppConfig.load()` 将 JSON 中与字段名匹配的值**原样 `setattr`**，不做类型与取值校验。其中 `overlay_script` 字段在 `start_overlay()` 中直接拼入 `subprocess.Popen([sys.executable, self._config.overlay_script])`——攻击者把该字段改为任意 Python 脚本路径（如指向自己放置的恶意 .py），用户点击"启动覆盖层"即执行任意代码。同理 `model_path` 指向任意 pickle（叠加 H1）、`data_dir`/`dataset_path` 可指向任意目录。配置字段缺失类型校验还会导致类型错误崩溃（如 `prediction_interval` 被写为字符串）。
- **证据**: `config.py:70` `setattr(config, key, value)`（无 `isinstance` 检查）；`controller.py:248` `cmd = [sys.executable, self._config.overlay_script]`
- **修复建议**: 加载时对每个字段做类型断言（`isinstance`）与取值校验：`overlay_script`/`training_script` 白名单限定为项目固定文件名；`model_path`/`dataset_path`/`data_dir` 限定为项目内相对路径（拒绝绝对路径与 `..`）；非法值回退默认并记录警告。

### Medium（4）

#### M1 — 日志全量堆栈泄露绝对路径与用户名，日志文件位置随 CWD

- **位置**: `src/logging_config.py:39`、`src/data/recorder.py:116`、`src/ui/overlay.py:167`、`launch.py:99`、`ai_engine.py:319/332/469`（legacy）
- **CWE**: CWE-200（敏感信息暴露）
- **描述**: 多处异常处理将 `traceback.format_exc()` 完整写入 `blackdragon.log`，实际日志（844 KB）中包含 `D:\Projects\BlackDragon\...` 绝对路径与 `C:\Users\19173\AppData\...` 用户名路径。日志文件固定写在**当前工作目录**的 `blackdragon.log`（`logging_config.py:39`），冻结模式下随用户双击位置落盘，若日志被分享/泄露出用户磁盘布局与账户名。
- **证据**: `recorder.py:116` `logger.warning(f"录制线程异常:\n{traceback.format_exc()}")`；`logging_config.py:39` `logging.FileHandler("blackdragon.log", ...)`
- **修复建议**: ① 日志输出前剥离用户主目录/项目根前缀；② 日志固定写入 `%APPDATA%/BlackDragon/blackdragon.log`（`Path.home()` 派生），不依赖 CWD；③ frozen 模式下生产级日志仅记录异常类型与信息，堆栈留 debug 级别。

#### M2 — GitHub Actions 未固定到 commit SHA，且无最小权限声明

- **位置**: `.github/workflows/test.yml:24, 27, 54`
- **CWE**: CWE-829（不可信源包含功能）
- **描述**: `actions/checkout@v4`、`actions/setup-python@v5`、`actions/upload-artifact@v4` 均以可变 major 标签引用，标签可被仓库维护者重新指向恶意代码；workflow 未声明 `permissions:` 最小化。当前流水线仅跑测试、不含 secrets，实际利用价值低，但属标准供应链加固项。
- **修复建议**: 将三个 action 固定到 commit SHA（并开启 Dependabot 自动更新 SHA）；顶部添加 `permissions: contents: read`。

#### M3 — CI 运行时依赖安装未按 requirements.txt 固定版本

- **位置**: `.github/workflows/test.yml:35-37`
- **CWE**: CWE-829 / 供应链
- **描述**: CI 用 `pip install numpy pandas scikit-learn lightgbm matplotlib joblib` 安装**未固定版本**的运行时依赖，与 `requirements.txt`（全部 `==` 精确固定）不一致，存在"本地通过、CI 失败"与供应链漂移风险；`pytest`/`pytest-cov` 同样未固定。
- **修复建议**: CI 改为 `pip install -r requirements.txt` + `pip install pytest==<固定版本> pytest-cov==<固定版本>`；测试仅对纯逻辑模块运行（现有 Linux 兼容设计已支持）。

#### M4 — data_cleaner 对畸形 CSV 无行级容错，单行异常中断整个训练流水线

- **位置**: `data_cleaner.py:24-91`（核心问题行：`data_cleaner.py:40` `int(row['action_id'])`；try/except 仅包裹 `read_csv`，行循环在 try 外）
- **CWE**: CWE-20（输入验证不当）、CWE-754（异常处理不当）
- **描述**: 录制数据 CSV 若被手工编辑或损坏（`action_id` 非数值、缺少 `distance`/`relative_angle` 等列），行处理循环中 `int()` 抛 ValueError / 字典键缺失抛 KeyError，直接中断 `clean_combat_data()`，`--pipeline` 训练流程（launch.py:57）随之失败。对比之下 `train_lgbm.py`（v1.1.1/1.1.2）已对 NaN label、非数值 label、未知动作做了完善过滤——cleaner 侧是明显的防御缺口。
- **修复建议**: 行循环加 try/except 跳过坏行并计数告警；解析前校验必需列存在性；`int()` 改用安全转换（`pd.to_numeric(errors='coerce')`，与 train_lgbm.py 的做法对齐）。

### Low（5）

#### L1 — 覆盖层窗口按标题查找，可能误操作其他同名窗口

- **位置**: `src/ui/overlay.py:128-133`、`ai_engine.py:356-358`
- **CWE**: CWE-283（未验证所有权）
- **描述**: `FindWindowW(None, "overlay")` 按窗口标题匹配，若系统存在另一个标题为 "overlay" 的窗口（其他程序或恶意创建），`SetWindowLongW`/`SetLayeredWindowAttributes` 会作用于该窗口（改变其透明样式）。影响为外观类/干扰其他应用，无权限提升。
- **修复建议**: 校验返回的 HWND 所属进程 PID 与自身一致（`GetWindowThreadProcessId` 对比 `os.getpid()`），不一致则跳过透明设置。

#### L2 — 启动时经用户确认后自动 pip install，requirements.txt 无完整性校验

- **位置**: `src/bootstrap/checker.py:111-128`、`launch.py:76`
- **CWE**: CWE-829
- **描述**: `launch.py` 启动即调用 `DependencyChecker.ensure()`，缺失依赖时提示用户后执行 `pip install <requirements.txt 内容>`。若项目目录被其他用户篡改（放入恶意 `requirements.txt` 或同名恶意包），用户确认后即安装恶意包、下次导入即执行。已有用户确认步骤降低了实际风险。
- **修复建议**: 安装前显示将安装的包列表并二次确认；将安装操作限制在明确标记的开发模式（frozen 模式已跳过）；提示用户核对 requirements.txt 来源。

#### L3 — 日志无轮转、无上限

- **位置**: `src/logging_config.py:39`
- **描述**: `FileHandler` 追加写入 `blackdragon.log`，无 RotatingFileHandler；当前已 844 KB 且持续增长（每帧异常都会写堆栈）。长时间运行可耗尽磁盘。
- **修复建议**: 改用 `RotatingFileHandler(maxBytes=1MB, backupCount=3)`（含 UTF-8 编码参数）。

#### L4 — 日志队列无界（Overlay 独立进程无人消费）

- **位置**: `src/logging_config.py:20`
- **描述**: `_log_queue` 为无界 `queue.Queue`，QueueHandler 无条件入队；Overlay 独立进程（overlay.py）不创建 LogView、无人消费该队列，长时间运行（WARNING 级异常持续产生）时内存无限增长。
- **修复建议**: 仅在创建 Dashboard 时挂载 QueueHandler；或改用有界队列（`queue.Queue(maxsize=N)`，满则丢弃）。

#### L5 — `blackdragon_config.json` 未加入 .gitignore

- **位置**: `.gitignore`
- **描述**: 配置文件由 `AppConfig.save()` 生成在项目根，.gitignore 未覆盖，存在被误提交风险（当前配置不含密钥，属预防性）。`*.tmp` 已覆盖保存用的临时文件。
- **修复建议**: 在 .gitignore 添加 `blackdragon_config.json`。

### Info（4）

#### I1 — SECURITY.md 漏洞报告链接为占位符

- **位置**: `SECURITY.md:18, 45`
- **描述**: 报告链接写死为 `https://github.com/<org>/<repo>/security/advisories/new` 与 `<org>/<repo>/issues` 占位符，无法直达。
- **建议**: 替换为实际仓库地址。

#### I2 — Overlay 进程硬编码模型路径，与配置不一致

- **位置**: `overlay.py:109` vs `src/app/controller.py:102`
- **描述**: `overlay.py` 用硬编码 `"models/fatalis_ai_model.pkl"`，而 Dashboard 侧用 `config.model_path`；用户通过配置更换模型后 Overlay 仍加载旧路径。
- **建议**: 统一从 `AppConfig.load()` 读取 `model_path`。

#### I3 — 依赖无自动漏洞审计步骤

- **位置**: `requirements.txt`（全 8 项 `==` 精确固定，做法良好）
- **描述**: 截至审查日，经 Snyk 数据库核实：`Pymem==1.14.0` 与 `dearpygui==2.3` 均无已知直接漏洞；其余依赖版本较新。但项目无任何依赖漏洞审计步骤。
- **建议**: CI 增加 `pip-audit`（或 trivy）步骤；发布前对依赖树做一次完整审计。

#### I4 — 按进程名附着，同名欺骗进程可能被读取

- **位置**: `src/app/game_service.py:29, 76`、`overlay.py:76`、`ai_engine.py:478`（legacy）
- **描述**: `pymem.Pymem("MonsterHunterWorld.exe")` 按名称匹配进程。攻击者可运行同名假进程诱使工具附着；因工具只读内存、不写不注入，假进程中无受害者敏感数据，实际影响有限，且属工具设计使然（SECURITY.md 已声明）。
- **建议**: 附着时校验进程路径位于游戏安装目录（`QueryFullProcessImageNameW`），可作为纵深防御。

---

## 四、已核查的安全基线（未发现问题项）

以下检查项经全仓库核查，**未发现**问题，属值得保持的良好实践：

| 检查项 | 结果 |
|--------|------|
| OS 命令注入（subprocess/exec/shell=True） | ✅ 无——全部 `subprocess` 调用均为列表参数、无 shell 拼接 |
| 进程注入 / 写内存（CreateRemoteThread / inject_dll / VirtualAllocEx / WriteProcessMemory） | ✅ 全仓零命中，工具仅读内存 |
| 网络面（requests / socket / urllib / http 调用） | ✅ 全仓零命中，无任何出站连接 |
| git 全历史密钥扫描（api key / secret / token / 私钥 / 连接串） | ✅ 零命中 |
| 硬编码凭据 / .env / 证书密钥文件 | ✅ 无 |
| 依赖版本固定 | ✅ requirements.txt 8 项全部 `==` 精确固定 |
| CSV 训练数据防御（train_lgbm.py v1.1.1/1.1.2） | ✅ NaN label、非数值 label、未知动作 label 均有检测、过滤与告警 |
| 内存读取异常处理 | ✅ 所有读取包裹 try/except 返回默认值；`read_monster_hp` 有除零保护（`memory_reader.py:158`） |
| 配置保存原子性 | ✅ tmp + `replace()` 原子写入（`config.py:75-83`） |
| 敏感产物 gitignore | ✅ `data/*.csv`、`models/*.pkl`、`*.log`、`.venv/`、`release/`、`dist/` 均已忽略 |
| UI 层输入 | ✅ Dashboard/Overlay 全部为展示逻辑，无用户输入到达危险汇点 |
| archive/ 遗留代码 | ✅ 仅存档、不参与构建与发布 |

---

## 五、优先修复建议

1. **（H1，最高优先）** 模型序列化改为 LightGBM 原生格式或增加 SHA-256 完整性校验——消除"恶意模型文件 → 启动即 RCE"。
2. **（H2）** `AppConfig.load()` 增加逐字段类型断言与取值白名单（`overlay_script` 等仅允许项目固定文件名），非法值回退默认。
3. **（M1）** 日志路径脱敏 + 固定日志目录（`%APPDATA%/BlackDragon`）+ RotatingFileHandler 轮转（一并解决 L3）。
4. **（M2/M3）** CI：actions 固定 commit SHA、声明 `permissions`、按 requirements.txt 安装依赖、增加 `pip-audit`（一并解决 I3）。
5. **（M4）** data_cleaner 行级容错，与 train_lgbm 的输入防御对齐。
6. **（L1/L2/L4/L5）** 窗口所有权校验、安装依赖二次确认、有界日志队列、.gitignore 补 `blackdragon_config.json`。

---

## 附录 A：审查文件清单

**核心/游戏交互**：`ai_engine.py`、`src/core/memory_reader.py`、`src/core/state_tracker.py`、`src/config/offsets.py`、`src/config/actions.py`、`src/app/game_service.py`、`src/app/controller.py`、`src/bootstrap/checker.py`

**应用/UI/数据/ML**：`launch.py`、`main.py`、`overlay.py`、`train_lgbm.py`、`data_cleaner.py`、`data_upgrade.py`、`src/app/config.py`、`src/data/recorder.py`、`src/model/predictor.py`、`src/logging_config.py`、`src/dashboard/main_window.py`、`src/dashboard/log_view.py`、`src/dashboard/status_bar.py`、`src/dashboard/training_panel.py`、`src/ui/fonts.py`、`src/ui/overlay.py`

**配置/CI/打包**：`requirements.txt`、`.gitignore`、`.coveragerc`、`pytest.ini`、`.github/workflows/test.yml`、`scripts/build_exe.ps1`、`build/BlackDragon.spec`、`build/BlackDragonOverlay.spec`、`SECURITY.md`、`README.md`、`blackdragon.log`（抽样）、`data/`、`models/`、`archive/`（抽样）、git 全历史

**说明**：本报告为静态审查结论，未对任何文件做修改；依赖 CVE 结论基于 Snyk 漏洞库公开数据（Pymem 1.14.0、DearPyGui 2.3 无已知直接漏洞），建议发布前以 `pip-audit` 对完整依赖树做实时复核。
