"""P4(AutoML 实验): scripts/train_automl.py 集成测试（integration 标记）。

策略：合成数据 + time_budget≈20s + 2 learner 端到端，断言产物齐全：
  - run_manifest.json（best_estimator / best_config / 数据指纹 / 库版本）
  - best_config.json
  - feature_builder.pkl（fit 后实例，P5 导出复用）
  - flaml_log.csv
  - 只喂 train_80：manifest 中 holdout 行数 = 全量 20%
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.config.actions import ACTION_DB

_SCRIPT = Path(__file__).parents[1] / "scripts" / "train_automl.py"
_spec = importlib.util.spec_from_file_location("train_automl_mod", _SCRIPT)
train_automl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(train_automl)

pytestmark = pytest.mark.integration

KNOWN_ACTIONS = sorted(set(ACTION_DB))[:6]  # 6 个真实动作 ID 作类别


@pytest.fixture
def synthetic_dataset(tmp_path):
    """6 类 × 60 行合成数据（特征与类别弱相关，保证搜索可学到非平凡结果）。"""
    rng = np.random.default_rng(42)
    rows = []
    for i, cls in enumerate(KNOWN_ACTIONS):
        for _ in range(60):
            rows.append({
                "distance": rng.uniform(50, 3000) + 200 * i,
                "relative_angle": rng.uniform(-180, 180),
                "posture": rng.integers(0, 3),
                "previous_action": rng.choice(KNOWN_ACTIONS),
                "phase": rng.integers(1, 4),
                "is_enraged": rng.integers(0, 2),
                "next_action": cls,
                "source_session": f"session_{i % 3}.csv",
            })
    df = pd.DataFrame(rows)
    path = tmp_path / "ML_Ready_Dataset.csv"
    df.to_csv(path, index=False)
    return path


class TestTrainAutomlSmoke:
    def test_smoke_run_a_end_to_end(self, synthetic_dataset, tmp_path):
        """Run A + 20s 预算 + lgbm/rf → 全部产物落盘且字段合法。"""
        run_dir = tmp_path / "runA"
        rc = train_automl.main([
            "--run", "A",
            "--dataset", str(synthetic_dataset),
            "--run-dir", str(run_dir),
            "--smoke", "--time-budget", "20",
        ])
        assert rc == 0

        manifest_path = run_dir / "run_manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        assert manifest["best_estimator"] in ("lgbm", "rf")
        assert manifest["best_config"], "best_config 为空"
        assert manifest["data"]["train_rows"] + manifest["data"]["holdout_rows"] == 360
        assert manifest["data"]["train_classes"] == 6
        # 只喂 train_80：holdout = 20%（72 行）
        assert manifest["data"]["holdout_rows"] == 72
        # Run A = 6 数值编码列，无派生列
        assert "angle_sin" not in manifest["data"]["feature_names"]
        assert manifest["data"]["n_groups"] == 3
        assert manifest["data"]["dataset_sha256"]

        assert (run_dir / "best_config.json").exists()
        assert (run_dir / "flaml_log.csv").exists()
        # P5 导出输入：fit 后 FeatureBuilder + 最优已训练模型（flaml wrapper）
        assert (run_dir / "feature_builder.pkl").exists()
        assert (run_dir / "automl_best.pkl").exists()

        import joblib
        fb = joblib.load(run_dir / "feature_builder.pkl")
        out = fb.transform(synthetic_df_head(synthetic_dataset))
        assert out.columns.tolist() == manifest["data"]["feature_names"]

    def test_smoke_run_b_derived_features(self, synthetic_dataset, tmp_path):
        """Run B：派生列进特征清单。"""
        run_dir = tmp_path / "runB"
        rc = train_automl.main([
            "--run", "B",
            "--dataset", str(synthetic_dataset),
            "--run-dir", str(run_dir),
            "--smoke", "--time-budget", "15",
            "--smoke-estimators", "lgbm",
        ])
        assert rc == 0
        manifest = json.loads(
            (run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert "angle_sin" in manifest["data"]["feature_names"]
        assert "prev_action_freq" in manifest["data"]["feature_names"]
        assert len(manifest["data"]["feature_names"]) == 12  # 6 + 6 派生


class TestPrepareTrainData:
    def test_prepare_train_data_golden_split(self, synthetic_dataset):
        """prepare_train_data 的 train/holdout = golden 口径（同一共享函数）。"""
        from src.model.dataset import load_ml_dataset, make_holdout_split, LABEL_COL

        X, y, fb, holdout, groups, meta = train_automl.prepare_train_data(
            synthetic_dataset, derived=False, n_bins=8)

        df = load_ml_dataset(synthetic_dataset)
        train_df, holdout_df = make_holdout_split(df, test_size=0.2, random_state=42)
        assert len(X) == len(train_df)
        assert list(y.index) == list(train_df.index)
        assert list(holdout.index) == list(holdout_df.index)
        assert list(y.values) == list(train_df[LABEL_COL].values)
        assert groups is not None and len(groups) == len(train_df)

    def test_feature_builder_input_contract(self, synthetic_dataset):
        """训练输入为纯数值矩阵（无 category dtype）—— FLAML 输入面契约。"""
        X, y, fb, _, _, _ = train_automl.prepare_train_data(
            synthetic_dataset, derived=False, n_bins=8)
        for dt in X.dtypes:
            assert str(dt) in ("int64", "float64")


def synthetic_df_head(dataset_path, n=3):
    return pd.read_csv(dataset_path).head(n)
