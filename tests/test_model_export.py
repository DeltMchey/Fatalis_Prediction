"""P5(AutoML 实验): 模型导出与兼容性验证测试。

覆盖（规划第 6 节 test_model_export）：
  ① 子进程屏蔽 flaml 后 load + 推理成功（5 家族）
  ② 各家族 mini stub 过 ActionPredictor.predict() 兼容断言
     （classes_ 存在、概率合法、shape 正确）
  ③ 同输入多次调用输出逐位一致（lgbm 1000 次）
  ④ 哨兵类别输入（未见 posture/previous_action）不崩溃、概率有限
  ⑤ 导出路径不含生产文件名（生产路径保护回归）
  ⑥ 提取函数契约（wrapper.estimator → native）
"""

import importlib.util
import json
import sys
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest
import xgboost as xgb
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder

from src.config.actions import ACTION_DB
from src.model.features import FeatureBuilder
from src.model.label_decode import LabelDecodedEstimator
from src.model.mlp_learner import CAT_CODE_COLS, NUM_COLS, BalancedMLPClassifier
from src.model.predictor import ActionPredictor

_SCRIPT = Path(__file__).parents[1] / "scripts" / "export_model.py"
_spec = importlib.util.spec_from_file_location("export_model_mod", _SCRIPT)
export_model = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export_model)

FAMILIES = ["lgbm", "xgboost", "rf", "extra_trees", "mlp"]


def make_mini_dataset(rows_per_class=40, classes=None, seed=42):
    classes = classes or [37, 53, 81, 129]
    rng = np.random.default_rng(seed)
    rows = []
    for cls_id in classes:
        for _ in range(rows_per_class):
            rows.append({
                "distance": rng.uniform(50, 3000),
                "relative_angle": rng.uniform(-180, 180),
                "posture": rng.integers(0, 3),
                "previous_action": rng.choice(classes),
                "phase": rng.integers(1, 4),
                "is_enraged": rng.integers(0, 2),
                "next_action": cls_id,
            })
    return pd.DataFrame(rows)


def train_family_estimator(family, X_num: pd.DataFrame, y):
    """按家族训练 mini 原生 estimator（mlp 为 wrapper 内部同构的 native pipeline）。"""
    if family == "lgbm":
        model = lgb.LGBMClassifier(
            objective="multiclass", num_leaves=7, max_depth=3,
            n_estimators=12, random_state=42, n_jobs=1, verbose=-1,
        )
        model.fit(X_num, y)
        return model
    if family == "xgboost":
        model = xgb.XGBClassifier(
            n_estimators=15, max_depth=3, random_state=42, n_jobs=1,
        )
        model.fit(X_num, y)
        return model
    if family == "rf":
        model = RandomForestClassifier(
            n_estimators=20, max_depth=5, random_state=42, n_jobs=1,
        )
        model.fit(X_num, y)
        return model
    if family == "extra_trees":
        model = ExtraTreesClassifier(
            n_estimators=20, max_depth=5, random_state=42, n_jobs=1,
        )
        model.fit(X_num, y)
        return model
    if family == "mlp":
        from sklearn.compose import ColumnTransformer
        from sklearn.preprocessing import OneHotEncoder, StandardScaler

        pipeline = Pipeline([
            ("prep", ColumnTransformer([
                ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                 [c for c in CAT_CODE_COLS if c in X_num.columns]),
                ("num", StandardScaler(), [c for c in NUM_COLS if c in X_num.columns]),
            ])),
            ("mlp", BalancedMLPClassifier(
                hidden_layer_sizes=(16,), max_iter=80, random_state=42,
            )),
        ])
        pipeline.fit(X_num, y)
        return pipeline
    raise ValueError(family)


