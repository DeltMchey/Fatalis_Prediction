"""P3.4: Integration tests for data_cleaner.py — 原始 CSV → ML 就绪数据集 ETL。

测试策略：
  - `pipeline_workdir` fixture 切换 CWD 到临时目录，脚本内的
    `data/fatalis_combat_data_*.csv` glob 自然指向临时 data/ 目录。
  - 写入新格式 v2 CSV（含 phase/is_enraged/posture 列），调用
    clean_combat_data()，读取 data/ML_Ready_Dataset.csv 断言结果。

覆盖：
  - 空输入（无 CSV / 单行 CSV → 优雅返回）
  - action mapping（38→37, 54→53 等）
  - SCRIPTED 动作排除（157-197）
  - MINOR/PASSIVE 动作排除
  - distance ≥ 5000 过滤
  - action_id == 1 过滤
  - posture FSM（stand/prone/fly 转换）
  - DOWN 后姿态恢复（DOWN_IDS → 306/307/308 → prone）
  - 畸形 CSV 跳过
  - 输出列顺序
"""

import pandas as pd

import data_cleaner
from tests.conftest import write_combat_csv


# =============================================================================
# 基础辅助
# =============================================================================

def make_rows(actions, distances=None, postures=None):
    """按动作序列构造 v2 格式数据行。

    Args:
        actions: action_id 列表
        distances: 可选距离列表（默认全 100.0）
        postures: 可选 posture 列表（默认全 1，仅作占位，cleaner 自行推算）
    """
    n = len(actions)
    distances = distances or [100.0] * n
    postures = postures or [1] * n
    rows = []
    for i, a in enumerate(actions):
        rows.append({
            "timestamp": float(i),
            "hp_percent": 0.90,
            "phase": 1,
            "is_enraged": 0,
            "distance": distances[i],
            "relative_angle": 0.0,
            "posture": postures[i],
            "action_id": a,
        })
    return rows


def run_cleaner(pipeline_workdir, rows=None, raw_csv_text=None):
    """写入数据并运行 clean_combat_data()，返回输出 DataFrame（若生成）。"""
    if raw_csv_text is not None:
        (pipeline_workdir / "data" / "fatalis_combat_data_raw.csv").write_text(
            raw_csv_text, encoding="utf-8")
    elif rows is not None:
        write_combat_csv(
            pipeline_workdir / "data" / "fatalis_combat_data_raw.csv", rows)

    data_cleaner.clean_combat_data()

    out_path = pipeline_workdir / "data" / "ML_Ready_Dataset.csv"
    if out_path.exists():
        return pd.read_csv(out_path)
    return None


# =============================================================================
# 1. 空输入
# =============================================================================

class TestEmptyInput:
    def test_no_csv_files_returns_gracefully(self, pipeline_workdir, capsys):
        """无任何战斗数据文件 → 打印错误并返回。"""
        result = data_cleaner.clean_combat_data()
        assert result is None
        captured = capsys.readouterr()
        assert "未找到任何战斗数据文件" in captured.out

    def test_single_row_no_transition(self, pipeline_workdir, capsys):
        """仅一行 → 无法产生动作对 → 无输出文件，打印警告。"""
        df = run_cleaner(pipeline_workdir, make_rows([37]))
        assert df is None
        captured = capsys.readouterr()
        assert "未提取到有效数据" in captured.out

    def test_all_rows_same_action_no_transition(self, pipeline_workdir, capsys):
        """所有行同一动作（合并后）→ 无动作对。"""
        # 38 映射到 37，因此 38,38,38 是同一动作
        df = run_cleaner(pipeline_workdir, make_rows([38, 38, 38]))
        assert df is None
        captured = capsys.readouterr()
        assert "未提取到有效数据" in captured.out


# =============================================================================
# 2. Action mapping
# =============================================================================

