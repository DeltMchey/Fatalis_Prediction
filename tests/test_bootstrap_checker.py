"""P5.1: DependencyChecker tests — 启动环境检查。

策略:
  - 纯 stdlib 依赖——无需 mock pymem/dearpygui
  - get_missing 通过 monkeypatch importlib.metadata 控制已安装包
  - install 通过 monkeypatch subprocess.run 验证调用

覆盖:
  - check_python_version
  - _parse_requirement 各种格式
  - get_missing（缺失/满足/版本约束/注释/空行/文件缺失）
  - install（成功/失败/空列表）
  - ensure（就绪/缺失自动安装/用户取消/Python版本不足）
"""

import sys
from unittest.mock import MagicMock

import pytest

from src.bootstrap.checker import DependencyChecker


class TestCheckPythonVersion:
    def test_current_version_ok(self):
        assert DependencyChecker.check_python_version() is True

    def test_lower_min_version_ok(self):
        assert DependencyChecker.check_python_version((3, 0)) is True

    def test_higher_min_version_fails(self, monkeypatch):
        monkeypatch.setattr(sys, "version_info", (3, 9, 0))
        assert DependencyChecker.check_python_version() is False


class TestParseRequirement:
    def test_exact_version(self):
        assert DependencyChecker._parse_requirement("Pymem==1.14.0") \
            == ("Pymem", "==", "1.14.0")

    def test_minimum_version(self):
        assert DependencyChecker._parse_requirement("numpy>=2.0") \
            == ("numpy", ">=", "2.0")

    def test_bare_name(self):
        assert DependencyChecker._parse_requirement("joblib") \
            == ("joblib", ">=", "0")

    def test_comment_ignored(self):
        assert DependencyChecker._parse_requirement("# comment") is None

    def test_empty_ignored(self):
        assert DependencyChecker._parse_requirement("") is None

    def test_invalid_ignored(self):
        assert DependencyChecker._parse_requirement("!!invalid!!") is None


class TestIsInstalled:
    def test_installed_exact_match(self, monkeypatch):
        monkeypatch.setattr(
            "importlib.metadata.version", lambda n: "1.14.0")
        assert DependencyChecker._is_installed("Pymem", "==", "1.14.0") is True

    def test_installed_version_mismatch(self, monkeypatch):
        monkeypatch.setattr(
            "importlib.metadata.version", lambda n: "1.13.0")
        assert DependencyChecker._is_installed("Pymem", "==", "1.14.0") is False

    def test_installed_minimum_satisfied(self, monkeypatch):
        monkeypatch.setattr(
            "importlib.metadata.version", lambda n: "2.4.4")
        assert DependencyChecker._is_installed("numpy", ">=", "2.0") is True

    def test_installed_minimum_not_satisfied(self, monkeypatch):
        monkeypatch.setattr(
            "importlib.metadata.version", lambda n: "1.9.0")
        assert DependencyChecker._is_installed("numpy", ">=", "2.0") is False

    def test_package_not_found(self, monkeypatch):
        import importlib.metadata
        def _raise(name):
            raise importlib.metadata.PackageNotFoundError(name)
        monkeypatch.setattr("importlib.metadata.version", _raise)
        assert DependencyChecker._is_installed("ghost", ">=", "0") is False


