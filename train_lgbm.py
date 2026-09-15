import numpy as np
import lightgbm as lgb
import matplotlib.pyplot as plt
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
    # P1(AutoML 实验): 过滤 + 切分逻辑提取至 src/model/dataset.py 共享模块
    # （基线补测/AutoML 训练与训练脚本消费同一份代码，留出集逐索引一致）。
    # 行为零变化：过滤顺序、warning 输出、切分参数与原内联实现逐字一致，
    # 由 tests/test_dataset_split.py golden 索引测试锁定。
    from src.model.dataset import (
        CATEGORICAL_COLS, FEATURE_COLS, LABEL_COL,
        EmptyDatasetError, load_ml_dataset, make_holdout_split,
    )
    try:
        df = load_ml_dataset("data/ML_Ready_Dataset.csv")
    except EmptyDatasetError as e:
        print(e.print_message)
        logger.error(e.log_message)
        return
    except Exception:
        logger.error("读取 data/ML_Ready_Dataset.csv 失败")
        return print("❌ 读取 data/ML_Ready_Dataset.csv 失败！")

    train_df, test_df = make_holdout_split(df, test_size=0.2, random_state=42)
    X_train, y_train = train_df[FEATURE_COLS], train_df[LABEL_COL]
    X_test, y_test = test_df[FEATURE_COLS], test_df[LABEL_COL]

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
        categorical_feature=CATEGORICAL_COLS,
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
    features = X_train.columns
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