class TestActionMapping:
    def test_raw_ids_mapped_to_base(self, pipeline_workdir):
        """38→37, 54→53：previous_action 和 next_action 均为映射后 base ID。"""
        df = run_cleaner(pipeline_workdir, make_rows([38, 54]))
        assert df is not None
        assert len(df) == 1
        row = df.iloc[0]
        assert row["previous_action"] == 37
        assert row["next_action"] == 53

    def test_unmapped_ids_kept(self, pipeline_workdir):
        """无映射的 ID 保持不变（如 129 蓄力火）。"""
        df = run_cleaner(pipeline_workdir, make_rows([129, 138]))
        assert df is not None
        assert len(df) == 1
        assert df.iloc[0]["previous_action"] == 129
        assert df.iloc[0]["next_action"] == 138


# =============================================================================
# 3. SCRIPTED 排除
# =============================================================================

class TestScriptedExclusion:
    def test_scripted_action_not_in_output(self, pipeline_workdir):
        """157-197（scripted）不作为 next_action 出现。

        注意：scripted 动作会把姿态置为 4，且提取要求 last_posture != 4，
        因此 scripted 及其紧邻后续转换都会被抑制。用 197（兼属
        POSTURE_STAND）后接 32（stand）复位姿态，再产生合法转换。
        """
        # 37 → 197（scripted）→ 32（stand 复位）→ 53
        df = run_cleaner(pipeline_workdir, make_rows([37, 197, 32, 53]))
        assert df is not None
        assert "next_action" in df.columns
        assert (df["next_action"] == 197).sum() == 0
        # 197→32 与 32→53 之间：197 的转换 target 被排除，32→53 产生 1 条
        assert len(df) == 1
        assert df.iloc[0]["previous_action"] == 32
        assert df.iloc[0]["next_action"] == 53


# =============================================================================
# 4. MINOR / PASSIVE 排除
# =============================================================================

class TestMinorPassiveExclusion:
    def test_minor_action_not_in_output(self, pipeline_workdir):
        """MINOR_AND_PASSIVE（如 306 等待）不作为 next_action 出现。"""
        # 37 → 306（minor，应排除）→ 53
        df = run_cleaner(pipeline_workdir, make_rows([37, 306, 53]))
        assert df is not None
        assert "next_action" in df.columns
        assert (df["next_action"] == 306).sum() == 0

    def test_roar_action_not_in_output(self, pipeline_workdir):
        """怒吼 4/5 也属于 MINOR_AND_PASSIVE → 不作为 next_action 出现。

        注意：生产逻辑只排除 target_action（next_action），不排除
        previous_action，因此这里只断言 next_action。
        """
        # 37 → 4（怒吼）→ 53
        df = run_cleaner(pipeline_workdir, make_rows([37, 4, 53]))
        assert df is not None
        assert (df["next_action"] == 4).sum() == 0
        assert (df["next_action"] == 53).sum() >= 1


# =============================================================================
# 5. distance 过滤
# =============================================================================

class TestDistanceFilter:
    def test_distance_over_5000_dropped(self, pipeline_workdir):
        """distance ≥ 5000 的行被整体丢弃。"""
        # row1 距离 6000（丢弃）→ 只剩 row2, row3 → 1 个转换对
        df = run_cleaner(
            pipeline_workdir,
            make_rows([37, 53, 81], distances=[6000.0, 100.0, 200.0]),
        )
        assert df is not None
        assert len(df) == 1
        # 转换对来自 row2 → row3，distance 应为 100.0
        assert df.iloc[0]["distance"] == 100.0
        assert df.iloc[0]["previous_action"] == 53
        assert df.iloc[0]["next_action"] == 81

    def test_distance_below_5000_kept(self, pipeline_workdir):
        """distance < 5000 的行正常参与转换对提取。"""
        df = run_cleaner(
            pipeline_workdir,
            make_rows([37, 53], distances=[4999.0, 100.0]),
        )
        assert df is not None
        assert len(df) == 1
        assert df.iloc[0]["previous_action"] == 37
        assert df.iloc[0]["next_action"] == 53


