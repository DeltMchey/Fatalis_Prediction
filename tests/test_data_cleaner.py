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
        """输出列为 ML 就绪数据集标准顺序（7 原有列 + P1 新增 source_session 末位）。"""
        df = run_cleaner(pipeline_workdir, make_rows([37, 53]))
        assert df is not None
        assert df.columns.tolist() == [
            "distance", "relative_angle", "posture",
            "previous_action", "phase", "is_enraged", "next_action",
            "source_session",
        ]

    def test_source_session_column(self, pipeline_workdir):
        """P1(AutoML 实验): source_session = 源战斗 CSV 文件名（不含路径）。

        用途：StratifiedGroupKFold 分组 CV 对照（防泄漏稳健性检查）。
        """
        df = run_cleaner(pipeline_workdir, make_rows([37, 53]))
        assert df is not None
        assert (df["source_session"] == "fatalis_combat_data_raw.csv").all()

    def test_source_session_distinguishes_files(self, pipeline_workdir):
        """两个源 CSV → 各自转换对带各自 source_session 值。"""
        data_dir = pipeline_workdir / "data"
        write_combat_csv(data_dir / "fatalis_combat_data_a.csv", make_rows([37, 53]))
        write_combat_csv(data_dir / "fatalis_combat_data_b.csv", make_rows([81, 129]))

        data_cleaner.clean_combat_data()

        df = pd.read_csv(data_dir / "ML_Ready_Dataset.csv")
        sessions = set(df["source_session"])
        assert sessions == {
            "fatalis_combat_data_a.csv", "fatalis_combat_data_b.csv",
        }

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


# =============================================================================
# 12. v3(F1) 合并语义 — 防止数据集被在场 CSV 静默替换
# =============================================================================