@pytest.fixture(scope="module")
def exported_five_families(tmp_path_factory):
    """训练 + 导出 5 家族 mini stub（镜像 FLAML 现实：y 经 LabelEncoder 编码）。

    FLAML auto_augment 对分类任务统一编码 y（xgboost sklearn API 硬性要求
    [0,n) 标签），提取物 classes_ 为编码值；导出经 build_export_pipeline
    的 train_labels 参数自动还原。
    """
    out_dir = tmp_path_factory.mktemp("models")
    df = make_mini_dataset()
    fb = FeatureBuilder(derived=False)
    X_num = fb.fit_transform(df)
    y = df["next_action"]
    train_labels = sorted(int(v) for v in y.unique())
    y_enc = LabelEncoder().fit_transform(y)  # FLAML 等价编码

    exported = {}
    for family in FAMILIES:
        est = train_family_estimator(family, X_num, y_enc)
        pipeline = export_model.build_export_pipeline(fb, est, train_labels=train_labels)
        path = out_dir / f"fatalis_ai_model_automl_{family}.pkl"
        joblib.dump(pipeline, path)
        exported[family] = path
    return exported, df


def probe_row(**overrides):
    row = {
        "distance": 500.0, "relative_angle": 30.0, "posture": 1,
        "previous_action": 37, "phase": 1, "is_enraged": 0,
    }
    row.update(overrides)
    X = pd.DataFrame([row])
    for col in ("posture", "previous_action", "phase", "is_enraged"):
        X[col] = X[col].astype("category")
    return X


# =============================================================================
# 1+2. 五家族：接口契约 + ActionPredictor 兼容
# =============================================================================

class TestFiveFamilyCompatibility:
    @pytest.mark.parametrize("family", FAMILIES)
    def test_predict_proba_contract(self, exported_five_families, family):
        """加载后 predict_proba(DataFrame[6 列, category dtype]) / classes_ 可用。"""
        exported, _ = exported_five_families
        model = joblib.load(exported[family])
        probs = model.predict_proba(probe_row())
        assert probs.shape == (1, len(model.classes_))
        assert abs(float(probs[0].sum()) - 1.0) < 1e-3
        assert np.all(np.isfinite(probs))

    @pytest.mark.parametrize("family", FAMILIES)
    def test_action_predictor_predict(self, exported_five_families, family):
        """ActionPredictor(导出路径).predict() 返回合法 top-3（生产链路零改动）。"""
        exported, _ = exported_five_families
        predictor = ActionPredictor(str(exported[family]))
        assert predictor.is_loaded
        result = predictor.predict(500.0, 30.0, 1, 37, 1, 0)
        assert isinstance(result, list)
        assert 1 <= len(result) <= 3
        probs = [p for _, p in result]
        assert all(0.0 < p <= 1.0 for p in probs)
        assert probs == sorted(probs, reverse=True)
        # 概率和 ≈ 1 不适用于过滤后 top-3，但总和不应超过 1
        # （xgboost 概率为 float32 精度，容差取 1e-6）
        assert sum(probs) <= 1.0 + 1e-6

    @pytest.mark.parametrize("family", FAMILIES)
    def test_classes_subset_of_action_db(self, exported_five_families, family):
        exported, _ = exported_five_families
        model = joblib.load(exported[family])
        assert set(int(c) for c in model.classes_) <= set(ACTION_DB)

    @pytest.mark.parametrize("family", FAMILIES)
    def test_no_flaml_subprocess_load(self, exported_five_families, family):
        """子进程屏蔽 flaml 导入 → joblib.load + 单行推理成功（兼容验证 ①）。"""
        exported, _ = exported_five_families
        result = export_model.verify_no_flaml_load(exported[family])
        assert result["n_classes"] >= 2
        assert abs(result["prob_sum"] - 1.0) < 1e-3


# =============================================================================
# 3. 确定性
# =============================================================================

class TestDeterminism:
    def test_same_input_1000_times_identical_lgbm(self, exported_five_families):
        """同输入 1000 次 → 输出逐位一致（规划验证 ③，lgbm 家族）。"""
        exported, _ = exported_five_families
        predictor = ActionPredictor(str(exported["lgbm"]))
        first = predictor.predict(800.0, -45.0, 2, 53, 2, 1)
        assert first
        for _ in range(999):
            assert predictor.predict(800.0, -45.0, 2, 53, 2, 1) == first

    @pytest.mark.parametrize("family", ["xgboost", "rf", "extra_trees", "mlp"])
    def test_same_input_identical_other_families(self, exported_five_families, family):
        exported, _ = exported_five_families
        predictor = ActionPredictor(str(exported[family]))
        first = predictor.predict(800.0, -45.0, 2, 53, 2, 1)
        for _ in range(49):
            assert predictor.predict(800.0, -45.0, 2, 53, 2, 1) == first


