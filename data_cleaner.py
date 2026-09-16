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
        ACTION_DB, ACTION_MAPPING, MINOR_AND_PASSIVE, SCRIPTED_IDS, DOWN_IDS,
        POSTURE_STAND, POSTURE_PRONE, POSTURE_FLY,
    )

    EXCLUDE_TARGETS = MINOR_AND_PASSIVE | SCRIPTED_IDS
    all_transitions = []
    # v1.1.1: 收集未在 ACTION_DB 中定义的未知动作（训练阶段会导致 unseen label 崩溃）
    unknown_targets: set = set()

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
                if action_id in POSTURE_STAND:
                    current_posture = 1
                elif action_id in POSTURE_PRONE:
                    current_posture = 0
                elif action_id in POSTURE_FLY:
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
                    # v1.1.1: 过滤未知动作——未在 ACTION_DB 中定义的动作不作为训练 label
                    #（否则训练阶段 LightGBM LabelEncoder 对稀有类 split 产生 unseen label 崩溃）
                    if target_action not in ACTION_DB:
                        unknown_targets.add(target_action)
                        continue
                    all_transitions.append({
                        'distance': last_row['distance'],
                        'relative_angle': last_row['relative_angle'],
                        'posture': last_posture,
                        'previous_action': last_mapped_action,  # 记录上一个是哪个合并招式
                        'phase': phase_val,
                        'is_enraged': enrage_val,
                        'next_action': target_action,
                        # P1(AutoML 实验): 会话来源标注——值=源战斗 CSV 文件名（不含路径）。
                        # 纯增量列（放末位）：train_lgbm 显式选 6 特征列不受影响；
                        # 用途 = StratifiedGroupKFold 分组 CV 对照（防泄漏稳健性检查）。
                        'source_session': os.path.basename(file),
                    })

            last_row = row
            last_posture = current_posture
            last_mapped_action = action_id  # 更新游标为映射后的动作

    # v1.1.1: 输出未知动作过滤警告（列出具体 action_id）
    if unknown_targets:
        print(f"⚠️ 已过滤 {len(unknown_targets)} 个未知动作 ID {sorted(unknown_targets)}（未在 ACTION_DB 中定义，训练时会导致崩溃）")

    if not all_transitions:
        print("⚠️ 未提取到有效数据。")
        return

    clean_df = pd.DataFrame(all_transitions)

    # ================= v3(F1): 合并语义 — 防止数据集被在场 CSV 静默替换 =================
    # 事故根因：发行包不带原始 CSV 时（或用户清理后），本函数只从在场 CSV 重建
    # 数据集 → 出厂 19 会话被单场会话替换。修复：写盘前读入现有数据集，
    # 保留 source_session 不在本次 CSV 集合中的历史行，再追加本次新提取的
    # 转移样本（同名会话以重新提取为准 = 全量 CSV 在场时行为与旧版零变化）。
    dataset_path = "data/ML_Ready_Dataset.csv"
    current_sessions = {os.path.basename(f) for f in all_files}
    merged_history_rows = 0
    if os.path.exists(dataset_path):
        try:
            old_df = pd.read_csv(dataset_path)
        except Exception:
            old_df = None
            print("⚠️ 已有数据集读取失败，无法合并历史会话（旧文件仍会备份保留）")
        if (old_df is not None and "source_session" in old_df.columns
                and set(clean_df.columns) <= set(old_df.columns)):
            keep = old_df[~old_df["source_session"].isin(current_sessions)]
            if len(keep):
                clean_df = pd.concat([keep[clean_df.columns], clean_df],
                                     ignore_index=True)
                merged_history_rows = len(keep)
                print(f"📦 已保留 {keep['source_session'].nunique()} 个历史会话的 "
                      f"{len(keep)} 行（本次未重录，合并进新数据集防止替换丢失）")
        elif old_df is not None:
            print("⚠️ 已有数据集缺少 source_session 列（远古格式），无法合并历史"
                  "会话——旧内容仅保留在 .bak/.bak2 备份链中")

    # v3(F3): 写盘改为 tmp 原子晋升 + 两代备份链（.bak/.bak2）+ 同 sha 跳过
    #（杜绝"数据未变时二次运行把上一版推进备份链、出厂备份被自吞"）
    from src.core.backup_chain import promote_with_backup
    tmp_path = dataset_path + ".tmp"
    clean_df.to_csv(tmp_path, index=False)
    promote_with_backup(tmp_path, dataset_path, generations=2)
    summary = (f"（含历史保留 {merged_history_rows} 条）"
               if merged_history_rows else "")
    print(f"✅ V4.5 纯粹观测流(含起手映射)数据提纯完成！有效样本: {len(clean_df)} 条{summary}")


if __name__ == "__main__":
    clean_combat_data()