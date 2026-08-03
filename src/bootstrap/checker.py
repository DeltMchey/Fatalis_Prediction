"""P5.1: DependencyChecker — 启动环境检查。

在 Dashboard 之前运行（控制台模式），负责：
  - 检查 Python 版本
  - 解析 requirements.txt 比对已安装包
  - 提示或自动安装缺失依赖

设计约束:
  - 零第三方依赖（仅 Python stdlib）—— bootstrap 在 pip install 之前运行
  - 不导入 dearpygui / pymem / P4 模块（依赖未安装时也可运行）
"""

import importlib.metadata
import re
import subprocess
import sys
from pathlib import Path


class DependencyChecker:
    """环境检查 + 依赖安装。"""

    MIN_PYTHON = (3, 11)

    # ================= 检查 =================

    @classmethod
    def check_python_version(cls, min_version=None) -> bool:
        """检查 Python 版本是否 ≥ 最低要求。

        Args:
            min_version: 最低版本 (major, minor)，默认 (3, 11)

        Returns:
            bool: 版本是否满足
        """
        if min_version is None:
            min_version = cls.MIN_PYTHON
        return sys.version_info[:2] >= min_version

    @classmethod
    def get_missing(cls, requirements_path: str = "requirements.txt") -> list[str]:
        """解析 requirements.txt，返回缺失/版本不满足的包列表。

        返回原始行（如 "Pymem==1.14.0"），便于 pip install 直接消费。
        文件缺失时返回空列表（视为无需检查）。
        """
        path = Path(requirements_path)
        if not path.exists():
            return []
        missing: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parsed = cls._parse_requirement(line)
            if parsed is None:
                continue
            name, op, version = parsed
            if not cls._is_installed(name, op, version):
                missing.append(line)
        return missing

    @classmethod
    def _parse_requirement(cls, line: str):
        """解析单行依赖为 (name, op, version)。

        支持: pkg==1.0  pkg>=1.0  pkg<=1.0  pkg~=1.0  pkg
        返回 None 表示无法解析。
        """
        m = re.match(
            r"^([A-Za-z0-9_.-]+)\s*(==|>=|<=|~=)\s*([A-Za-z0-9_.-]+)$",
            line,
        )
        if m:
            return m.group(1), m.group(2), m.group(3)
        # 仅包名（无版本约束）
        m2 = re.match(r"^([A-Za-z0-9_.-]+)$", line)
        if m2:
            return m2.group(1), ">=", "0"
        return None

    @classmethod
    def _is_installed(cls, name: str, op: str, version: str) -> bool:
        """检查包是否已安装且满足版本约束。"""
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return False
        # 简单版本比较（major.minor.patch）
        try:
            installed_tuple = tuple(int(x) for x in installed.split(".")[:3])
            required_tuple = tuple(int(x) for x in version.split(".")[:3])
        except ValueError:
            # 版本号无法解析——存在即视为满足
            return True
        if op == "==":
            return installed_tuple == required_tuple
        if op == ">=":
            return installed_tuple >= required_tuple
        if op == "<=":
            return installed_tuple <= required_tuple
        if op == "~=":
            # ~= 兼容版本：前两位相同
            return installed_tuple[:2] == required_tuple[:2]
        return True

    # ================= 安装 =================

    @staticmethod
    def install(packages: list[str]) -> bool:
        """通过 pip 安装缺失依赖。

        Returns:
            bool: 是否全部安装成功
        """
        if not packages:
            return True
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", *packages],
                capture_output=True,
                text=True,
                timeout=300,
            )
            return result.returncode == 0
        except Exception:
            return False

    # ================= 一站式 =================

    @classmethod
    def ensure(cls, requirements_path: str = "requirements.txt",
               auto_install: bool = False) -> bool:
        """环境就绪检查 + 安装（launch.py 调用）。

        Args:
            requirements_path: requirements.txt 路径
            auto_install: True 时不提示直接安装（CI 模式）

        Returns:
            bool: 环境是否就绪（True → 继续启动；False → 退出）
        """
        print("BlackDragon 环境检查...")

        # 1. Python 版本
        if not cls.check_python_version():
            print(f"  Python {sys.version.split()[0]} ❌ (需要 ≥ 3.11)")
            print("请升级 Python 后重试。")
            return False
        print(f"  Python {sys.version.split()[0]} ✅")

        # 2. 依赖
        missing = cls.get_missing(requirements_path)
        if not missing:
            print("  依赖检查: 全部满足 ✅")
            return True
        print(f"  依赖检查: 缺失 {len(missing)} 个: {missing}")

        # 3. 安装
        if not auto_install:
            try:
                answer = input("自动安装缺失依赖? [Y/n]: ").strip().lower()
            except EOFError:
                answer = "n"
            if answer not in ("y", "yes", ""):
                print("已取消安装。")
                return False
        if cls.install(missing):
            print("  安装完成 ✅")
            return True
        print("  安装失败，请手动运行: pip install -r requirements.txt")
        return False
