"""P8(AutoML 采纳后): 一键训练正式后端 — Run B 胜出配置（xgboost）确定性重训。

把 experiments/automl_20260915/p7_repro_runB.py 验证过的复现链路
（逐位一致，max_abs_diff=0.0）提升为正式模块，供 launch.py --pipeline
（Dashboard「开始训练」按钮）消费；train_lgbm.py 保留为 legacy --train 入口。

完整链路（与 FLAML 训练 Run B 时的数据口径逐项对齐，来源核实记录见
experiments/automl_20260915/reports/p7_repro_runB.json）：
  1. load_ml_dataset        — 加载 + 过滤（与 train_lgbm/golden 测试同一实现）
  2. make_holdout_split     — 分层 80/20 切分（random_state=42，golden 索引一致）
  3. FeatureBuilder.fit_transform(train_80) — 6 原始列 → 12 数值列；
     分箱边缘/频次表只在 train 上学习（防泄漏红线 R-05）
  4. FLAML auto_augment 镜像 — 计数 <20 的稀有类整行复制至 ≥20（升标签序）
  5. shuffle(random_state=1) + reset_index — flaml.config.RANDOM_SEED 口径
  6. LabelEncoder 编码 y → XGBClassifier(Run B best_config) 训练
     （n_jobs=1 内嵌；不设 random_state → XGBClassifier 默认 0，与 FLAML 一致）
  7. LabelDecodedEstimator 包装还原 classes_ 为动作 ID → Pipeline 导出
  8. 写前 .bak 轮换 → joblib.dump → feature_importance.png → sidecar meta

接口契约：与 train_fatalis_ai 对等——无参调用读 CWD 相对路径
（开发模式 CWD=项目根，冻结模式 CWD=exe 目录，由 controller 保证），
产物结构与现行采纳模型完全同构：
  Pipeline[('features', FeatureBuilder),
           ('estimator', LabelDecodedEstimator(XGBClassifier(n_jobs=1)))]
ActionPredictor 零改动加载（joblib.load → predict_proba）。
"""

import datetime
import json
import os
import platform
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder
from sklearn.utils import shuffle as sklearn_shuffle

from src.core.backup_chain import (
    ROTATED,
    promote_with_backup,
    sha256_file as _sha256_file,
)
from src.logging_config import setup_logging

logger = setup_logging()

# ================== 常量（Run B 胜出配置，单一事实源）==================

# 来源：experiments/automl_20260915/p6_runB/run_manifest.json best_config
# （FLAML 搜索胜出，CV top3 72.51%；正式值不再依赖 experiments/ 运行时读取）
RUNB_BEST_CONFIG: dict = {
    "n_estimators": 190,
    "max_leaves": 4,
    "min_child_weight": 0.019429439515313975,
    "learning_rate": 0.07796774685886149,
    "subsample": 0.9457311987921387,
    "colsample_bylevel": 1.0,
    "colsample_bytree": 0.7781106489263098,
    "reg_alpha": 0.0009765625,
    "reg_lambda": 0.042063643624928454,
    "max_depth": 4,
}

# FLAML 重训口径注入项（经 get_params() 核实，p7_repro_runB）：
# 不设 random_state —— FLAML 未注入，XGBClassifier 默认 0
RUNB_FIXED_EXTRA_PARAMS: dict = {
    "objective": "multi:softprob",
    "enable_categorical": True,
    "verbosity": 0,
    "n_jobs": 1,
}

# FeatureBuilder 配置（Run B：6 基础 + 6 派生 = 12 列）
RUNB_FEATURE_RUN: dict = {"derived": True, "n_bins": 8}

FLAML_RANDOM_SEED = 1        # flaml.config.RANDOM_SEED（数据准备 shuffle 用）
RARE_CLASS_THRESHOLD = 20    # flaml generic_task.prepare_data auto_augment 阈值
HOLDOUT_RANDOM_STATE = 42    # 与 train_lgbm / golden 索引测试一致

# v3(F4) 训练守门阈值（只告警不阻断——用户可能就是想在小数据上试，
# 但数据量骤减必须被看见；告警同时写入 sidecar 的 gate_warnings）
GATE_MIN_ROWS_RATIO = 0.5     # 新数据集行数低于原模型的 50% → 告警
GATE_MIN_HOLDOUT_ROWS = 100   # 留出集 <100 行 → 指标精度告警
GATE_CLASS_DROP_RATIO = 0.2   # 类别数较原模型下降 ≥20% → 告警

