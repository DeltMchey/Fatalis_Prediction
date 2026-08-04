"""P5: AppConfig tests — JSON 配置持久化。

覆盖：
  - 默认值
  - save/load 往返
  - 文件缺失 → 默认值
  - 损坏 JSON → 默认值
  - 未知字段忽略
  - 字段类型恢复
  - reset_to_defaults
"""

import json

import pytest

from src.app.config import AppConfig


class TestDefaults:
    def test_default_model_path(self):
        assert AppConfig().model_path == "models/fatalis_ai_model.pkl"

    def test_default_data_dir(self):
        assert AppConfig().data_dir == "data"

    def test_default_auto_start_overlay_true(self):
        """ADR-P5.3: 默认自动启动覆盖层子进程。"""
        cfg = AppConfig()
        assert cfg.auto_start_overlay is True

    def test_default_auto_record_true(self):
        """ADR-P5.3: 默认开启录制模式。"""
        cfg = AppConfig()
        assert cfg.auto_record is True

    def test_default_overlay_opacity(self):
        assert AppConfig().overlay_opacity == 1.0


class TestSaveLoad:
    def test_save_load_roundtrip(self, tmp_path):
        path = str(tmp_path / "cfg.json")
        cfg = AppConfig()
        cfg.model_path = "models/custom.pkl"
        cfg.overlay_opacity = 0.7
        cfg.save(path)
        loaded = AppConfig.load(path)
        assert loaded.model_path == "models/custom.pkl"
        assert loaded.overlay_opacity == 0.7

    def test_save_creates_valid_json(self, tmp_path):
        path = tmp_path / "cfg.json"
        AppConfig().save(str(path))
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "model_path" in data

    def test_load_missing_file_returns_defaults(self, tmp_path):
        loaded = AppConfig.load(str(tmp_path / "nope.json"))
        assert loaded == AppConfig()

    def test_load_corrupted_json_returns_defaults(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not valid json", encoding="utf-8")
        loaded = AppConfig.load(str(path))
        assert loaded == AppConfig()

    def test_load_unknown_fields_ignored(self, tmp_path):
        path = tmp_path / "unknown.json"
        path.write_text(
            json.dumps({"model_path": "models/x.pkl", "bogus_field": 123}),
            encoding="utf-8",
        )
        loaded = AppConfig.load(str(path))
        assert loaded.model_path == "models/x.pkl"
        assert not hasattr(loaded, "bogus_field")

    def test_load_type_coercion(self, tmp_path):
        """非 dict JSON（如列表）→ 默认值。"""
        path = tmp_path / "list.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        assert AppConfig.load(str(path)) == AppConfig()


class TestReset:
    def test_reset_to_defaults(self):
        cfg = AppConfig()
        cfg.model_path = "custom"
        cfg.overlay_opacity = 0.1
        cfg.reset_to_defaults()
        assert cfg.model_path == "models/fatalis_ai_model.pkl"
        assert cfg.overlay_opacity == 1.0
