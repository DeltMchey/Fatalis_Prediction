"""P2(AutoML 实验): 模型基准测量 CLI — 基线与 AutoML 候选统一口径。

四项指标（规划 P2 契约）：
  1. top-1 / top-3 准确率（固定留出集，P1 make_holdout_split 口径）
     - top3_raw: np.argsort(probs)[:, -3:] 命中率（与 train_lgbm.py 打印口径逐行一致）
     - top3_filtered: 逐行以其自身 phase/posture 调用 ActionPredictor 静态过滤链
       （filter_probs_by_phase → filter_probs_by_posture → renormalize → select_top_k(3, 0.03)）
     - macro / micro 双报告（46 类长尾诊断）
  2. 端到端推理时延：复用 ActionPredictor.predict() 生产链路
     （特征构造 → predict_proba → 过滤 → 重归一化 → top-3），预热后测 N 次
  3. CPU / 内存开销：干净子进程隔离（父进程 psutil 采样，不污染时延数字）
  4. EXE 包体积：不在本脚本（P7 采纳阶段另行测量）

用法：
    python scripts/benchmark_model.py --model models/fatalis_ai_model.pkl \
        --report experiments/run/reports/baseline.json \
        [--holdout-csv experiments/holdout_cache.csv] [--latency-iters 1000] \
        [--mem-duration 300] [--skip-mem] [--skip-latency]

留出集缓存契约：首次运行把留出集写到缓存 CSV（含 SHA-256 sidecar），
后续所有模型复用同一缓存（--holdout-csv 指定），保证逐模型同集。
"""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd

# 支持从项目根以模块方式运行（python scripts/benchmark_model.py）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.model.dataset import (  # noqa: E402
    FEATURE_COLS,
    LABEL_COL,
    load_ml_dataset,
    make_holdout_split,
)
from src.model.predictor import ActionPredictor  # noqa: E402

# 探针输入（内存画像 runner 用：0.5s 节奏连续推理的代表性单行）
_RUNNER_PROBE = (500.0, 30.0, 1, 37, 1, 0)

DEFAULT_HOLDOUT_CACHE = Path("experiments") / "holdout_cache.csv"


# ================== 工具 ==================

def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _as_category(X: pd.DataFrame) -> pd.DataFrame:
    """4 个类别列转 category dtype（生产模型的输入契约；导出管线亦按此契约接受输入）。"""
    X = X.copy()
    for col in ("posture", "previous_action", "phase", "is_enraged"):
        if col in X.columns:
            X[col] = X[col].astype("category")
    return X


# ================== 指标 1：top-1 / top-3 ==================

def _topk_hit_rows(probs, classes, y_true, k=3):
    """argsort 前 k 命中（raw 口径，与 train_lgbm.py:127-129 逐行一致）。"""
    topk = np.argsort(probs, axis=1)[:, -k:]
    return np.array([
        y_true[i] in classes[topk[i]] for i in range(len(y_true))
    ])


def _topk_hit_filtered(probs, classes, y_true, phases, postures):
    """实战口径：逐行按自身 phase/posture 走 ActionPredictor 过滤链后 select_top_k(3, 0.03)。"""
    hits = []
    for i in range(len(y_true)):
        row = np.array(probs[i], dtype=float, copy=True)
        row = ActionPredictor.filter_probs_by_phase(row, classes, int(phases[i]))
        row = ActionPredictor.filter_probs_by_posture(row, classes, int(postures[i]))
        row = ActionPredictor.renormalize_probs(row)
        selected = ActionPredictor.select_top_k(row, classes, k=3, threshold=0.03)
        hits.append(any(int(c) == int(y_true[i]) for c, _ in selected))
    return np.array(hits)


def _macro_from_hits(hits, y_true):
    """逐类命中率取均值（macro）。"""
    y_arr = np.asarray(y_true)
    per_class = []
    for cls in np.unique(y_arr):
        mask = y_arr == cls
        per_class.append(hits[mask].mean())
    return float(np.mean(per_class)) if per_class else 0.0


