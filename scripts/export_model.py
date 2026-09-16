"""P5(AutoML 实验): 模型导出 CLI — FLAML 产物 → 零 flaml 运行时依赖的生产对象。

主路径（提取）：
    导出对象 = Pipeline([('features', fit 后 FeatureBuilder),
                          ('estimator', 从 automl_best.pkl 提取的原生 estimator)])
    - lgbm/xgboost/rf/extra_tree → LGBMClassifier / XGBClassifier /
      RandomForestClassifier / ExtraTreesClassifier
    - mlp → Pipeline(OneHot+Scaler, BalancedMLPClassifier)（src/model/ 可导入）
    提取后重持久化（joblib.dump 到新文件），pickle 内不含 flaml 引用。

备选路径（确定性重训，R-08 缓解）：若提取对象 pickle 仍引用 flaml 内部类，
用 best_config 以原生 API（seed=42, n_jobs=1）在 train_80 上重训等价模型。

接口契约（ActionPredictor 不改一行即可加载）：
    joblib.load(导出文件).predict_proba(DataFrame[6 列, 4 列 category dtype])
    .classes_ 经 sklearn Pipeline available_if 委托末步可访问

生产路径保护（规划 5.3 三层机制之第 1 层——物理隔离）：
    写路径白名单 = {fatalis_ai_model_automl*} ∪ experiments/；
    代码层面不存在写 fatalis_ai_model(.bak) 的语句（tests 断言源码约束）。

用法：
    python scripts/export_model.py --run-dir experiments/automl_<...>_A \
        [--out models/fatalis_ai_model_automl.pkl] [--dataset data/ML_Ready_Dataset.csv] \
        [--no-verify]
"""

import argparse
import datetime
import json
import platform
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.model.dataset import LABEL_COL, load_ml_dataset, make_holdout_split  # noqa: E402
from src.model.features import FeatureBuilder  # noqa: E402

# ================== 生产路径保护 ==================

# 生产模型文件名（任何情况下不得作为导出目标）
PRODUCTION_MODEL_NAMES = {"fatalis_ai_model.pkl", "fatalis_ai_model.pkl.bak"}
# 导出主产物基名（采纳前与生产模型物理隔离）
EXPORT_BASENAME = "fatalis_ai_model_automl"
# 允许写入的目录名（相对项目根）
ALLOWED_DIRS = {"experiments", "models"}


def assert_safe_export_path(out_path: Path) -> None:
    """导出写路径白名单校验（物理隔离机制）。

    规则：basename 以 fatalis_ai_model_automl 开头（任意扩展），且父目录
    为 models/ 或 experiments/；绝不等于生产文件名。
    """
    out_path = Path(out_path)
    if out_path.name in PRODUCTION_MODEL_NAMES:
        raise ValueError(f"拒绝写入生产模型路径: {out_path}")
    parent_name = out_path.parent.name.lower()
    if parent_name not in ALLOWED_DIRS:
        raise ValueError(
            f"导出目录不在白名单 {sorted(ALLOWED_DIRS)} 内: {out_path.parent}"
        )
    if not out_path.name.startswith(EXPORT_BASENAME):
        raise ValueError(
            f"导出文件名必须以 {EXPORT_BASENAME} 开头: {out_path.name}"
        )


# ================== 提取主路径 ==================

def extract_native_estimator(wrapper):
    """从 flaml wrapper（automl_best.pkl 反序列化对象）提取原生 estimator。"""
    for attr in ("estimator", "model"):
        native = getattr(wrapper, attr, None)
        if native is not None and hasattr(native, "predict_proba"):
            return native
    # 兼容：直接传入原生对象（重训产物 / 手工构造）
    if hasattr(wrapper, "predict_proba"):
        return wrapper
    raise TypeError(f"无法从 {type(wrapper)} 提取原生 estimator")


def build_export_pipeline(feature_builder: FeatureBuilder, native_estimator,
                          train_labels=None):
    """组装导出对象：Pipeline(FeatureBuilder, 原生 estimator)。

    输入契约：6 生产列 DataFrame（4 列可为 category dtype）。

    Args:
        train_labels: 训练原始标签全集（run_manifest.data.train_labels）。
            FLAML auto_augment 对分类任务 LabelEncoder 编码 y——提取物
            classes_ 为 [0..n-1] 编码值；提供 train_labels 时自动包一层
            LabelDecodedEstimator 还原为原始动作 ID（ActionPredictor 过滤
            链依赖动作 ID）。已是原始标签的 estimator（重训路径）则透传。
    """
    from sklearn.pipeline import Pipeline

    estimator = wrap_with_label_decoder(native_estimator, train_labels)
    return Pipeline([
        ("features", feature_builder),
        ("estimator", estimator),
    ])


