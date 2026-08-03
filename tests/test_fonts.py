"""P5.1.1: fonts tests — 共享中文字体加载。

策略：
  - patch src.ui.fonts.dpg → 不触发真实 DPG
  - 验证字体候选探测、字体缺失降级、字体绑定

覆盖：
  - setup_cjk_font 加载并绑定字体
  - 字体文件缺失 → 降级到默认（不抛异常）
  - _find_existing 候选探测
  - 显式 font_path 优先
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.ui.fonts import _find_existing, setup_cjk_font


class TestFindExisting:
    def test_returns_first_existing(self, tmp_path):
        existing = tmp_path / "a.ttc"
        existing.write_text("x")
        missing = tmp_path / "b.ttc"
        result = _find_existing([str(missing), str(existing)])
        assert result == str(existing)

    def test_returns_none_when_all_missing(self, tmp_path):
        result = _find_existing([str(tmp_path / "x"), str(tmp_path / "y")])
        assert result is None


class TestSetupCjkFont:
    def test_loads_and_binds_font(self, tmp_path):
        """字体存在 → 加载并绑定。"""
        font_path = tmp_path / "msyh.ttc"
        font_path.write_text("fake")
        with patch("src.ui.fonts.dpg") as mock_dpg:
            setup_cjk_font(font_path=str(font_path))
        # font_registry 上下文被使用
        mock_dpg.font_registry.assert_called_once()
        # font 被创建
        mock_dpg.font.assert_called_once()

    def test_font_missing_degrades_gracefully(self, tmp_path, caplog):
        """字体缺失 → 降级到默认，不抛异常。"""
        with patch("src.ui.fonts.dpg") as mock_dpg:
            setup_cjk_font(font_path=str(tmp_path / "missing.ttc"))
        # font_registry 未被调用（路径不存在 → 提前返回）
        mock_dpg.font_registry.assert_not_called()

    def test_uses_msyh_on_windows(self, monkeypatch):
        """默认候选第一项是微软雅黑。"""
        from src.ui.fonts import _FONT_CANDIDATES
        assert _FONT_CANDIDATES[0] == "C:/Windows/Fonts/msyh.ttc"