def compute_metrics(model, holdout_df: pd.DataFrame) -> dict:
    """在留出集上计算 top-1 / top-3（raw + 过滤口径，micro + macro）。

    Args:
        model: 任何提供 predict_proba(DataFrame)/classes_ 的对象
                （基线 pkl 与 P5 导出管线满足同一契约）
        holdout_df: make_holdout_split 产出的留出集（含 FEATURE_COLS + LABEL_COL）
    """
    X = _as_category(holdout_df[FEATURE_COLS])
    y_true = holdout_df[LABEL_COL].values

    probs = np.asarray(model.predict_proba(X))
    classes = np.asarray(model.classes_)

    assert probs.shape[0] == len(y_true), "predict_proba 行数与留出集不一致"
    assert probs.shape[1] == len(classes), "概率列数与 classes_ 不一致"

    top1_hits = np.asarray(y_true) == classes[np.argmax(probs, axis=1)]
    top3_hits = _topk_hit_rows(probs, classes, y_true, k=3)
    top3f_hits = _topk_hit_filtered(
        probs, classes, y_true,
        phases=holdout_df["phase"].astype(int).values,
        postures=holdout_df["posture"].astype(int).values,
    )

    return {
        "top1": float(top1_hits.mean()),
        "top1_macro": _macro_from_hits(top1_hits, y_true),
        "top3_raw": float(top3_hits.mean()),
        "macro_top3": _macro_from_hits(top3_hits, y_true),
        "micro_top3": float(top3_hits.mean()),
        "top3_filtered": float(top3f_hits.mean()),
        "macro_top3_filtered": _macro_from_hits(top3f_hits, y_true),
        "holdout_rows": int(len(y_true)),
        "n_classes_seen": int(len(np.unique(y_true))),
    }


# ================== 指标 2：端到端时延 ==================

def measure_latency(model_path, holdout_df, warmup=10, iters=1000, seed=42) -> dict:
    """复用 ActionPredictor.predict() 生产链路测端到端时延。

    输入：从留出集按 seed 抽 iters 行（不足则全量循环），逐次调用 predict。
    """
    predictor = ActionPredictor(str(model_path))
    if not predictor.is_loaded:
        raise RuntimeError(f"模型加载失败: {model_path}")

    rng = np.random.default_rng(seed)
    n = len(holdout_df)
    pick = rng.choice(n, size=min(iters, n), replace=False)
    rows = holdout_df.iloc[pick]

    args_seq = [
        (
            float(r["distance"]), float(r["relative_angle"]),
            int(r["posture"]), int(r["previous_action"]),
            int(r["phase"]), int(r["is_enraged"]),
        )
        for _, r in rows.iterrows()
    ]
    while len(args_seq) < iters:
        args_seq.extend(args_seq[: iters - len(args_seq)])

    for a in args_seq[:warmup]:
        predictor.predict(*a)

    non_empty = 0
    samples = np.empty(iters, dtype=float)
    for i in range(iters):
        t0 = time.perf_counter()
        result = predictor.predict(*args_seq[i])
        samples[i] = (time.perf_counter() - t0) * 1000.0
        if result:
            non_empty += 1

    return {
        "iters": int(iters),
        "warmup": int(warmup),
        "non_empty_ratio": non_empty / iters,
        "mean_ms": float(samples.mean()),
        "p50_ms": float(np.percentile(samples, 50)),
        "p95_ms": float(np.percentile(samples, 95)),
        "p99_ms": float(np.percentile(samples, 99)),
        "max_ms": float(samples.max()),
    }


# ================== 指标 3：CPU / 内存（干净子进程隔离） ==================

def _runner_main(model_path, duration, cadence=0.5) -> int:
    """内存画像 runner（由父进程 spawn，事件经 stdout JSONL 上报）。

    事件序列：baseline（加载前 RSS）→ loaded（加载后 RSS + 加载耗时）
    → tick（每 5s 心跳，含自报 RSS/CPU/推理时延统计）→ done。

    设计说明（Windows 代码现实）：venv 的 python.exe 是启动器存根，真实
    工作进程是其子进程——父进程按 pid 采 psutil 只能看到 4MB 存根。
    因此 RSS/CPU 由 runner 进程内 psutil 自报（隔离子进程内部，psutil
    调用开销 μs 级，不影响 0.5s 节奏的推理时延自报）。
    """
    import psutil

    proc = psutil.Process()
    proc.cpu_percent(interval=None)  # 预热（首次调用恒 0）

    def emit(event, **kw):
        print(json.dumps({"event": event, **kw}), flush=True)

    emit("baseline", rss_mb=proc.memory_info().rss / (1 << 20))
    t0 = time.perf_counter()
    predictor = ActionPredictor(str(model_path))
    load_s = time.perf_counter() - t0
    if not predictor.is_loaded:
        emit("error", message="model load failed")
        return 1
    emit("loaded", rss_mb=proc.memory_info().rss / (1 << 20), load_s=load_s)

    latencies = []
    start = time.perf_counter()
    last_tick = start
    # 心跳间隔自适应：默认 5s；短时长（测试）按 duration/6 收缩保证有采样点
    tick_interval = min(5.0, max(0.5, duration / 6.0))
    while time.perf_counter() - start < duration:
        t1 = time.perf_counter()
        predictor.predict(*_RUNNER_PROBE)
        latencies.append((time.perf_counter() - t1) * 1000.0)
        now = time.perf_counter()
        if now - last_tick >= tick_interval:
            lat = np.asarray(latencies[-50:]) if latencies else np.zeros(1)
            emit(
                "tick", elapsed_s=now - start,
                rss_mb=proc.memory_info().rss / (1 << 20),
                cpu_percent=proc.cpu_percent(interval=None),
                self_latency_mean_ms=float(lat.mean()),
            )
            last_tick = now
        time.sleep(max(0.0, cadence - (time.perf_counter() - now)))
    emit("done", rss_mb=proc.memory_info().rss / (1 << 20))
    return 0


