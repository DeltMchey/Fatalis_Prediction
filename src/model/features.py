"""P4/P5(AutoML 实验): FeatureBuilder — 统一数值编码 + 派生特征（无 flaml 依赖）。

架构决策（AutoML_Experiment_Plan P4 核心）：
  - 输入：生产格式 DataFrame（6 锁定列；posture/previous_action/phase/is_enraged
    可为 category dtype 或整数列——ActionPredictor 推理链给出的两种形态都接受）
  - 输出：纯数值矩阵（列名保留）——FLAML 与全部 5 种 learner 只见数值，
    根除 FLAML 内部编码与生产 category 输入格式不一致的风险（R-01/R-02）
  - 编码：4 个类别列 → 固定词表有序数值码（词表来源：枚举 + ACTION_DB 全集，
    与训练数据无关，保证跨 run 确定）；未见值 → -1 哨兵码
  - 派生特征（Run B）：全部由本类内部生成，fit 于 train_80、transform 于推理，
    防泄漏（R-05）——分箱边缘与频次表只在 fit 中学习

序列化契约（P5 导出）：fit 后的实例随 Pipeline 一起 joblib 持久化；
本模块不得 import flaml（推理零 flaml 依赖）。
"""

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

from src.config.actions import ACTION_DB

# ================== 常量 ==================

# 6 锁定特征列（与 dataset.FEATURE_COLS 一致；此处独立声明避免循环依赖）
FEATURE_COLS = [
    'distance', 'relative_angle', 'posture',
    'previous_action', 'phase', 'is_enraged',
]

# 固定词表（与训练数据无关——确定性保证）
POSTURE_VOCAB = [0, 1, 2, 3, 4]           # 0 趴下 / 1 站立 / 2 飞行 / 3 倒地 / 4 脚本
PHASE_VOCAB = [1, 2, 3]                   # 战斗阶段
ENRAGE_VOCAB = [0, 1]                     # 是否发怒
PREV_ACTION_VOCAB = sorted(set(ACTION_DB.keys()))  # 已知动作 ID 全集

SENTINEL_CODE = -1                        # 未见值哨兵码

# 派生列名（Run B）
DERIVED_COLS = [
    'angle_sin', 'angle_cos',
    'distance_bin', 'distance_x_enraged',
    'posture_x_phase', 'prev_action_freq',
]


def _column_int_codes(series: pd.Series, vocab: list) -> np.ndarray:
    """把一列（int 或 category dtype）映射为固定词表数值码；未见值/NaN → -1。"""
    if isinstance(series.dtype, pd.CategoricalDtype):
        series = series.astype(int)
    else:
        series = pd.to_numeric(series, errors='coerce')
    lookup = {v: i for i, v in enumerate(vocab)}
    values = series.to_numpy()
    out = np.full(len(values), SENTINEL_CODE, dtype=np.int64)
    for i, v in enumerate(values):
        if pd.notna(v):
            out[i] = lookup.get(int(v), SENTINEL_CODE)
    return out


class FeatureBuilder(BaseEstimator, TransformerMixin):
    """数值编码 + 可选派生特征的 fit/transform 分离变换器。

    Args:
        derived: 是否生成派生特征列（Run B）；False = Run A（仅 6 数值编码列）
        n_bins: distance 等频分箱箱数（计划锁定 5–10，默认 8）

    fit 学习内容（仅 derived=True 时非平凡）：
        - distance 分箱边缘（train 分位数）
        - previous_action 频次表（train 归一化频率；未见码 → 0.0）
    """

    def __init__(self, derived: bool = False, n_bins: int = 8):
        self.derived = derived
        self.n_bins = n_bins

    # ---------- sklearn 契约 ----------

    def fit(self, X: pd.DataFrame, y=None):
        X = self._validate_input(X)
        if self.derived:
            dist = self._numeric_series(X['distance']).to_numpy()
            # 等频分箱边缘：train 分位数（去重保证 bins 退化时仍可用）
            qs = np.linspace(0, 1, self.n_bins + 1)[1:-1]
            self.bin_edges_ = np.unique(np.quantile(dist, qs))
            codes = _column_int_codes(X['previous_action'], PREV_ACTION_VOCAB)
            counts = pd.Series(codes).value_counts()
            # 哨兵码不进频次表（未见动作频率恒 0）
            counts = counts.drop(labels=SENTINEL_CODE, errors='ignore')
            self.freq_table_ = {int(k): float(v) / len(codes) for k, v in counts.items()}
        self.n_features_in_ = len(self.get_feature_names_out())
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        X = self._validate_input(X)
        out = pd.DataFrame(index=X.index)

        # ---- 6 基础列数值编码（列名保留）----
        out['distance'] = self._numeric_series(X['distance']).to_numpy()
        out['relative_angle'] = self._numeric_series(X['relative_angle']).to_numpy()
        out['posture'] = _column_int_codes(X['posture'], POSTURE_VOCAB)
        out['previous_action'] = _column_int_codes(X['previous_action'], PREV_ACTION_VOCAB)
        out['phase'] = _column_int_codes(X['phase'], PHASE_VOCAB)
        out['is_enraged'] = _column_int_codes(X['is_enraged'], ENRAGE_VOCAB)

        if not self.derived:
            return out

        # ---- 派生列（Run B）----
        angle = out['relative_angle'].to_numpy()
        rad = np.deg2rad(angle)
        out['angle_sin'] = np.sin(rad)
        out['angle_cos'] = np.cos(rad)

        dist = out['distance'].to_numpy()
        out['distance_bin'] = np.digitize(dist, self.bin_edges_).astype(np.int64)
        out['distance_x_enraged'] = dist * out['is_enraged'].to_numpy()

        posture_code = out['posture'].to_numpy()
        phase_code = out['phase'].to_numpy()
        out['posture_x_phase'] = posture_code * len(PHASE_VOCAB) + phase_code

        prev_codes = out['previous_action'].to_numpy()
        freq = np.array([self.freq_table_.get(int(c), 0.0) for c in prev_codes])
        out['prev_action_freq'] = freq
        return out

    def get_feature_names_out(self, input_features=None) -> list:
        return list(FEATURE_COLS) + (list(DERIVED_COLS) if self.derived else [])

    # ---------- 内部 ----------

    @staticmethod
    def _validate_input(X: pd.DataFrame) -> pd.DataFrame:
        missing = [c for c in FEATURE_COLS if c not in X.columns]
        if missing:
            raise ValueError(f"FeatureBuilder 输入缺列: {missing}")
        return X

    @staticmethod
    def _numeric_series(series: pd.Series) -> pd.Series:
        if isinstance(series.dtype, pd.CategoricalDtype):
            series = series.astype(float)
        return pd.to_numeric(series, errors='coerce')
