import pandas as pd
import glob
import os


def clean_combat_data():
    print("🔍 正在扫描当前目录下的实战数据文件...")
    all_files = glob.glob("data/fatalis_combat_data_*.csv")
    if not all_files:
        print("❌ 未找到任何战斗数据文件！")
        return

    # ==================== 🚫 动作分类与映射集 ====================
    # 🌟 新增：多段动作合并字典，将动画中后段强制映射为起手 Base ID
    ACTION_MAPPING = {
        # 龙车 (立/趴)
        38: 37, 39: 37, 40: 37,
        50: 49, 51: 49, 52: 49,
        # 连咬 (立/趴)
        54: 53, 55: 53, 56: 53,57:53,
        69: 68, 70: 68, 71: 68, 72: 68,
        # 地毯火系列
        132: 131, 133: 131,
        141: 140, 142: 140,
        144: 143, 145: 143,
        85: 84, 86: 84, 87: 84,
        # 后撤 (立/趴)
        147: 146, 148: 146,
        150: 149, 151: 149,
        # 捕食
        209: 208, 210: 208, 211: 208, 212: 208, 213: 208, 214: 208, 215: 208, 216: 208,
        # 其他多段动作
        92: 91, 97: 96, 95: 94, 90: 89,  # 三连火球
        104: 103, 106: 105,  # 空中三连火球
        127: 126, 122: 121,  # 飞天俯冲
        101: 100, 99: 98,  # 三连蓄力火
        156: 155,  # 360度扫火
        80: 79,  # 大咬
        34: 33,  # 拍地
        36: 35,  # 扫地
        82: 81, 83: 81,  # 吐痰
        119: 129,  # 蓄力火 (趴→立)
        116: 115,  # 俯冲
        108: 107  # 跳投
    }

    MINOR_AND_PASSIVE = {306, 307, 308, 309, 4, 5, 28, 21, 22, 23, 24, 74, 295, 294, 296, 297, 219, 222, 217, 220, 221,
                         75, 241, 242, 249, 245, 246, 237, 236, 232, 278, 279, 280, 30}
    SCRIPTED_IDS = set(range(157, 198))
    DOWN_IDS = {75, 221, 232, 236, 237, 241, 242, 245, 246, 249, 278, 279, 280}

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