def run_memory_profile(model_path, duration=300, sample_interval=10.0) -> dict:
    """spawn 隔离子进程做稳态推理；RSS/CPU 曲线取 runner 自报 tick 事件。"""
    cmd = [
        sys.executable, str(Path(__file__).resolve()),
        "--_runner", "--model", str(model_path), "--duration", str(duration),
    ]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    )

    events = {"lines": []}

    def reader():
        for line in proc.stdout:
            line = line.strip()
            if line:
                events["lines"].append(line)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()

    deadline = time.perf_counter() + duration + 120  # runner 卡死保护
    while proc.poll() is None and time.perf_counter() < deadline:
        time.sleep(sample_interval)
    proc.wait(timeout=60)
    thread.join(timeout=10)

    parsed = []
    for line in events["lines"]:
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    by_event = {}
    for ev in parsed:
        by_event.setdefault(ev.get("event"), []).append(ev)

    if "error" in by_event:
        raise RuntimeError(f"runner 加载模型失败: {by_event['error'][0].get('message')}")

    baseline_rss = by_event["baseline"][0]["rss_mb"] if "baseline" in by_event else None
    loaded = by_event["loaded"][0] if "loaded" in by_event else None
    ticks = by_event.get("tick", [])
    self_lat = [t["self_latency_mean_ms"] for t in ticks if "self_latency_mean_ms" in t]

    rss_samples = [(t["elapsed_s"], t["rss_mb"]) for t in ticks if "rss_mb" in t]
    cpu_samples = [t["cpu_percent"] for t in ticks if "cpu_percent" in t]

    if len(rss_samples) >= 2:
        ts = np.array([t for t, _ in rss_samples])
        vs = np.array([v for _, v in rss_samples])
        slope_mb_per_s = float(np.polyfit(ts, vs, 1)[0])
    else:
        slope_mb_per_s = 0.0

    return {
        "duration_s": float(duration),
        "load_rss_delta_mb": (
            float(loaded["rss_mb"]) - float(baseline_rss)
            if loaded and baseline_rss is not None else None
        ),
        "load_time_s": float(loaded["load_s"]) if loaded else None,
        "steady_rss_mb": float(np.mean([v for _, v in rss_samples])) if rss_samples else None,
        "steady_rss_min_mb": float(np.min([v for _, v in rss_samples])) if rss_samples else None,
        "steady_rss_max_mb": float(np.max([v for _, v in rss_samples])) if rss_samples else None,
        "drift_mb_per_5min": slope_mb_per_s * 300.0,
        "cpu_mean_percent": float(np.mean(cpu_samples)) if cpu_samples else None,
        "runner_self_latency_mean_ms": float(np.mean(self_lat)) if self_lat else None,
        "n_ticks": len(ticks),
    }


# ================== 留出集缓存 ==================

def get_holdout(holdout_csv: Path, dataset_csv: Path, refresh=False):
    """加载或构建（并缓存）留出集。

    Returns:
        (holdout_df, meta) — meta 含 dataset_sha256 / holdout_sha256 / cache_path
    """
    meta_path = holdout_csv.with_suffix(".meta.json")
    if holdout_csv.exists() and not refresh:
        # round_trip 解析器保证 %.17g 写出的 double 逐位可逆（与首测同输入）
        holdout_df = pd.read_csv(holdout_csv, float_precision="round_trip")
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        meta.setdefault("holdout_sha256", sha256_file(holdout_csv))
        return holdout_df, meta

    if not dataset_csv.exists():
        raise FileNotFoundError(
            f"留出集缓存不存在且找不到数据集 {dataset_csv}；"
            f"请先在有数据集的机器上生成缓存"
        )
    df = load_ml_dataset(dataset_csv)
    _, holdout_df = make_holdout_split(df, test_size=0.2, random_state=42)
    holdout_csv.parent.mkdir(parents=True, exist_ok=True)
    # %.17g 保证 double 精度经 CSV 往返逐位可逆（缓存后评估与首测完全同输入）
    holdout_df.to_csv(holdout_csv, index=False, float_format="%.17g")
    meta = {
        "dataset": str(dataset_csv),
        "dataset_sha256": sha256_file(dataset_csv),
        "split": "make_holdout_split(test_size=0.2, random_state=42)",
        "rows": int(len(holdout_df)),
    }
    meta_path.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    meta["holdout_sha256"] = sha256_file(holdout_csv)
    return holdout_df, meta