# 产物路径（相对 CWD；与 train_lgbm.py 同口径）
DEFAULT_DATASET_CSV = "data/ML_Ready_Dataset.csv"
DEFAULT_MODELS_DIR = "models"
PRODUCTION_MODEL_NAME = "fatalis_ai_model.pkl"
BACKUP_MODEL_NAME = "fatalis_ai_model.pkl.bak"
SIDECAR_NAME = "fatalis_ai_model.pkl.meta.json"
IMPORTANCE_PNG_NAME = "feature_importance.png"

# 12 列中文名映射（特征重要性图用；6 基础 + 6 派生）
FEATURE_NAME_ZH: dict = {
    "distance": "距离",
    "relative_angle": "相对角度",
    "posture": "姿态",
    "previous_action": "上一招",
    "phase": "阶段",
    "is_enraged": "是否发怒",
    "angle_sin": "角度正弦",
    "angle_cos": "角度余弦",
    "distance_bin": "距离分箱",
    "distance_x_enraged": "距离×发怒",
    "posture_x_phase": "姿态×阶段",
    "prev_action_freq": "上一招频率",
}


# ================== FLAML 数据准备镜像（p7_repro_runB 逐位复现口径）==================

def flaml_auto_augment(X: pd.DataFrame, y: pd.Series,
                       rare_threshold: int = RARE_CLASS_THRESHOLD
                       ) -> tuple[pd.DataFrame, pd.Series]:
    """镜像 flaml generic_task.prepare_data 的稀有类增广。

    对计数 < rare_threshold 的类别（升标签序逐类处理）整行复制追加，
    直到该类计数 ≥ rare_threshold；充足类别不动。

    Args:
        X: 特征 DataFrame（已过 FeatureBuilder，纯数值 12 列）
        y: 与 X 行对齐的标签 Series
        rare_threshold: 稀有类判定阈值（FLAML 默认 20）

    Returns:
        (X_aug, y_aug): 增广后的特征与标签（原行在前，副本按标签升序追加）
    """
    parts_X, parts_y = [X], [y]
    for label in np.unique(y):
        count = int((y == label).sum())
        if count >= rare_threshold:
            continue
        n = count
        while n < rare_threshold:
            parts_X.append(X[y == label])
            parts_y.append(y[y == label])
            n += count
    return pd.concat(parts_X), pd.concat(parts_y)


def flaml_data_prep(X_train: pd.DataFrame, y_train: pd.Series
                    ) -> tuple[pd.DataFrame, np.ndarray]:
    """FLAML 数据准备镜像：auto_augment → shuffle(1) → reset_index → 标签编码。

    Args:
        X_train: train_80 特征（FeatureBuilder 产出，12 数值列）
        y_train: 原始动作 ID 标签

    Returns:
        (X_prep, y_encoded): 打乱重置索引后的特征 + LabelEncoder 编码标签
        （xgboost sklearn API 要求标签 ∈ [0, n)，编码不可省略）
    """
    X_aug, y_aug = flaml_auto_augment(X_train, y_train)
    X_s, y_s = sklearn_shuffle(X_aug, y_aug, random_state=FLAML_RANDOM_SEED)
    X_s = X_s.reset_index(drop=True)
    y_s = pd.Series(y_s).reset_index(drop=True)
    y_enc = LabelEncoder().fit_transform(y_s)
    return X_s, y_enc


# ================== 估计器构造 ==================

def build_runb_estimator():
    """按 FLAML 重训口径构造 XGBClassifier（Run B best_config + 固定注入项）。

    不设 random_state（XGBClassifier 默认 0）——与 FLAML 训练时一致，
    是 p7_repro_runB 逐位复现的必要条件之一。
    """
    from xgboost import XGBClassifier

    params = dict(RUNB_BEST_CONFIG)
    params.update(RUNB_FIXED_EXTRA_PARAMS)
    return XGBClassifier(**params)


# _sha256_file 由 src.core.backup_chain 导入（v3 起共享实现，旧名保留供调用方）


# ================== 特征重要性图 ==================