class TestGetMissing:
    def test_all_installed(self, tmp_path, monkeypatch):
        req = tmp_path / "requirements.txt"
        req.write_text("Pymem==1.14.0\nnumpy>=2.0\n", encoding="utf-8")

        def _fake_version(name):
            return {"Pymem": "1.14.0", "numpy": "2.4.4"}.get(name, "0.0.0")
        monkeypatch.setattr("importlib.metadata.version", _fake_version)
        assert DependencyChecker.get_missing(str(req)) == []

    def test_missing_packages(self, tmp_path, monkeypatch):
        import importlib.metadata
        req = tmp_path / "requirements.txt"
        req.write_text("Pymem==1.14.0\nGhostPkg>=1.0\n", encoding="utf-8")

        def _fake_version(name):
            if name == "GhostPkg":
                raise importlib.metadata.PackageNotFoundError(name)
            return "1.14.0"
        monkeypatch.setattr("importlib.metadata.version", _fake_version)
        missing = DependencyChecker.get_missing(str(req))
        assert missing == ["GhostPkg>=1.0"]

    def test_file_missing_returns_empty(self, tmp_path):
        assert DependencyChecker.get_missing(
            str(tmp_path / "nope.txt")) == []

    def test_comments_and_blanks_skipped(self, tmp_path, monkeypatch):
        req = tmp_path / "requirements.txt"
        req.write_text("# comment\n\nPymem==1.14.0\n", encoding="utf-8")
        monkeypatch.setattr(
            "importlib.metadata.version", lambda n: "1.14.0")
        assert DependencyChecker.get_missing(str(req)) == []


class TestInstall:
    def test_install_calls_pip(self, monkeypatch):
        import subprocess
        result = MagicMock(returncode=0)
        mock_run = MagicMock(return_value=result)
        monkeypatch.setattr(subprocess, "run", mock_run)
        ok = DependencyChecker.install(["Pymem==1.14.0"])
        assert ok is True
        mock_run.assert_called_once()
        # 验证命令包含 pip install
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == sys.executable
        assert cmd[1] == "-m"
        assert cmd[2] == "pip"
        assert cmd[3] == "install"
        assert "Pymem==1.14.0" in cmd

    def test_install_failure(self, monkeypatch):
        result = MagicMock(returncode=1)
        monkeypatch.setattr(
            "subprocess.run", MagicMock(return_value=result))
        assert DependencyChecker.install(["pkg"]) is False

    def test_install_empty_list(self):
        assert DependencyChecker.install([]) is True

    def test_install_exception(self, monkeypatch):
        monkeypatch.setattr(
            "subprocess.run",
            MagicMock(side_effect=RuntimeError("pip missing")))
        assert DependencyChecker.install(["pkg"]) is False


class TestEnsure:
    def test_ensure_ready(self, tmp_path, monkeypatch, capsys):
        req = tmp_path / "requirements.txt"
        req.write_text("Pymem==1.14.0\n", encoding="utf-8")
        monkeypatch.setattr(
            "importlib.metadata.version", lambda n: "1.14.0")
        monkeypatch.setattr(sys, "version_info", (3, 12, 0))
        assert DependencyChecker.ensure(str(req)) is True

    def test_ensure_python_too_old(self, tmp_path, monkeypatch, capsys):
        req = tmp_path / "requirements.txt"
        req.write_text("", encoding="utf-8")
        monkeypatch.setattr(sys, "version_info", (3, 9, 0))
        assert DependencyChecker.ensure(str(req)) is False
        captured = capsys.readouterr()
        assert "Python" in captured.out

    def test_ensure_auto_install(self, tmp_path, monkeypatch, capsys):
        req = tmp_path / "requirements.txt"
        req.write_text("GhostPkg>=1.0\n", encoding="utf-8")
        import importlib.metadata

        def _fake_version(name):
            if name == "GhostPkg":
                raise importlib.metadata.PackageNotFoundError(name)
            return "1.0"
        monkeypatch.setattr("importlib.metadata.version", _fake_version)
        result = MagicMock(returncode=0)
        monkeypatch.setattr("subprocess.run", MagicMock(return_value=result))
        assert DependencyChecker.ensure(str(req), auto_install=True) is True

    def test_ensure_user_cancels(self, tmp_path, monkeypatch, capsys):
        req = tmp_path / "requirements.txt"
        req.write_text("GhostPkg>=1.0\n", encoding="utf-8")
        import importlib.metadata

        def _fake_version(name):
            if name == "GhostPkg":
                raise importlib.metadata.PackageNotFoundError(name)
            return "1.0"
        monkeypatch.setattr("importlib.metadata.version", _fake_version)
        # 用户输入 n → 取消
        monkeypatch.setattr("builtins.input", lambda _: "n")
        assert DependencyChecker.ensure(str(req)) is False