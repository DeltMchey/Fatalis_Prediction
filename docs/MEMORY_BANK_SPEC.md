# Memory Bank 初始化任务

请阅读整个代码仓库，包括：

* PROJECT_ANALYSIS.md
* Project_map.md
* Tech_debt.md
* Refactoring_roadmap.md

然后生成标准的 `memory-bank/` 目录，并包含以下文件：

1. projectbrief.md
2. productContext.md
3. systemPatterns.md
4. techContext.md
5. progress.md
6. activeContext.md

---

# 信息来源要求（Source of Truth）

只能使用代码仓库中已经明确存在的信息。

禁止：

* 虚构功能
* 猜测未出现的模块
* 推测未来实现方案
* 创建仓库中不存在的功能描述

如果某部分信息缺失，请明确标注：

“当前未知（Currently Unknown）”。

---

# 一致性要求（Consistency）

生成的 Memory Bank 必须与以下文档保持严格一致：

* PROJECT_ANALYSIS.md
* Project_map.md
* Tech_debt.md
* Refactoring_roadmap.md

如果发现文档之间存在冲突：

不要自行解决冲突。

请明确指出冲突内容。

---

# 当前开发阶段（Current Development Phase）

当前项目处于：

P1 —— 项目规范化（Repository Standardization）

本次 Memory Bank 的唯一目的：

支持 P1 阶段工作。

当前允许进行的工作：

* 项目目录整理
* GitHub 项目规范化
* 文档建设
* Memory Bank 建设
* 配置文件规划
* 配置集中化方案设计

---

# 当前禁止进行的工作（Out of Scope）

以下内容属于后续阶段：

禁止出现在当前任务中：

* 架构重构
* God Class 拆分
* 模块重设计
* 核心 Python 逻辑修改
* 机器学习逻辑修改
* 游戏逻辑修改
* 特征工程修改
* 推理逻辑修改
* 模型行为修改

这些内容应保留到未来阶段。

不得作为当前任务。

---

# activeContext.md 特殊要求

activeContext.md 是最重要的文件。

必须明确记录：

当前阶段：

P1 —— 项目规范化

当前目标：

为未来重构建立标准项目结构。

硬性约束：

* 不修改核心 Python 逻辑
* 不修改游戏机制逻辑
* 不修改模型行为
* 不修改特征工程
* 暂不进行架构拆分

成功标准：

* 项目目录规范化
* 文档体系建立
* Memory Bank 建立完成
* 项目保持可运行状态

---

# progress.md 特殊要求

严格按照 Refactoring_roadmap.md 中定义的阶段生成。

必须包含：

* P1
* P2
* P3
* P4
* P5

状态要求：

* P1 = Active
* P2 = Planned
* P3 = Planned
* P4 = Planned
* P5 = Planned

不得将未来阶段标记为进行中。

---

# 输出风格要求

所有 Memory Bank 文件应：

* 简洁
* 基于事实
* 易于长期维护
* 适合 Claude Code 长期记忆使用

避免：

* 过长说明
* 实现细节堆砌
* 猜测性描述

优先记录：

* 项目事实
* 当前状态
* 阶段目标
* 关键约束