def _evaluate_holdout(pipeline: Pipeline, test_df: pd.DataFrame
                      ) -> tuple[float, float]:
    """留出集指标（predict 经解码层还原动作 ID）。

    Returns:
        (top1_accuracy, top3_hit_rate)：与 train_lgbm 同口径的黄金指标。
    """
    from src.model.dataset import LABEL_COL

    y_test = test_df[LABEL_COL].to_numpy()
    y_pred = pipeline.predict(test_df)
    accuracy = float(np.mean(y_pred == y_test))
    probs = pipeline.predict_proba(test_df)
    classes = pipeline.classes_
    top3_idx = np.argsort(probs, axis=1)[:, -3:]
    top3 = float(np.mean(
        [y_test[i] in classes[top3_idx[i]] for i in range(len(y_test))]))
    return accuracy, top3


def _plot_feature_importance(estimator, feature_names: list, out_path) -> None:
    """xgboost gain 重要性横向条形图（中文列名，SimHei/YaHei 配置与 legacy 一致）。"""
    import matplotlib
    matplotlib.use("Agg")  # 仅 savefig 无交互显示——显式 Agg 保证冻结/CI 安全
    import matplotlib.pyplot as plt

    # gain 口径直接从 booster 取，不改构造参数（避免动训练配置）
    gain = estimator.get_booster().get_score(importance_type="gain")
    importance = np.array([float(gain.get(name, 0.0)) for name in feature_names])

    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.figure(figsize=(10, 6))
    indices = np.argsort(importance)
    plt.barh(range(len(indices)), importance[indices], color="mediumturquoise")
    plt.yticks(range(len(indices)),
               [FEATURE_NAME_ZH.get(feature_names[i], feature_names[i])
                for i in indices])
    plt.title("黑龙出招决策权重（Run B · XGBoost gain）")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close(plt.gcf())


# ================== 主入口 =================

def _load_previous_stats(models_dir) -> dict | None:
    """读取现有 sidecar 的上一版训练数据规模（F4 守门对照基准）。

    Returns:
        {"rows": int|None, "sessions": int|None, "classes": int|None}；
        sidecar 缺失/损坏/字段缺失 → 对应项 None（首训/旧版 sidecar 场景）。
    """
    try:
        data = json.loads(
            (Path(models_dir) / SIDECAR_NAME).read_text(encoding="utf-8"))
        d = data.get("data", {})
        return {
            "rows": d.get("dataset_rows"),
            "sessions": d.get("train_sessions"),
            "classes": data.get("n_classes"),
        }
    except Exception:
        return None


def evaluate_gates(new_rows: int, new_classes: int, holdout_rows: int,
                   prev: dict | None) -> list[str]:
    """v3(F4) 破坏性变化守门——返回告警消息列表（不阻断训练）。

    规则（任一命中即一条告警；prev 缺失项跳过对应规则）：
      1. 新数据集行数 < 原模型的 GATE_MIN_ROWS_RATIO（50%）
      2. 留出集 < GATE_MIN_HOLDOUT_ROWS 行（指标百分比不可当精确值）
      3. 类别数较原模型下降 ≥ GATE_CLASS_DROP_RATIO（20%）
    """
    warnings: list[str] = []
    prev = prev or {}
    prev_rows = prev.get("rows")
    prev_classes = prev.get("classes")
    if isinstance(prev_rows, (int, float)) and prev_rows > 0 \
            and new_rows < GATE_MIN_ROWS_RATIO * prev_rows:
        warnings.append(
            f"新数据集仅 {new_rows} 行，不足原模型训练数据（{int(prev_rows)} 行）"
            f"的 {int(GATE_MIN_ROWS_RATIO * 100)}% —— 若非有意精简数据，请检查"
            " data/ 目录战斗 CSV 是否齐全（数据清洗已保留历史会话，见上方合并日志）")
    if holdout_rows < GATE_MIN_HOLDOUT_ROWS:
        warnings.append(
            f"留出集仅 {holdout_rows} 行：本次 Accuracy/Top-3 百分比随机波动"
            "很大，仅供趋势参考，请勿当精确指标解读")
    if isinstance(prev_classes, (int, float)) and prev_classes > 0 \
            and new_classes < prev_classes \
            and (prev_classes - new_classes) / prev_classes >= GATE_CLASS_DROP_RATIO:
        warnings.append(
            f"动作类别数从 {int(prev_classes)} 降至 {new_classes}"
            f"（降幅 ≥{int(GATE_CLASS_DROP_RATIO * 100)}%）—— 训练数据多样性"
            "明显缩水，若非有意请检查数据来源")
    return warnings


