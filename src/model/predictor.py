"""P4 Step 3: ActionPredictor — LightGBM 模型加载与 AI 推理管线。

从 ai_engine.py 迁移：
  - `_POSTURE_STAND_EXCLUDE` / `_POSTURE_PRONE_EXCLUDE` 常量（P3.3B）
  - `filter_probs_by_phase` / `filter_probs_by_posture` / `renormalize_probs`（P3.3B）
  - `select_top_k`（P3.3A）
  - `update_logic()` 内联推理管线（feature 构造 → predict_proba → 过滤 → top-k）

设计约束（与架构 Review 一致）：
  - 依赖 joblib / pandas / numpy / src.config.actions
  - 不依赖 pymem / dearpygui / threading / StateTracker / MemoryReader
  - predict() 返回原始 (class_id, probability) 元组，不含 ACTION_DB 中文名（显示由调用方负责）
  - 模型加载失败时 self._model = None，predict() 返回空列表
"""

import joblib
import numpy as np
import pandas as pd


# ================== P3.3B: 预测过滤常量（从 ai_engine.py 迁移）==================

# 站立姿态（posture=1）不可用的动作 ID — AI 预测概率将被置零
_POSTURE_STAND_EXCLUDE: set[int] = {
    129, 119, 98, 99, 68, 69, 70, 71, 72, 149, 150, 151, 152, 153, 93,
}

# 趴下姿态（posture=0）不可用的动作 ID — AI 预测概率将被置零
_POSTURE_PRONE_EXCLUDE: set[int] = {
    138, 49, 50, 51, 52, 73, 107, 108, 136, 88, 91, 92, 94, 95, 96, 97,
    100, 101, 137, 154, 155, 156, 37, 38, 39, 40, 131, 132, 133, 140,
    141, 142, 135, 134, 81, 82, 83,
}


class ActionPredictor:
    """LightGBM 模型加载与 AI 推理管线。

    用法：
        predictor = ActionPredictor("models/fatalis_ai_model.pkl")
        result = predictor.predict(distance, angle, posture, prev_action, phase, enrage)
        # result: [(class_id, prob), ...] 按概率降序，最多 3 个，prob > 3%
    """

    # ================= 常量 =================

    _FEATURE_COLS = [
        "distance", "relative_angle", "posture",
        "previous_action", "phase", "is_enraged",
    ]
    _CATEGORICAL_COLS = [
        "posture", "previous_action", "phase", "is_enraged",
    ]
    _DEFAULT_TOP_K = 3
    _DEFAULT_THRESHOLD = 0.03

    def __init__(self, model_path: str):
        """加载 LightGBM 模型。

        Args:
            model_path: 模型文件路径（如 "models/fatalis_ai_model.pkl"）

        加载失败时 self._model = None（predict() 返回空列表）。
        """
        try:
            self._model = joblib.load(model_path)
        except Exception:
            self._model = None

    @property
    def is_loaded(self) -> bool:
        """模型是否成功加载。"""
        return self._model is not None

    # ================= 推理管线 =================

    def predict(
        self,
        distance: float,
        relative_angle: float,
        posture: int,
        previous_action: int,
        phase: int,
        is_enraged: int,
    ) -> list[tuple[int, float]]:
        """运行完整推理管线：特征构造 → predict_proba → 过滤 → 归一化 → Top-K。

        Args:
            distance:        XZ 平面距离
            relative_angle:  怪物→玩家相对角度（度）
            posture:         怪物姿态（0=趴下, 1=站立, 2=飞行）
            previous_action: 上一动作 Base ID（已映射）
            phase:           战斗阶段（1|2|3）
            is_enraged:      是否发怒（0|1）

        Returns:
            [(class_id, probability), ...] 按概率降序，最多 3 个，prob > 3%；
            模型未加载时返回空列表。

        Pipeline（与 ai_engine.py update_logic 完全一致）:
            predict_proba → filter_probs_by_phase → filter_probs_by_posture
                          → renormalize_probs → select_top_k
        """
        if self._model is None:
            return []

        input_dict = {
            'distance': distance,
            'relative_angle': relative_angle,
            'posture': posture,
            'previous_action': previous_action,
            'phase': phase,
            'is_enraged': is_enraged,
        }
        input_data = pd.DataFrame([input_dict])
        for col in self._CATEGORICAL_COLS:
            if col in input_data.columns:
                input_data[col] = input_data[col].astype('category')

        probs = self._model.predict_proba(input_data)[0]
        classes = self._model.classes_

        probs = self.filter_probs_by_phase(probs, classes, phase)
        probs = self.filter_probs_by_posture(probs, classes, posture)
        probs = self.renormalize_probs(probs)

        return self.select_top_k(
            probs, classes,
            k=self._DEFAULT_TOP_K,
            threshold=self._DEFAULT_THRESHOLD,
        )

    # ================= P3.3B: 预测过滤辅助函数（从 ai_engine.py 迁移，行为一致）==================

    @staticmethod
    def filter_probs_by_phase(probs, classes, phase,
                              p1_only=None, p2_plus=None, p3_only=None):
        """根据战斗阶段将不可能的动作概率置零（原地修改）。

        与 ai_engine.py filter_probs_by_phase 逐行等价。
        """
        if p1_only is None:
            from src.config.actions import P1_ONLY_IDS as p1_only
        if p2_plus is None:
            from src.config.actions import P2_PLUS_IDS as p2_plus
        if p3_only is None:
            from src.config.actions import P3_ONLY_IDS as p3_only

        for i, class_id in enumerate(classes):
            if phase > 1 and class_id in p1_only:
                probs[i] = 0.0
            if phase < 2 and class_id in p2_plus:
                probs[i] = 0.0
            if phase < 3 and class_id in p3_only:
                probs[i] = 0.0
        return probs

    @staticmethod
    def filter_probs_by_posture(probs, classes, posture,
                                stand_exclude=None, prone_exclude=None):
        """根据怪物姿态将不可能的动作概率置零（原地修改）。

        与 ai_engine.py filter_probs_by_posture 逐行等价。
        """
        if stand_exclude is None:
            stand_exclude = _POSTURE_STAND_EXCLUDE
        if prone_exclude is None:
            prone_exclude = _POSTURE_PRONE_EXCLUDE

        for i, class_id in enumerate(classes):
            if posture == 1 and class_id in stand_exclude:
                probs[i] = 0.0
            elif posture == 0 and class_id in prone_exclude:
                probs[i] = 0.0
        return probs

    @staticmethod
    def renormalize_probs(probs):
        """将概率数组重新归一化，使总和为 1。

        处理全零数组：总和为 0 时返回原数组不做修改。
        与 ai_engine.py renormalize_probs 逐行等价。
        """
        prob_sum = np.sum(probs)
        if prob_sum > 0:
            probs = probs / prob_sum
        return probs

    # ================= P3.3A: Top-K 选择（从 ai_engine.py 迁移，行为一致）==================

    @staticmethod
    def select_top_k(probs, classes, k=3, threshold=0.03):
        """从概率数组中选出 Top-K 个预测，排除低于阈值的项。

        与 ai_engine.py select_top_k 逐行等价。
        """
        result = []
        for idx in np.argsort(probs)[-k:][::-1]:
            if probs[idx] > threshold:
                result.append((classes[idx], float(probs[idx])))
        return result
