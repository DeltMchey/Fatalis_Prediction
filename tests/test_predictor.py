"""P4 Step 3: ActionPredictor tests — 模型加载与推理管线测试。

策略：
  - 使用 mini 数据集训练真实 LightGBM 模型（确定性 seed，约 0.02s）
  - 使用 MagicMock 模拟 LGBMClassifier 的 predict_proba/classes_ 验证 feature 格式
  - 静态方法（filter_probs_by_phase 等）直接行为验证

覆盖：
  - 模型成功加载 / 缺失文件 → None
  - mini 模型端到端预测
  - feature DataFrame 格式（列顺序 + category dtype）
  - phase 过滤
  - posture 过滤
  - 全零概率重新归一
  - top-k 排序 + threshold 过滤
  - 模型不存在 → predict 返回空列表
"""

import os
from unittest.mock import MagicMock

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

from src.model.predictor import ActionPredictor


# =============================================================================
# Mini LightGBM 模型工具
# =============================================================================

def make_mini_dataset(rows_per_class=50, classes=None, seed=42):
    """构造确定性 mini ML 数据集（4 类 × N 行）。"""
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


def train_mini_model(tmp_path, rows_per_class=50, seed=42):
    """训练 mini LightGBM 模型，保存到 tmp_path，返回模型文件路径。"""
    df = make_mini_dataset(rows_per_class, seed=seed)
    for col in ["posture", "previous_action", "phase", "is_enraged"]:
        df[col] = df[col].astype("category")

    feature_cols = ["distance", "relative_angle", "posture",
                    "previous_action", "phase", "is_enraged"]
    X, y = df[feature_cols], df["next_action"]

    model = lgb.LGBMClassifier(
        objective="multiclass",
        num_leaves=7, max_depth=3,
        learning_rate=0.1, n_estimators=10,
        random_state=42, n_jobs=-1,
    )
    model.fit(X, y, categorical_feature=["posture", "previous_action", "phase", "is_enraged"])

    path = tmp_path / "mini_model.pkl"
    joblib.dump(model, path)
    return str(path)


# =============================================================================
# 1. 模型加载
# =============================================================================

class TestModelLoading:
    def test_valid_model_loads(self, tmp_path):
        """有效 .pkl → is_loaded=True。"""
        model_path = train_mini_model(tmp_path)
        predictor = ActionPredictor(model_path)
        assert predictor.is_loaded is True
        assert predictor._model is not None

    def test_missing_file_sets_none(self, tmp_path):
        """缺失文件 → is_loaded=False，predict 返回空列表。"""
        predictor = ActionPredictor(str(tmp_path / "nonexistent.pkl"))
        assert predictor.is_loaded is False
        assert predictor._model is None
        assert predictor.predict(100.0, 0.0, 1, 37, 1, 0) == []

    def test_corrupted_file_sets_none(self, tmp_path):
        """损坏文件 → is_loaded=False。"""
        bad_path = tmp_path / "bad.pkl"
        bad_path.write_bytes(b"not a valid pickle")
        predictor = ActionPredictor(str(bad_path))
        assert predictor.is_loaded is False

    # ── Hotfix RC1: 加载失败必须留 ERROR 痕迹（曾经三层静默吞噬） ──

    def test_missing_file_logs_error_with_path(self, tmp_path, caplog):
        """缺失文件 → ERROR 日志包含模型路径（回传日志可定谳）。"""
        import logging as _logging
        missing = str(tmp_path / "nonexistent.pkl")
        with caplog.at_level(_logging.ERROR, logger="BlackDragon"):
            ActionPredictor(missing)
        assert any("AI 模型加载失败" in r.message for r in caplog.records)
        assert missing in caplog.text

    def test_corrupted_file_logs_error_with_traceback(self, tmp_path, caplog):
        """损坏文件 → ERROR 日志含 traceback（区分 FileNotFoundError / 反序列化失败）。"""
        import logging as _logging
        bad_path = tmp_path / "bad.pkl"
        bad_path.write_bytes(b"not a valid pickle")
        with caplog.at_level(_logging.ERROR, logger="BlackDragon"):
            ActionPredictor(str(bad_path))
        assert any("AI 模型加载失败" in r.message for r in caplog.records)
        assert "Traceback" in caplog.text

    def test_successful_load_logs_no_error(self, tmp_path, caplog):
        """成功加载 → 无 ERROR 日志（避免噪音）。"""
        import logging as _logging
        model_path = train_mini_model(tmp_path)
        with caplog.at_level(_logging.ERROR, logger="BlackDragon"):
            ActionPredictor(model_path)
        assert not [r for r in caplog.records if r.levelno >= 40]