class TestMergeSemantics:
    """事故修复：发行包不带全量 CSV 时，点一次训练不得丢弃历史会话数据。

    语义：写盘前读现有数据集，保留 source_session 不在本次 CSV 集合中的
    历史行，再追加本次新提取样本（同名会话以重新提取为准）。
    """

    def test_full_csvs_present_zero_change(self, pipeline_workdir):
        """全量 CSV 在场（=仓库 dev 环境）→ 输出与旧版逐字节零变化。

        连续两次运行（CSV 集合不变）：第二次不追加任何历史行，
        输出文件内容与第一次完全一致。
        """
        data_dir = pipeline_workdir / "data"
        write_combat_csv(data_dir / "fatalis_combat_data_a.csv",
                         make_rows([37, 53, 81]))
        write_combat_csv(data_dir / "fatalis_combat_data_b.csv",
                         make_rows([81, 129, 138]))

        data_cleaner.clean_combat_data()
        first = (data_dir / "ML_Ready_Dataset.csv").read_bytes()

        data_cleaner.clean_combat_data()
        second = (data_dir / "ML_Ready_Dataset.csv").read_bytes()

        assert first == second, "全量 CSV 在场时第二次运行输出必须零变化"
        df = pd.read_csv(data_dir / "ML_Ready_Dataset.csv")
        assert len(df) == 4          # 2 会话 × 2 转换，无重复追加

    def test_missing_csv_preserves_history_sessions(self, pipeline_workdir,
                                                    capsys):
        """历史会话 CSV 缺席（事故场景）→ 其数据从现有数据集保留。"""
        data_dir = pipeline_workdir / "data"
        csv_a = data_dir / "fatalis_combat_data_a.csv"
        csv_b = data_dir / "fatalis_combat_data_b.csv"
        write_combat_csv(csv_a, make_rows([37, 53, 81]))    # 2 转换
        write_combat_csv(csv_b, make_rows([81, 129, 138]))  # 2 转换

        data_cleaner.clean_combat_data()
        df1 = pd.read_csv(data_dir / "ML_Ready_Dataset.csv")
        assert len(df1) == 4

        # 事故场景：A 的 CSV 被清理/未随包，只新增 C
        csv_a.unlink()
        write_combat_csv(data_dir / "fatalis_combat_data_c.csv",
                         make_rows([37, 53]))               # 1 转换

        data_cleaner.clean_combat_data()
        df2 = pd.read_csv(data_dir / "ML_Ready_Dataset.csv")

        # A 的 2 行从历史数据集保留 + B 重提取 2 行 + C 新增 1 行
        assert len(df2) == 5, "历史会话 A 的数据必须被保留，不得被替换丢失"
        sessions = set(df2["source_session"])
        assert sessions == {"fatalis_combat_data_a.csv",
                            "fatalis_combat_data_b.csv",
                            "fatalis_combat_data_c.csv"}
        # A 的历史行内容与第一次运行一致（next_action 集合）
        a_rows = df2[df2["source_session"] == "fatalis_combat_data_a.csv"]
        assert sorted(a_rows["next_action"]) == sorted(
            df1[df1["source_session"] == "fatalis_combat_data_a.csv"]
            ["next_action"])
        captured = capsys.readouterr()
        assert "已保留 1 个历史会话的 2 行" in captured.out

    def test_renamed_session_reextracted_not_duplicated(self,
                                                        pipeline_workdir):
        """同名会话 CSV 在场 → 以重新提取为准（旧行替换，不重复追加）。"""
        data_dir = pipeline_workdir / "data"
        write_combat_csv(data_dir / "fatalis_combat_data_a.csv",
                         make_rows([37, 53, 81]))

        data_cleaner.clean_combat_data()
        assert len(pd.read_csv(data_dir / "ML_Ready_Dataset.csv")) == 2

        # 同名 CSV 内容变化（多一个动作）→ 重提取覆盖旧 2 行
        write_combat_csv(data_dir / "fatalis_combat_data_a.csv",
                         make_rows([37, 53, 81, 129]))
        data_cleaner.clean_combat_data()

        df = pd.read_csv(data_dir / "ML_Ready_Dataset.csv")
        assert len(df) == 3, "同名会话应以重新提取为准，不得追加重复行"

    def test_ancient_dataset_without_source_session_kept_in_backup(
            self, pipeline_workdir, capsys):
        """远古格式数据集（无 source_session 列）→ 无法合并，警告 + 备份保留。"""
        data_dir = pipeline_workdir / "data"
        # 构造无 source_session 的旧格式数据集
        pd.DataFrame({
            "distance": [100.0], "relative_angle": [0.0], "posture": [1],
            "previous_action": [37], "phase": [1], "is_enraged": [0],
            "next_action": [53],
        }).to_csv(data_dir / "ML_Ready_Dataset.csv", index=False)

        write_combat_csv(data_dir / "fatalis_combat_data_a.csv",
                         make_rows([37, 53]))
        data_cleaner.clean_combat_data()

        captured = capsys.readouterr()
        assert "无法合并历史" in captured.out
        # 旧内容保留在 .bak（两代链第一代）
        assert (data_dir / "ML_Ready_Dataset.csv.bak").exists()
        df = pd.read_csv(data_dir / "ML_Ready_Dataset.csv")
        assert len(df) == 1  # 仅本次提取

    def test_backup_chain_and_same_sha_skip(self, pipeline_workdir):
        """v3(F3) 数据集侧备份链：内容变化推进两代；内容相同跳过轮换。"""
        data_dir = pipeline_workdir / "data"
        dataset = data_dir / "ML_Ready_Dataset.csv"
        bak = data_dir / "ML_Ready_Dataset.csv.bak"
        bak2 = data_dir / "ML_Ready_Dataset.csv.bak2"

        csv_a = data_dir / "fatalis_combat_data_a.csv"
        write_combat_csv(csv_a, make_rows([37, 53]))
        data_cleaner.clean_combat_data()
        assert dataset.exists() and not bak.exists()   # 首写无备份

        # 内容变化（加动作）→ .bak 推进
        write_combat_csv(csv_a, make_rows([37, 53, 81]))
        data_cleaner.clean_combat_data()
        v1 = dataset.read_bytes()
        assert bak.exists()
        first_bak = bak.read_bytes()

        # 数据未变 → 同 sha 跳过：.bak 不被推进（自吞防护）
        data_cleaner.clean_combat_data()
        assert dataset.read_bytes() == v1
        assert bak.read_bytes() == first_bak
        assert not bak2.exists()
