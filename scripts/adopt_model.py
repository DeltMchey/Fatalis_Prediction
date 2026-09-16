"""P7(AutoML 采纳阶段): 生产模型正式采纳 CLI — 导出候选 → 生产路径（显式受保护操作）。

规划 5.3 三层生产路径保护之第 2 层（显式采纳）：
    切换生产模型只经本脚本（export_model.py 保持物理隔离——其源码层面
    不存在写生产文件名的语句，tests/test_model_export.py 断言该约束）。

流程（采纳为独立 commit，可单独 revert）：
    1. 前置校验：benchmark 报告存在且 model_sha256 与导出文件一致；
       G4 模型体积 ≤ 40MB；G1 top3_raw ≥ 基线 + 1.0pp（拒绝线）；
       G5a 加载 RSS 增量 ≤ 100MB，超标时必须显式 --g5a-override "<裁决理由>"
       （Tier 2 人工评审路径，理由记入 sidecar）
    2. .bak 轮换（与 train_lgbm.py 机制一致，单代）：
       fatalis_ai_model.pkl → fatalis_ai_model.pkl.bak
    3. 拷贝导出文件 → models/fatalis_ai_model.pkl
    4. 采纳后验证：ActionPredictor 实际加载生产路径 + 单行推理 + sha256 复核
    5. 写 sidecar models/fatalis_ai_model.meta.json（来源 run、sha256、日期、
       门槛数据、回滚路径）

回滚：拷贝 .bak 回生产名（P7 已演练，见 obsidian/docs/AutoML_P6_Comparison.md §9）。

用法：
    python scripts/adopt_model.py \
        --export experiments/fatalis_ai_model_automl_p6runB.pkl \
        --report experiments/automl_20260915/reports/candidate_runB.json \
        --baseline-report experiments/automl_20260915/reports/baseline_report.json \
        [--g5a-override "Tier 2 人工评审：用户接受一次性启动增量"] [--models-dir models]
"""

import argparse
import datetime
import hashlib
import json
import platform
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PRODUCTION_NAME = "fatalis_ai_model.pkl"
BACKUP_NAME = "fatalis_ai_model.pkl.bak"

G4_MAX_MB = 40.0          # 模型文件体积门槛
G5A_MAX_MB = 100.0        # 加载 RSS 增量门槛
G1_MIN_DELTA_PP = 1.0     # top3_raw 相对基线最低增量（< 此值 = 拒绝区）


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_gates(export_path: Path, report: dict, baseline: dict,
                   g5a_override: str | None) -> dict:
    """采纳前置门槛校验（规划 P6 门槛的采纳子集）。返回门槛摘要；不满足硬门槛时抛错。"""
    metrics = report.get("metrics", {})
    mem = report.get("memory", {})
    for key in ("top3_raw", "top1"):
        if key not in metrics:
            raise ValueError(f"benchmark 报告缺 {key} 指标，无法校验门槛")
    if mem.get("load_rss_delta_mb") is None:
        raise ValueError("benchmark 报告缺 memory.load_rss_delta_mb，无法校验 G5a")

    # G4：模型体积（以导出文件实测为准，报告值为记录）
    size_mb = export_path.stat().st_size / (1 << 20)
    if size_mb > G4_MAX_MB:
        raise ValueError(f"G4 FAIL：模型 {size_mb:.2f}MB > {G4_MAX_MB}MB")

    # G1：相对基线增量（拒绝线）
    g1_delta_pp = None
    if baseline:
        base_top3 = baseline.get("metrics", {}).get("top3_raw")
        if base_top3 is not None:
            g1_delta_pp = (metrics["top3_raw"] - base_top3) * 100.0
            if g1_delta_pp < G1_MIN_DELTA_PP:
                raise ValueError(
                    f"G1 FAIL：top3_raw 相对基线 {g1_delta_pp:+.2f}pp < +{G1_MIN_DELTA_PP}pp（拒绝区）")

    # G5a：加载 RSS 增量（超标需显式 override）
    g5a_mb = float(mem["load_rss_delta_mb"])
    g5a_overridden = False
    if g5a_mb > G5A_MAX_MB:
        if not g5a_override:
            raise ValueError(
                f"G5a FAIL：加载 RSS 增量 {g5a_mb:.1f}MB > {G5A_MAX_MB}MB；"
                f"Tier 2 人工评审采纳须显式 --g5a-override \"<裁决理由>\"")
        g5a_overridden = True

    return {
        "g1_top3_raw": metrics["top3_raw"],
        "g1_delta_pp_vs_baseline": g1_delta_pp,
        "g2_top1": metrics["top1"],
        "g4_model_mb": size_mb,
        "g5a_load_rss_delta_mb": g5a_mb,
        "g5a_overridden": g5a_overridden,
        "g5a_override_reason": g5a_override,
    }


