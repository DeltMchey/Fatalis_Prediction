import pandas as pd
import glob
import os


def clean_combat_data():
    print("🔍 正在扫描当前目录下的实战数据文件...")
    all_files = glob.glob("data/fatalis_combat_data_*.csv")
    if not all_files:
        print("❌ 未找到任何战斗数据文件！")
        return

    # ==================== 动作分类与映射集 (从 src/config/actions.py 导入) ====================
    from src.config.actions import (
        ACTION_MAPPING, MINOR_AND_PASSIVE, SCRIPTED_IDS, DOWN_IDS,
    )

    EXCLUDE_TARGETS = MINOR_AND_PASSIVE | SCRIPTED_IDS
    all_transitions = []

    for file in all_files:
        print(f"🔄 正在处理: {file}")
        try:
            df = pd.read_csv(file)
        except Exception as e:
            continue

        df = df[df['distance'] < 5000]
        df = df[df['action_id'] != 1]

        last_row = None
        current_posture = 1  # 默认开局站立
        last_posture = 1
        last_mapped_action = -1  # 🌟 新增：追踪映射后的主动作，防止动画帧内部抖动

        for idx, row in df.iterrows():
            raw_action_id = int(row['action_id'])
            # 🌟 核心整合：立刻将生肉 ID 转换为起手 Base ID
            action_id = ACTION_MAPPING.get(raw_action_id, raw_action_id)

            phase_val = row.get('phase', 1)
            enrage_val = row.get('is_enraged', 0)

            # ----------------------------------------------------
            # 🌟 V4.5 绝对姿态状态机 (保留了头硬 219, 222 修复)
            # ----------------------------------------------------
            # 只有当【合并后的主动作】发生变化时，才触发布尔判定
            if last_mapped_action != -1 and action_id != last_mapped_action:
                if action_id in {115, 116, 121, 122, 129, 119, 98, 99, 68, 69, 70, 71, 72, 149, 150, 151, 32, 19, 197,
                                 219, 222}:
                    current_posture = 1
                elif action_id in {138, 49, 50, 51, 52, 73, 30, 74, 75}:
                    current_posture = 0
                elif action_id in {107, 108, 167, 179}:
                    current_posture = 2

            if action_id in SCRIPTED_IDS:
                current_posture = 4
            elif action_id in DOWN_IDS and action_id not in {74, 219, 222, 217, 220, 221, 75}:
                current_posture = 3

            # 倒地发呆强转趴下逻辑
            if last_mapped_action != -1:
                if last_mapped_action in DOWN_IDS and action_id in {306, 307, 308}:
                    current_posture = 0
            # ----------------------------------------------------

            # 提取动作派生关系：仅在【合并后的主动作】跨越时提取
            if last_row is not None and action_id != last_mapped_action:
                target_action = action_id
                if target_action not in EXCLUDE_TARGETS and last_posture != 4:
                    all_transitions.append({
                        'distance': last_row['distance'],
                        'relative_angle': last_row['relative_angle'],
                        'posture': last_posture,
                        'previous_action': last_mapped_action,  # 记录上一个是哪个合并招式
                        'phase': phase_val,
                        'is_enraged': enrage_val,
                        'next_action': target_action
                    })

            last_row = row
            last_posture = current_posture
            last_mapped_action = action_id  # 更新游标为映射后的动作

    if not all_transitions:
        print("⚠️ 未提取到有效数据。")
        return

    clean_df = pd.DataFrame(all_transitions)
    clean_df.to_csv("data/ML_Ready_Dataset.csv", index=False)
    print(f"✅ V4.5 纯粹观测流(含起手映射)数据提纯完成！有效样本: {len(clean_df)} 条")


if __name__ == "__main__":
    clean_combat_data()