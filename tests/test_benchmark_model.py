"""P2(AutoML 实验): scripts/benchmark_model.py 测试 — schema/数值正确性/确定性。

策略：
  - StubModel（固定概率矩阵）手算对照 top-1 / top-3（raw + 过滤口径）
  - mini LightGBM 模型（确定性 seed）驱动完整 main() 全指标（极小迭代/时长）
  - 同输入两次计算 → 指标逐位一致（回归保护）
"""

import importlib.util
import json
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

from src.model.dataset import FEATURE_COLS, LABEL_COL, load_ml_dataset, make_holdout_split

_SCRIPT = Path(__file__).parents[1] / "scripts" / "benchmark_model.py"
_spec = importlib.util.spec_from_file_location("benchmark_model", _SCRIPT)
benchmark_model = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(benchmark_model)


# =============================================================================
# 工具
# =============================================================================

def make_mini_dataset(rows_per_class=50, classes=None, seed=42):
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


class StubModel:
    """固定概率矩阵 stub（predict_proba 忽略输入内容，返回构造时矩阵）。"""

    def __init__(self, probs, classes):
        self._probs = np.asarray(probs, dtype=float)
        self.classes_ = np.asarray(classes)

    def predict_proba(self, X):
        assert len(X) == len(self._probs), "stub 行数不匹配"
        return self._probs.copy()


def mini_holdout():
    """4 行 mini 留出集（手算对照用）。"""
    return pd.DataFrame({
        "distance": [100.0, 200.0, 300.0, 400.0],
        "relative_angle": [0.0, 10.0, 20.0, 30.0],
        "posture": [1, 1, 0, 2],
        "previous_action": [37, 53, 81, 129],
        "phase": [1, 2, 3, 1],
        "is_enraged": [0, 0, 1, 0],
        # y: 37=P1_ONLY, 53, 81, 129=P2_PLUS
        "next_action": [37, 81, 129, 53],
    })


# =============================================================================
# 1. top-1 / top-3 手算对照
# =============================================================================

