"""P3.4: Smoke tests for train_lgbm.py — LightGBM 训练管线（mini 数据集）。

策略：
  - 不使用真实大模型：构造确定性 mini ML 数据集（4 类 × 50 行 = 200 行），
    训练约 0.02s（early_stopping 提前终止）。
  - **不 monkeypatch LGBMClassifier.__init__**：保持 sklearn estimator API
    契约完整（get_params/clone 依赖构造签名）。
  - `pipeline_workdir` 把 CWD 切到临时目录，`train_fatalis_ai()` 自然读取
    data/ML_Ready_Dataset.csv，输出 models/fatalis_ai_model.pkl 与
    models/feature_importance.png —— 无需 patch 文件 I/O。

覆盖：
  - mini 数据训练成功
  - model 输出（.pkl 可加载，含 classes_/feature_importances_）
  - feature importance 输出（.png 已生成）
  - 少样本类别过滤（<3 样本类别被丢弃）
  - 异常日志（CSV 缺失 → logger.error）
"""

import os
import numpy as np
import pandas as pd

# 确保 matplotlib 使用无 GUI 后端（CI Linux 无 DISPLAY 时也必须可运行）
os.environ.setdefault("MPLBACKEND", "Agg")

import joblib
import train_lgbm


# =============================================================================
# 基础辅助
# =============================================================================

FEATURE_COLS = [
    "distance", "relative_angle", "posture",
    "previous_action", "phase", "is_enraged",
]


def make_mini_dataset(rows_per_class=50, classes=None, seed=42):
    """构造确定性 mini ML 就绪数据集。

    Args:
        rows_per_class: 每个类别行数
        classes: 类别 ID 列表（默认 4 类）
        seed: numpy 随机种子

    Returns:
        pd.DataFrame: 含 7 列（6 特征 + next_action）
    """
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


def write_mini_dataset(pipeline_workdir, df):
    """把 mini 数据集写入 tmp 的 data/ML_Ready_Dataset.csv。"""
    path = pipeline_workdir / "data" / "ML_Ready_Dataset.csv"
    df.to_csv(path, index=False)
    return path


# =============================================================================
# 1. mini 数据训练成功 + model 输出
# =============================================================================

class TestMiniTraining:
    def test_train_succeeds_and_saves_model(self, pipeline_workdir):
        """mini 数据集 → 训练完成，模型文件生成且可加载。"""
        df = make_mini_dataset()
        write_mini_dataset(pipeline_workdir, df)

        train_lgbm.train_fatalis_ai()

        model_path = pipeline_workdir / "models" / "fatalis_ai_model.pkl"
        assert model_path.exists(), "模型文件未生成"
        assert model_path.stat().st_size > 0

        model = joblib.load(model_path)
        assert hasattr(model, "classes_")
        assert len(model.classes_) >= 2
        assert hasattr(model, "feature_importances_")
        assert len(model.feature_importances_) == len(FEATURE_COLS)

    def test_model_predicts_mini_data(self, pipeline_workdir):
        """加载后的模型能对 mini 特征做 predict_proba。"""
        df = make_mini_dataset()
        write_mini_dataset(pipeline_workdir, df)

        train_lgbm.train_fatalis_ai()

        model = joblib.load(pipeline_workdir / "models" / "fatalis_ai_model.pkl")
        probe = df[FEATURE_COLS].iloc[:1].copy()
        for col in ["posture", "previous_action", "phase", "is_enraged"]:
            probe[col] = probe[col].astype("category")
        probs = model.predict_proba(probe)
        assert probs.shape == (1, len(model.classes_))
        assert abs(probs.sum() - 1.0) < 1e-3


# =============================================================================
# 2. feature importance 输出
# =============================================================================

class TestFeatureImportance:
    def test_importance_plot_saved(self, pipeline_workdir):
        """训练后生成 models/feature_importance.png。"""
        df = make_mini_dataset()
        write_mini_dataset(pipeline_workdir, df)

        train_lgbm.train_fatalis_ai()

        png_path = pipeline_workdir / "models" / "feature_importance.png"
        assert png_path.exists(), "特征重要性图未生成"
        assert png_path.stat().st_size > 0


# =============================================================================
# 3. 少样本类别过滤
# =============================================================================

class TestRareClassFilter:
    def test_class_with_less_than_3_samples_filtered(self, pipeline_workdir):
        """出现次数 < 3 的类别被丢弃，不参与训练。"""
        # 4 类中 129 只有 2 行 → 应被过滤
        classes = [37, 53, 81, 129]
        df = make_mini_dataset(rows_per_class=10, classes=classes, seed=7)
        # 把 129 的样本削减到 2 行（只保留前 2 行）
        rare_keep = df[df["next_action"] == 129].head(2)
        df = pd.concat([df[df["next_action"] != 129], rare_keep])
        assert (df["next_action"] == 129).sum() == 2

        write_mini_dataset(pipeline_workdir, df)

        train_lgbm.train_fatalis_ai()

        model = joblib.load(pipeline_workdir / "models" / "fatalis_ai_model.pkl")
        classes_in_model = [int(c) for c in model.classes_]
        assert 129 not in classes_in_model, "少样本类别未被过滤"
        assert 37 in classes_in_model and 53 in classes_in_model


# =============================================================================
# 4. 异常日志
# =============================================================================

class TestMissingCsvLogging:
    def test_missing_csv_logs_error(self, pipeline_workdir, monkeypatch, caplog):
        """ML_Ready_Dataset.csv 缺失 → logger.error 记录，不崩溃。"""
        # 确保目录里没有数据集文件
        csv_path = pipeline_workdir / "data" / "ML_Ready_Dataset.csv"
        assert not csv_path.exists()

        import logging
        with caplog.at_level(logging.ERROR, logger="BlackDragon"):
            train_lgbm.train_fatalis_ai()

        messages = [r.message for r in caplog.records if r.levelno >= logging.ERROR]
        assert any("找不到" in m for m in messages), f"未记录缺失错误: {messages}"
