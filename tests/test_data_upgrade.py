"""P3.4: Integration tests for data_upgrade.py — 旧版 CSV 回填 phase/enrage 列。

测试策略：
  - 通过 `pipeline_workdir` fixture 把 CWD 切到临时目录，脚本内的
    `data/fatalis_combat_data_*.csv` glob 自然指向临时 data/ 目录。
  - 写入旧格式 CSV（无 phase/is_enraged 列），调用 upgrade_old_csv_files()，
    再读回同一文件断言回填结果。

覆盖：
  - 空目录（无 CSV → 优雅返回）
  - 已升级文件跳过（幂等）
  - phase 三阶段计算（>0.78 → 1, ≤0.78 → 2, ≤0.50 → 3）
  - enrage 180 秒软计时器窗口
  - 多次怒吼刷新窗口
  - 边界时间（current_time == enrage_end_time → 0）
  - 输出列顺序
  - 混合旧/新 CSV（仅旧文件被升级）
"""

import pandas as pd

import data_upgrade
from tests.conftest import write_combat_csv


# =============================================================================
# 基础 fixture 辅助
# =============================================================================

def make_old_rows():
    """构造旧格式数据行（无 phase / is_enraged 列，但可能含 posture）。

    列顺序: timestamp, hp_percent, distance, relative_angle, posture, action_id
    """
    return [
        {"timestamp": 0.0, "hp_percent": 0.90, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 81},
        {"timestamp": 10.0, "hp_percent": 0.80, "distance": 90.0, "relative_angle": -10.0, "posture": 1, "action_id": 81},
        {"timestamp": 20.0, "hp_percent": 0.70, "distance": 80.0, "relative_angle": 20.0, "posture": 1, "action_id": 81},
    ]


