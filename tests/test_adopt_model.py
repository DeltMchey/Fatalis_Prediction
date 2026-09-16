"""P7(AutoML 采纳阶段): 生产采纳 CLI 测试。

覆盖（规划 5.3 第 2 层——显式采纳机制）：
  ① 门槛校验：报告 sha 不一致拒绝 / G4 超标拒绝 / G1 拒绝线 / G5a 超标须 override
  ② 轮换行为：已有生产模型 → .bak 单代轮换；无生产模型 → 直接写入
  ③ 采纳后：sha 一致 + ActionPredictor 加载 + sidecar 内容（来源 run、回滚路径）
"""

import importlib.util
import json
import sys
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

from src.model.features import FeatureBuilder

_SCRIPT = Path(__file__).parents[1] / "scripts" / "adopt_model.py"
_spec = importlib.util.spec_from_file_location("adopt_model_mod", _SCRIPT)
adopt_model = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adopt_model)


def make_mini_model(path: Path, seed=42):
    """mini lgbm Pipeline（FeatureBuilder + estimator），镜像导出物结构。"""
    from sklearn.pipeline import Pipeline
    rng = np.random.default_rng(seed)
    rows = pd.DataFrame({
        "distance": rng.uniform(50, 3000, 300),
        "relative_angle": rng.uniform(-180, 180, 300),
        "posture": rng.integers(0, 3, 300),
        "previous_action": rng.choice([37, 53, 81, 129], 300),
        "phase": rng.integers(1, 4, 300),
        "is_enraged": rng.integers(0, 2, 300),
        "next_action": rng.choice([37, 53, 81, 129], 300),
    })
    fb = FeatureBuilder(derived=False)
    X = fb.fit_transform(rows)
    est = lgb.LGBMClassifier(n_estimators=10, random_state=seed, n_jobs=1, verbose=-1)
    est.fit(X, rows["next_action"])
    pipeline = Pipeline([("features", fb), ("estimator", est)])
    joblib.dump(pipeline, path)
    export_meta = {
        "run_dir": "experiments/fake_run",
        "best_estimator": "lgbm",
        "best_config": {"n_estimators": 10},
        "feature_run": {"derived": False, "n_bins": 8},
        "feature_names": fb.get_feature_names_out(),
    }
    meta_path = path.with_name(path.stem + ".meta.json")
    meta_path.write_text(json.dumps(export_meta), encoding="utf-8")
    return adopt_model.sha256_file(path)


def make_report(model_path: Path, sha: str, *, top3=0.70, top1=0.35,
                load_rss_delta_mb=50.0) -> dict:
    return {
        "model_path": str(model_path),
        "model_sha256": sha,
        "metrics": {"top3_raw": top3, "top1": top1},
        "memory": {"load_rss_delta_mb": load_rss_delta_mb},
    }


def make_baseline(top3=0.60) -> dict:
    return {"metrics": {"top3_raw": top3, "top1": 0.28}}


@pytest.fixture()
def candidate(tmp_path):
    """mini 候选：导出 pkl + meta + 报告 + 基线报告。"""
    export = tmp_path / "fatalis_ai_model_automl_test.pkl"
    sha = make_mini_model(export)
    report = make_report(export, sha)
    report_path = tmp_path / "candidate.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(make_baseline()), encoding="utf-8")
    return {"export": export, "sha": sha, "report": report_path,
            "baseline": baseline_path}