def post_adopt_check(prod_path: Path, expected_sha: str) -> dict:
    """采纳后验证：sha 复核 + ActionPredictor 生产链路加载与单行推理。"""
    actual_sha = sha256_file(prod_path)
    if actual_sha != expected_sha:
        raise RuntimeError(f"采纳后 sha256 不一致: {actual_sha} != {expected_sha}")

    from src.model.predictor import ActionPredictor
    predictor = ActionPredictor(str(prod_path))
    if not predictor.is_loaded:
        raise RuntimeError("ActionPredictor 加载生产模型失败")
    result = predictor.predict(500.0, 30.0, 1, 37, 1, 0)
    if not isinstance(result, list):
        raise RuntimeError("ActionPredictor.predict 返回类型异常")
    return {"predictor_loaded": True, "probe_result_len": len(result)}


def adopt(export_path: Path, report_path: Path, models_dir: Path,
          baseline_report: Path | None = None,
          g5a_override: str | None = None) -> dict:
    """执行采纳：校验 → 轮换 → 拷贝 → 复核 → sidecar。"""
    export_path = Path(export_path)
    report_path = Path(report_path)
    models_dir = Path(models_dir)

    if not export_path.exists():
        raise FileNotFoundError(f"导出模型不存在: {export_path}")
    report = _load_json(report_path)

    # 报告与产物一致性（防止拿 A 的报告采纳 B 的模型）
    export_sha = sha256_file(export_path)
    if report.get("model_sha256") != export_sha:
        raise ValueError(
            f"benchmark 报告 model_sha256 与导出文件不一致:\n"
            f"  report: {report.get('model_sha256')}\n  export: {export_sha}")

    baseline = _load_json(baseline_report) if baseline_report else {}
    gate_summary = validate_gates(export_path, report, baseline, g5a_override)

    # 导出 sidecar（存在则读来源 run 信息）
    export_meta_path = export_path.with_name(export_path.stem + ".meta.json")
    export_meta = _load_json(export_meta_path) if export_meta_path.exists() else {}

    prod_path = models_dir / PRODUCTION_NAME
    backup_path = models_dir / BACKUP_NAME
    models_dir.mkdir(parents=True, exist_ok=True)

    previous_sha = sha256_file(prod_path) if prod_path.exists() else None
    rotated = False
    if prod_path.exists():
        import os
        os.replace(prod_path, backup_path)   # 单代轮换（train_lgbm 同机制）
        rotated = True
    shutil.copyfile(export_path, prod_path)

    post = post_adopt_check(prod_path, export_sha)

    sidecar = {
        "adopted_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "production_model": str(prod_path),
        "model_sha256": export_sha,
        "source_export": str(export_path),
        "source_run_dir": export_meta.get("run_dir"),
        "benchmark_report": str(report_path),
        "previous_production_sha256": previous_sha,
        "rollback": {"backup": str(backup_path), "rotated": rotated,
                     "procedure": "拷贝 fatalis_ai_model.pkl.bak 覆盖 fatalis_ai_model.pkl 后冻结冒烟"},
        "gates": gate_summary,
        "model_info": {
            "best_estimator": export_meta.get("best_estimator"),
            "best_config": export_meta.get("best_config"),
            "feature_run": export_meta.get("feature_run"),
            "feature_names": export_meta.get("feature_names"),
            "best_cv_top3_acc": export_meta.get("best_cv_top3_acc"),
        },
        "post_adopt_check": post,
        "env": {
            "python": platform.python_version(),
            "os": platform.platform(),
        },
    }
    sidecar_path = models_dir / (PRODUCTION_NAME + ".meta.json")
    sidecar_path.write_text(json.dumps(sidecar, indent=1, ensure_ascii=False),
                            encoding="utf-8")
    return sidecar


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--export", required=True, help="待采纳的导出模型 .pkl")
    ap.add_argument("--report", required=True, help="对应 benchmark 报告 JSON")
    ap.add_argument("--baseline-report", default=None,
                    help="基线锚点报告 JSON（G1 增量校验用）")
    ap.add_argument("--models-dir", default="models",
                    help="生产模型目录（默认 models/）")
    ap.add_argument("--g5a-override", default=None, metavar="REASON",
                    help="G5a 超标时的 Tier 2 人工裁决理由（记入 sidecar）")
    args = ap.parse_args(argv)

    sidecar = adopt(
        Path(args.export), Path(args.report), Path(args.models_dir),
        baseline_report=Path(args.baseline_report) if args.baseline_report else None,
        g5a_override=args.g5a_override,
    )
    g = sidecar["gates"]
    print(f"adopted: {sidecar['production_model']}")
    print(f"  sha256={sidecar['model_sha256'][:16]}…  source={sidecar['source_run_dir']}")
    print(f"  G1 top3_raw={g['g1_top3_raw']*100:.2f}%"
          + (f" ({g['g1_delta_pp_vs_baseline']:+.2f}pp vs baseline)" if g['g1_delta_pp_vs_baseline'] is not None else ""))
    print(f"  G5a {g['g5a_load_rss_delta_mb']:.1f}MB"
          + (" [OVERRIDDEN: " + g['g5a_override_reason'] + "]" if g['g5a_overridden'] else " (pass)"))
    print(f"  rollback backup: {sidecar['rollback']['backup']} (rotated={sidecar['rollback']['rotated']})")
    print(f"  sidecar -> {Path(sidecar['production_model']).with_name(PRODUCTION_NAME + '.meta.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
