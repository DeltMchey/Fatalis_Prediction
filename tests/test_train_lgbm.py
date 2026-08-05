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


# =============================================================================
# 5. 未知动作 label 处理（v1.1.1 — 训练崩溃根因修复）
# =============================================================================

class TestUnknownLabelFiltering:
    """训练阶段检测并过滤未在 ACTION_DB 中定义的 label。

    根因：未知动作 label 通过清洗进入训练集 → train_test_split 无序分层时
    稀有类全入 test → LightGBM LabelEncoder "unseen labels" 崩溃。
    修复：训练前检测未知 label + 输出具体 ID + 过滤 + 分层抽样。
    """

    def test_train_with_invalid_label_does_not_crash(self, pipeline_workdir, capsys):
        """数据集混入未知 label 117 → 训练不崩溃，117 被过滤，模型正常保存。"""
        df = make_mini_dataset(rows_per_class=50, classes=[37, 53, 81, 129])
        # 混入 3 条未知 label 117（足以通过 >=3 过滤，触发旧 bug）
        unknown_rows = df.iloc[:3].copy()
        unknown_rows["next_action"] = 117
        df = pd.concat([df, unknown_rows], ignore_index=True)
        write_mini_dataset(pipeline_workdir, df)

        train_lgbm.train_fatalis_ai()

        model = joblib.load(pipeline_workdir / "models" / "fatalis_ai_model.pkl")
        assert 117 not in [int(c) for c in model.classes_]
        captured = capsys.readouterr()
        assert "117" in captured.out
        assert "未知动作" in captured.out

    def test_train_all_invalid_labels_graceful(self, pipeline_workdir, capsys):
        """数据集全部为未知 label → 优雅停止，不崩溃，不覆盖旧模型。"""
        df = make_mini_dataset(rows_per_class=10, classes=[37, 53])
        df["next_action"] = 117
        write_mini_dataset(pipeline_workdir, df)

        # 预置旧模型，验证不被覆盖
        old_model = pipeline_workdir / "models" / "fatalis_ai_model.pkl"
        old_model.write_bytes(b"OLD")

        train_lgbm.train_fatalis_ai()

        assert old_model.read_bytes() == b"OLD", "旧模型被覆盖"
        captured = capsys.readouterr()
        assert "未知动作" in captured.out
        assert "117" in captured.out

    def test_stratified_split_keeps_all_classes_in_both(self, pipeline_workdir):
        """stratify=y 保证每个 >=3 的类在 train/test 中都有实例。"""
        from sklearn.model_selection import train_test_split
        df = make_mini_dataset(rows_per_class=10, classes=[37, 53, 81])
        write_mini_dataset(pipeline_workdir, df)

        # 直接验证 train_test_split 行为（与 train_fatalis_ai 相同的参数）
        y = df["next_action"]
        _, _, y_train, y_test = train_test_split(
            df[["distance"]], y, test_size=0.2, random_state=42, stratify=y
        )
        train_classes = set(int(c) for c in y_train.unique())
        test_classes = set(int(c) for c in y_test.unique())
        assert train_classes == {37, 53, 81}
        assert test_classes == {37, 53, 81}


# =============================================================================
# 6. 极小数据集 stratify 降级（v1.1.2 — 审查 Must Fix）
# =============================================================================

# 30 个真实 ACTION_DB 战斗动作（用于构造 30 classes × 3 samples = 90 rows）
_SMALL_CLASSES = [
    37, 53, 81, 129, 138, 49, 73, 107, 115, 119, 121, 122, 98, 99, 100, 101,
    131, 132, 133, 140, 141, 142, 143, 144, 145, 84, 85, 86, 87, 78,
]


class TestStratifySmallDatasetFallback:
    """当 ceil(test_size * n) < n_classes 时 stratify 会抛 ValueError。

    修复：检测并降级为非分层 split + warning，保证极小数据集仍可训练。
    """

    def test_small_dataset_fallback_without_crash(self, pipeline_workdir, capsys):
        """30 classes × 3 samples = 90 rows → 降级为非分层 split，训练不崩溃。"""
        df = make_mini_dataset(rows_per_class=3, classes=_SMALL_CLASSES)
        assert df["next_action"].nunique() == 30
        write_mini_dataset(pipeline_workdir, df)

        train_lgbm.train_fatalis_ai()  # 不抛异常即通过

        captured = capsys.readouterr()
        assert "Dataset too small for stratified split" in captured.out
        assert "test samples=18" in captured.out
        assert "classes=30" in captured.out
        assert "Fallback to non-stratified split" in captured.out

        # 模型仍正常保存
        model_path = pipeline_workdir / "models" / "fatalis_ai_model.pkl"
        assert model_path.exists(), "降级路径下模型未保存"

    def test_normal_dataset_still_stratified(self, pipeline_workdir, capsys):
        """正常数据（2000+ samples / 4 classes）→ 不触发降级，无 fallback warning。"""
        df = make_mini_dataset(rows_per_class=500, classes=[37, 53, 81, 129])
        assert len(df) == 2000
        write_mini_dataset(pipeline_workdir, df)

        train_lgbm.train_fatalis_ai()

        captured = capsys.readouterr()
        assert "Dataset too small for stratified split" not in captured.out


# =============================================================================
# 7. 数据质量 warning（v1.1.2 — 审查 Should Fix A/B）
# =============================================================================

class TestLabelDataQualityWarnings:
    def test_nan_label_warning(self, pipeline_workdir, capsys):
        """next_action 含 NaN → 过滤并输出 "Removed N rows with empty labels"。"""
        df = make_mini_dataset(rows_per_class=50, classes=[37, 53, 81, 129])
        # 把 3 行 next_action 置为 NaN（列转 float，to_csv 写空 → read 回 NaN）
        df.loc[df.index[:3], "next_action"] = float("nan")
        write_mini_dataset(pipeline_workdir, df)

        train_lgbm.train_fatalis_ai()

        captured = capsys.readouterr()
        assert "Removed 3 rows with empty labels" in captured.out

        # 训练仍成功（200 - 3 = 197 行）
        model_path = pipeline_workdir / "models" / "fatalis_ai_model.pkl"
        assert model_path.exists()

    def test_non_numeric_label_warning(self, pipeline_workdir, capsys):
        """next_action 含非数值 'abc' → int(v) 安全降级 + warning，训练不崩溃。"""
        df = make_mini_dataset(rows_per_class=50, classes=[37, 53, 81, 129])
        # 把 1 行 next_action 改为字符串（列转 object）
        df = df.astype({"next_action": object})
        df.loc[df.index[0], "next_action"] = "abc"
        write_mini_dataset(pipeline_workdir, df)

        train_lgbm.train_fatalis_ai()

        captured = capsys.readouterr()
        assert "非数值 label" in captured.out
        assert "abc" in captured.out

        # 训练仍成功（199 行有效）
        model_path = pipeline_workdir / "models" / "fatalis_ai_model.pkl"
        assert model_path.exists()