# =============================================================================
# 2. Mini 模型端到端预测
# =============================================================================

class TestMiniModelPrediction:
    def test_predict_returns_top3(self, tmp_path):
        """mini 模型 → predict 返回最多 3 个预测。"""
        model_path = train_mini_model(tmp_path)
        predictor = ActionPredictor(model_path)

        result = predictor.predict(500.0, 30.0, 1, 37, 1, 0)
        assert isinstance(result, list)
        assert 0 < len(result) <= 3

    def test_predict_result_format(self, tmp_path):
        """返回 (class_id, prob) 元组，概率在 (0, 1] 区间，降序排列。"""
        model_path = train_mini_model(tmp_path)
        predictor = ActionPredictor(model_path)

        result = predictor.predict(500.0, 30.0, 1, 37, 1, 0)
        for class_id, prob in result:
            assert isinstance(class_id, (int, np.integer))
            assert isinstance(prob, float)
            assert 0.0 < prob <= 1.0

        # 降序排列
        probs = [p for _, p in result]
        assert probs == sorted(probs, reverse=True)

    def test_predict_deterministic(self, tmp_path):
        """同一特征多次调用 → 相同结果（random_state 固定）。"""
        model_path = train_mini_model(tmp_path)
        predictor = ActionPredictor(model_path)

        features = (500.0, 30.0, 1, 37, 1, 0)
        result1 = predictor.predict(*features)
        result2 = predictor.predict(*features)
        assert result1 == result2

    def test_predict_probabilities_sum_to_one(self, tmp_path):
        """过滤+归一化后概率和 ≈ 1（当有预测返回时）。"""
        model_path = train_mini_model(tmp_path)
        predictor = ActionPredictor(model_path)

        result = predictor.predict(500.0, 30.0, 1, 37, 1, 0)
        if result:
            total = sum(p for _, p in result)
            # Top-3 只是部分概率，但归一化后的 top-3 之和 <= 1
            assert total <= 1.0 + 1e-9


# =============================================================================
# 3. Feature DataFrame 格式
# =============================================================================

class TestFeatureDataFrame:
    def _make_predictor_with_mock_model(self):
        """构造 Predictor，_model 为 MagicMock（模拟 predict_proba + classes_）。"""
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.array([[0.1, 0.2, 0.3, 0.4]])
        mock_model.classes_ = np.array([37, 53, 81, 129])
        predictor = ActionPredictor.__new__(ActionPredictor)
        predictor._model = mock_model
        return predictor

    def test_feature_columns_order(self):
        """feature DataFrame 列顺序与训练时一致。"""
        predictor = self._make_predictor_with_mock_model()
        captured = {}

        # 拦截 predict_proba 的输入
        original_proba = predictor._model.predict_proba
        def spy(input_data):
            captured['df'] = input_data
            return original_proba(input_data)
        predictor._model.predict_proba = spy

        predictor.predict(100.0, 20.0, 1, 37, 1, 0)

        df = captured['df']
        assert df.columns.tolist() == [
            "distance", "relative_angle", "posture",
            "previous_action", "phase", "is_enraged",
        ]
        assert len(df) == 1

    def test_categorical_dtypes_set(self):
        """4 个 categorical 列转换为 category dtype。"""
        predictor = self._make_predictor_with_mock_model()
        captured = {}

        original_proba = predictor._model.predict_proba
        def spy(input_data):
            captured['df'] = input_data
            return original_proba(input_data)
        predictor._model.predict_proba = spy

        predictor.predict(100.0, 20.0, 1, 37, 1, 0)

        df = captured['df']
        for col in ["posture", "previous_action", "phase", "is_enraged"]:
            assert df[col].dtype.name == "category", f"{col} 未转换为 category"
        # 数值特征保持数值类型
        assert df["distance"].dtype == np.float64 or df["distance"].dtype == np.int64
        assert df["relative_angle"].dtype == np.float64 or df["relative_angle"].dtype == np.int64

    def test_predict_values_passed_through(self):
        """输入特征值正确传入 DataFrame。"""
        predictor = self._make_predictor_with_mock_model()
        captured = {}

        original_proba = predictor._model.predict_proba
        def spy(input_data):
            captured['df'] = input_data
            return original_proba(input_data)
        predictor._model.predict_proba = spy

        predictor.predict(150.5, -45.0, 0, 53, 2, 1)

        df = captured['df']
        row = df.iloc[0]
        assert row["distance"] == 150.5
        assert row["relative_angle"] == -45.0
        assert row["posture"] == 0
        assert row["previous_action"] == 53
        assert row["phase"] == 2
        assert row["is_enraged"] == 1


