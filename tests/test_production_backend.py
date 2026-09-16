"""P8(AutoML 一键训练接入): production_backend 单元测试 — Run B 正式后端。

覆盖（mini 数据集，确定性，秒级）：
  - FLAML auto_augment 镜像正确性（稀有类整行复制 → 行数与分布断言）
  - flaml_data_prep 确定性与标签编码值域
  - 端到端训练：产物结构 = Pipeline[FeatureBuilder, LabelDecodedEstimator(
    XGBClassifier(n_jobs=1))]、classes_ = 原始动作 ID、图表/sidecar 产出
  - 泄漏防护：pipeline 内 FeatureBuilder 的分箱边缘 = 仅 train_80 拟合值
    （≠ 全量数据拟合值）
  - 确定性：同数据两次训练 predict_proba 逐位一致
  - .bak 轮换；缺数据集/空数据集优雅返回且不覆盖旧模型
  - ActionPredictor 消费契约（load + predict）
"""

import json
import os

import joblib
import numpy as np
import pandas as pd

import src.model.production_backend as pb
from src.model.features import FeatureBuilder
from tests.test_train_lgbm import make_mini_dataset, write_mini_dataset

FEATURES_12 = list(pb.FEATURE_NAME_ZH)  # 12 列名（6 基础 + 6 派生）


# =============================================================================
# 1. FLAML auto_augment 镜像（纯函数）
# =============================================================================

def _xy_for_counts(counts: dict) -> tuple[pd.DataFrame, pd.Series]:
    """按 {label: 行数} 构造确定性特征/标签对。"""
    rng = np.random.default_rng(7)
    rows, labels = [], []
    for label, n in counts.items():
        for _ in range(n):
            rows.append({"distance": rng.uniform(0, 1000),
                         "relative_angle": rng.uniform(-180, 180),
                         "posture": int(rng.integers(0, 3)),
                         "previous_action": int(label),
                         "phase": int(rng.integers(1, 4)),
                         "is_enraged": int(rng.integers(0, 2))})
            labels.append(label)
    return pd.DataFrame(rows), pd.Series(labels)


class TestFlamlAutoAugment:
    def test_rare_class_replicated_to_threshold(self):
        """计数 5 的稀有类被整行复制至 ≥20（5→25），充足类不动。"""
        X, y = _xy_for_counts({37: 5, 53: 30, 81: 21})
        X_aug, y_aug = pb.flaml_auto_augment(X, y)

        vc = y_aug.value_counts()
        assert len(X_aug) == len(y_aug)
        # while n<20: 追加整块(5 行)——n: 5→10→15→20 退出 → 4 块 × 5 = 恰好 20
        assert vc[37] == 20, f"稀有类应复制到 ≥20（5→20），实际 {vc[37]}"
        assert vc[53] == 30 and vc[81] == 21
        # 分布断言：追加行与原行内容一致（该类的整块复制）
        orig_37 = X[y == 37].reset_index(drop=True)
        aug_37 = X_aug[y_aug == 37].reset_index(drop=True)
        pd.testing.assert_frame_equal(
            aug_37.iloc[:5], orig_37,
            check_dtype=False)  # 首 5 行 = 原始行（原行在前）
        pd.testing.assert_frame_equal(aug_37.iloc[5:10].reset_index(drop=True),
                                      orig_37)  # 第一批副本 = 原始行整块

    def test_noop_when_all_classes_sufficient(self):
        """全部类别 ≥20 → 行集与顺序完全不变。"""
        X, y = _xy_for_counts({37: 20, 53: 25})
        X_aug, y_aug = pb.flaml_auto_augment(X, y)
        pd.testing.assert_frame_equal(X_aug.reset_index(drop=True),
                                      X.reset_index(drop=True))
        assert list(y_aug) == list(y)

    def test_augment_exact_rowcount_math(self):
        """行数复刻 FLAML 语义：while n < 20 整块追加。"""
        X, y = _xy_for_counts({37: 7, 53: 40})       # 7 → 7*3=21（整块追加 2 次）
        _, y_aug = pb.flaml_auto_augment(X, y)
        assert int((y_aug == 37).sum()) == 21
        assert len(y_aug) == 61

    def test_threshold_kwarg(self):
        """rare_threshold 参数生效（自定义阈值）。"""
        X, y = _xy_for_counts({37: 3, 53: 40})
        _, y_aug = pb.flaml_auto_augment(X, y, rare_threshold=5)
        assert int((y_aug == 37).sum()) == 6          # 3 → 6 ≥ 5