# =============================================================================
# 4. 哨兵输入
# =============================================================================

class TestSentinelInput:
    @pytest.mark.parametrize("family", FAMILIES)
    def test_unseen_category_no_crash(self, exported_five_families, family):
        """未见 posture=99 / previous_action=12345 → 不崩溃、概率有限（哨兵 -1 路径）。"""
        exported, _ = exported_five_families
        model = joblib.load(exported[family])
        probs = model.predict_proba(probe_row(posture=99, previous_action=12345))
        assert np.all(np.isfinite(probs))
        assert probs.shape == (1, len(model.classes_))

    @pytest.mark.parametrize("family", FAMILIES)
    def test_sentinel_via_action_predictor(self, exported_five_families, family):
        exported, _ = exported_five_families
        predictor = ActionPredictor(str(exported[family]))
        result = predictor.predict(1200.0, 170.0, 99, 12345, 3, 1)
        assert isinstance(result, list)
        assert len(result) <= 3


# =============================================================================
# 5. 生产路径保护
# =============================================================================

class TestProductionPathProtection:
    def test_production_path_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="生产模型路径"):
            export_model.assert_safe_export_path(tmp_path / "fatalis_ai_model.pkl")
        with pytest.raises(ValueError, match="生产模型路径"):
            export_model.assert_safe_export_path(tmp_path / "fatalis_ai_model.pkl.bak")

    def test_non_whitelisted_basename_rejected(self, tmp_path):
        (tmp_path / "models").mkdir()
        with pytest.raises(ValueError, match="automl 开头"):
            export_model.assert_safe_export_path(tmp_path / "models" / "other_model.pkl")

    def test_non_whitelisted_dir_rejected(self, tmp_path):
        with pytest.raises(ValueError, match="白名单"):
            export_model.assert_safe_export_path(tmp_path / "random" / "fatalis_ai_model_automl.pkl")

    def test_whitelisted_paths_accepted(self, tmp_path):
        (tmp_path / "models").mkdir()
        (tmp_path / "experiments").mkdir()
        export_model.assert_safe_export_path(tmp_path / "models" / "fatalis_ai_model_automl.pkl")
        export_model.assert_safe_export_path(tmp_path / "experiments" / "fatalis_ai_model_automl_runA.pkl")

    def test_export_source_has_no_production_write(self):
        """源码约束：export_model.py 不含对生产文件名的写入语句（物理隔离回归）。"""
        source = _SCRIPT.read_text(encoding="utf-8")
        for name in ("fatalis_ai_model.pkl", "fatalis_ai_model.pkl.bak"):
            for pattern in (f"dump", "replace", "write"):
                # 生产名只允许出现在保护常量/校验逻辑中（PRODUCTION_MODEL_NAMES 行）
                pass
        lines = source.splitlines()
        offenders = [
            ln for ln in lines
            if "fatalis_ai_model.pkl" in ln
            and "PRODUCTION_MODEL_NAMES" not in ln
            and "生产模型路径" not in ln
            and not ln.strip().startswith("#")
            and 'f"models/{EXPORT_BASENAME}' not in ln
        ]
        assert not offenders, f"导出源码疑似包含生产路径写入: {offenders}"


# =============================================================================
# 6b. 标签还原层（FLAML LabelEncoder 现实的对策）
# =============================================================================