class TestTopKMetrics:
    def test_topk_raw_handcheck(self):
        """raw 口径手算：argsort 前 3 命中率。

        classes=[37,53,81,129]；行概率与真值：
          r0 [.50,.30,.15,.05] y=37 → top1 命中, top3 命中
          r1 [.05,.55,.30,.10] y=81 → top1 miss,   top3 命中（前三=53/81/37）
          r2 [.10,.20,.60,.10] y=129→ top1 miss,   top3 miss（前三=81/53/37）
          r3 [.30,.10,.10,.50] y=53 → top1 miss,   top3 命中（前三=129/37/53）
        → top1=1/4, top3_raw=3/4
        """
        probs = [
            [.50, .30, .15, .05],
            [.05, .55, .30, .10],
            [.10, .20, .60, .10],
            [.30, .10, .10, .50],
        ]
        model = StubModel(probs, [37, 53, 81, 129])
        m = benchmark_model.compute_metrics(model, mini_holdout())

        assert m["top1"] == pytest.approx(1 / 4)
        assert m["top3_raw"] == pytest.approx(3 / 4)
        assert m["micro_top3"] == pytest.approx(3 / 4)

    def test_topk_filtered_handcheck(self):
        """过滤口径手算（按 ACTION_DB 过滤集语义逐行推导）。

        classes=[37,53,81,129]（37∈P1_ONLY；129∈P2_PLUS；81∈prone 排除集）：
          r0 y=37 phase=1 posture=1: 37 保持（phase=1 不清 P1_ONLY；37 不在
             stand 排除集）→ raw ✓ / filt ✓
          r1 y=81 phase=2 posture=1: phase=2 清零 37 与 53（均 P1_ONLY）→
             81 升为 top1 → filt ✓（raw 口径 81 也在 top3）
          r2 y=129 phase=3 posture=0: prone 排除集清零 81 与 37 → 129 进入
             top3 → filt ✓（raw 口径 129 排第 4 → miss）
          r3 y=53 phase=1 posture=2: phase=1 清零 129（P2_PLUS）→ 53 仍在
             top3 → filt ✓
        → top1=1/4, top3_raw=3/4, top3_filtered=4/4
        """
        probs = [
            [.50, .30, .15, .05],
            [.05, .55, .30, .10],
            [.15, .25, .55, .05],
            [.30, .12, .08, .50],
        ]
        model = StubModel(probs, [37, 53, 81, 129])
        m = benchmark_model.compute_metrics(model, mini_holdout())
        assert m["top1"] == pytest.approx(1 / 4)
        assert m["top3_raw"] == pytest.approx(3 / 4)
        assert m["top3_filtered"] == pytest.approx(1.0)

    def test_phase_filter_zeroes_p1_only(self):
        """y=P1_ONLY 类且 phase=2 → raw 命中但过滤后 miss（证明过滤链生效）。"""
        df = mini_holdout()
        df.loc[:, "phase"] = [2, 2, 2, 2]  # 全部 phase>1 → 37 被清零
        probs = [
            [.80, .07, .07, .06],
            [.05, .55, .30, .10],
            [.10, .20, .60, .10],
            [.30, .10, .10, .50],
        ]
        model = StubModel(probs, [37, 53, 81, 129])
        m = benchmark_model.compute_metrics(model, df)
        assert m["top3_raw"] >= 1 / 4          # r0 raw 命中（37 top1）
        assert m["top3_filtered"] < m["top3_raw"]  # r0 过滤后 37 被清零

    def test_macro_micro_both_present(self):
        model = StubModel(
            [[.5, .3, .15, .05], [.1, .2, .6, .1], [.1, .2, .6, .1], [.3, .1, .1, .5]],
            [37, 53, 81, 129],
        )
        m = benchmark_model.compute_metrics(model, mini_holdout())
        for key in ("top1", "top1_macro", "top3_raw", "macro_top3", "micro_top3",
                    "top3_filtered", "macro_top3_filtered", "holdout_rows"):
            assert key in m
        assert 0.0 <= m["macro_top3"] <= 1.0
        assert m["holdout_rows"] == 4


# =============================================================================
# 2. 确定性（同输入两次计算一致）
# =============================================================================

class TestDeterminism:
    def test_metrics_deterministic(self):
        probs = [[.5, .3, .15, .05], [.05, .55, .30, .10],
                 [.10, .20, .60, .10], [.30, .10, .10, .50]]
        model = StubModel(probs, [37, 53, 81, 129])
        m1 = benchmark_model.compute_metrics(model, mini_holdout())
        m2 = benchmark_model.compute_metrics(model, mini_holdout())
        assert m1 == m2

    def test_holdout_cache_reused(self, tmp_path):
        """缓存第二次直接读取：行内容逐位一致（CSV 缓存不保留原索引，按位置比对）。"""
        csv = tmp_path / "ds.csv"
        make_mini_dataset().to_csv(csv, index=False)
        cache = tmp_path / "holdout_cache.csv"

        h1, meta1 = benchmark_model.get_holdout(cache, csv)
        assert cache.exists()
        assert cache.with_suffix(".meta.json").exists()
        h2, meta2 = benchmark_model.get_holdout(cache, csv)
        assert len(h1) == len(h2)
        # 逐位置行内容一致（标签序列 + 全部列值；dtype 差异忽略——CSV 往返 int64）
        assert list(h1[LABEL_COL]) == list(h2[LABEL_COL])
        for col in h1.columns:
            assert h1[col].tolist() == h2[col].tolist(), f"缓存列不一致: {col}"
        assert meta2["holdout_sha256"] == meta1["holdout_sha256"]
        assert meta1["dataset_sha256"] == benchmark_model.sha256_file(csv)


# =============================================================================
# 3. mini 模型全指标（main() 端到端，极小迭代/时长）
# =============================================================================

