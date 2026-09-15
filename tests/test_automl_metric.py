"""P4(AutoML 实验): 自定义 top-3 metric + custom_hp 约束表测试。

覆盖（规划第 6 节）：
  ① top-3 metric 与手算对照（构造已知概率矩阵）
  ② 返回契约（flaml 2.6.0 实际契约：二元组 (val_loss, metrics_dict)，
     metrics_dict 含 pred_time —— 规划文档中的三元组契约已按代码现实修正）
  ③ custom_hp 约束表加载与上限校验（lgbm ≤400/127/9；xgb ≤400/8；rf/et ≤500/16）
  ④ FLAML AutoML(metric=...) 接受性（微预算真实验证）
"""

import json
from pathlib import Path

import numpy as np
import pytest

import importlib.util

_SCRIPT = Path(__file__).parents[1] / "scripts" / "train_automl.py"
_spec = importlib.util.spec_from_file_location("train_automl_mod", _SCRIPT)
train_automl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(train_automl)

CONFIG_PATH = Path(__file__).parents[1] / "configs" / "automl_experiment.json"


class StubEstimator:
    """固定概率矩阵 stub（predict_proba/classes_）。"""

    def __init__(self, probs, classes):
        self._probs = np.asarray(probs, dtype=float)
        self.classes_ = np.asarray(classes)

    def predict_proba(self, X):
        return self._probs.copy()


class TestTop3Metric:
    def test_handcheck_against_manual(self):
        """classes=[37,53,81,129]：
        r0 [.50,.30,.15,.05] y=37 → top3 命中（37 top1）
        r1 [.05,.55,.30,.10] y=81 → 命中（81 第 2）
        r2 [.10,.20,.60,.10] y=129→ 未命中（129 第 3/4 —— .10 平局，
           argsort 稳定序取后位；显式构造无双平局避免歧义：改 .09）
        r3 [.30,.10,.10,.50] y=53 → 命中（53 第 3 —— .10/.10 平局改无平局）
        → 保守构造无平局矩阵：top3=3/4, top1=2/4
        """
        probs = [
            [.50, .30, .15, .05],
            [.05, .55, .30, .10],
            [.40, .20, .25, .15],   # top3={40?}: argsort → {c0,c2,c1} 不含 c3
            [.30, .12, .08, .50],
        ]
        y = [37, 81, 129, 53]
        est = StubEstimator(probs, [37, 53, 81, 129])

        loss, metrics = train_automl.top3_metric(None, y, est, None)

        # 手算：r0 y=37 ∈ top3{37,53,81} ✓；r1 y=81 ∈ {53,81,129} ✓；
        # r2 probs [.40,.20,.25,.15] → top3={c0,c2,c1}={37,81,53}，y=129 ✗；
        # r3 → top3={129,37,53}，y=53 ✓ → top3=3/4；top1: r0 ✓, r1 ✗(53), r2 ✗(37),
        # r3 ✗(129) → top1=1/4
        assert metrics["top3_acc"] == pytest.approx(3 / 4)
        assert metrics["top1_acc"] == pytest.approx(1 / 4)
        assert loss == pytest.approx(1 - 3 / 4)

    def test_return_contract(self):
        """flaml 2.6.0 契约：二元组 (val_loss, metrics_dict)，dict 含 pred_time。"""
        est = StubEstimator([[.5, .3, .2]], [37, 53, 81])
        result = train_automl.top3_metric(None, [37], est, None)
        assert isinstance(result, tuple) and len(result) == 2
        loss, metrics = result
        assert isinstance(metrics, dict)
        assert "pred_time" in metrics
        assert "top3_acc" in metrics and "top1_acc" in metrics
        assert np.isfinite(loss) and np.isfinite(metrics["pred_time"])
        assert 0.0 <= metrics["top3_acc"] <= 1.0

    def test_loss_equals_one_minus_top3(self):
        est = StubEstimator([[.2, .5, .3], [.1, .2, .7]], [37, 53, 81])
        loss, metrics = train_automl.top3_metric(None, [37, 81], est, None)
        assert loss == pytest.approx(1.0 - metrics["top3_acc"])

    def test_accepts_extra_positional_args(self):
        """FLAML 实际以 11 个位置参数调用——stub 额外参数被 *args 吸收。"""
        est = StubEstimator([[.5, .3, .2]], [37, 53, 81])
        loss, metrics = train_automl.top3_metric(
            None, [37], est, None,
            "X_train", "y_train", None, None, {"hl": 32}, None, None,
        )
        assert metrics["top3_acc"] == pytest.approx(1.0)


class TestCustomHp:
    def test_config_loads_and_decodes(self):
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        hp = train_automl.build_custom_hp(config["custom_hp"])
        assert set(hp.keys()) == {"lgbm", "xgboost", "rf", "extra_tree", "mlp"}

        # lgbm ≤400 树 / 127 叶 / 深 9
        d = hp["lgbm"]["n_estimators"]["domain"]
        assert d.upper <= 400 and d.lower >= 1
        d = hp["lgbm"]["num_leaves"]["domain"]
        assert d.upper <= 127
        d = hp["lgbm"]["max_depth"]["domain"]
        assert d.upper <= 9

        # xgboost ≤400 / 深 8
        assert hp["xgboost"]["n_estimators"]["domain"].upper <= 400
        assert hp["xgboost"]["max_depth"]["domain"].upper <= 8

        # rf / extra_tree ≤500 / 深 16
        assert hp["rf"]["n_estimators"]["domain"].upper <= 500
        assert hp["rf"]["max_depth"]["domain"].upper <= 16
        assert hp["extra_tree"]["n_estimators"]["domain"].upper <= 500
        assert hp["extra_tree"]["max_depth"]["domain"].upper <= 16

        # class_weight 固定 balanced（规划 3.4）
        assert hp["lgbm"]["class_weight"]["domain"] == "balanced"
        assert hp["rf"]["class_weight"]["domain"] == "balanced"

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValueError, match="未知 custom_hp kind"):
            train_automl.build_custom_hp({"lgbm": {"n_estimators": {"kind": "bogus"}}})

    def test_fixed_value_passthrough(self):
        hp = train_automl.build_custom_hp({"rf": {"class_weight": {"fixed": "balanced"}}})
        assert hp["rf"]["class_weight"]["domain"] == "balanced"


class TestFlamlMetricAcceptance:
    def test_automl_accepts_custom_metric(self):
        """微预算真实验证：AutoML(metric=top3_metric) 可被接受并完成搜索。"""
        pytest.importorskip("flaml")
        from flaml import AutoML

        rng = np.random.default_rng(3)
        n = 240
        X = pd.DataFrame(rng.normal(size=(n, 4)), columns=["f0", "f1", "f2", "f3"])
        y = rng.integers(0, 4, n)

        automl = AutoML()
        automl.fit(
            X, y, task="classification", metric=train_automl.top3_metric,
            time_budget=5, estimator_list=["lgbm"], eval_method="cv",
            split_type="stratified", n_splits=2, seed=42, verbose=0,
            log_file_name="",
        )
        assert automl.best_estimator == "lgbm"
        # loss = 1 - top3（同一概率口径）
        assert automl.best_loss < 1.0


import pandas as pd  # noqa: E402 — TestFlamlMetricAcceptance 使用