class TestLabelDecoding:
    def _encoded_stub(self):
        """编码 y 训练的 mini rf + 原始标签表。"""
        df = make_mini_dataset(rows_per_class=20)
        fb = FeatureBuilder(derived=False)
        X_num = fb.fit_transform(df)
        y = df["next_action"]
        y_enc = LabelEncoder().fit_transform(y)
        est = RandomForestClassifier(n_estimators=15, random_state=42, n_jobs=1)
        est.fit(X_num, y_enc)
        return est, sorted(int(v) for v in y.unique()), df, fb

    def test_classes_restored_to_original(self):
        est, labels, _, _ = self._encoded_stub()
        decoded = LabelDecodedEstimator(est, labels)
        assert [int(c) for c in decoded.classes_] == labels

    def test_predict_proba_aligned_and_predict_maps_back(self):
        est, labels, df, fb = self._encoded_stub()
        decoded = LabelDecodedEstimator(est, labels)
        X_raw = df.head(5)
        probs = decoded.predict_proba(fb.transform(X_raw))
        assert probs.shape == (5, len(labels))
        assert abs(float(probs.sum(axis=1)[0]) - 1.0) < 1e-6
        preds = decoded.predict(fb.transform(X_raw))
        assert all(int(p) in labels for p in preds)
        # argmax 与 predict 一致（口径自洽）
        argmax_labels = [labels[int(i)] for i in np.argmax(probs, axis=1)]
        assert [int(p) for p in preds] == argmax_labels

    def test_passthrough_when_already_original(self):
        """classes_ 已是原始标签 → wrap_with_label_decoder 透传不包一层。"""
        df = make_mini_dataset(rows_per_class=20)
        fb = FeatureBuilder(derived=False)
        X_num = fb.fit_transform(df)
        y = df["next_action"]
        est = RandomForestClassifier(n_estimators=10, random_state=42, n_jobs=1)
        est.fit(X_num, y)
        out = export_model.wrap_with_label_decoder(est, sorted(int(v) for v in y.unique()))
        assert out is est

    def test_invalid_inner_classes_rejected(self):
        df = make_mini_dataset(rows_per_class=20)
        fb = FeatureBuilder(derived=False)
        X_num = fb.fit_transform(df)
        y = df["next_action"]  # 原始标签直接训练 → classes_ 非 [0..n)
        est = RandomForestClassifier(n_estimators=10, random_state=42, n_jobs=1)
        est.fit(X_num, y)
        with pytest.raises(ValueError, match="非编码序"):
            LabelDecodedEstimator(est, sorted(int(v) for v in y.unique()))

    def test_pickle_roundtrip(self, tmp_path):
        """joblib 往返后 decoder 正常工作（导出持久化路径）。"""
        est, labels, df, fb = self._encoded_stub()
        decoded = LabelDecodedEstimator(est, labels)
        path = tmp_path / "decoded.pkl"
        joblib.dump(decoded, path)
        loaded = joblib.load(path)
        assert [int(c) for c in loaded.classes_] == labels
        probs = loaded.predict_proba(fb.transform(df.head(3)))
        assert probs.shape == (3, len(labels))


# =============================================================================
# 6c. 确定性重训备选路径（R-08）参数映射回归
# =============================================================================

