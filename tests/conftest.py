"""P3.1: Shared fixtures for all test files.

Available fixtures:
  - sample_df: small example DataFrame simulating combat data
  - sample_csv_path: sample_df written to a CSV file in a temp directory
  - mock_offsets: deep copy of OFFSETS for safe modification during tests
  - temp_data_dir: temporary data subdirectory that is guaranteed to exist
"""

import os

# matplotlib 后端必须在任何 matplotlib 核心模块导入之前确定。
# sklearn/xgboost 的导入链会拉起 matplotlib 核心；若核心先于本变量导入，
# pyplot 的惰性 backend 解析将忽略后设的 env 而落到 TkAgg——测试期弹 GUI
# 窗口并偶发 TclError（invalid command name "tcl_findLibrary"）。
# conftest 在所有测试模块之前导入，是保证顺序的唯一可靠挂载点。
os.environ.setdefault("MPLBACKEND", "Agg")

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from copy import deepcopy

from src.config.offsets import GameOffsets, OFFSETS
from src.config.actions import ACTION_DB, ACTION_MAPPING


# =============================================================================
# DataFrame / CSV fixtures
# =============================================================================

@pytest.fixture
def sample_df():
    """Return a small example DataFrame simulating combat data format."""
    return pd.DataFrame({
        "timestamp": [0.0, 0.5, 1.0, 1.5, 2.0],
        "action_id": [81, 82, 81, 96, 81],
        "action_name": ["dodge", "move", "dodge", "bite", "dodge"],
        "phase": [1, 1, 1, 1, 2],
        "hp_percent": [100.0, 99.5, 99.0, 98.0, 97.5],
        "enrage": [0, 0, 0, 0, 0],
        "distance": [12.5, 11.0, 9.5, 8.0, 7.2],
        "angle": [180, 175, 170, 165, 160],
        "player_x": [0.0, 1.0, 2.0, 3.0, 4.0],
        "player_y": [0.0, 0.0, 0.0, 0.0, 0.0],
        "monster_x": [12.5, 12.0, 11.0, 10.0, 9.0],
        "monster_y": [0.0, 2.0, 3.0, 4.0, 5.0],
        "posture": ["stand", "stand", "stand", "prone", "stand"],
    })


@pytest.fixture
def sample_csv_path(tmp_path, sample_df):
    """Write sample_df to a CSV file in the temp directory, return its path."""
    path = tmp_path / "sample_combat.csv"
    sample_df.to_csv(path, index=False)
    return str(path)


# =============================================================================
# Config fixtures
# =============================================================================

@pytest.fixture
def mock_offsets():
    """Return a deep copy of OFFSETS for safe mutation during tests."""
    return deepcopy(OFFSETS)


# =============================================================================
# Directory fixtures
# =============================================================================

@pytest.fixture
def temp_data_dir(tmp_path):
    """Return path to a temp data/ subdirectory, ensuring it exists."""
    d = tmp_path / "data"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


# =============================================================================
# P3.4: Data pipeline fixtures (data_cleaner / data_upgrade / train_lgbm)
# =============================================================================

# 录制 CSV 的 v2 列顺序（与 ai_engine.data_logger_thread 写入的头部一致）
COMBAT_CSV_COLUMNS = [
    "timestamp", "hp_percent", "phase", "is_enraged",
    "distance", "relative_angle", "posture", "action_id",
]


def write_combat_csv(path, rows):
    """Write rows (list[dict]) to a v2-format combat CSV at `path`.

    列顺序与 ai_engine 录制格式一致；`path` 的父目录必须已存在。
    """
    df = pd.DataFrame(rows)
    # 固定列顺序，避免 dict 顺序漂移影响断言
    df = df[COMBAT_CSV_COLUMNS]
    df.to_csv(path, index=False)


@pytest.fixture
def pipeline_workdir(tmp_path, monkeypatch):
    """P3.4: 创建临时 data/ + models/ 目录，并把 CWD 切换到 tmp_path。

    三个数据管线脚本内部使用相对路径 `data/...` / `models/...`。
    本 fixture 通过 chdir 让这些路径自然指向临时目录，从而
    避免 monkeypatch glob.glob，更接近真实运行行为。
    """
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "models").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def old_format_csv(pipeline_workdir):
    """P3.4: 返回一个旧格式 CSV 文件路径（无 phase/is_enraged 列）。

    测试通过 write_combat_csv 覆盖内容。
    """
    return pipeline_workdir / "data" / "fatalis_combat_data_old.csv"


@pytest.fixture
def new_format_csv(pipeline_workdir):
    """P3.4: 返回一个新格式 CSV 文件路径（已含 phase/is_enraged 列）。

    测试通过 write_combat_csv 覆盖内容。
    """
    return pipeline_workdir / "data" / "fatalis_combat_data_new.csv"
