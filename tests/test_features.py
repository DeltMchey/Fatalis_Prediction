"""P4(AutoML 实验): src/model/features.py 测试 — 编码/派生正确性/防泄漏。

覆盖（规划第 6 节）：
  ① sin/cos 周期正确（±180° 连续）
  ② 分箱边缘/频次表 fit 于 train、transform 于新数据（防泄漏）
  ③ 词表确定（枚举全集固定、未见值 → -1 哨兵）
  ④ 输入 category dtype DataFrame 契约
  ⑤ fit/transform 分离 + 确定性
"""

import numpy as np
import pandas as np_pd  # noqa: F401 — 保持与仓库其它测试一致的导入习惯
import pandas as pd
import pytest

from src.model.features import (
    DERIVED_COLS,
    ENRAGE_VOCAB,
    FEATURE_COLS,
    PHASE_VOCAB,
    POSTURE_VOCAB,
    PREV_ACTION_VOCAB,
    SENTINEL_CODE,
    FeatureBuilder,
)
from src.config.actions import ACTION_DB


def make_df(n=200, seed=42, with_session=False):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "distance": rng.uniform(50, 3000, n),
        "relative_angle": rng.uniform(-180, 180, n),
        "posture": rng.integers(0, 3, n),
        "previous_action": rng.choice(PREV_ACTION_VOCAB, n),
        "phase": rng.integers(1, 4, n),
        "is_enraged": rng.integers(0, 2, n),
        "next_action": rng.choice(PREV_ACTION_VOCAB, n),
    })
    if with_session:
        df["source_session"] = "s1.csv"
    return df


def as_category(df):
    df = df.copy()
    for col in ("posture", "previous_action", "phase", "is_enraged"):
        df[col] = df[col].astype("category")
    return df


# =============================================================================
# 1. Run A：数值编码
# =============================================================================

class TestRunAEncoding:
    def test_output_columns_and_dtypes(self):
        df = make_df()
        fb = FeatureBuilder(derived=False)
        out = fb.fit_transform(df)
        assert out.columns.tolist() == FEATURE_COLS
        for col in out.columns:
            assert str(out[col].dtype) in ("int64", "float64"), f"{col} 非数值: {out[col].dtype}"

    def test_category_dtype_input_same_as_int(self):
        """category dtype 与 int 输入 → 输出逐位一致（生产推理契约）。"""
        df = make_df(seed=7)
        out_int = FeatureBuilder(derived=False).fit_transform(df)
        out_cat = FeatureBuilder(derived=False).fit_transform(as_category(df))
        for col in FEATURE_COLS:
            assert out_int[col].tolist() == out_cat[col].tolist()

    def test_unseen_values_get_sentinel(self):
        """未见 posture/phase/previous_action → -1 哨兵码，不崩溃。"""
        df = make_df(n=10, seed=1)
        df.loc[0, "posture"] = 99
        df.loc[1, "phase"] = 9
        df.loc[2, "previous_action"] = 12345
        df.loc[3, "is_enraged"] = 7
        out = FeatureBuilder(derived=False).fit_transform(df)
        assert out.loc[0, "posture"] == SENTINEL_CODE
        assert out.loc[1, "phase"] == SENTINEL_CODE
        assert out.loc[2, "previous_action"] == SENTINEL_CODE
        assert out.loc[3, "is_enraged"] == SENTINEL_CODE

    def test_known_values_map_deterministically(self):
        """已知值 → 词表索引码（与数据无关的固定映射）。"""
        df = make_df(n=5, seed=2)
        df.loc[0, "phase"] = 1
        out = FeatureBuilder(derived=False).fit_transform(df)
        assert out.loc[0, "phase"] == PHASE_VOCAB.index(1)
        df.loc[1, "previous_action"] = PREV_ACTION_VOCAB[0]
        out = FeatureBuilder(derived=False).fit_transform(df)
        assert out.loc[1, "previous_action"] == 0

    def test_vocab_is_fixed_and_complete(self):
        """词表 = 枚举 + ACTION_DB 全集（不依赖数据）。"""
        assert POSTURE_VOCAB == [0, 1, 2, 3, 4]
        assert PHASE_VOCAB == [1, 2, 3]
        assert ENRAGE_VOCAB == [0, 1]
        assert PREV_ACTION_VOCAB == sorted(set(ACTION_DB))


# =============================================================================
# 2. Run B：派生特征
# =============================================================================