class TestRetrainNative:
    """retrain_native 参数映射（xgboost **kwargs 透传修复的回归锁）。

    修复背景：XGBClassifier.__init__ 签名为 (objective, **kwargs)，
    按显式签名过滤会把 best_config 全部丢弃 → 静默训练默认配置模型。
    """

    def _mini_xy(self, rows_per_class=20):
        """mini 数据集：y 经 LabelEncoder 编码（镜像 FLAML 现实，xgboost 硬性要求 [0,n)）。"""
        df = make_mini_dataset(rows_per_class=rows_per_class)
        X = FeatureBuilder().fit_transform(df)
        y_enc = LabelEncoder().fit_transform(df["next_action"])
        return X, y_enc

    def test_xgboost_config_passthrough(self):
        """xgboost：best_config 必须全部生效（修复前 n_estimators 被滤成默认 100）。"""
        X, y = self._mini_xy(rows_per_class=30)
        best_config = {
            "n_estimators": 15, "max_depth": 3, "max_leaves": 4,
            "learning_rate": 0.3, "subsample": 0.8, "colsample_bytree": 0.8,
            "min_child_weight": 1.0, "reg_alpha": 0.0, "reg_lambda": 1.0,
            "colsample_bylevel": 1.0,
        }
        est = export_model.retrain_native("xgboost", best_config, X, y)
        assert est.n_estimators == 15
        assert est.max_depth == 3
        assert est.max_leaves == 4
        assert est.subsample == 0.8
        assert est.colsample_bytree == 0.8
        # FLAML config2params 镜像注入项
        assert est.objective == "multi:softprob"
        assert est.enable_categorical is True
        assert est.n_jobs == 1
        assert est.random_state == 42

    def test_xgboost_flaml_sample_size_dropped(self):
        X, y = self._mini_xy()
        est = export_model.retrain_native(
            "xgboost", {"n_estimators": 12, "FLAML_sample_size": 500}, X, y)
        assert est.n_estimators == 12
        assert "FLAML_sample_size" not in est.get_xgb_params()

    def test_lgbm_max_leaves_converted(self):
        X, y = self._mini_xy()
        est = export_model.retrain_native(
            "lgbm", {"n_estimators": 12, "max_leaves": 7}, X, y)
        assert est.num_leaves == 7

    def test_rf_signature_filter_unchanged(self):
        """显式签名构造器（rf）保持白名单过滤行为。"""
        X, y = self._mini_xy()
        est = export_model.retrain_native(
            "rf", {"n_estimators": 12, "not_a_real_param": 1}, X, y)
        assert est.n_estimators == 12
        assert not hasattr(est, "not_a_real_param")

    def test_mlp_rejected(self):
        X, y = self._mini_xy()
        with pytest.raises(ValueError, match="不支持"):
            export_model.retrain_native("mlp", {}, X, y)


# =============================================================================
# 6. 提取契约 + 端到端导出（integration）
# =============================================================================

class TestExtractionContract:
    def test_extract_from_wrapper_attr(self):
        class FakeWrapper:
            estimator = train_family_estimator(
                "rf",
                FeatureBuilder().fit_transform(make_mini_dataset(10)),
                make_mini_dataset(10)["next_action"],
            )
        native = export_model.extract_native_estimator(FakeWrapper())
        assert hasattr(native, "predict_proba")

    def test_extract_from_native_passthrough(self):
        est = train_family_estimator(
            "lgbm", FeatureBuilder().fit_transform(make_mini_dataset(10)),
            make_mini_dataset(10)["next_action"])
        assert export_model.extract_native_estimator(est) is est

    def test_extract_failure_raises(self):
        with pytest.raises(TypeError):
            export_model.extract_native_estimator(object())


@pytest.mark.integration
class TestEndToEndExport:
    def test_train_then_export(self, tmp_path):
        """mini FLAML run → export_model CLI → 无 flaml 加载 + ActionPredictor。"""
        train_script = Path(__file__).parents[1] / "scripts" / "train_automl.py"
        spec = importlib.util.spec_from_file_location("train_automl_mod2", train_script)
        train_automl = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(train_automl)

        dataset = tmp_path / "ML_Ready_Dataset.csv"
        make_mini_dataset(rows_per_class=30).to_csv(dataset, index=False)
        run_dir = tmp_path / "runA"
        rc = train_automl.main([
            "--run", "A", "--dataset", str(dataset),
            "--run-dir", str(run_dir),
            "--smoke", "--smoke-estimators", "lgbm", "--time-budget", "10",
        ])
        assert rc == 0
        assert (run_dir / "automl_best.pkl").exists()

        models_dir = tmp_path / "models"
        models_dir.mkdir()
        out = models_dir / "fatalis_ai_model_automl.pkl"
        rc = export_model.main([
            "--run-dir", str(run_dir), "--out", str(out),
            "--dataset", str(dataset),
        ])
        assert rc == 0
        assert out.exists()
        meta_path = out.with_name("fatalis_ai_model_automl.meta.json")
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta["extraction_path"] == "extract"
        assert meta["best_estimator"] == "lgbm"

        # ActionPredictor 兼容 + pickle 无 flaml 引用
        assert not export_model.pickle_references_flaml(out)
        predictor = ActionPredictor(str(out))
        assert predictor.is_loaded
        result = predictor.predict(500.0, 30.0, 1, 37, 1, 0)
        assert isinstance(result, list) and len(result) <= 3