# =============================================================================
# 6. action_id == 1 过滤
# =============================================================================

class TestActionIdOneFilter:
    def test_action_id_one_dropped(self, pipeline_workdir):
        """action_id == 1 的行被丢弃。"""
        # row1 action=1（丢弃）→ 只剩 row2, row3 → 1 个转换对
        df = run_cleaner(pipeline_workdir, make_rows([1, 37, 53]))
        assert df is not None
        assert len(df) == 1
        assert df.iloc[0]["previous_action"] == 37
        assert df.iloc[0]["next_action"] == 53


# =============================================================================
# 7. Posture FSM
# =============================================================================

class TestPostureFSM:
    def test_stand_to_prone(self, pipeline_workdir):
        """POSTURE_PRONE 动作（138 孕吐）→ 后续转换对 posture=0。"""
        # row1: 37（保持站立）→ row2: 138（prone）→ row3: 53
        df = run_cleaner(pipeline_workdir, make_rows([37, 138, 53]))
        assert df is not None
        # 转换对 1: 37→138（posture=1，上一姿态站立）
        # 转换对 2: 138→53（posture=0，上一姿态趴下）
        assert len(df) == 2
        assert df.iloc[0]["posture"] == 1
        assert df.iloc[1]["posture"] == 0

    def test_prone_to_stand(self, pipeline_workdir):
        """POSTURE_STAND 动作（115 俯冲）→ 后续转换对 posture=1。

        注意：首行姿态不触发 FSM（last_mapped_action == -1），因此
        需 37 建立起始态、138 建立 prone、115 复位 stand、53 产出转换。
        """
        # 37 → 138（prone）→ 115（stand）→ 53
        df = run_cleaner(pipeline_workdir, make_rows([37, 138, 115, 53]))
        assert df is not None
        assert len(df) == 3
        # 37→138: posture=1（上一姿态站立）
        assert df.iloc[0]["posture"] == 1
        # 138→115: posture=0（上一姿态趴下）
        assert df.iloc[1]["posture"] == 0
        # 115→53: posture=1（上一姿态站立）
        assert df.iloc[2]["posture"] == 1

    def test_fly_posture(self, pipeline_workdir):
        """POSTURE_FLY 动作（107 跳投）→ 后续转换对 posture=2。"""
        # row1: 37 → row2: 107（fly）→ row3: 53
        df = run_cleaner(pipeline_workdir, make_rows([37, 107, 53]))
        assert df is not None
        assert len(df) == 2
        assert df.iloc[1]["posture"] == 2

    def test_initial_posture_is_standing(self, pipeline_workdir):
        """第一条转换对 posture 默认站立（1）。"""
        # row1: 37 → row2: 53（无姿态触发动作）
        df = run_cleaner(pipeline_workdir, make_rows([37, 53]))
        assert df is not None
        assert df.iloc[0]["posture"] == 1


# =============================================================================
# 8. DOWN 后姿态恢复
# =============================================================================

class TestDownRecovery:
    def test_down_then_wait_recovers_prone(self, pipeline_workdir):
        """DOWN_IDS（232 击龙枪倒地）→ 306 等待 → 姿态强转趴下（0）。

        注意：232 与 306 均属 EXCLUDE_TARGETS，作为 target 的转换被排除，
        最终只产生 306→53 一条转换，posture=0 证明 DOWN 恢复生效。
        """
        # row1: 37 → row2: 232（downed, posture=3）→ row3: 306（等待, 强制趴下 0）→ row4: 53
        df = run_cleaner(pipeline_workdir, make_rows([37, 232, 306, 53]))
        assert df is not None
        assert len(df) == 1
        assert df.iloc[0]["posture"] == 0
        assert df.iloc[0]["previous_action"] == 306
        assert df.iloc[0]["next_action"] == 53


# =============================================================================
# 9. 畸形 CSV
# =============================================================================