class TestDerivedFeatures:
    def test_run_b_columns(self):
        df = make_df()
        out = FeatureBuilder(derived=True, n_bins=8).fit_transform(df)
        assert out.columns.tolist() == FEATURE_COLS + DERIVED_COLS
        assert len(out) == len(df)

    def test_angle_sin_cos_periodicity(self):
        """±180° 断裂消除：180 与 -180 的 sin/cos 相同；90 与 -90 的 sin 相反。"""
        df = pd.DataFrame({
            "distance": [100.0, 100.0, 100.0, 100.0],
            "relative_angle": [180.0, -180.0, 90.0, -90.0],
            "posture": [1, 1, 1, 1],
            "previous_action": [37, 37, 37, 37],
            "phase": [1, 1, 1, 1],
            "is_enraged": [0, 0, 0, 0],
        })
        out = FeatureBuilder(derived=True).fit_transform(df)
        assert out.loc[0, "angle_sin"] == pytest.approx(out.loc[1, "angle_sin"], abs=1e-12)
        assert out.loc[0, "angle_cos"] == pytest.approx(out.loc[1, "angle_cos"], abs=1e-12)
        assert out.loc[0, "angle_sin"] == pytest.approx(0.0, abs=1e-12)
        assert out.loc[0, "angle_cos"] == pytest.approx(-1.0)
        assert out.loc[2, "angle_sin"] == pytest.approx(1.0)
        assert out.loc[3, "angle_sin"] == pytest.approx(-1.0)

    def test_distance_bin_edges_from_train(self):
        """分箱边缘只在 train 上 fit：train 范围外的新值仍映射到边缘箱。"""
        train = pd.DataFrame({
            "distance": np.linspace(100, 1000, 50),
            "relative_angle": [0.0] * 50,
            "posture": [1] * 50, "previous_action": [37] * 50,
            "phase": [1] * 50, "is_enraged": [0] * 50,
        })
        fb = FeatureBuilder(derived=True, n_bins=4).fit(train)
        assert hasattr(fb, "bin_edges_")
        assert len(fb.bin_edges_) >= 1

        new = train.iloc[:3].copy()
        new["distance"] = [-500.0, 500.0, 9999.0]
        out = fb.transform(new)
        assert out.loc[0, "distance_bin"] == 0        # 低于最小边缘
        assert out.loc[2, "distance_bin"] == len(fb.bin_edges_)  # 高于最大边缘

    def test_prev_action_freq_fit_on_train_only(self):
        """频次表只在 train 上 fit：同一行在不同 fit 的 builder 下频次不同（防泄漏）。"""
        train_a = make_df(n=100, seed=1)
        train_b = make_df(n=100, seed=2)
        probe = make_df(n=1, seed=3)
        probe.loc[0, "previous_action"] = 37

        fb_a = FeatureBuilder(derived=True).fit(train_a)
        fb_b = FeatureBuilder(derived=True).fit(train_b)
        fa = fb_a.transform(probe).loc[0, "prev_action_freq"]
        fbb = fb_b.transform(probe).loc[0, "prev_action_freq"]
        assert fa != fbb, "不同 train 的频次表对同一行给出相同频次——疑似泄漏了 transform 侧数据"

    def test_freq_of_unseen_action_is_zero(self):
        train = make_df(n=50, seed=4)
        fb = FeatureBuilder(derived=True).fit(train)
        probe = train.iloc[:1].copy()
        probe["previous_action"] = 12345
        out = fb.transform(probe)
        assert out.loc[0, "prev_action_freq"] == 0.0

    def test_interaction_and_product(self):
        df = pd.DataFrame({
            "distance": [1000.0], "relative_angle": [30.0],
            "posture": [2], "previous_action": [37],
            "phase": [3], "is_enraged": [1],
        })
        out = FeatureBuilder(derived=True).fit_transform(df)
        assert out.loc[0, "distance_x_enraged"] == pytest.approx(1000.0)
        # posture_x_phase = posture_code * len(PHASE_VOCAB) + phase_code
        assert out.loc[0, "posture_x_phase"] == 2 * len(PHASE_VOCAB) + 2


# =============================================================================
# 3. fit/transform 分离 + 确定性
# =============================================================================

class TestFitTransformContract:
    def test_transform_before_fit_raises_for_derived(self):
        fb = FeatureBuilder(derived=True)
        with pytest.raises(AttributeError):
            fb.transform(make_df(n=5))

    def test_deterministic_output(self):
        df = make_df(seed=11)
        out1 = FeatureBuilder(derived=True).fit_transform(df)
        out2 = FeatureBuilder(derived=True).fit_transform(df)
        pd.testing.assert_frame_equal(out1, out2)

    def test_extra_columns_ignored_or_rejected(self):
        """缺列 → 明确报错；多列（如 source_session）不影响输出。"""
        df = make_df(with_session=True)
        out = FeatureBuilder(derived=False).fit_transform(df)
        assert out.columns.tolist() == FEATURE_COLS

        bad = make_df(n=5).drop(columns=["phase"])
        with pytest.raises(ValueError, match="缺列"):
            FeatureBuilder(derived=False).fit_transform(bad)

    def test_sklearn_get_params_roundtrip(self):
        fb = FeatureBuilder(derived=True, n_bins=6)
        params = fb.get_params()
        assert params["derived"] is True
        assert params["n_bins"] == 6