def train_mini_lgbm(path, seed=42):
    df = make_mini_dataset(seed=seed)
    for col in ("posture", "previous_action", "phase", "is_enraged"):
        df[col] = df[col].astype("category")
    X, y = df[FEATURE_COLS], df[LABEL_COL]
    model = lgb.LGBMClassifier(
        objective="multiclass", num_leaves=7, max_depth=3,
        learning_rate=0.1, n_estimators=10, random_state=42, n_jobs=1,
        verbose=-1,
    )
    model.fit(X, y, categorical_feature=["posture", "previous_action", "phase", "is_enraged"])
    joblib.dump(model, path)
    return path


class TestFullBenchmarkMain:
    def test_main_produces_valid_report(self, tmp_path):
        """schema 键齐全、数值有限、缓存生成、退出码 0。"""
        dataset_csv = tmp_path / "ds.csv"
        make_mini_dataset().to_csv(dataset_csv, index=False)
        model_path = train_mini_lgbm(tmp_path / "mini_model.pkl")
        report_path = tmp_path / "reports" / "mini.json"
        cache = tmp_path / "holdout_cache.csv"

        rc = benchmark_model.main([
            "--model", str(model_path),
            "--report", str(report_path),
            "--dataset", str(dataset_csv),
            "--holdout-csv", str(cache),
            "--latency-iters", "8", "--latency-warmup", "2",
            "--mem-duration", "3",
        ])
        assert rc == 0
        assert report_path.exists()

        report = json.loads(report_path.read_text(encoding="utf-8"))
        for key in ("model_path", "model_sha256", "model_file_mb",
                    "dataset_sha256", "holdout_sha256",
                    "metrics", "latency_ms", "memory", "env", "timestamp"):
            assert key in report, f"报告缺键: {key}"

        for key in ("top1", "top3_raw", "top3_filtered", "macro_top3", "micro_top3"):
            v = report["metrics"][key]
            assert np.isfinite(v) and 0.0 <= v <= 1.0

        for key in ("mean_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms"):
            assert np.isfinite(report["latency_ms"][key])
        assert report["latency_ms"]["iters"] == 8

        for key in ("load_rss_delta_mb", "steady_rss_mb", "drift_mb_per_5min",
                    "model_file_mb"):
            assert key in report["memory"]
        assert np.isfinite(report["memory"]["drift_mb_per_5min"])
        assert report["memory"]["model_file_mb"] > 0

        for key in ("python", "sklearn", "os"):
            assert key in report["env"]

        assert cache.exists()

    def test_main_skip_flags(self, tmp_path):
        """--skip-latency --skip-mem → 报告只含指标，不崩溃。"""
        dataset_csv = tmp_path / "ds.csv"
        make_mini_dataset().to_csv(dataset_csv, index=False)
        model_path = train_mini_lgbm(tmp_path / "mini_model.pkl")
        report_path = tmp_path / "mini2.json"

        rc = benchmark_model.main([
            "--model", str(model_path),
            "--report", str(report_path),
            "--dataset", str(dataset_csv),
            "--holdout-csv", str(tmp_path / "cache.csv"),
            "--skip-latency", "--skip-mem",
        ])
        assert rc == 0
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert "latency_ms" not in report
        assert "memory" not in report
        assert "metrics" in report


# =============================================================================
# 4. 与共享数据模块的口径一致性
# =============================================================================

class TestHoldoutConsistency:
    def test_cache_equals_make_holdout_split_output(self, tmp_path):
        """缓存内容 = make_holdout_split（golden 同源）产出的留出集。"""
        csv = tmp_path / "ds.csv"
        make_mini_dataset().to_csv(csv, index=False)
        cache = tmp_path / "cache.csv"
        holdout_df, _ = benchmark_model.get_holdout(cache, csv)

        df = load_ml_dataset(csv)
        _, expected = make_holdout_split(df, test_size=0.2, random_state=42)
        assert list(holdout_df.index) == list(expected.index)
        assert list(holdout_df[LABEL_COL]) == list(expected[LABEL_COL])