class TestFlamlDataPrep:
    def test_deterministic_and_encoded(self):
        """同输入两次准备 → 特征/标签逐位一致；标签编码 ∈ [0, n)。"""
        X, y = _xy_for_counts({37: 5, 53: 30, 81: 25})
        X1, y1 = pb.flaml_data_prep(X, y)
        X2, y2 = pb.flaml_data_prep(X, y)
        pd.testing.assert_frame_equal(X1, X2)
        assert np.array_equal(y1, y2)
        assert sorted(np.unique(y1)) == [0, 1, 2]

    def test_index_reset(self):
        """shuffle 后索引重置为 0..n-1（xgboost 输入契约）。"""
        X, y = _xy_for_counts({37: 6, 53: 30})
        X_prep, _ = pb.flaml_data_prep(X, y)
        assert list(X_prep.index) == list(range(len(X_prep)))


# =============================================================================
# 2. 端到端 mini 训练：产物结构与 sidecar
# =============================================================================

class TestEndToEndArtifacts:
    def test_train_produces_expected_structure_and_sidecar(self,
                                                           pipeline_workdir):
        """完整训练 → 产物结构与现行采纳模型同构，sidecar 字段齐全。"""
        df = make_mini_dataset()
        write_mini_dataset(pipeline_workdir, df)

        result = pb.train_runb_backend()
        assert isinstance(result, dict)

        model_path = pipeline_workdir / "models" / "fatalis_ai_model.pkl"
        assert model_path.exists() and model_path.stat().st_size > 0

        model = joblib.load(model_path)
        assert [name for name, _ in model.steps] == ["features", "estimator"]
        fb, wrapped = model.steps[0][1], model.steps[1][1]

        # estimator 层：LabelDecodedEstimator(XGBClassifier(n_jobs=1))
        assert type(wrapped).__name__ == "LabelDecodedEstimator"
        inner = wrapped.estimator
        assert type(inner).__name__ == "XGBClassifier"
        assert inner.n_jobs == 1
        assert inner.n_estimators == pb.RUNB_BEST_CONFIG["n_estimators"]
        assert inner.objective == "multi:softprob"
        assert getattr(inner, "random_state", None) is None  # FLAML 口径

        # classes_ = 原始动作 ID（升序）；特征 12 列
        assert [int(c) for c in model.classes_] == sorted(df["next_action"].unique())
        assert fb.get_feature_names_out() == FEATURES_12

        # 图表
        png = pipeline_workdir / "models" / "feature_importance.png"
        assert png.exists() and png.stat().st_size > 0

        # sidecar 字段
        sidecar = json.loads(
            (pipeline_workdir / "models" / "fatalis_ai_model.pkl.meta.json")
            .read_text(encoding="utf-8"))
        assert sidecar["backend"] == "runb_config"
        assert sidecar["config"]["n_jobs"] == 1
        assert sidecar["config"]["n_estimators"] == 190
        assert sidecar["n_classes"] == df["next_action"].nunique()
        assert sidecar["data"]["dataset_sha256"] == pb._sha256_file(
            pipeline_workdir / "data" / "ML_Ready_Dataset.csv")
        assert "trained_at" in sidecar and "source" in sidecar
        assert sidecar["rollback"]["rotated"] is False
        # metrics 在 [0,1]
        assert 0.0 <= sidecar["metrics"]["top1"] <= 1.0
        assert 0.0 <= sidecar["metrics"]["top3"] <= 1.0

    def test_bak_rotation(self, pipeline_workdir):
        """已有旧模型 → 写前轮换 .bak，sidecar 记录 rotated。"""
        write_mini_dataset(pipeline_workdir, make_mini_dataset())
        old = pipeline_workdir / "models" / "fatalis_ai_model.pkl"
        old.write_bytes(b"OLD_MODEL_SENTINEL")

        result = pb.train_runb_backend()
        assert result["rollback"]["rotated"] is True
        assert ((pipeline_workdir / "models" / "fatalis_ai_model.pkl.bak")
                .read_bytes()) == b"OLD_MODEL_SENTINEL"
        model = joblib.load(old)  # 新模型可加载
        assert hasattr(model, "predict_proba")


# =============================================================================
# 3. 泄漏防护：FeatureBuilder 仅在 train_80 上 fit
# =============================================================================

