"""P5(AutoML 实验): FLAML 标签编码还原层（导出契约的一部分）。

背景（代码现实，规划未覆盖）：FLAML auto_augment 对分类任务统一用
sklearn LabelEncoder 编码 y（xgboost sklearn API 硬性要求标签 ∈ [0, n)，
该编码不可关闭）。因此从 automl 产物提取的原生 estimator 的 classes_
是编码值 [0..n-1] 而非动作 ID——直接导出会让 ActionPredictor 的
phase/posture 过滤链（按动作 ID 匹配）整体失效。

LabelDecodedEstimator 把 classes_ 还原为原始标签：
  - 持有内层 estimator（以编码标签训练）+ 原始标签表
  - predict_proba 列序 = 编码序 = 原始标签升序（LabelEncoder 语义），
    因此直接透传即可与 self.classes_ 对齐
  - predict 把内层编码输出映射回原始标签
  - 不 import flaml（推理零 flaml 依赖），随导出 pickle 持久化
"""

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin


class LabelDecodedEstimator(BaseEstimator, ClassifierMixin):
    """classes_ 还原为原始标签的原生 estimator 包装（导出专用）。

    Args:
        estimator: 以 LabelEncoder 编码 y 训练的原生 estimator
                   （其 classes_ 为 [0..n-1] 升序）
        original_labels: 原始标签全集（将作为本对象的 classes_，升序）
    """

    _estimator_type = "classifier"

    def __init__(self, estimator, original_labels):
        self.estimator = estimator
        self.original_labels = original_labels
        self.classes_ = np.asarray(sorted(original_labels))
        inner_classes = np.asarray(estimator.classes_)
        if not np.array_equal(inner_classes, np.arange(len(self.classes_))):
            raise ValueError(
                f"内层 estimator classes_ 非编码序 [0..n): {inner_classes[:8]}..."
            )
        if len(inner_classes) != len(self.classes_):
            raise ValueError("内层类别数与原始标签数不一致")

    # ---- 推理契约（ActionPredictor 依赖面）----

    def predict_proba(self, X):
        return self.estimator.predict_proba(X)

    def predict(self, X):
        encoded = np.asarray(self.estimator.predict(X))
        mapping = {int(c): i for i, c in enumerate(self.estimator.classes_)}
        return np.asarray([self.classes_[mapping[int(e)]] for e in encoded])

    # ---- 元信息委托（feature_importances_ 等，缺失安全）----

    def __getattr__(self, name):
        # 守卫：dunder 与核心属性不委托——unpickle 期间 self.estimator 尚未
        # 赋值，无守卫的委托会无限递归（RecursionError）
        if name.startswith("__") or name in ("estimator", "classes_", "original_labels"):
            raise AttributeError(name)
        return getattr(self.estimator, name)
