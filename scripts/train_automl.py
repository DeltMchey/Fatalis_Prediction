"""P4(AutoML 实验): FLAML 训练 CLI — 5 算法搜索 + 自定义 top-3 指标 + 超参约束。

用法：
    python scripts/train_automl.py --run A                 # 仅 6 锁定特征
    python scripts/train_automl.py --run B                 # 6 + 派生特征
    python scripts/train_automl.py --run A --smoke         # 小预算冒烟（管线验证）
    python scripts/train_automl.py --run A --time-budget 5400

核心设计（AutoML_Experiment_Plan P4，附录 A 锁定决策）：
  - 统一数值编码：FeatureBuilder 把 6 生产列转为纯数值矩阵（4 类别列 →
    固定词表码），FLAML 与 5 种 learner 不见 category dtype
  - 只喂 train_80：留出集绝不进入搜索（make_holdout_split，golden 锁定索引）
  - 自定义 top-3 metric（flaml 2.6.0 契约：返回 (val_loss, metrics_dict)）
  - estimator_list：['lgbm','xgboost','rf','extra_tree','mlp']——
    extra_tree 为 flaml 2.6.0 实际内置键；mlp 为 add_learner 注册的自定义 learner
  - custom_hp 上限：lgbm ≤400/127/9、xgb ≤400/8、rf/et ≤500/16；
    lgbm/rf/et 固定 class_weight='balanced'
  - 产物：run 目录下 run_manifest.json + FLAML log csv + best_config.json

本脚本仅 dev 使用，不进 EXE（build spec 不收集 scripts/）。
"""

import argparse
import datetime
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.model.dataset import (  # noqa: E402
    LABEL_COL,
    SOURCE_SESSION_COL,
    load_ml_dataset,
    make_holdout_split,
)
from src.model.features import FeatureBuilder  # noqa: E402
from src.model.mlp_learner import mlp_learner_wrapper  # noqa: E402