# =============================================================================
# 4. 静态方法：phase 过滤（P3.3B 迁移验证）
# =============================================================================

class TestFilterProbsByPhase:
    def test_phase1_zeros_p2_plus(self):
        """P1 阶段：P2+ 专属动作被置零。"""
        probs = np.array([0.5, 0.3, 0.2])
        classes = np.array([1, 10, 20])  # 1=P1-only, 10=P2+, 20=P3-only
        result = ActionPredictor.filter_probs_by_phase(
            probs.copy(), classes, 1,
            p1_only={1}, p2_plus={10}, p3_only={20},
        )
        assert result[0] == pytest.approx(0.5)   # P1-only 保留
        assert result[1] == 0.0                   # P2+ 置零
        assert result[2] == 0.0                   # P3-only 置零

    def test_phase3_zeros_p1_only(self):
        """P3 阶段：P1-only 动作被置零，P3-only 保留。"""
        probs = np.array([0.5, 0.3, 0.2])
        classes = np.array([1, 10, 20])
        result = ActionPredictor.filter_probs_by_phase(
            probs.copy(), classes, 3,
            p1_only={1}, p2_plus={10}, p3_only={20},
        )
        assert result[0] == 0.0                   # P1-only 置零
        assert result[1] == pytest.approx(0.3)   # P2+ 保留
        assert result[2] == pytest.approx(0.2)   # P3-only 保留

    def test_default_uses_real_sets(self):
        """不传集合时使用 src.config.actions 的真实集合。"""
        from src.config.actions import P1_ONLY_IDS, P2_PLUS_IDS, P3_ONLY_IDS
        probs = np.array([0.5, 0.5])
        classes = np.array([37, 129])  # 37 ∈ P1_ONLY, 129 ∈ P2_PLUS
        result = ActionPredictor.filter_probs_by_phase(probs.copy(), classes, 2)
        assert result[0] == 0.0   # P1-only 在 P2 置零
        assert result[1] == pytest.approx(0.5)  # P2+ 保留


# =============================================================================
# 5. 静态方法：posture 过滤（P3.3B 迁移验证）
# =============================================================================

class TestFilterProbsByPosture:
    def test_standing_filters_stand_exclude(self):
        """站立（1）：stand_exclude 中的动作被置零。"""
        probs = np.array([0.5, 0.5])
        classes = np.array([30, 40])
        result = ActionPredictor.filter_probs_by_posture(
            probs.copy(), classes, 1,
            stand_exclude={30}, prone_exclude={40},
        )
        assert result[0] == 0.0
        assert result[1] == pytest.approx(0.5)

    def test_prone_filters_prone_exclude(self):
        """趴下（0）：prone_exclude 中的动作被置零。"""
        probs = np.array([0.5, 0.5])
        classes = np.array([30, 40])
        result = ActionPredictor.filter_probs_by_posture(
            probs.copy(), classes, 0,
            stand_exclude={30}, prone_exclude={40},
        )
        assert result[0] == pytest.approx(0.5)
        assert result[1] == 0.0

    def test_flying_no_filter(self):
        """飞行（2）：无过滤。"""
        probs = np.array([0.5, 0.5])
        classes = np.array([30, 40])
        result = ActionPredictor.filter_probs_by_posture(
            probs.copy(), classes, 2,
            stand_exclude={30}, prone_exclude={40},
        )
        assert result[0] == pytest.approx(0.5)
        assert result[1] == pytest.approx(0.5)

    def test_default_uses_real_sets(self):
        """默认使用真实 exclude 集合。"""
        probs = np.array([0.5, 0.5])
        # 129 ∈ _POSTURE_STAND_EXCLUDE, 37 ∈ _POSTURE_PRONE_EXCLUDE
        classes = np.array([129, 37])
        result = ActionPredictor.filter_probs_by_posture(probs.copy(), classes, 1)
        assert result[0] == 0.0   # 129 在站立时不可用
        assert result[1] == pytest.approx(0.5)


# =============================================================================
# 6. 静态方法：renormalize_probs（P3.3B 迁移验证）
# =============================================================================

class TestRenormalizeProbs:
    def test_normalizes_to_one(self):
        probs = np.array([0.25, 0.25, 0.5])
        result = ActionPredictor.renormalize_probs(probs.copy())
        assert np.sum(result) == pytest.approx(1.0)
        # 比例保持
        assert result[0] == pytest.approx(0.25)
        assert result[2] == pytest.approx(0.5)

    def test_all_zeros_unchanged(self):
        """全零数组 → 不做修改（避免除零）。"""
        probs = np.array([0.0, 0.0, 0.0])
        result = ActionPredictor.renormalize_probs(probs.copy())
        assert result[0] == 0.0
        assert result[1] == 0.0
        assert result[2] == 0.0

    def test_preserves_relative_ratios(self):
        probs = np.array([2.0, 1.0, 1.0])
        result = ActionPredictor.renormalize_probs(probs.copy())
        assert np.sum(result) == pytest.approx(1.0)
        assert result[0] == pytest.approx(0.5)
        assert result[1] == pytest.approx(0.25)
        assert result[2] == pytest.approx(0.25)


