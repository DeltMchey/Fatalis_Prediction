"""P0: FLAML 2.6.0 依赖冒烟脚本 — AutoML 实验硬闸门（7 项）。

验证 FLAML 2.6.0 在钉版环境（Python 3.12.6 / pandas 3.0.2 / numpy 2.4.4 /
sklearn 1.8.0 / lightgbm 4.6.0 / Windows 原生）下的可用性。

冒烟清单（全部必须通过，任一失败则 AutoML 实验后续阶段全部停止）：
  1. import flaml / xgboost / psutil 成功，版本打印
  2. xgboost sklearn API（XGBClassifier）合成多分类 fit/predict/predict_proba/joblib round-trip
  3. FLAML 微搜索：~50 类 × 2000 行合成数据，['lgbm','xgboost','rf','extra_trees']，time_budget_s=60，cv
  4. FLAML 自定义 learner 注册路径：add_learner（flaml 2.6.0 的实际 API；
     规划文档中的 @register_learner 装饰器在 2.6.0 中不存在——代码现实优先）
  5. FLAML 自定义 metric 契约：(X_val, y_val, estimator, labels) -> (name, value, True)
  6. FLAML 纯数值列 DataFrame 输入路径（无 category/object dtype）
  7. automl.model 可访问且可提取原生 estimator

用法：
    python scripts/smoke_test_automl.py [--time-budget 60] [--out-dir experiments/automl_<date>]

输出：逐项 PASS/FAIL 打印 + smoke_report.md（含钉版号、通过项、warning 摘要）。
"""

import argparse
import io
import json
import os
import sys
import time
import warnings
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

# 保证从项目根可运行（python scripts/smoke_test_automl.py）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RESULTS = []


def check_item(item_id, title):
    """注册一个检查项的执行上下文，捕获 stdout/warning。"""

    def _run(fn):
        buf_out, buf_err = io.StringIO(), io.StringIO()
        t0 = time.perf_counter()
        err = None
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                with redirect_stdout(buf_out), redirect_stderr(buf_err):
                    fn()
            except Exception as exc:  # noqa: BLE001 — 冒烟脚本需报告任意失败
                err = exc
        elapsed = time.perf_counter() - t0
        RESULTS.append({
            "item": item_id,
            "title": title,
            "passed": err is None,
            "elapsed_s": round(elapsed, 1),
            "error": f"{type(err).__name__}: {err}" if err else None,
            "warnings": sorted({f"{w.category.__name__}: {str(w.message)[:160]}" for w in caught}),
            "stdout_tail": buf_out.getvalue()[-500:],
        })
        status = "PASS" if err is None else f"FAIL ({err})"
        print(f"[{item_id}] {title} -> {status} ({elapsed:.1f}s)")
        if err is not None:
            import traceback
            traceback.print_exc()
        return err is None

    return _run


def make_synthetic(n_rows=2000, n_classes=50, seed=42):
    """合成多分类数据：纯数值 DataFrame，规模模拟真实数据集（51 类 / 2444 行）。"""
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    n_features = 6
    centers = rng.normal(0, 3.0, size=(n_classes, n_features))
    cls = rng.integers(0, n_classes, size=n_rows)
    X = centers[cls] + rng.normal(0, 1.5, size=(n_rows, n_features))
    df = pd.DataFrame(
        X, columns=[f"f{i}" for i in range(n_features)]
    ).round(3)  # 纯 float64 列——统一数值编码方案下 FLAML 的实际输入面
    y = pd.Series(cls, name="label")
    return df, y


def item1_imports():
    import flaml
    import xgboost
    import psutil
    import sklearn
    import pandas
    import numpy
    import lightgbm
    print(f"flaml={flaml.__version__} xgboost={xgboost.__version__} psutil={psutil.__version__}")
    print(f"sklearn={sklearn.__version__} pandas={pandas.__version__} "
          f"numpy={numpy.__version__} lightgbm={lightgbm.__version__}")


def item2_xgboost_roundtrip(tmpdir):
    import joblib
    import numpy as np
    from xgboost import XGBClassifier

    df, y = make_synthetic(n_rows=400, n_classes=8, seed=1)
    clf = XGBClassifier(n_estimators=30, max_depth=3, random_state=42, n_jobs=1)
    clf.fit(df, y)
    pred = clf.predict(df.iloc[:10])
    proba = clf.predict_proba(df.iloc[:10])
    assert pred.shape == (10,)
    assert proba.shape == (10, 8)
    assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-6)
    assert len(clf.classes_) == 8

    path = str(Path(tmpdir) / "xgb_roundtrip.pkl")
    joblib.dump(clf, path)
    loaded = joblib.load(path)
    assert np.allclose(loaded.predict_proba(df.iloc[:10]), proba)
    print("XGBClassifier fit/predict/predict_proba/joblib round-trip OK")