def sha256_file(path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ================== 自定义 metric ==================

def top3_metric(X_val, y_val, estimator, labels, *args, **kwargs):
    """FLAML 2.6.0 自定义指标：top-3 命中率（raw 口径，与 train_lgbm 一致）。

    契约（ml.py _eval_estimator）：入参 11 个位置参数；返回
    (val_loss, metrics_dict)，metrics_dict 须含 "pred_time"。
    top-1 并行记录于 metrics_dict（规划附录 A）。
    """
    import time as _time

    t0 = _time.perf_counter()
    probs = np.asarray(estimator.predict_proba(X_val))
    classes = np.asarray(estimator.classes_)
    top3 = np.argsort(probs, axis=1)[:, -3:]
    y = np.asarray(y_val)
    top3_hits = [y[i] in classes[top3[i]] for i in range(len(y))]
    top1_hits = [y[i] == classes[np.argmax(probs[i])] for i in range(len(y))]
    elapsed = _time.perf_counter() - t0
    return 1.0 - float(np.mean(top3_hits)), {
        "pred_time": elapsed / max(len(y), 1),
        "top3_acc": float(np.mean(top3_hits)),
        "top1_acc": float(np.mean(top1_hits)),
    }


# ================== custom_hp 解码 ==================

def build_custom_hp(spec: dict) -> dict:
    """把 configs/automl_experiment.json 的 custom_hp 数值表解码为 flaml tune domain。

    kind 支持：qlograndint / qrandint / loguniform / randint；fixed = 常量。
    """
    from flaml import tune

    makers = {
        "qlograndint": lambda s: tune.qlograndint(
            lower=s["lower"], upper=s["upper"], q=s.get("q", 1)),
        "qrandint": lambda s: tune.qrandint(
            lower=s["lower"], upper=s["upper"], q=s.get("q", 1)),
        "loguniform": lambda s: tune.loguniform(
            lower=s["lower"], upper=s["upper"]),
        "randint": lambda s: tune.randint(lower=s["lower"], upper=s["upper"]),
    }

    out = {}
    for learner, hps in spec.items():
        decoded = {}
        for name, s in hps.items():
            if "fixed" in s:
                decoded[name] = {"domain": s["fixed"]}
                continue
            kind = s.get("kind")
            if kind not in makers:
                raise ValueError(f"未知 custom_hp kind: {kind}（{learner}.{name}）")
            entry = {"domain": makers[kind](s)}
            for opt in ("init_value", "low_cost_init_value"):
                if opt in s:
                    entry[opt] = s[opt]
            decoded[name] = entry
        out[learner] = decoded
    return out


# ================== 训练流程 ==================

def prepare_train_data(dataset_csv: Path, derived: bool, n_bins: int):
    """加载数据 → golden 口径切分 → train_80 上 fit FeatureBuilder → 数值矩阵。

    Returns:
        (X_train, y_train, fb, holdout_df, groups_train, meta)
    """
    df = load_ml_dataset(dataset_csv)
    train_df, holdout_df = make_holdout_split(
        df, test_size=0.2, random_state=42,
    )

    fb = FeatureBuilder(derived=derived, n_bins=n_bins)
    X_train = fb.fit_transform(train_df)
    y_train = train_df[LABEL_COL]

    groups = (
        train_df[SOURCE_SESSION_COL].to_numpy()
        if SOURCE_SESSION_COL in train_df.columns else None
    )
    meta = {
        "dataset": str(dataset_csv),
        "dataset_sha256": sha256_file(dataset_csv),
        "train_rows": int(len(train_df)),
        "holdout_rows": int(len(holdout_df)),
        "train_classes": int(y_train.nunique()),
        "feature_run": {"derived": derived, "n_bins": n_bins},
        "feature_names": fb.get_feature_names_out(),
        "n_groups": int(pd.Series(groups).nunique()) if groups is not None else None,
    }
    return X_train, y_train, fb, holdout_df, groups, meta


def run_search(run_name: str, args, config: dict) -> dict:
    """执行一次 FLAML 搜索并落盘 manifest。"""
    from flaml import AutoML

    run_cfg = config["feature_runs"][run_name]
    X_train, y_train, fb, holdout_df, groups, meta = prepare_train_data(
        Path(args.dataset), run_cfg["derived"], run_cfg.get("n_bins", 8),
    )

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_root) / f"automl_{stamp}_{run_name}" \
        if args.run_dir is None else Path(args.run_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    custom_hp = build_custom_hp(config["custom_hp"])
    estimator_list = list(config["estimator_list"])
    if args.smoke:
        estimator_list = args.smoke_estimators.split(",")

    automl = AutoML()
    if "mlp" in estimator_list:
        automl.add_learner(learner_name="mlp", learner_class=mlp_learner_wrapper())

    settings = dict(
        task="classification",
        metric=top3_metric,
        eval_method=config["eval_method"],
        split_type=config["split_type"],
        n_splits=config["n_splits"],
        seed=config["seed"],
        time_budget=args.time_budget,
        estimator_list=estimator_list,
        custom_hp=custom_hp,
        log_file_name=str(out_dir / "flaml_log.csv"),
        retrain_full=config.get("retrain_full", True),
        verbose=1 if args.smoke else 2,
        keep_search_state=True,
    )
    automl.fit(X_train, y_train, **settings)

    # ---- manifest（规划 P4 运行清单）----
    best_estimator = automl.best_estimator
    wrapper = automl.model
    native = getattr(wrapper, "estimator", None) or getattr(wrapper, "model", None)

    manifest = {
        "run": run_name,
        "config": config,
        "cli_args": {
            "time_budget": args.time_budget, "smoke": args.smoke,
            "dataset": args.dataset,
        },
        "data": meta,
        "best_estimator": best_estimator,
        "best_config": automl.best_config,
        "best_cv_loss": float(automl.best_loss),
        "best_cv_top3_acc": (
            1.0 - float(automl.best_loss)
            if automl.best_loss is not None else None
        ),
        "native_estimator_type": f"{type(native).__module__}.{type(native).__name__}",
        "flaml_log": str(out_dir / "flaml_log.csv"),
        "env": {
            "python": platform.python_version(),
            "os": platform.platform(),
            "flaml": __import__("flaml").__version__,
            "sklearn": __import__("sklearn").__version__,
            "lightgbm": __import__("lightgbm").__version__,
            "xgboost": __import__("xgboost").__version__,
        },
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    (out_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8",
    )
    (out_dir / "best_config.json").write_text(
        json.dumps({"best_estimator": best_estimator, "best_config": automl.best_config},
                   indent=1, ensure_ascii=False),
        encoding="utf-8",
    )
    # 保存 fit 后的 FeatureBuilder（P5 导出复用同一实例，词表/分箱/频次表一致）
    import joblib
    joblib.dump(fb, out_dir / "feature_builder.pkl")

    print(f"\n=== run {run_name} done ===")
    print(f"best_estimator={best_estimator}")
    print(f"best CV top3={manifest['best_cv_top3_acc'] * 100 if manifest['best_cv_top3_acc'] is not None else 'n/a'}%")
    print(f"manifest -> {out_dir / 'run_manifest.json'}")
    return {"manifest": manifest, "out_dir": out_dir, "automl": automl}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", required=True, choices=["A", "B"],
                    help="特征 run：A=仅 6 锁定列；B=6+派生列")
    ap.add_argument("--dataset", default="data/ML_Ready_Dataset.csv")
    ap.add_argument("--config", default="configs/automl_experiment.json")
    ap.add_argument("--time-budget", type=float, default=None,
                    help="覆盖 config 的 time_budget_s（秒）")
    ap.add_argument("--output-root", default=None)
    ap.add_argument("--run-dir", default=None, help="覆盖输出目录（默认自动时间戳）")
    ap.add_argument("--smoke", action="store_true",
                    help="小预算冒烟：验证管线跑通（不产正式结果）")
    ap.add_argument("--smoke-estimators", default="lgbm,rf",
                    help="冒烟模式使用的 estimator 子集（逗号分隔）")
    args = ap.parse_args(argv)

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.time_budget is None:
        args.time_budget = 60.0 if args.smoke else float(config["time_budget_s"])
    if args.output_root is None:
        args.output_root = config.get("output_root", "experiments")

    if not Path(args.dataset).exists():
        print(f"数据集不存在: {args.dataset}")
        return 2

    run_search(args.run, args, config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