def train_runb_backend(dataset_csv=DEFAULT_DATASET_CSV,
                       models_dir=DEFAULT_MODELS_DIR) -> dict | None:
    """一键训练正式后端：以 Run B 胜出配置确定性重训并写生产产物。

    与 train_fatalis_ai 对等：默认读 CWD 相对路径 data/ML_Ready_Dataset.csv，
    写 models/fatalis_ai_model.pkl（写前轮换 .bak）、feature_importance.png、
    fatalis_ai_model.pkl.meta.json sidecar。数据缺失/为空时优雅返回
    （print + logger.error），不覆盖旧模型。

    Args:
        dataset_csv: ML 就绪数据集路径（默认 data/ML_Ready_Dataset.csv）
        models_dir: 产物目录（默认 models/）

    Returns:
        成功: 摘要 dict（指标/路径/耗时/sidecar）；失败/跳过: None
    """
    from src.model.dataset import (
        EmptyDatasetError, LABEL_COL, SOURCE_SESSION_COL, load_ml_dataset,
        make_holdout_split,
    )
    from src.model.features import FeatureBuilder
    from src.model.label_decode import LabelDecodedEstimator

    # v1.1 口径：显式检查输入数据集存在——clean 失败时停止，不覆盖旧模型
    if not os.path.exists(dataset_csv):
        logger.error("找不到 %s", dataset_csv)
        print(f"❌ 找不到 {dataset_csv}！请先录制战斗数据或运行 data_cleaner.py")
        return None

    print("🔄 正在加载纯粹观测流战斗数据集...")
    try:
        df = load_ml_dataset(dataset_csv)
    except EmptyDatasetError as e:
        print(e.print_message)
        logger.error(e.log_message)
        return None
    except Exception:
        logger.error("读取 %s 失败", dataset_csv)
        print(f"❌ 读取 {dataset_csv} 失败！")
        return None

    # ---- v3(F4): 本次训练数据统计（摘要行 + 守门基准）----
    n_rows = int(len(df))
    n_classes = int(df[LABEL_COL].nunique())
    if SOURCE_SESSION_COL in df.columns:
        n_sessions = int(df[SOURCE_SESSION_COL].nunique())
        sessions_desc = f"{n_sessions} 会话"
    else:
        n_sessions = None
        sessions_desc = "未知会话数（无 source_session 列）"
    prev_stats = _load_previous_stats(models_dir)

    # ---- 切分 + 特征（FeatureBuilder 只在 train_80 上 fit——防泄漏红线）----
    train_df, test_df = make_holdout_split(
        df, test_size=0.2, random_state=HOLDOUT_RANDOM_STATE)
    fb = FeatureBuilder(**RUNB_FEATURE_RUN)
    X_train = fb.fit_transform(train_df)
    y_train = train_df[LABEL_COL]
    train_labels = sorted(int(v) for v in y_train.unique())

    # ---- FLAML 镜像数据准备（增广 + shuffle + 编码）----
    X_prep, y_enc = flaml_data_prep(X_train, y_train)
    rare_classes = sum(
        1 for c in np.unique(y_train)
        if int((y_train == c).sum()) < RARE_CLASS_THRESHOLD)
    print(f"📊 训练行数: {len(X_train)} → 增广后 {len(X_prep)}"
          f"（稀有类 <{RARE_CLASS_THRESHOLD} 复制: {rare_classes} 个）")

    # ---- 训练（Run B best_config，确定性口径）----
    print("\n🚀 正在训练 XGBoost (Run B 胜出配置)...")
    t0 = time.perf_counter()
    estimator = build_runb_estimator()
    estimator.fit(X_prep, y_enc)
    fit_seconds = time.perf_counter() - t0

    # ---- 组装导出对象（与采纳模型同构：解码包装 + Pipeline）----
    pipeline = Pipeline([
        ("features", fb),
        ("estimator", LabelDecodedEstimator(estimator, train_labels)),
    ])

    # ---- 留出集指标（predict 经解码层还原动作 ID）----
    accuracy, top3 = _evaluate_holdout(pipeline, test_df)
    print(f"\n🏆 绝对准确率 (Accuracy): {accuracy * 100:.2f}%")
    print(f"🌟 实战黄金指标：Top-3 命中率: {top3 * 100:.2f}%")

    # ---- v3(F4): 数据摘要行 + 破坏性变化守门（只告警不阻断）----
    prev_sessions = prev_stats.get("sessions") if prev_stats else None
    prev_rows = prev_stats.get("rows") if prev_stats else None
    if isinstance(prev_rows, int):
        prev_desc = (f"{prev_sessions if isinstance(prev_sessions, int) else '?'}"
                     f" 会话 / {prev_rows} 行")
    else:
        prev_desc = "首次训练，无历史记录"
    print(f"📊 本次训练数据：{sessions_desc} / {n_rows} 行 / {n_classes} 类"
          f"（原模型：{prev_desc}）")
    gate_warnings = evaluate_gates(n_rows, n_classes, int(len(test_df)),
                                   prev_stats)
    for warning in gate_warnings:
        print(f"⚠️ {warning}")

    # ---- 写产物：tmp 原子晋升 + 两代备份链 + 同 sha 跳过（v3/F3）----
    # 同数据二次训练（确定性 → 新旧模型 sha 相同）不再推进备份链，
    # 出厂备份 / models/factory_model.pkl 不会被自吞。
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = models_dir / PRODUCTION_MODEL_NAME
    backup_path = models_dir / BACKUP_MODEL_NAME
    tmp_model_path = models_dir / (PRODUCTION_MODEL_NAME + ".tmp")
    try:
        joblib.dump(pipeline, tmp_model_path)
        rotation_status = promote_with_backup(tmp_model_path, model_path,
                                              generations=2)
    finally:
        if tmp_model_path.exists():
            tmp_model_path.unlink()  # 异常路径残留清理（晋升成功时已移走）
    rotated = rotation_status == ROTATED
    print(f"💾 模型已保存至: {model_path}")

    # ---- 特征重要性图（gain 口径，12 列中文名）----
    png_path = models_dir / IMPORTANCE_PNG_NAME
    _plot_feature_importance(estimator,
                             fb.get_feature_names_out(), png_path)
    print(f"📈 图表已保存为 {png_path}！")

    # ---- sidecar（backend=runb_config：配置、dataset sha、日期、来源）----
    sidecar = {
        "backend": "runb_config",
        "trained_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "model_file": str(model_path),
        "model_sha256": _sha256_file(model_path),
        "config": {**RUNB_BEST_CONFIG, **RUNB_FIXED_EXTRA_PARAMS},
        "feature_run": dict(RUNB_FEATURE_RUN),
        "n_classes": len(train_labels),
        "gate_warnings": gate_warnings,
        "data": {
            "dataset_path": str(dataset_csv),
            "dataset_sha256": _sha256_file(dataset_csv),
            "dataset_rows": n_rows,
            "dataset_classes": n_classes,
            "train_sessions": n_sessions,
            "train_rows_raw": int(len(X_train)),
            "train_rows_after_augment": int(len(X_prep)),
            "rare_classes_augmented": int(rare_classes),
            "flaml_mirror": {
                "auto_augment": (f"稀有类(<{RARE_CLASS_THRESHOLD})整行复制"
                                 f"至 ≥{RARE_CLASS_THRESHOLD}，升标签序"),
                "shuffle_random_state": FLAML_RANDOM_SEED,
                "label_encoder": "sklearn.preprocessing.LabelEncoder",
            },
            "holdout_random_state": HOLDOUT_RANDOM_STATE,
        },
        "metrics": {"top1": accuracy, "top3": top3},
        "source": {
            "origin": "oneclick --pipeline (src.model.production_backend)",
            "provenance": (
                "Run B best_config（experiments/automl_20260915/p6_runB），"
                "复现口径经 p7_repro_runB 逐位验证（max_abs_diff=0.0）"),
        },
        "rollback": {"backup": str(backup_path), "rotated": rotated,
                     "rotation_status": rotation_status},
        "fit_seconds": round(fit_seconds, 2),
        "env": {
            "python": platform.python_version(),
            "os": platform.platform(),
        },
    }
    sidecar_path = models_dir / SIDECAR_NAME
    sidecar_path.write_text(json.dumps(sidecar, indent=1, ensure_ascii=False),
                            encoding="utf-8")
    print(f"🧾 模型信息已写入: {sidecar_path}")

    return sidecar