def item3_flaml_micro_search(budget):
    from flaml import AutoML

    df, y = make_synthetic(n_rows=2000, n_classes=50, seed=42)
    automl = AutoML()
    automl.fit(
        df, y,
        task="classification",
        time_budget=budget,
        estimator_list=["lgbm", "xgboost", "rf", "extra_tree"],
        eval_method="cv",
        split_type="stratified",
        n_splits=3,
        seed=42,
        verbose=0,
        log_file_name="",
    )
    best = automl.best_estimator
    print(f"best_estimator={best}, best_config={json.dumps(automl.best_config)}")
    assert best is not None


def item4_custom_learner_registration(budget):
    """自定义 learner 注册路径（mlp 家族冒烟，等价物在 src/model/mlp_learner.py）。"""
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from flaml import AutoML
    from flaml.automl.model import BaseEstimator

    class _SmokeMLP(BaseEstimator):
        """最小可搜索 MLP wrapper：Pipeline(StandardScaler, MLPClassifier)。"""

        def __init__(self, task="multiclass", **config):
            super().__init__(task, **config)

        @classmethod
        def search_space(cls, **kwargs):
            return {
                "hl": {
                    "domain": (16, 32),
                    "init_value": 16,
                    "low_cost_init_value": 16,
                },
            }

        def fit(self, X_train, y_train, budget=None, **kwargs):
            hl = self.params.get("hl", 16)
            self._model = Pipeline([
                ("scaler", StandardScaler()),
                ("mlp", MLPClassifier(
                    hidden_layer_sizes=(hl,),
                    max_iter=80, random_state=42,
                )),
            ])
            self._model.fit(X_train, y_train)
            return self

    df, y = make_synthetic(n_rows=300, n_classes=6, seed=7)
    automl = AutoML()
    automl.add_learner(learner_name="smoke_mlp", learner_class=_SmokeMLP)
    automl.fit(
        df, y,
        task="classification",
        time_budget=budget,
        estimator_list=["smoke_mlp"],
        eval_method="cv",
        split_type="stratified",
        n_splits=2,
        seed=42,
        verbose=0,
        log_file_name="",
    )
    assert automl.best_estimator == "smoke_mlp"
    proba = automl.predict_proba(df.iloc[:5])
    assert proba.shape == (5, 6)
    print("add_learner + searchable + predict_proba OK")


def item5_custom_metric_contract(budget):
    """自定义 top-3 metric 契约。

    FLAML 2.6.0 实际契约（与规划文档的三元组不同，以代码现实为准）：
      - 调用签名：metric(X_val, y_val, estimator, labels, X_train, y_train,
                        weight_val, weight_train, config, groups_val, groups_train)
      - 返回值：二元组 (val_loss, metrics_dict) —— loss 被最小化；
        metrics_dict 至少含 "pred_time"（FLAML 内部 .get 读取）。
    """
    import time as _time

    import numpy as np
    from flaml import AutoML

    def top3_metric(X_val, y_val, estimator, labels, *metric_args):
        t0 = _time.perf_counter()
        probs = np.asarray(estimator.predict_proba(X_val))
        top3 = np.argsort(probs, axis=1)[:, -3:]
        y_arr = np.asarray(y_val)
        hit = np.mean([y_arr[i] in top3[i] for i in range(len(y_arr))])
        return 1.0 - float(hit), {
            "pred_time": (_time.perf_counter() - t0) / max(len(y_arr), 1),
            "top3_acc": float(hit),
        }

    df, y = make_synthetic(n_rows=400, n_classes=10, seed=3)
    automl = AutoML()
    automl.fit(
        df, y,
        task="classification",
        metric=top3_metric,
        time_budget=budget,
        estimator_list=["lgbm"],
        eval_method="cv",
        split_type="stratified",
        n_splits=2,
        seed=42,
        verbose=0,
        log_file_name="",
    )
    # automl.best_result 里的 metric 名应为自定义名
    assert automl.best_result is not None
    print(f"custom metric accepted; best_result keys={list(automl.best_result.keys())[:6]}")


def item6_numeric_dataframe_path(budget):
    """纯数值列 DataFrame（统一数值编码方案的实际输入面）无 category/object 异常。"""
    import numpy as np
    import pandas as pd
    from flaml import AutoML

    rng = np.random.default_rng(11)
    n = 600
    df = pd.DataFrame({
        "distance": rng.uniform(0, 5000, n),
        "relative_angle": rng.uniform(-180, 180, n),
        "posture": rng.integers(-1, 3, n),          # 数值码（含哨兵 -1）
        "previous_action": rng.integers(-1, 200, n),
        "phase": rng.integers(1, 4, n),
        "is_enraged": rng.integers(0, 2, n),
    })
    y = pd.Series(rng.integers(0, 12, n))
    assert all(str(dt) in ("float64", "int64") for dt in df.dtypes)

    automl = AutoML()
    automl.fit(
        df, y,
        task="classification",
        time_budget=budget,
        estimator_list=["lgbm", "rf"],
        eval_method="cv",
        split_type="stratified",
        n_splits=2,
        seed=42,
        verbose=0,
        log_file_name="",
    )
    assert automl.model is not None
    print("pure numeric DataFrame path OK")