def wrap_with_label_decoder(native_estimator, train_labels):
    """必要时用 LabelDecodedEstimator 还原 classes_ 为原始标签。"""
    if train_labels is None:
        return native_estimator
    native_classes = set(int(c) for c in np.asarray(native_estimator.classes_))
    if native_classes == set(int(v) for v in train_labels):
        return native_estimator  # 已是原始标签（确定性重训路径）
    from src.model.label_decode import LabelDecodedEstimator
    return LabelDecodedEstimator(native_estimator, train_labels)


# ================== 备选路径：确定性重训 ==================

_NATIVE_FAMILIES = None


def _native_family_constructors():
    """family → (原生类, 兼容参数过滤表)。惰性导入避免不必要的重依赖。"""
    global _NATIVE_FAMILIES
    if _NATIVE_FAMILIES is None:
        import inspect

        import lightgbm as lgb
        import xgboost as xgb
        from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier

        def _sig_params(cls):
            """构造参数白名单；纯 kwargs 转发构造器返回 None（透传模式）。

            两种 **kwargs 形态必须区分：
            - xgboost sklearn 包装：签名只有 (objective, **kwargs)，booster
              参数全部经 kwargs 转发——按签名过滤会把 best_config 全部丢弃
              （静默训练默认配置模型），须走透传分支；
            - lgbm/rf 等：签名显式枚举模型参数 + 尾部 **kwargs 接收别名，
              白名单过滤仍然有效。
            判据：签名除 self/objective 外无显式参数 → 透传。
            """
            sig = inspect.signature(cls.__init__).parameters
            explicit = {
                k for k, p in sig.items()
                if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD,
                              inspect.Parameter.KEYWORD_ONLY)
                and k != "self"
            }
            if not explicit - {"objective"}:
                return None
            return {"class_weight", "n_jobs", "random_state"} | explicit

        _NATIVE_FAMILIES = {
            "lgbm": (lgb.LGBMClassifier, _sig_params(lgb.LGBMClassifier)),
            "xgboost": (xgb.XGBClassifier, _sig_params(xgb.XGBClassifier)),
            "rf": (RandomForestClassifier, _sig_params(RandomForestClassifier)),
            "extra_tree": (ExtraTreesClassifier, _sig_params(ExtraTreesClassifier)),
        }
    return _NATIVE_FAMILIES


def retrain_native(estimator_family: str, best_config: dict, X_train, y_train):
    """备选路径（R-08）：best_config → 原生 API 确定性重训（seed=42, n_jobs=1）。

    配置映射保守处理：显式签名构造器（lgbm/rf/extra_tree）只保留签名内
    参数；**kwargs 构造器（xgboost sklearn 包装）走透传分支并镜像 FLAML
    config2params 的注入项（objective/enable_categorical/verbosity），
    保证重训产物与 FLAML 重训等价。flaml 特有键丢弃
    （FLAML_sample_size / max_leaves→num_leaves 换算 lgbm 家族）。
    mlp 家族的重训走 wrapper（build 后 fit），此处不支持（提取路径必然纯净）。
    """
    if estimator_family not in _native_family_constructors():
        raise ValueError(
            f"确定性重训不支持 {estimator_family}（mlp 走提取路径，无需重训）"
        )
    cls, allowed = _native_family_constructors()[estimator_family]
    config = dict(best_config)
    config.pop("FLAML_sample_size", None)
    if estimator_family == "lgbm" and "max_leaves" in config and "num_leaves" not in config:
        config["num_leaves"] = config.pop("max_leaves")
    if allowed is None:
        # 纯 kwargs 转发构造器（xgboost sklearn 包装）：booster 参数透传
        # + FLAML config2params 注入项（objective/enable_categorical/verbosity）
        config.update(objective="multi:softprob", enable_categorical=True,
                      verbosity=0)
        params = config
    else:
        params = {k: v for k, v in config.items() if k in allowed}
    params["random_state"] = 42
    params["n_jobs"] = 1
    model = cls(**params)
    model.fit(X_train, y_train)
    return model


# ================== 无 flaml 加载验证 ==================

_VERIFY_CODE = r"""
import sys
sys.modules['flaml'] = None
sys.modules['flaml.automl'] = None
import joblib, json
model = joblib.load(r"{path}")
row = {{'distance': 500.0, 'relative_angle': 30.0, 'posture': 1,
        'previous_action': 37, 'phase': 1, 'is_enraged': 0}}
import pandas as pd
X = pd.DataFrame([row])
for c in ('posture', 'previous_action', 'phase', 'is_enraged'):
    X[c] = X[c].astype('category')
probs = model.predict_proba(X)
print(json.dumps({{
    'classes': [int(c) for c in model.classes_],
    'n_classes': len(model.classes_),
    'prob_sum': float(probs[0].sum()),
}}))
"""