def write_old_csv(path, rows):
    """以旧格式（无 phase/is_enraged）写入 CSV。"""
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def make_new_rows():
    """构造新格式数据行（含 phase / is_enraged 列），用于已升级文件场景。"""
    return [
        {"timestamp": 0.0, "hp_percent": 0.90, "phase": 1, "is_enraged": 0,
         "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 81},
        {"timestamp": 10.0, "hp_percent": 0.80, "phase": 1, "is_enraged": 0,
         "distance": 90.0, "relative_angle": -10.0, "posture": 1, "action_id": 81},
        {"timestamp": 20.0, "hp_percent": 0.70, "phase": 2, "is_enraged": 0,
         "distance": 80.0, "relative_angle": 20.0, "posture": 1, "action_id": 81},
    ]


# =============================================================================
# 1. 空目录
# =============================================================================

class TestEmptyDirectory:
    def test_no_csv_returns_gracefully(self, pipeline_workdir, capsys):
        """无任何战斗数据文件 → 函数打印错误并返回，不崩溃。"""
        result = data_upgrade.upgrade_old_csv_files()
        assert result is None
        captured = capsys.readouterr()
        assert "未找到任何战斗数据文件" in captured.out


# =============================================================================
# 2. 已升级文件跳过
# =============================================================================

class TestAlreadyUpgraded:
    def test_new_format_file_is_skipped(self, pipeline_workdir, capsys):
        """已含 phase + is_enraged 列的文件 → 跳过，内容不变。"""
        path = pipeline_workdir / "data" / "fatalis_combat_data_new.csv"
        write_combat_csv(path, make_new_rows())

        data_upgrade.upgrade_old_csv_files()

        captured = capsys.readouterr()
        assert "共抢救回 0 个" in captured.out

        df = pd.read_csv(path)
        assert "phase" in df.columns
        assert "is_enraged" in df.columns
        # 内容未被改动（与写入时一致）
        assert df["phase"].tolist() == [1, 1, 2]
        assert df["is_enraged"].tolist() == [0, 0, 0]


# =============================================================================
# 3. phase 三阶段计算
# =============================================================================

class TestPhaseCalculation:
    def test_phase_boundaries(self, pipeline_workdir):
        """hp 阈值边界: >0.78 → 1, 0.78~0.50 → 2, ≤0.50 → 3。"""
        path = pipeline_workdir / "data" / "fatalis_combat_data_phase.csv"
        rows = [
            {"timestamp": 0.0, "hp_percent": 0.90, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 81},
            {"timestamp": 1.0, "hp_percent": 0.78, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 81},
            {"timestamp": 2.0, "hp_percent": 0.60, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 81},
            {"timestamp": 3.0, "hp_percent": 0.50, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 81},
            {"timestamp": 4.0, "hp_percent": 0.30, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 81},
        ]
        write_old_csv(path, rows)

        data_upgrade.upgrade_old_csv_files()

        df = pd.read_csv(path)
        assert df["phase"].tolist() == [1, 2, 2, 3, 3]

    def test_phase_defaults_to_one_without_hp(self, pipeline_workdir):
        """hp_percent 缺失（NaN）→ 默认 phase=1。"""
        path = pipeline_workdir / "data" / "fatalis_combat_data_nohp.csv"
        rows = [
            {"timestamp": 0.0, "hp_percent": float("nan"), "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 81},
        ]
        write_old_csv(path, rows)

        data_upgrade.upgrade_old_csv_files()

        df = pd.read_csv(path)
        # NaN 与 0.78 / 0.50 比较均为 False → 保持默认 1
        assert df["phase"].tolist() == [1]


# =============================================================================
# 4. enrage 180 秒窗口
# =============================================================================

class TestEnrageWindow:
    def test_single_roar_180s_window(self, pipeline_workdir):
        """单次怒吼（action=4）→ 之后 180 秒内 is_enraged=1，过期后=0。"""
        path = pipeline_workdir / "data" / "fatalis_combat_data_enrage.csv"
        rows = [
            # 怒吼前
            {"timestamp": 0.0, "hp_percent": 0.90, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 81},
            # 怒吼当帧（t=10, action=4 → enrage_end=190）
            {"timestamp": 10.0, "hp_percent": 0.90, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 4},
            # 窗口内
            {"timestamp": 100.0, "hp_percent": 0.90, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 81},
            # 窗口外（t=200 > 190）
            {"timestamp": 200.0, "hp_percent": 0.90, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 81},
        ]
        write_old_csv(path, rows)

        data_upgrade.upgrade_old_csv_files()

        df = pd.read_csv(path)
        assert df["is_enraged"].tolist() == [0, 1, 1, 0]


# =============================================================================
# 5. 多次怒吼刷新
# =============================================================================

class TestMultipleRoars:
    def test_roars_refresh_window(self, pipeline_workdir):
        """连续怒吼会刷新窗口，最后一次怒吼决定过期时间。"""
        path = pipeline_workdir / "data" / "fatalis_combat_data_multi_roar.csv"
        rows = [
            # t=0, action=4 → end=180
            {"timestamp": 0.0, "hp_percent": 0.90, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 4},
            # t=100, action=5 → end=280（刷新）
            {"timestamp": 100.0, "hp_percent": 0.90, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 5},
            # t=200, action=179 → end=380（再刷新）
            {"timestamp": 200.0, "hp_percent": 0.90, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 179},
            # t=300 < 380 → 仍在窗口内
            {"timestamp": 300.0, "hp_percent": 0.90, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 81},
            # t=400 > 380 → 窗口过期
            {"timestamp": 400.0, "hp_percent": 0.90, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 81},
        ]
        write_old_csv(path, rows)

        data_upgrade.upgrade_old_csv_files()

        df = pd.read_csv(path)
        assert df["is_enraged"].tolist() == [1, 1, 1, 1, 0]


# =============================================================================
# 6. 边界时间
# =============================================================================

class TestEnrageBoundary:
    def test_exactly_at_end_time_is_not_enraged(self, pipeline_workdir):
        """current_time == enrage_end_time → is_enraged=0（严格小于）。"""
        path = pipeline_workdir / "data" / "fatalis_combat_data_boundary.csv"
        rows = [
            # t=10, action=4 → end=190
            {"timestamp": 10.0, "hp_percent": 0.90, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 4},
            # t=190 恰好等于 end → 0
            {"timestamp": 190.0, "hp_percent": 0.90, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 81},
        ]
        write_old_csv(path, rows)

        data_upgrade.upgrade_old_csv_files()

        df = pd.read_csv(path)
        assert df["is_enraged"].tolist() == [1, 0]


# =============================================================================
# 7. 输出列顺序
# =============================================================================

class TestColumnOrder:
    def test_column_order_matches_expected(self, pipeline_workdir):
        """旧 CSV（无 posture）→ 输出列顺序为 7 列标准顺序。"""
        path = pipeline_workdir / "data" / "fatalis_combat_data_cols.csv"
        rows = [
            {"timestamp": 0.0, "hp_percent": 0.90, "distance": 100.0, "relative_angle": 0.0, "action_id": 81},
        ]
        write_old_csv(path, rows)

        data_upgrade.upgrade_old_csv_files()

        df = pd.read_csv(path)
        assert df.columns.tolist() == [
            "timestamp", "hp_percent", "phase", "is_enraged",
            "distance", "relative_angle", "action_id",
        ]

    def test_posture_column_preserved_and_positioned(self, pipeline_workdir):
        """旧 CSV 含 posture → 保留且插入到 action_id 之前。"""
        path = pipeline_workdir / "data" / "fatalis_combat_data_cols2.csv"
        rows = [
            {"timestamp": 0.0, "hp_percent": 0.90, "distance": 100.0, "relative_angle": 0.0, "posture": 1, "action_id": 81},
        ]
        write_old_csv(path, rows)

        data_upgrade.upgrade_old_csv_files()

        df = pd.read_csv(path)
        assert df.columns.tolist() == [
            "timestamp", "hp_percent", "phase", "is_enraged",
            "distance", "relative_angle", "posture", "action_id",
        ]


# =============================================================================
# 8. 混合旧/新 CSV
# =============================================================================

class TestMixedFiles:
    def test_only_old_files_upgraded(self, pipeline_workdir, capsys):
        """目录中同时存在旧/新格式 → 仅旧文件被回填，新文件保持不变。"""
        data_dir = pipeline_workdir / "data"
        old_path = data_dir / "fatalis_combat_data_old.csv"
        new_path = data_dir / "fatalis_combat_data_new.csv"

        write_old_csv(old_path, make_old_rows())
        write_combat_csv(new_path, make_new_rows())

        data_upgrade.upgrade_old_csv_files()

        captured = capsys.readouterr()
        assert "共抢救回 1 个" in captured.out

        # 旧文件已升级
        old_df = pd.read_csv(old_path)
        assert "phase" in old_df.columns
        assert "is_enraged" in old_df.columns

        # 新文件未被修改（列保持 v2 顺序，无多余列）
        new_df = pd.read_csv(new_path)
        assert new_df.columns.tolist() == [
            "timestamp", "hp_percent", "phase", "is_enraged",
            "distance", "relative_angle", "posture", "action_id",
        ]

    def test_multiple_old_files_all_upgraded(self, pipeline_workdir, capsys):
        """多个旧文件 → 全部升级。"""
        data_dir = pipeline_workdir / "data"
        write_old_csv(data_dir / "fatalis_combat_data_a.csv", make_old_rows())
        write_old_csv(data_dir / "fatalis_combat_data_b.csv", make_old_rows())

        data_upgrade.upgrade_old_csv_files()

        captured = capsys.readouterr()
        assert "共抢救回 2 个" in captured.out
        for name in ["fatalis_combat_data_a.csv", "fatalis_combat_data_b.csv"]:
            df = pd.read_csv(data_dir / name)
            assert "phase" in df.columns
            assert "is_enraged" in df.columns
