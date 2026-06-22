import pandas as pd
import glob
import os


def upgrade_old_csv_files():
    # 找到所有的实战数据文件
    all_files = glob.glob("data/fatalis_combat_data_*.csv")
    if not all_files:
        print("❌ 未找到任何战斗数据文件！")
        return

    upgraded_count = 0

    for file in all_files:
        df = pd.read_csv(file)

        # 检查是否已经是新版数据（如果已经有 phase 列，说明是新录的，跳过）
        if 'phase' in df.columns and 'is_enraged' in df.columns:
            continue

        print(f"🔄 正在升级旧数据: {file} ...")

        # 1. 补全阶段 (Phase)
        # 默认是 1，如果血量 <= 78% 变 2，<= 50% 变 3
        df['phase'] = 1
        df.loc[df['hp_percent'] <= 0.78, 'phase'] = 2
        df.loc[df['hp_percent'] <= 0.50, 'phase'] = 3

        # 2. 补全发怒状态 (Enrage) 软计时器回溯
        enrage_end_time = 0.0
        is_enraged_list = []

        # 遍历每一行，模拟时光倒流
        for idx, row in df.iterrows():
            current_time = float(row['timestamp'])
            action = int(row['action_id'])

            # 如果捕捉到 4, 5, 179，并且是该动作的第一帧（这里简化处理，只要检测到就刷新时间）
            if action in {4, 5, 179}:
                # 往后推 180 秒
                enrage_end_time = current_time + 180.0

            # 判断当前时间是否在发怒区间内
            if current_time < enrage_end_time:
                is_enraged_list.append(1)
            else:
                is_enraged_list.append(0)

        # 将算好的发怒状态作为新列加入
        df['is_enraged'] = is_enraged_list

        # 3. 重新调整列的顺序（保持和新代码一致）
        # 新代码的列顺序: timestamp, hp_percent, phase, is_enraged, distance, relative_angle, posture, action_id
        # 注意：旧数据可能没有存 posture（当时是用 cleaner 推算的），没关系，清洁脚本 V4.1 会再次推算
        expected_cols = ['timestamp', 'hp_percent', 'phase', 'is_enraged', 'distance', 'relative_angle', 'action_id']

        # 保留存在的列
        final_cols = [col for col in expected_cols if col in df.columns]
        # 如果旧数据存了 posture 也保留
        if 'posture' in df.columns:
            final_cols.insert(-1, 'posture')

        df = df[final_cols]

        # 覆盖保存
        df.to_csv(file, index=False)
        upgraded_count += 1
        print(f"   ✅ 成功补充 Phase 和 Enrage 维度！")

    print(f"\n🎉 升级完成！共抢救回 {upgraded_count} 个旧对战记录。")
    print("现在你可以直接运行 V4.1 的 data_cleaner.py 来混合清洗新旧数据了！")


if __name__ == "__main__":
    upgrade_old_csv_files()