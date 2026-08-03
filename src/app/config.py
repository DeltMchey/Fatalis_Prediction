"""P5: AppConfig — 用户设置持久化（JSON）。

为 Dashboard 控制中心提供可持久化的配置：
  - model_path: AI 模型路径
  - data_dir:   录制 CSV 输出目录
  - auto_start_overlay / auto_start_recording: 启动行为
  - overlay_opacity / prediction_interval: 运行参数

设计约束:
  - 纯 Python（无 dearpygui / pymem 依赖）→ Linux CI 可 import
  - JSON 文件持久化，缺失/损坏时降级到默认值
"""

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path

logger = logging.getLogger("BlackDragon")


@dataclass
class AppConfig:
    """应用配置 — JSON 序列化。

    用法:
        config = AppConfig.load("blackdragon_config.json")
        config.model_path = "models/my_model.pkl"
        config.save("blackdragon_config.json")
    """

    # ── 模型 ──
    model_path: str = "models/fatalis_ai_model.pkl"

    # ── 录制 ──
    data_dir: str = "data"

    # ── Overlay ──
    auto_start_overlay: bool = False
    overlay_opacity: float = 1.0

    # ── 预测 ──
    prediction_interval: float = 0.5

    # ── 训练 ──
    training_script: str = "train_lgbm.py"
    dataset_path: str = "data/ML_Ready_Dataset.csv"

    # ================= 持久化 =================

    @classmethod
    def load(cls, path: str = "blackdragon_config.json") -> "AppConfig":
        """从 JSON 文件加载配置。

        文件缺失 / 损坏 / 字段不匹配时降级到默认值，绝不抛异常。
        """
        config = cls()
        filepath = Path(path)
        if not filepath.exists():
            return config
        try:
            raw = json.loads(filepath.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return config
            valid_names = {f.name for f in fields(cls)}
            for key, value in raw.items():
                if key in valid_names:
                    setattr(config, key, value)
        except Exception:
            logger.warning("配置加载失败，使用默认值: %s", path)
        return config

    def save(self, path: str = "blackdragon_config.json") -> None:
        """将配置写入 JSON 文件（原子写入：先写临时文件再替换）。"""
        filepath = Path(path)
        tmp = filepath.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(filepath)

    def reset_to_defaults(self) -> None:
        """将当前实例重置为默认值。"""
        defaults = AppConfig()
        for f in fields(defaults):
            setattr(self, f.name, getattr(defaults, f.name))
