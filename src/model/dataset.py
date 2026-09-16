"""P1(AutoML 实验): 共享数据模块 — 加载/过滤/切分的单一事实源。

从 train_lgbm.py 原地提取（行为零变化，golden 索引测试锁定）：
  - load_ml_dataset(csv_path): 读 CSV → NaN label 过滤 → 非数值 label 过滤
    → ACTION_DB 未知 label 过滤 → 类频 >=3 过滤 → 4 列 category dtype
    （逐条复刻原 train_lgbm.py v1.1.1/v1.1.2 的顺序与 warning 输出）
  - make_holdout_split(df): 分层切分 + 极小数据集降级（复刻原逻辑）
  - FEATURE_COLS / LABEL_COL / CATEGORICAL_COLS 常量

使用方：
  - train_lgbm.py（基线训练，行为不变）
  - scripts/benchmark_model.py（基线补测 P3 / 候选评估 P6——同一留出集）
  - scripts/train_automl.py（AutoML 训练 P4——只喂 train_80）

设计约束（AutoML_Experiment_Plan 3.2）：
  留出集索引与 train_lgbm 历史口径逐索引一致（golden 测试
  tests/test_dataset_split.py），保证基线与候选的公平比较。
"""

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from src.logging_config import setup_logging

logger = setup_logging()

# ================== 常量（与 train_lgbm.py / predictor.py 一致）==================

# 6 锁定特征列（规划附录 A：无条件锁定）
FEATURE_COLS = [
    'distance', 'relative_angle', 'posture',
    'previous_action', 'phase', 'is_enraged',
]

LABEL_COL = 'next_action'

# 4 个类别 dtype 列（生产模型训练口径）
CATEGORICAL_COLS = ['posture', 'previous_action', 'phase', 'is_enraged']

# 会话来源列（P1 新增，data_cleaner 输出；分组 CV 对照用，不进特征）
SOURCE_SESSION_COL = 'source_session'


class EmptyDatasetError(Exception):
    """过滤后数据集为空——训练必须停止且不得覆盖旧模型。

    Attributes:
        stage: 'unknown_label'（未知动作全被过滤）或 'frequency'（类频不足）
        print_message: 与原 train_lgbm.py 逐字一致的停止提示
        log_message: 与原 train_lgbm.py 逐字一致的 logger.error 文案
    """

    def __init__(self, stage: str, print_message: str, log_message: str):
        super().__init__(print_message)
        self.stage = stage
        self.print_message = print_message
        self.log_message = log_message


# ================== 加载与过滤 ==================

def load_ml_dataset(csv_path) -> pd.DataFrame:
    """读取 ML 就绪数据集并执行训练前过滤（与原 train_lgbm.py 行为逐字一致）。

    顺序（不可调换——warning 语义与原实现保持一致）：
      1. pd.read_csv
      2. NaN label 过滤 + warning
      3. 非数值 label 安全转换（to_numeric coerce）+ warning
      4. ACTION_DB 未知 label 过滤 + warning（空集抛 EmptyDatasetError）
      5. 类频 >=3 过滤（空集抛 EmptyDatasetError）
      6. 4 列 astype('category')

    Raises:
        OSError/pd.errors.ParserError: CSV 读取失败（调用方决定提示文案）
        EmptyDatasetError: 过滤后为空（含阶段与原版停止文案）
    """
    df = pd.read_csv(csv_path)

    # v1.1.2: NaN label 过滤 + warning（不再静默丢弃）
    _orig_len = len(df)
    df = df[df['next_action'].notna()]
    _nan_removed = _orig_len - len(df)
    if _nan_removed:
        print(f"⚠️ Removed {_nan_removed} rows with empty labels.")
        logger.warning("Removed %d rows with empty labels", _nan_removed)

    # v1.1.2: 非数值 label 安全转换——手工编辑 CSV 后数字可能以字符串存储
    _numeric = pd.to_numeric(df['next_action'], errors='coerce')
    _non_numeric = sorted({str(v) for v in df.loc[_numeric.isna(), 'next_action'].tolist()})
    if _non_numeric:
        print(f"⚠️ 检测到非数值 label: {_non_numeric}（已从训练集过滤）")
        logger.warning("过滤非数值 label: %s", _non_numeric)
    df = df[_numeric.notna()]
    df['next_action'] = _numeric[_numeric.notna()].astype(int)

    # v1.1.1: 未知动作 label（数值但未在 ACTION_DB 中定义）
    from src.config.actions import ACTION_DB
    known_mask = df['next_action'].isin(set(ACTION_DB))
    unknown_labels = sorted({int(v) for v in df.loc[~known_mask, 'next_action'].tolist()})
    if unknown_labels:
        print(f"⚠️ 检测到未知动作 label: {unknown_labels}（未在 ACTION_DB 中定义，已从训练集过滤）")
        logger.warning("过滤未知动作 label: %s", unknown_labels)
    df = df[known_mask]
    if df.empty:
        raise EmptyDatasetError(
            'unknown_label',
            "❌ 训练数据集为空（未知动作全部被过滤），已停止训练，保留旧模型",
            "训练数据集为空，停止训练",
        )

    action_counts = df['next_action'].value_counts()
    valid_actions = action_counts[action_counts >= 3].index
    df = df[df['next_action'].isin(valid_actions)]
    if df.empty:
        raise EmptyDatasetError(
            'frequency',
            "❌ 没有足够的训练样本（每个动作至少需要 3 条），已停止训练，保留旧模型",
            "训练样本不足，停止训练",
        )

    for col in CATEGORICAL_COLS:
        df[col] = df[col].astype('category')

    return df


# ================== 切分 ==================

def make_holdout_split(df: pd.DataFrame, test_size: float = 0.2,
                       random_state: int = 42):
    """分层 80/20 切分（与原 train_lgbm.py 逐字一致，含极小数据集降级）。

    Returns:
        (train_df, holdout_df): 按原实现同样打乱顺序返回完整行 DataFrame；
        调用方按 FEATURE_COLS / LABEL_COL 自行选列。

    说明：原实现对 X=df[feature_cols] 切分；本函数对整行切分。
    train_test_split 只依据 y 与行序，二者产出的索引/标签序列逐位一致
    （由 tests/test_dataset_split.py golden 测试锁定）。
    """
    y = df[LABEL_COL]

    # v1.1.2: 极小数据集降级——sklearn stratify 要求 test_size >= n_classes
    _n_samples = len(y)
    _n_classes = int(y.nunique())
    _test_size_samples = int(np.ceil(test_size * _n_samples))
    if _test_size_samples >= _n_classes:
        _stratify = y
    else:
        _stratify = None
        print(f"⚠️ Dataset too small for stratified split: test samples={_test_size_samples}, classes={_n_classes}. Fallback to non-stratified split.")
        logger.warning(
            "Dataset too small for stratified split: test samples=%d, classes=%d. Fallback to non-stratified split.",
            _test_size_samples, _n_classes,
        )
    train_df, holdout_df = train_test_split(
        df, test_size=test_size, random_state=random_state, stratify=_stratify
    )
    return train_df, holdout_df