class TestLeakGuard:
    def test_bin_edges_fit_on_train_only(self, pipeline_workdir):
        """pipeline 内分箱边缘 = 仅 train_80 拟合值，≠ 全量数据拟合值。"""
        from src.model.dataset import load_ml_dataset, make_holdout_split

        csv = write_mini_dataset(
            pipeline_workdir,
            make_mini_dataset(rows_per_class=60, seed=11))
        pb.train_runb_backend()

        model = joblib.load(
            pipeline_workdir / "models" / "fatalis_ai_model.pkl")

        df = load_ml_dataset(csv)
        train_df, _ = make_holdout_split(df, test_size=0.2, random_state=42)

        fb_train_only = FeatureBuilder(derived=True, n_bins=8).fit(train_df)
        fb_full = FeatureBuilder(derived=True, n_bins=8).fit(df)

        np.testing.assert_array_equal(
            model.steps[0][1].bin_edges_, fb_train_only.bin_edges_)
        assert not np.array_equal(
            model.steps[0][1].bin_edges_, fb_full.bin_edges_), (
            "分箱边缘与全量拟合一致 → FeatureBuilder 泄漏了留出集")

    def test_freq_table_fit_on_train_only(self, pipeline_workdir):
        """prev_action 频次表同样仅来自 train_80。"""
        from src.model.dataset import load_ml_dataset, make_holdout_split

        csv = write_mini_dataset(
            pipeline_workdir,
            make_mini_dataset(rows_per_class=60, seed=13))
        pb.train_runb_backend()

        model = joblib.load(
            pipeline_workdir / "models" / "fatalis_ai_model.pkl")
        df = load_ml_dataset(csv)
        train_df, _ = make_holdout_split(df, test_size=0.2, random_state=42)
        fb_train_only = FeatureBuilder(derived=True, n_bins=8).fit(train_df)

        assert model.steps[0][1].freq_table_ == fb_train_only.freq_table_


# =============================================================================
# 4. 确定性：同数据两次训练 → predict_proba 逐位一致
# =============================================================================

class TestDeterminism:
    def test_two_runs_bitwise_identical(self, pipeline_workdir):
        """同数据集两次完整训练 → 固定探针集 predict_proba 逐位一致。"""
        write_mini_dataset(pipeline_workdir, make_mini_dataset(seed=21))

        probe = pd.DataFrame([
            {"distance": 500.0, "relative_angle": 30.0, "posture": 1,
             "previous_action": 37, "phase": 1, "is_enraged": 0},
            {"distance": 1800.0, "relative_angle": -120.0, "posture": 2,
             "previous_action": 53, "phase": 3, "is_enraged": 1},
        ])
        for col in ("posture", "previous_action", "phase", "is_enraged"):
            probe[col] = probe[col].astype("category")

        pb.train_runb_backend()
        m1 = joblib.load(
            pipeline_workdir / "models" / "fatalis_ai_model.pkl")
        p1 = np.asarray(m1.predict_proba(probe))

        # 清空产物后重训（保留数据集）
        models_dir = pipeline_workdir / "models"
        for f in models_dir.iterdir():
            f.unlink()
        pb.train_runb_backend()
        m2 = joblib.load(models_dir / "fatalis_ai_model.pkl")
        p2 = np.asarray(m2.predict_proba(probe))

        assert np.array_equal(p1, p2), "两次训练预测不一致（确定性被破坏）"


# =============================================================================
# 5. 失败路径：缺数据集 / 空数据集 → 优雅返回，不覆盖旧模型
# =============================================================================

class TestFailurePaths:
    def test_missing_dataset_no_overwrite(self, pipeline_workdir, caplog):
        """数据集缺失 → 返回 None，旧模型不被覆盖。"""
        import logging
        old = pipeline_workdir / "models" / "fatalis_ai_model.pkl"
        old.write_bytes(b"OLD")

        with caplog.at_level(logging.ERROR, logger="BlackDragon"):
            result = pb.train_runb_backend()
        assert result is None
        assert old.read_bytes() == b"OLD"
        assert any("找不到" in r.message for r in caplog.records
                   if r.levelno >= logging.ERROR)

    def test_empty_dataset_no_overwrite(self, pipeline_workdir, capsys):
        """全部 label 未知 → EmptyDatasetError 路径优雅返回。"""
        df = make_mini_dataset(rows_per_class=10, classes=[37, 53])
        df["next_action"] = 117  # 全部未知 → 过滤后为空
        write_mini_dataset(pipeline_workdir, df)
        old = pipeline_workdir / "models" / "fatalis_ai_model.pkl"
        old.write_bytes(b"OLD")

        result = pb.train_runb_backend()
        assert result is None
        assert old.read_bytes() == b"OLD"
        captured = capsys.readouterr()
        assert "未知动作" in captured.out


# =============================================================================
# 6. ActionPredictor 消费契约（load + predict）
# =============================================================================

class TestPredictorContract:
    def test_actionpredictor_loads_and_predicts(self, pipeline_workdir):
        """产物可被 ActionPredictor 零改动加载并推理。"""
        from src.model.predictor import ActionPredictor

        write_mini_dataset(pipeline_workdir, make_mini_dataset())
        pb.train_runb_backend()

        predictor = ActionPredictor(str(
            pipeline_workdir / "models" / "fatalis_ai_model.pkl"))
        assert predictor.is_loaded
        result = predictor.predict(500.0, 30.0, 1, 37, 1, 0)
        assert isinstance(result, list)
        assert len(result) <= 3
        valid_classes = {37, 53, 81, 129}
        for class_id, prob in result:
            assert int(class_id) in valid_classes
            assert 0.0 <= prob <= 1.0