def verify_no_flaml_load(path) -> dict:
    """子进程屏蔽 flaml 导入后 joblib.load + 单行推理（规划 P5 兼容验证 ①）。"""
    import subprocess

    code = _VERIFY_CODE.format(path=str(Path(path).resolve()))
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(Path(__file__).resolve().parents[1]),
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"无 flaml 环境加载/推理失败 (rc={result.returncode}): "
            f"{result.stderr.strip()[-500:]}"
        )
    line = result.stdout.strip().splitlines()[-1]
    return json.loads(line)


def pickle_references_flaml(path) -> bool:
    """检查 pickle 字节流是否包含 flaml 模块路径字符串（粗粒度快速判定）。"""
    data = Path(path).read_bytes()
    return re.search(rb"flaml[\./]", data) is not None


# ================== 导出主流程 ==================

def export_from_run(run_dir: Path, out_path: Path, dataset_csv: Path = None,
                    verify: bool = True) -> dict:
    """从 run 目录（train_automl 产物）导出生产可加载模型 + sidecar meta。"""
    import joblib

    run_dir = Path(run_dir)
    manifest = json.loads(
        (run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    fb = joblib.load(run_dir / "feature_builder.pkl")
    wrapper = joblib.load(run_dir / "automl_best.pkl")

    assert_safe_export_path(out_path)

    native = extract_native_estimator(wrapper)
    train_labels = manifest["data"].get("train_labels")
    extraction = "extract"

    # 提取后先持久化到目标，再验证 pickle 是否残留 flaml 引用 → 备选重训
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pipeline = build_export_pipeline(fb, native, train_labels=train_labels)
    joblib.dump(pipeline, out_path)

    if pickle_references_flaml(out_path):
        # 备选路径：确定性重训（mlp 家族提取物为纯 sklearn，理论不触发）
        family = manifest["best_estimator"]
        if family == "mlp":
            raise RuntimeError("mlp 提取物不应含 flaml 引用——请检查导出逻辑")
        if dataset_csv is None:
            raise RuntimeError(
                "提取物含 flaml 引用且未提供 --dataset，无法执行确定性重训备选路径"
            )
        df = load_ml_dataset(dataset_csv)
        train_df, _ = make_holdout_split(df, test_size=0.2, random_state=42)
        X_train = fb.transform(train_df)
        y_train = train_df[LABEL_COL]
        native = retrain_native(family, manifest["best_config"], X_train, y_train)
        pipeline = build_export_pipeline(fb, native, train_labels=train_labels)
        joblib.dump(pipeline, out_path)
        if pickle_references_flaml(out_path):
            raise RuntimeError("重训后 pickle 仍含 flaml 引用（R-08 双路径均失败）")
        extraction = "retrain"

    meta = {
        "run_dir": str(run_dir),
        "export_path": str(out_path),
        "export_sha256": _sha256(out_path),
        "dataset_sha256": manifest["data"]["dataset_sha256"],
        "feature_run": manifest["data"]["feature_run"],
        "feature_names": manifest["data"]["feature_names"],
        "best_estimator": manifest["best_estimator"],
        "best_config": manifest["best_config"],
        "best_cv_top3_acc": manifest.get("best_cv_top3_acc"),
        "extraction_path": extraction,
        "env": {
            "python": platform.python_version(),
            "sklearn": __import__("sklearn").__version__,
            "lightgbm": __import__("lightgbm").__version__,
            "os": platform.platform(),
        },
        "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }

    if verify:
        meta["no_flaml_verification"] = verify_no_flaml_load(out_path)

    meta_path = out_path.with_suffix("").with_name(
        out_path.with_suffix("").name + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=1, ensure_ascii=False),
                         encoding="utf-8")

    print(f"exported: {out_path}")
    print(f"  family={meta['best_estimator']} extraction={extraction} "
          f"features={len(meta['feature_names'])}")
    if verify:
        v = meta["no_flaml_verification"]
        print(f"  no-flaml load OK: {v['n_classes']} classes, "
              f"prob_sum={v['prob_sum']:.4f}")
    print(f"meta -> {meta_path}")
    return meta


def _sha256(path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", required=True, help="train_automl 的 run 目录")
    ap.add_argument("--out", default=f"models/{EXPORT_BASENAME}.pkl",
                    help=f"导出路径（默认 models/{EXPORT_BASENAME}.pkl；白名单保护）")
    ap.add_argument("--dataset", default="data/ML_Ready_Dataset.csv",
                    help="确定性重训备选路径用数据集")
    ap.add_argument("--no-verify", action="store_true",
                    help="跳过无 flaml 子进程加载验证")
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir)
    if not (run_dir / "run_manifest.json").exists():
        print(f"run 目录缺 run_manifest.json: {run_dir}")
        return 2

    export_from_run(run_dir, Path(args.out), Path(args.dataset),
                    verify=not args.no_verify)
    return 0


if __name__ == "__main__":
    sys.exit(main())