# =============================================================================
# 7. 静态方法：select_top_k（P3.3A 迁移验证）
# =============================================================================

class TestSelectTopK:
    def test_returns_top3_by_default(self):
        probs = np.array([0.1, 0.5, 0.2, 0.3, 0.05])
        classes = np.array([10, 20, 30, 40, 50])
        result = ActionPredictor.select_top_k(probs, classes)
        assert len(result) == 3
        assert result[0][0] == 20   # 0.5 最大
        assert result[0][1] == pytest.approx(0.5)

    def test_sorted_descending(self):
        probs = np.array([0.1, 0.5, 0.2, 0.3])
        classes = np.array([10, 20, 30, 40])
        result = ActionPredictor.select_top_k(probs, classes)
        probs_out = [p for _, p in result]
        assert probs_out == sorted(probs_out, reverse=True)

    def test_threshold_filters_low_probs(self):
        """低于 threshold 的预测被排除。"""
        probs = np.array([0.1, 0.02, 0.5, 0.01])
        classes = np.array([10, 20, 30, 40])
        result = ActionPredictor.select_top_k(probs, classes, k=3, threshold=0.03)
        assert len(result) == 2  # 0.5, 0.1 超过 0.03；0.02/0.01 被排除
        assert all(p > 0.03 for _, p in result)

    def test_custom_k(self):
        probs = np.array([0.1, 0.5, 0.2, 0.3])
        classes = np.array([10, 20, 30, 40])
        result = ActionPredictor.select_top_k(probs, classes, k=2)
        assert len(result) == 2

    def test_all_below_threshold_returns_empty(self):
        probs = np.array([0.01, 0.02, 0.03])
        classes = np.array([10, 20, 30])
        result = ActionPredictor.select_top_k(probs, classes, k=3, threshold=0.03)
        assert result == []


# =============================================================================
# 8. 常量完整性
# =============================================================================

class TestConstants:
    def test_stand_exclude_15_elements(self):
        from src.model.predictor import _POSTURE_STAND_EXCLUDE
        assert len(_POSTURE_STAND_EXCLUDE) == 15

    def test_prone_exclude_37_elements(self):
        from src.model.predictor import _POSTURE_PRONE_EXCLUDE
        assert len(_POSTURE_PRONE_EXCLUDE) == 37


# =============================================================================
# 9. 边界情况
# =============================================================================

class TestEdgeCases:
    def test_phase_out_of_range_no_crash(self):
        """phase 超出 1/2/3 → filter 不崩溃。"""
        probs = np.array([0.5, 0.5])
        classes = np.array([37, 129])
        result = ActionPredictor.filter_probs_by_phase(
            probs.copy(), classes, 5,
            p1_only={37}, p2_plus={129}, p3_only=set(),
        )
        # phase=5 > 1 → P1-only 置零；phase > 2 → P3-only 已空；phase >= 2 → P2+ 保留
        assert result[0] == 0.0
        assert result[1] == pytest.approx(0.5)

    def test_posture_out_of_range_no_crash(self):
        """posture 超出 0/1/2 → filter 不崩溃（不置零）。"""
        probs = np.array([0.5, 0.5])
        classes = np.array([30, 40])
        result = ActionPredictor.filter_probs_by_posture(
            probs.copy(), classes, 5,
            stand_exclude={30}, prone_exclude={40},
        )
        assert result[0] == pytest.approx(0.5)
        assert result[1] == pytest.approx(0.5)

    def test_empty_classes_select_top_k(self):
        """空 classes → select_top_k 返回空列表。"""
        result = ActionPredictor.select_top_k(
            np.array([]), np.array([]), k=3, threshold=0.03)
        assert result == []

    def test_predict_called_multiple_times_independent(self, tmp_path):
        """连续调用 predict → 每次独立，无状态残留。"""
        model_path = train_mini_model(tmp_path)
        predictor = ActionPredictor(model_path)

        r1 = predictor.predict(100.0, 0.0, 1, 37, 1, 0)
        r2 = predictor.predict(2500.0, 90.0, 0, 53, 3, 1)
        r3 = predictor.predict(100.0, 0.0, 1, 37, 1, 0)
        assert r1 == r3  # 相同输入相同输出
