import pandas as pd
import numpy as np
import lightgbm as lgb
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib
import os
from src.logging_config import setup_logging

logger = setup_logging()

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

def train_fatalis_ai():
    # v1.1: 显式检查输入数据集存在——clean 失败时停止，不覆盖旧模型
    if not os.path.exists("data/ML_Ready_Dataset.csv"):
        logger.error("找不到 data/ML_Ready_Dataset.csv")
        return print("❌ 找不到 data/ML_Ready_Dataset.csv！请先录制战斗数据或运行 data_cleaner.py")

    print("🔄 正在加载纯粹观测流战斗数据集...")
    try:
        df = pd.read_csv("data/ML_Ready_Dataset.csv")
    except Exception:
        logger.error("读取 data/ML_Ready_Dataset.csv 失败")
        return print("❌ 读取 data/ML_Ready_Dataset.csv 失败！")

    # v1.1.1: 训练阶段检测未知动作 label——未在 ACTION_DB 中定义的动作会导致
    # LightGBM LabelEncoder "unseen labels" 崩溃（根因：随机 split 将稀有类全放入 test）。
    # 显式检测并输出具体 action_id，然后从训练集过滤，而不是简单 catch Exception。
    from src.config.actions import ACTION_DB
    # v1.1.2: NaN label 过滤 + warning（不再静默丢弃）
    _orig_len = len(df)
    df = df[df['next_action'].notna()]
    _nan_removed = _orig_len - len(df)
    if _nan_removed:
        print(f"⚠️ Removed {_nan_removed} rows with empty labels.")
        logger.warning("Removed %d rows with empty labels", _nan_removed)

    # v1.1.2: 非数值 label 安全转换——手工编辑 CSV 后数字可能以字符串存储（整列变 object）
    # pd.to_numeric(errors='coerce') 将 '37' → 37、'abc' → NaN，随后过滤并 warning。
    _numeric = pd.to_numeric(df['next_action'], errors='coerce')
    _non_numeric = sorted({str(v) for v in df.loc[_numeric.isna(), 'next_action'].tolist()})
    if _non_numeric:
        print(f"⚠️ 检测到非数值 label: {_non_numeric}（已从训练集过滤）")
        logger.warning("过滤非数值 label: %s", _non_numeric)
    df = df[_numeric.notna()]
    df['next_action'] = _numeric[_numeric.notna()].astype(int)

    # v1.1.1: 未知动作 label（数值但未在 ACTION_DB 中定义）
    known_mask = df['next_action'].isin(set(ACTION_DB))
    unknown_labels = sorted({int(v) for v in df.loc[~known_mask, 'next_action'].tolist()})
    if unknown_labels:
        print(f"⚠️ 检测到未知动作 label: {unknown_labels}（未在 ACTION_DB 中定义，已从训练集过滤）")
        logger.warning("过滤未知动作 label: %s", unknown_labels)
    df = df[known_mask]
    if df.empty:
        print("❌ 训练数据集为空（未知动作全部被过滤），已停止训练，保留旧模型")
        logger.error("训练数据集为空，停止训练")
        return

    action_counts = df['next_action'].value_counts()
    valid_actions = action_counts[action_counts >= 3].index
    df = df[df['next_action'].isin(valid_actions)]
    if df.empty:
        print("❌ 没有足够的训练样本（每个动作至少需要 3 条），已停止训练，保留旧模型")
        logger.error("训练样本不足，停止训练")
        return

    categorical_features = ['posture', 'previous_action', 'phase', 'is_enraged']
    for col in categorical_features:
        df[col] = df[col].astype('category')

    # 🌟 恢复为 6 维核心特征
    feature_cols = ['distance', 'relative_angle', 'posture', 'previous_action', 'phase', 'is_enraged']
    X = df[feature_cols]
    y = df['next_action']

    # v1.1.1: 分层抽样——保证每个类在 train/test 中都有实例，避免 eval_set 出现 unseen label。
    # v1.1.2: 极小数据集降级——sklearn stratify 要求 test_size >= n_classes，否则抛
    # ValueError: "The test_size should be greater or equal to the number of classes"。
    # 正常数据（2000+ samples / 40~50 classes）始终满足，保持 stratify=y。
    _n_samples = len(y)
    _n_classes = int(y.nunique())
    _test_size_samples = int(np.ceil(0.2 * _n_samples))
    if _test_size_samples >= _n_classes:
        _stratify = y
    else:
        _stratify = None
        print(f"⚠️ Dataset too small for stratified split: test samples={_test_size_samples}, classes={_n_classes}. Fallback to non-stratified split.")
        logger.warning(
            "Dataset too small for stratified split: test samples=%d, classes=%d. Fallback to non-stratified split.",
            _test_size_samples, _n_classes,
        )
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=_stratify
    )

    model = lgb.LGBMClassifier(
        objective='multiclass',
        num_leaves=63,
        max_depth=7,
        learning_rate=0.03,
        n_estimators=300,
        random_state=42,
        class_weight='balanced',
        n_jobs=-1,
        subsample=0.8,
        colsample_bytree=0.8,
        importance_type='gain'
    )

    print("\n🚀 正在训练 LightGBM (V4.5 纯粹观测流)...")
    model.fit(
        X_train, y_train,
        categorical_feature=categorical_features,
        eval_set=[(X_test, y_test)],
        eval_metric='multi_logloss',
        callbacks=[lgb.early_stopping(stopping_rounds=15, verbose=False)]
    )

    y_pred = model.predict(X_test)
    print(f"\n🏆 绝对准确率 (Accuracy): {accuracy_score(y_test, y_pred) * 100:.2f}%")

    probs = model.predict_proba(X_test)
    top3_indices = np.argsort(probs, axis=1)[:, -3:]
    y_test_array = y_test.values
    top3_accuracy = np.mean([y_test_array[i] in model.classes_[top3_indices[i]] for i in range(len(y_test_array))])
    print(f"🌟 实战黄金指标：Top-3 命中率: {top3_accuracy * 100:.2f}%")

    # 保存前确保 models/ 目录存在（开发模式 CWD 为项目根，冻结模式 cwd 为 exe 目录）
    os.makedirs("models", exist_ok=True)
    # v1.1: 写入前备份已有模型，训练失败时 Dashboard/Overlay 仍可使用旧模型
    if os.path.exists("models/fatalis_ai_model.pkl"):
        os.replace("models/fatalis_ai_model.pkl", "models/fatalis_ai_model.pkl.bak")
    joblib.dump(model, "models/fatalis_ai_model.pkl")
    print(f"💾 模型已保存至: models/fatalis_ai_model.pkl")

    importance = model.feature_importances_
    features = X.columns
    feature_names = {'distance': '距离', 'relative_angle': '相对角度', 'posture': '姿态', 'previous_action': '上一招', 'phase': '阶段', 'is_enraged': '是否发怒'}
    translated_features = [feature_names.get(f, f) for f in features]

    plt.figure(figsize=(10, 6))
    indices = np.argsort(importance)
    plt.barh(range(len(indices)), importance[indices], color='mediumturquoise')
    plt.yticks(range(len(indices)), [translated_features[i] for i in indices])
    plt.title("黑龙出招决策权重")
    plt.tight_layout()
    plt.savefig("models/feature_importance.png")
    print("📈 图表已保存为 models/feature_importance.png！")

if __name__ == "__main__":
    train_fatalis_ai()