"""P4/P5(AutoML 实验): MLP 自定义 learner — 类别均衡采样 + FLAML 注册 wrapper。

两个类（均为导出契约的一部分——放 src/model/ 随应用分发，保证 pickle
反序列化时类可导入；禁止移入 scripts/）：

  BalancedMLPClassifier
      MLPClassifier 薄封装。MLPClassifier 无 class_weight 参数，fit 内按
      类权重过采样（少数类复制到最大类计数，带 random_state 确定性）实现
      类别均衡（规划附录 A 已锁定方案）。

  MLPPipelineEstimator
      FLAML learner wrapper（flaml.automl.model.BaseEstimator 子类）：
      Pipeline(OneHotEncoder(类别码列) + StandardScaler(数值列),
      BalancedMLPClassifier)。超参域锁定：隐层 ≤ (128, 64)、max_iter ≤ 500。
      注册方式（flaml 2.6.0 实际 API，规划中的 @register_learner 不存在）：
          automl.add_learner("mlp", MLPPipelineEstimator)

导出（P5）：从 wrapper 的 `estimator` 属性提取原生 Pipeline 重持久化，
推理零 flaml 依赖（OneHotEncoder/Scaler/BalancedMLP 全部随 pickle 持久化）。
"""

import numpy as np
import pandas as pd
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# FeatureBuilder 输出中的类别码列 / 数值列（编码后仍用原列名）
CAT_CODE_COLS = ['posture', 'previous_action', 'phase', 'is_enraged']
NUM_COLS = ['distance', 'relative_angle']


class BalancedMLPClassifier(MLPClassifier):
    """fit 内做过采样的 MLPClassifier（类别均衡；无 class_weight 参数的替代）。

    不覆盖 __init__（保持 sklearn estimator 契约：get_params/clone）。
    """

    def fit(self, X, y):
        X_bal, y_bal = self._oversample(X, y)
        return super().fit(X_bal, y_bal)

    def _oversample(self, X, y):
        """少数类有放回复制到最大类计数，整体洗牌（random_state 确定）。"""
        rng = np.random.RandomState(self.random_state)
        y_arr = np.asarray(y)
        X_arr = np.asarray(X)
        classes, counts = np.unique(y_arr, return_counts=True)
        max_count = int(counts.max())
        keep_X, keep_y = [X_arr], [y_arr]
        for cls, cnt in zip(classes, counts):
            if cnt >= max_count:
                continue
            idx = np.where(y_arr == cls)[0]
            extra = rng.choice(idx, size=max_count - int(cnt), replace=True)
            keep_X.append(X_arr[extra])
            keep_y.append(y_arr[extra])
        X_bal = np.concatenate(keep_X, axis=0)
        y_bal = np.concatenate(keep_y, axis=0)
        perm = rng.permutation(len(y_bal))
        return X_bal[perm], y_bal[perm]


def mlp_learner_wrapper():
    """返回 FLAML 2.6.0 的 MLP learner 类（BaseEstimator 子类，惰性构建）。

    用法（scripts/train_automl.py）：
        automl.add_learner(learner_name='mlp', learner_class=mlp_learner_wrapper())

    惰性构建原因：本模块会被导出模型的加载路径导入（取 BalancedMLPClassifier），
    顶层 import flaml 会把 flaml 拉进推理依赖——违反零 flaml 运行时约束。
    wrapper 类实例本身不进导出 pickle（导出取 `estimator` 属性内的原生 Pipeline）。
    """
    from flaml import tune
    from flaml.automl.model import BaseEstimator

    class _MLPPipelineEstimator(BaseEstimator):
        """Pipeline(OneHot+Scaler, BalancedMLPClassifier) 的可搜索 wrapper。"""

        @classmethod
        def search_space(cls, data_size, task, **kwargs):
            # 锁定约束：隐层 ≤ (128, 64)、max_iter ≤ 500（规划附录 A）
            return {
                'hl_1': {
                    'domain': tune.qrandint(lower=16, upper=128, q=16),
                    'init_value': 64, 'low_cost_init_value': 16,
                },
                'hl_2': {
                    'domain': tune.qrandint(lower=0, upper=64, q=16),
                    'init_value': 0, 'low_cost_init_value': 0,
                },
                'alpha': {
                    'domain': tune.loguniform(lower=1e-6, upper=1e-2),
                    'init_value': 1e-4,
                },
                'learning_rate_init': {
                    'domain': tune.loguniform(lower=1e-4, upper=1e-2),
                    'init_value': 1e-3,
                },
                'max_iter': {
                    'domain': tune.qrandint(lower=50, upper=500, q=50),
                    'init_value': 200, 'low_cost_init_value': 100,
                },
            }

        def __init__(self, task='multiclass', **config):
            super().__init__(task, **config)

        def _build_pipeline(self):
            params = dict(self.params)
            hl_1 = int(params.pop('hl_1', 64))
            hl_2 = int(params.pop('hl_2', 0))
            max_iter = int(params.pop('max_iter', 200))
            alpha = float(params.pop('alpha', 1e-4))
            lr_init = float(params.pop('learning_rate_init', 1e-3))
            params.pop('n_jobs', None)
            hidden = (hl_1, hl_2) if hl_2 > 0 else (hl_1,)

            prep_cols = []
            cat_present = [c for c in CAT_CODE_COLS if c in self._input_cols]
            num_present = [c for c in NUM_COLS if c in self._input_cols]
            if cat_present:
                prep_cols.append((
                    'cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False),
                    cat_present,
                ))
            if num_present:
                prep_cols.append(('num', StandardScaler(), num_present))
            from sklearn.compose import ColumnTransformer
            return Pipeline([
                ('prep', ColumnTransformer(prep_cols)),
                ('mlp', BalancedMLPClassifier(
                    hidden_layer_sizes=hidden,
                    alpha=alpha,
                    learning_rate_init=lr_init,
                    max_iter=max_iter,
                    early_stopping=True,
                    n_iter_no_change=15,
                    random_state=42,
                )),
            ])

        def fit(self, X_train, y_train, budget=None, **kwargs):
            self._input_cols = list(X_train.columns) if isinstance(
                X_train, pd.DataFrame) else list(CAT_CODE_COLS + NUM_COLS)
            self._model = self._build_pipeline()
            self._model.fit(X_train, y_train)
            return self

    return _MLPPipelineEstimator
