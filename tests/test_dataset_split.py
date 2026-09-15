"""P1(AutoML 实验): src/model/dataset.py golden 索引测试 + source_session additive 检查。

核心保障（规划 G8 可复现）：
  1. golden：重构后 make_holdout_split 在真实 ML_Ready_Dataset.csv 上产出的
     train/holdout 索引与标签序列，与重构前 train_lgbm.py 内联实现逐位一致。
     golden 文件由重构前一次性生成（tests/golden_holdout_split.json），
     数据集本身不入库——测试按其记录的 dataset_sha256 判定是否可比，
     不匹配则跳过（CI 无真实数据时仍可运行其余检查）。
  2. source_session 列 additive：不影响 6 特征列 + label 的过滤/切分行为。
  3. 类频 >=3 过滤行为不变。
  4. 极小数据集分层降级分支。
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.model.dataset import (
    CATEGORICAL_COLS,
    FEATURE_COLS,
    LABEL_COL,
    SOURCE_SESSION_COL,
    EmptyDatasetError,
    load_ml_dataset,
    make_holdout_split,
)
from src.config.actions import ACTION_DB

GOLDEN_PATH = Path(__file__).parent / "golden_holdout_split.json"
REAL_DATASET = Path("data") / "ML_Ready_Dataset.csv"


def make_mini_dataset(rows_per_class=50, classes=None, seed=42, with_session=False):
    """确定性 mini 数据集（与 test_train_lgbm.py 同模式）。"""
    classes = classes or [37, 53, 81, 129]
    rng = np.random.default_rng(seed)
    rows = []
    for cls_id in classes:
        for _ in range(rows_per_class):
            row = {
                "distance": rng.uniform(50, 3000),
                "relative_angle": rng.uniform(-180, 180),
                "posture": rng.integers(0, 3),
                "previous_action": rng.choice(classes),
                "phase": rng.integers(1, 4),
                "is_enraged": rng.integers(0, 2),
                "next_action": cls_id,
            }
            if with_session:
                row[SOURCE_SESSION_COL] = f"fatalis_combat_data_{cls_id % 3}.csv"
            rows.append(row)
    return pd.DataFrame(rows)


# =============================================================================
# 1. golden 索引一致（真实数据集存在且 SHA 匹配时执行；否则跳过）
# =============================================================================

class TestGoldenSplit:
    def _load_golden(self):
        return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    def _dataset_usable(self, golden):
        if not REAL_DATASET.exists():
            return False
        import hashlib
        digest = hashlib.sha256(REAL_DATASET.read_bytes()).hexdigest()
        accepted = [golden["dataset_sha256"], *golden.get("dataset_sha256_aliases", [])]
        return digest in accepted

    def test_golden_file_exists_and_schema(self):
        """golden 文件存在且字段齐全（无真实数据集的 CI 也必须可校验）。"""
        golden = self._load_golden()
        for key in (
            "dataset_sha256", "filtered_rows", "filtered_classes",
            "train_rows", "holdout_rows", "train_index_sha256",
            "holdout_index", "holdout_labels", "train_labels_sha256",
        ):
            assert key in golden, f"golden 缺字段: {key}"
        assert golden["filtered_rows"] == golden["train_rows"] + golden["holdout_rows"]
        assert len(golden["holdout_index"]) == golden["holdout_rows"]
        assert len(golden["holdout_labels"]) == golden["holdout_rows"]

    def test_real_dataset_split_matches_golden(self, capsys):
        """真实数据集 + 重构后共享模块 → 索引/标签逐位等于重构前 golden。"""
        golden = self._load_golden()
        if not self._dataset_usable(golden):
            pytest.skip(
                f"真实数据集缺失或 SHA 不匹配（数据集不入库）；"
                f"golden 记录 {golden['dataset_sha256'][:12]}..."
            )

        df = load_ml_dataset(REAL_DATASET)
        assert len(df) == golden["filtered_rows"]
        assert int(df[LABEL_COL].nunique()) == golden["filtered_classes"]

        train_df, holdout_df = make_holdout_split(df, test_size=0.2, random_state=42)

        assert len(train_df) == golden["train_rows"]
        assert len(holdout_df) == golden["holdout_rows"]

        holdout_index = [int(i) for i in holdout_df.index]
        holdout_labels = [int(v) for v in holdout_df[LABEL_COL].values]
        assert holdout_index == golden["holdout_index"], "留出集索引与 golden 不一致"
        assert holdout_labels == golden["holdout_labels"], "留出集标签序列与 golden 不一致"

        train_index_sha = _sha_list([int(i) for i in train_df.index])
        train_labels_sha = _sha_list([int(v) for v in train_df[LABEL_COL].values])
        assert train_index_sha == golden["train_index_sha256"]
        assert train_labels_sha == golden["train_labels_sha256"]

        # golden 是在"无 source_session 列"的数据集上生成的——确认本测试无过滤输出
        captured = capsys.readouterr()
        assert "Removed" not in captured.out or "0 rows" not in captured.out


def _sha_list(values):
    import hashlib
    return hashlib.sha256(json.dumps(list(values)).encode()).hexdigest()


# =============================================================================
# 2. source_session 列 additive
# =============================================================================

class TestSourceSessionAdditive:
    def test_session_column_does_not_change_split(self, tmp_path):
        """带/不带 source_session 列 → 过滤行、切分索引、标签序列完全一致。"""
        df_plain = make_mini_dataset(seed=42)
        df_session = make_mini_dataset(seed=42, with_session=True)
        assert SOURCE_SESSION_COL in df_session.columns
        assert SOURCE_SESSION_COL not in df_plain.columns

        csv_plain = tmp_path / "plain.csv"
        csv_session = tmp_path / "session.csv"
        df_plain.to_csv(csv_plain, index=False)
        df_session.to_csv(csv_session, index=False)

        loaded_plain = load_ml_dataset(csv_plain)
        loaded_session = load_ml_dataset(csv_session)

        # 6 特征 + label 内容逐行一致
        cols = FEATURE_COLS + [LABEL_COL]
        pd.testing.assert_frame_equal(
            loaded_plain[cols].reset_index(drop=True),
            loaded_session[cols].reset_index(drop=True),
        )

        train_a, hold_a = make_holdout_split(loaded_plain)
        train_b, hold_b = make_holdout_split(loaded_session)
        assert list(train_a.index) == list(train_b.index)
        assert list(hold_a.index) == list(hold_b.index)
        assert list(hold_a[LABEL_COL].values) == list(hold_b[LABEL_COL].values)

    def test_session_column_survives_load(self, tmp_path):
        """load_ml_dataset 不丢弃 source_session（分组 CV 需要）。"""
        df = make_mini_dataset(seed=7, with_session=True)
        csv = tmp_path / "session.csv"
        df.to_csv(csv, index=False)
        loaded = load_ml_dataset(csv)
        assert SOURCE_SESSION_COL in loaded.columns
        assert loaded[SOURCE_SESSION_COL].notna().all()


# =============================================================================
# 3. 过滤行为不变（与原 train_lgbm 语义一致）
# =============================================================================

class TestFilterBehavior:
    def test_rare_class_filtered(self, tmp_path):
        """类频 <3 的类被过滤。"""
        df = make_mini_dataset(rows_per_class=10, classes=[37, 53, 81, 129], seed=7)
        rare_keep = df[df[LABEL_COL] == 129].head(2)
        df = pd.concat([df[df[LABEL_COL] != 129], rare_keep])
        csv = tmp_path / "rare.csv"
        df.to_csv(csv, index=False)

        loaded = load_ml_dataset(csv)
        assert 129 not in set(loaded[LABEL_COL])
        assert {37, 53, 81} <= set(loaded[LABEL_COL])

    def test_unknown_label_filtered_with_warning(self, tmp_path, capsys):
        """未知 label（不在 ACTION_DB）被过滤且打印 warning。"""
        df = make_mini_dataset(rows_per_class=10, classes=[37, 53, 81])
        unknown_rows = df.iloc[:3].copy()
        unknown_rows[LABEL_COL] = 117
        df = pd.concat([df, unknown_rows], ignore_index=True)
        csv = tmp_path / "unknown.csv"
        df.to_csv(csv, index=False)

        loaded = load_ml_dataset(csv)
        assert 117 not in set(loaded[LABEL_COL])
        captured = capsys.readouterr()
        assert "117" in captured.out
        assert "未知动作" in captured.out

    def test_all_unknown_labels_raise(self, tmp_path):
        """全为未知 label → EmptyDatasetError('unknown_label')。"""
        df = make_mini_dataset(rows_per_class=5, classes=[37, 53])
        df[LABEL_COL] = 117
        csv = tmp_path / "all_unknown.csv"
        df.to_csv(csv, index=False)

        with pytest.raises(EmptyDatasetError) as exc_info:
            load_ml_dataset(csv)
        assert exc_info.value.stage == "unknown_label"
        assert "未知动作全部被过滤" in exc_info.value.print_message
        assert "训练数据集为空" in exc_info.value.log_message

    def test_insufficient_frequency_raises(self, tmp_path):
        """所有类都 <3 条 → EmptyDatasetError('frequency')。"""
        df = make_mini_dataset(rows_per_class=2, classes=[37, 53, 81])
        csv = tmp_path / "tiny.csv"
        df.to_csv(csv, index=False)

        with pytest.raises(EmptyDatasetError) as exc_info:
            load_ml_dataset(csv)
        assert exc_info.value.stage == "frequency"
        assert "每个动作至少需要 3 条" in exc_info.value.print_message

    def test_nan_and_non_numeric_filtered(self, tmp_path, capsys):
        """NaN + 非数值 label 过滤路径照常工作。"""
        df = make_mini_dataset(rows_per_class=20, classes=[37, 53, 81])
        df.loc[df.index[:2], LABEL_COL] = float("nan")
        df = df.astype({LABEL_COL: object})
        df.loc[df.index[5], LABEL_COL] = "abc"
        csv = tmp_path / "dirty.csv"
        df.to_csv(csv, index=False)

        loaded = load_ml_dataset(csv)
        assert "abc" not in set(loaded[LABEL_COL])
        captured = capsys.readouterr()
        assert "非数值 label" in captured.out
        assert "abc" in captured.out

    def test_category_dtype_applied(self, tmp_path):
        """4 列在 load 后即为 category dtype（生产模型输入契约）。"""
        df = make_mini_dataset(seed=3)
        csv = tmp_path / "ok.csv"
        df.to_csv(csv, index=False)
        loaded = load_ml_dataset(csv)
        for col in CATEGORICAL_COLS:
            assert str(loaded[col].dtype) == "category"


# =============================================================================
# 4. 极小数据集分层降级分支
# =============================================================================

class TestStratifyFallback:
    _SMALL_CLASSES = [
        37, 53, 81, 129, 138, 49, 73, 107, 115, 119, 121, 122, 98, 99, 100, 101,
        131, 132, 133, 140, 141, 142, 143, 144, 145, 84, 85, 86, 87, 78,
    ]

    def test_small_dataset_fallback_warning(self, tmp_path, capsys):
        """30 classes × 3 rows = 90 行 → 降级非分层切分 + warning。"""
        df = make_mini_dataset(rows_per_class=3, classes=self._SMALL_CLASSES)
        csv = tmp_path / "small.csv"
        df.to_csv(csv, index=False)
        loaded = load_ml_dataset(csv)

        train_df, holdout_df = make_holdout_split(loaded, test_size=0.2, random_state=42)
        captured = capsys.readouterr()
        assert "Dataset too small for stratified split" in captured.out
        assert "test samples=18" in captured.out
        assert "classes=30" in captured.out
        assert "Fallback to non-stratified split" in captured.out
        assert len(train_df) + len(holdout_df) == len(loaded)

    def test_normal_dataset_still_stratified(self, tmp_path, capsys):
        """正常规模 → 不触发降级 warning。"""
        df = make_mini_dataset(rows_per_class=50, classes=[37, 53, 81, 129])
        csv = tmp_path / "normal.csv"
        df.to_csv(csv, index=False)
        loaded = load_ml_dataset(csv)

        make_holdout_split(loaded, test_size=0.2, random_state=42)
        captured = capsys.readouterr()
        assert "Dataset too small for stratified split" not in captured.out