class TestCorruptedCsv:
    def test_corrupted_csv_skipped(self, pipeline_workdir, capsys):
        """畸形 CSV（空文件）→ 跳过，正常文件仍被处理。"""
        data_dir = pipeline_workdir / "data"
        # 正常文件
        write_combat_csv(data_dir / "fatalis_combat_data_ok.csv", make_rows([37, 53]))
        # 畸形文件（空文件 → pandas EmptyDataError）
        (data_dir / "fatalis_combat_data_bad.csv").write_text("", encoding="utf-8")

        data_cleaner.clean_combat_data()

        out_path = pipeline_workdir / "data" / "ML_Ready_Dataset.csv"
        assert out_path.exists()
        df = pd.read_csv(out_path)
        assert len(df) == 1
        assert df.iloc[0]["previous_action"] == 37
        assert df.iloc[0]["next_action"] == 53


# =============================================================================
# 10. 输出格式
# =============================================================================

class TestOutputFormat:
    def test_output_columns(self, pipeline_workdir):
        """输出列顺序为 ML 就绪数据集 7 列标准顺序。"""
        df = run_cleaner(pipeline_workdir, make_rows([37, 53]))
        assert df is not None
        assert df.columns.tolist() == [
            "distance", "relative_angle", "posture",
            "previous_action", "phase", "is_enraged", "next_action",
        ]

    def test_multiple_transitions_count(self, pipeline_workdir):
        """N 个不同动作 → N-1 个转换对（全为战斗动作时）。"""
        df = run_cleaner(pipeline_workdir, make_rows([37, 53, 81, 129, 138]))
        assert df is not None
        assert len(df) == 4


# =============================================================================
# 11. 未知动作过滤（v1.1.1 — 训练崩溃根因修复）
# =============================================================================

class TestUnknownActionFiltering:
    """未在 ACTION_DB 中定义的动作（如 117）不得作为 next_action 输出。

    根因：未知动作进入训练 label → train_test_split 无序分层时稀有类全入 test
    → LightGBM LabelEncoder "unseen labels" 崩溃。清洗阶段过滤 + 输出 warning。
    """

    def test_unknown_action_not_in_output(self, pipeline_workdir, capsys):
        """未知动作 117 不作为 next_action 输出，并打印 warning。"""
        # 37 → 117（未知）→ 53：117 的转换被过滤，37→53 保留
        df = run_cleaner(pipeline_workdir, make_rows([37, 117, 53]))
        assert df is not None
        assert "next_action" in df.columns
        assert (df["next_action"] == 117).sum() == 0
        captured = capsys.readouterr()
        assert "未知动作" in captured.out
        assert "117" in captured.out

    def test_known_action_still_in_output(self, pipeline_workdir):
        """已知动作不受影响，正常作为 next_action 输出。"""
        df = run_cleaner(pipeline_workdir, make_rows([37, 53]))
        assert df is not None
        assert (df["next_action"] == 53).sum() >= 1

    def test_multiple_unknown_actions_all_filtered(self, pipeline_workdir, capsys):
        """多个未知动作（117, 118）全部过滤，warning 列出全部 ID。"""
        df = run_cleaner(pipeline_workdir, make_rows([37, 117, 118, 53]))
        assert df is not None
        assert (df["next_action"] == 117).sum() == 0
        assert (df["next_action"] == 118).sum() == 0
        captured = capsys.readouterr()
        assert "117" in captured.out
        assert "118" in captured.out

    def test_all_unknown_actions_graceful(self, pipeline_workdir, capsys):
        """全部为未知动作 → 无有效转换，优雅返回不崩溃。"""
        # 37→117（未知）→118（未知）：两个未知动作都作为 target 被过滤
        result = run_cleaner(pipeline_workdir, make_rows([37, 117, 118]))
        assert result is None
        captured = capsys.readouterr()
        assert "未知动作" in captured.out
        assert "117" in captured.out
        assert "118" in captured.out
