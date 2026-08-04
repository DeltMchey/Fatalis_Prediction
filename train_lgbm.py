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
    print("🔄 正在加载纯粹观测流战斗数据集...")
    try:
        df = pd.read_csv("data/ML_Ready_Dataset.csv")
    except Exception:
        logger.error("找不到 data/ML_Ready_Dataset.csv")
        return print("❌ 找不到 data/ML_Ready_Dataset.csv！")

    action_counts = df['next_action'].value_counts()
    valid_actions = action_counts[action_counts >= 3].index
    df = df[df['next_action'].isin(valid_actions)]

    categorical_features = ['posture', 'previous_action', 'phase', 'is_enraged']
    for col in categorical_features:
        df[col] = df[col].astype('category')

    # 🌟 恢复为 6 维核心特征
    feature_cols = ['distance', 'relative_angle', 'posture', 'previous_action', 'phase', 'is_enraged']
    X = df[feature_cols]
    y = df['next_action']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

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