# ================== 报告 ==================

def build_report(model_path, holdout_df, holdout_meta, args) -> dict:
    import joblib
    import sklearn

    report = {
        "model_path": str(model_path),
        "model_sha256": sha256_file(model_path),
        "model_file_mb": Path(model_path).stat().st_size / (1 << 20),
        "dataset_sha256": holdout_meta.get("dataset_sha256"),
        "holdout_sha256": holdout_meta.get("holdout_sha256"),
    }

    # 指标 1：准确率（与基线/候选统一：同缓存留出集）
    model = joblib.load(model_path)
    report["metrics"] = compute_metrics(model, holdout_df)

    # 指标 2：端到端时延（生产链路）
    if not args.skip_latency:
        report["latency_ms"] = measure_latency(
            model_path, holdout_df,
            warmup=args.latency_warmup, iters=args.latency_iters,
        )

    # 指标 3：CPU / 内存（干净子进程）
    if not args.skip_mem:
        interval = max(1.0, min(10.0, args.mem_duration / 5))
        report["memory"] = run_memory_profile(
            model_path, duration=args.mem_duration, sample_interval=interval,
        )
        report["memory"]["model_file_mb"] = report["model_file_mb"]

    try:
        import lightgbm
        lgbm_ver = lightgbm.__version__
    except ImportError:
        lgbm_ver = None
    try:
        import xgboost
        xgb_ver = xgboost.__version__
    except ImportError:
        xgb_ver = None

    report["env"] = {
        "python": platform.python_version(),
        "sklearn": sklearn.__version__,
        "lightgbm": lgbm_ver,
        "xgboost": xgb_ver,
        "os": platform.platform(),
        "cpu_count": __import__("os").cpu_count(),
    }
    import datetime
    report["timestamp"] = datetime.datetime.now().isoformat(timespec="seconds")
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, help="被测模型 .pkl 路径")
    ap.add_argument("--report", default=None, help="输出 JSON 报告路径（runner 模式无需）")
    ap.add_argument("--dataset", default="data/ML_Ready_Dataset.csv",
                    help="留出集来源数据集（缓存不存在时使用）")
    ap.add_argument("--holdout-csv", default=str(DEFAULT_HOLDOUT_CACHE),
                    help=f"留出集缓存路径（默认 {DEFAULT_HOLDOUT_CACHE}，所有模型复用）")
    ap.add_argument("--refresh-holdout", action="store_true", help="强制从数据集重建缓存")
    ap.add_argument("--latency-iters", type=int, default=1000)
    ap.add_argument("--latency-warmup", type=int, default=10)
    ap.add_argument("--mem-duration", type=float, default=300.0)
    ap.add_argument("--skip-latency", action="store_true")
    ap.add_argument("--skip-mem", action="store_true")
    # 内部：内存画像 runner 模式（父进程 spawn）
    ap.add_argument("--_runner", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--duration", type=float, default=300.0, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    if args._runner:
        return _runner_main(args.model, args.duration)

    if not args.report:
        ap.error("--report is required (missing for benchmark mode)")

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"模型不存在: {model_path}")
        return 2

    holdout_df, holdout_meta = get_holdout(
        Path(args.holdout_csv), Path(args.dataset), refresh=args.refresh_holdout,
    )

    report = build_report(model_path, holdout_df, holdout_meta, args)

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8",
    )

    m = report["metrics"]
    print(f"\n=== benchmark: {model_path} ===")
    print(f"top1={m['top1']*100:.2f}%  top3_raw={m['top3_raw']*100:.2f}%  "
          f"top3_filtered={m['top3_filtered']*100:.2f}%")
    print(f"macro_top3={m['macro_top3']*100:.2f}%  (rows={m['holdout_rows']})")
    if "latency_ms" in report:
        lat = report["latency_ms"]
        print(f"latency: mean={lat['mean_ms']:.2f}ms p50={lat['p50_ms']:.2f}ms "
              f"p95={lat['p95_ms']:.2f}ms p99={lat['p99_ms']:.2f}ms")
    if "memory" in report:
        mem = report["memory"]

        def _fmt(v, spec=".1f"):
            return format(v, spec) if v is not None else "n/a"

        print(f"memory: load_delta={_fmt(mem['load_rss_delta_mb'])}MB "
              f"steady={_fmt(mem['steady_rss_mb'])}MB "
              f"drift/5min={_fmt(mem['drift_mb_per_5min'], '.2f')}MB "
              f"size={mem['model_file_mb']:.2f}MB")
    print(f"report -> {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