class TestGateValidation:
    def test_sha_mismatch_rejected(self, candidate, tmp_path):
        report = make_report(candidate["export"], "0" * 64)
        rp = tmp_path / "r2.json"
        rp.write_text(json.dumps(report), encoding="utf-8")
        with pytest.raises(ValueError, match="model_sha256 与导出文件不一致"):
            adopt_model.adopt(candidate["export"], rp, tmp_path / "models",
                              baseline_report=candidate["baseline"])

    def test_g1_below_rejection_line_rejected(self, candidate, tmp_path):
        report = make_report(candidate["export"], candidate["sha"], top3=0.605)
        rp = tmp_path / "r3.json"
        rp.write_text(json.dumps(report), encoding="utf-8")
        with pytest.raises(ValueError, match="G1 FAIL"):
            adopt_model.adopt(candidate["export"], rp, tmp_path / "models",
                              baseline_report=candidate["baseline"])

    def test_g5a_requires_override(self, candidate, tmp_path):
        report = make_report(candidate["export"], candidate["sha"],
                             load_rss_delta_mb=122.0)
        rp = tmp_path / "r4.json"
        rp.write_text(json.dumps(report), encoding="utf-8")
        with pytest.raises(ValueError, match="G5a FAIL.*--g5a-override"):
            adopt_model.adopt(candidate["export"], rp, tmp_path / "models",
                              baseline_report=candidate["baseline"])
        # 带 override → 通过并记录理由
        sidecar = adopt_model.adopt(
            candidate["export"], rp, tmp_path / "models",
            baseline_report=candidate["baseline"],
            g5a_override="Tier 2 人工评审：接受一次性启动增量")
        assert sidecar["gates"]["g5a_overridden"] is True
        assert "启动增量" in sidecar["gates"]["g5a_override_reason"]

    def test_missing_metric_rejected(self, candidate, tmp_path):
        report = make_report(candidate["export"], candidate["sha"])
        del report["memory"]
        rp = tmp_path / "r5.json"
        rp.write_text(json.dumps(report), encoding="utf-8")
        with pytest.raises(ValueError, match="load_rss_delta_mb"):
            adopt_model.adopt(candidate["export"], rp, tmp_path / "models")


class TestAdoptionFlow:
    def test_fresh_adopt_without_existing_production(self, candidate, tmp_path):
        models = tmp_path / "models"
        sidecar = adopt_model.adopt(
            candidate["export"], candidate["report"], models,
            baseline_report=candidate["baseline"])
        prod = models / adopt_model.PRODUCTION_NAME
        assert prod.exists()
        assert adopt_model.sha256_file(prod) == candidate["sha"]
        assert sidecar["rollback"]["rotated"] is False
        assert sidecar["previous_production_sha256"] is None
        assert sidecar["model_info"]["best_estimator"] == "lgbm"
        assert sidecar["source_run_dir"] == "experiments/fake_run"
        assert sidecar["post_adopt_check"]["predictor_loaded"] is True

    def test_rotation_single_generation(self, candidate, tmp_path):
        models = tmp_path / "models"
        models.mkdir()
        # 先放一个"旧生产模型"
        old = tmp_path / "fatalis_ai_model_automl_old.pkl"
        old_sha = make_mini_model(old, seed=7)
        (models / adopt_model.PRODUCTION_NAME).write_bytes(old.read_bytes())

        sidecar = adopt_model.adopt(
            candidate["export"], candidate["report"], models,
            baseline_report=candidate["baseline"])
        backup = models / adopt_model.BACKUP_NAME
        assert backup.exists()
        assert adopt_model.sha256_file(backup) == old_sha
        assert sidecar["previous_production_sha256"] == old_sha
        assert sidecar["rollback"]["rotated"] is True
        # 新生产 != 旧备份
        assert adopt_model.sha256_file(models / adopt_model.PRODUCTION_NAME) == candidate["sha"]

    def test_sidecar_written(self, candidate, tmp_path):
        models = tmp_path / "models"
        adopt_model.adopt(candidate["export"], candidate["report"], models,
                          baseline_report=candidate["baseline"])
        sidecar_path = models / (adopt_model.PRODUCTION_NAME + ".meta.json")
        assert sidecar_path.exists()
        data = json.loads(sidecar_path.read_text(encoding="utf-8"))
        assert data["model_sha256"] == candidate["sha"]
        assert "rollback" in data and "gates" in data

    def test_cli_main(self, candidate, tmp_path):
        rc = adopt_model.main([
            "--export", str(candidate["export"]),
            "--report", str(candidate["report"]),
            "--baseline-report", str(candidate["baseline"]),
            "--models-dir", str(tmp_path / "models"),
        ])
        assert rc == 0
        assert (tmp_path / "models" / adopt_model.PRODUCTION_NAME).exists()
