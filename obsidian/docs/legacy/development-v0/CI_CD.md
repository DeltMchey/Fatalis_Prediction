---
title: CI/CD
tags:
  - CI
  - GitHub-Actions
  - automation
  - testing
created: 2026-07-26
updated: 2026-07-26
---

# CI/CD

## 概述

BlackDragon 使用 GitHub Actions 实现持续集成。当前已配置测试 workflow，未来计划加入 lint 和 release。

## 当前 CI 配置

### test.yml

```yaml
name: Test

on:
  push:
    branches: [master, main]
  pull_request:
    branches: [master, main]

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest]
        python-version: ["3.11", "3.12"]
    
    steps:
      - checkout
      - setup Python
      - install pytest, pytest-cov
      - install numpy, pandas, scikit-learn, lightgbm, matplotlib, joblib
      - [Windows only] install Pymem, dearpygui
      - check core imports
      - pytest --cov --cov-report=term --cov-report=xml --cov-report=html
      - upload coverage artifact
```

### 跨平台矩阵

| 维度 | 配置 |
|------|------|
| **操作系统** | ubuntu-latest, windows-latest |
| **Python 版本** | 3.11, 3.12 |
| **组合总数** | 4 |

### 平台差异处理

| 依赖 | Linux | Windows |
|------|-------|---------|
| numpy, pandas, sklearn | ✅ pip install | ✅ pip install |
| lightgbm, matplotlib, joblib | ✅ pip install | ✅ pip install |
| Pymem (进程内存读取) | ❌ 不安装 | ✅ pip install |
| dearpygui (GUI 框架) | ❌ 不安装 | ✅ pip install |

> [!note] 跨平台测试策略
> Windows-only 依赖（Pymem, dearpygui）只在 Windows runner 上安装。纯逻辑测试（Config, 数学函数, 过滤）在 Linux 上也能运行。

## CI 触发条件

| 事件 | 触发 |
|------|------|
| Push 到 master/main | ✅ 自动 |
| Pull Request 到 master/main | ✅ 自动 |
| 其他分支 Push | ❌ 不触发 |

## 产物

通过 `upload-artifact@v4` 上传覆盖率报告：
- `htmlcov/` — HTML 覆盖率报告
- `coverage.xml` — XML 覆盖率数据
- 保留 7 天

## 状态验证

CI 检查的核心导入:
```bash
python -c "import numpy, pandas, sklearn, lightgbm, matplotlib, joblib; print('Core imports OK')"
```

## 计划扩展（P5）

### lint.yml — 代码检查

```yaml
name: Lint
on: [push, pull_request]
jobs:
  lint:
    steps:
      - uses: ruff check .
      - uses: ruff format --check .
```

### release.yml — 自动发布

```yaml
name: Release
on:
  push:
    tags: ['v*']
jobs:
  release:
    steps:
      - create GitHub Release
      - publish release notes
```

## 本地运行

### 运行 CI 相同命令

```bash
# 安装依赖
pip install -r requirements.txt
pip install pytest pytest-cov

# 运行测试（与 CI 相同）
pytest --cov --cov-report=term --cov-report=html -v

# 查看 HTML 报告
# 浏览器打开 htmlcov/index.html
```

### 检查覆盖率

```bash
pytest --cov --cov-report=term -q
```

## 环境信息

| 属性 | 本地 | CI (Windows) | CI (Linux) |
|------|------|-------------|------------|
| OS | Windows | windows-latest | ubuntu-latest |
| Python | 3.12.6 | 3.11 / 3.12 | 3.11 / 3.12 |
| 虚拟环境 | .venv/ | 系统 pip | 系统 pip |
| Pymem 可用 | ✅ | ✅ | ❌ |
| dearpygui 可用 | ✅ | ✅ | ❌ |

## 关键测试文件

| 文件 | Linux 可跑 | 说明 |
|------|------------|------|
| `test_infrastructure.py` | ✅ | 纯配置验证 |
| `test_actions.py` | ✅ | 纯数据结构 |
| `test_offsets.py` | ✅ | 纯配置类 |
| `test_logging.py` | ✅ | 文件 I/O |
| `test_math_logic.py` | ✅ | 纯数学 |
| `test_phase_filter.py` | ✅ | 纯数组操作 |
| `test_nova.py` | ✅ | 纯状态机 |

> [!note] 所有 7 个测试文件均可跨平台运行
> 经过 P2 重构，所有测试只依赖纯 Python 逻辑和标准库，不依赖 pymem 或 dearpygui。