def item7_model_extraction():
    """automl.model 可访问且其类型为原生 estimator（或可提取）。"""
    from flaml import AutoML

    df, y = make_synthetic(n_rows=300, n_classes=6, seed=5)
    automl = AutoML()
    automl.fit(
        df, y,
        task="classification",
        time_budget=15,
        estimator_list=["lgbm", "rf"],
        eval_method="cv",
        n_splits=2,
        seed=42,
        verbose=0,
        log_file_name="",
    )
    wrapper = automl.model  # flaml BaseEstimator wrapper
    native = getattr(wrapper, "estimator", None) or getattr(wrapper, "model", None)
    print(f"wrapper={type(wrapper).__name__}, native={type(native).__name__}")
    assert native is not None
    # 原生对象具有生产推理所需接口
    assert hasattr(native, "predict_proba")
    assert hasattr(native, "classes_")
    import flaml
    assert "flaml" not in type(native).__module__
    print(f"native estimator module={type(native).__module__}")


def write_report(out_dir, args):
    import datetime
    import platform

    try:
        import flaml, xgboost, psutil, sklearn, pandas, numpy, lightgbm
        versions = {
            "python": platform.python_version(),
            "os": platform.platform(),
            "flaml": flaml.__version__,
            "xgboost": xgboost.__version__,
            "psutil": psutil.__version__,
            "sklearn": sklearn.__version__,
            "pandas": pandas.__version__,
            "numpy": numpy.__version__,
            "lightgbm": lightgbm.__version__,
        }
    except Exception:  # noqa: BLE001
        versions = {"error": "version collection failed"}

    passed = sum(1 for r in RESULTS if r["passed"])
    lines = [
        "# P0 AutoML 依赖冒烟报告",
        "",
        f"- 时间：{datetime.datetime.now().isoformat(timespec='seconds')}",
        f"- 结果：**{passed}/{len(RESULTS)} 通过**",
        f"- 微搜索预算：item3={args.time_budget}s, item4/5/6={args.small_budget}s",
        "",
        "## 钉版环境",
        "",
    ]
    lines += [f"- {k}: {v}" for k, v in versions.items()]
    lines += ["", "## 逐项结果", ""]
    for r in RESULTS:
        mark = "PASS" if r["passed"] else "FAIL"
        lines.append(f"### [{r['item']}] {mark} — {r['title']} ({r['elapsed_s']}s)")
        if r["error"]:
            lines.append(f"- error: `{r['error']}`")
        for w in r["warnings"]:
            lines.append(f"- warning: {w}")
        lines.append("")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "smoke_report.md").write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "smoke_report.json").write_text(
        json.dumps({"versions": versions, "results": RESULTS}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nreport -> {out_dir / 'smoke_report.md'}")
    return passed == len(RESULTS)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--time-budget", type=int, default=60, help="item3 微搜索预算（秒）")
    ap.add_argument("--small-budget", type=int, default=25, help="item4/5/6/7 小搜索预算（秒）")
    ap.add_argument("--out-dir", type=str, default=None, help="报告输出目录")
    args = ap.parse_args()

    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="automl_smoke_")

    ok = True
    ok &= check_item(1, "imports + versions")(item1_imports)
    ok &= check_item(2, "xgboost sklearn API + joblib round-trip")(lambda: item2_xgboost_roundtrip(tmpdir))
    ok &= check_item(3, f"FLAML micro search (4 learners, {args.time_budget}s)")(
        lambda: item3_flaml_micro_search(args.time_budget))
    ok &= check_item(4, f"custom learner registration (add_learner, {args.small_budget}s)")(
        lambda: item4_custom_learner_registration(args.small_budget))
    ok &= check_item(5, f"custom metric contract ({args.small_budget}s)")(
        lambda: item5_custom_metric_contract(args.small_budget))
    ok &= check_item(6, f"pure numeric DataFrame path ({args.small_budget}s)")(
        lambda: item6_numeric_dataframe_path(args.small_budget))
    ok &= check_item(7, "automl.model native extraction")(item7_model_extraction)

    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        import datetime
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        out_dir = Path("experiments") / f"automl_{stamp}"
    report_ok = write_report(out_dir, args)

    if not (ok and report_ok):
        print("\nSMOKE FAILED — 后续阶段（P1+ 中依赖 FLAML 的部分 / P4）必须停止并上报")
        sys.exit(1)
    print("\nSMOKE PASSED 7/7")


if __name__ == "__main__":
    main()
