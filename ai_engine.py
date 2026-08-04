# LEGACY
# Superseded by src/ architecture (P4–P5.3 modular extraction + dual-process).
# Preserved for: P3 test backward compatibility + reference fallback.
# Recommended: use `python launch.py` or `python overlay.py`.
import pymem
import pymem.process
import time
import math
import threading
import ctypes
import csv
import os
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
from collections import deque
from dearpygui import dearpygui as dpg
import traceback
from src.logging_config import setup_logging

logger = setup_logging()

# ================== 1. 动作数据库 (从 src/config/actions.py 导入) ==================
from src.config.actions import (
    ACTION_DB, ACTION_MAPPING,
    P1_ONLY_IDS, P2_PLUS_IDS, P3_ONLY_IDS,
    DOWN_IDS, SCRIPTED_IDS, MINOR_AND_PASSIVE,
    NOVA_THRESHOLDS,
    POSTURE_STAND, POSTURE_PRONE, POSTURE_FLY,
)
from src.config.offsets import OFFSETS

# 🌟 剔除了废弃的 enrage_end_time
shared_state = {
    'action_id': -1, 'posture': 1, 'phase': 1, 'is_enraged': 0,
    'is_recording': True, 'nova_warning': False, 'hp_initialized': False, 'triggered_novas': set()
}

lock = threading.Lock()
action_buffer = deque(maxlen=100)


# ================== P3.3B: 预测过滤常量（从 update_logic 内联集合提取）==================

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


# ================== P3.3A: 纯数学辅助函数（提取以便测试）==================

def calc_distance_2d(p_coords, m_coords):
    """计算玩家与怪物在 XZ 平面上的二维欧几里得距离（忽略 Y 轴）。

    Args:
        p_coords: [x, y, z] 玩家坐标
        m_coords: [x, y, z] 怪物坐标

    Returns:
        float: XZ 平面上的距离
    """
    return math.sqrt((p_coords[0] - m_coords[0]) ** 2 + (p_coords[2] - m_coords[2]) ** 2)


def calc_relative_angle(p_coords, m_coords, m_quat):
    """计算从怪物朝向到玩家的相对角度。

    算法：
      1. 从怪物四元数 (quaternion) 提取 yaw 角
      2. 从位置差计算玩家相对于怪物的方位角
      3. 归一化到 [-180, 180] 度范围

    Args:
        p_coords: [x, y, z] 玩家坐标
        m_coords: [x, y, z] 怪物坐标
        m_quat: [w, x, y, z] 怪物四元数旋转

    Returns:
        float: 相对角度（度），归一化到 [-180, 180]
    """
    monster_yaw = math.degrees(math.atan2(
        2.0 * (m_quat[1] * m_quat[3] + m_quat[0] * m_quat[2]),
        1.0 - 2.0 * (m_quat[0] ** 2 + m_quat[1] ** 2)
    ))
    target_yaw = math.degrees(math.atan2(
        p_coords[0] - m_coords[0],
        p_coords[2] - m_coords[2]
    ))
    return (target_yaw - monster_yaw + 180) % 360 - 180


def select_top_k(probs, classes, k=3, threshold=0.03):
    """从概率数组中选出 Top-K 个预测，排除低于阈值的项。

    Args:
        probs: np.ndarray, 每个类别的预测概率
        classes: np.ndarray, 对应的类别 ID
        k: 返回的最大数量（默认 3）
        threshold: 最小概率阈值（默认 0.03）

    Returns:
        list of (int, float): (class_id, probability) 元组列表，按概率降序排列
    """
    result = []
    for idx in np.argsort(probs)[-k:][::-1]:
        if probs[idx] > threshold:
            result.append((classes[idx], float(probs[idx])))
    return result


# ================== P3.3B: 预测过滤辅助函数（提取以便测试）==================

def filter_probs_by_phase(probs, classes, phase,
                          p1_only=None, p2_plus=None, p3_only=None):
    """根据战斗阶段将不可能的动作概率置零（原地修改）。

    Args:
        probs: np.ndarray, 预测概率数组（会被原地修改）
        classes: np.ndarray, 对应的类别 ID
        phase: 当前战斗阶段 (1, 2, 或 3)
        p1_only: P1 阶段独有招式 ID 集合
        p2_plus: P2+ 阶段才能使用的招式 ID 集合
        p3_only: P3 阶段独有招式 ID 集合

    Returns:
        np.ndarray: 修改后的 probs 数组（与原数组相同对象）
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


def filter_probs_by_posture(probs, classes, posture,
                            stand_exclude=None, prone_exclude=None):
    """根据怪物姿态将不可能的动作概率置零（原地修改）。

    Args:
        probs: np.ndarray, 预测概率数组（会被原地修改）
        classes: np.ndarray, 对应的类别 ID
        posture: 当前怪物姿态 (0=趴下, 1=站立, 2=飞行)
        stand_exclude: 站立姿态不可用的动作 ID 集合
        prone_exclude: 趴下姿态不可用的动作 ID 集合

    Returns:
        np.ndarray: 修改后的 probs 数组（与原数组相同对象）
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


def renormalize_probs(probs):
    """将概率数组重新归一化，使总和为 1。

    处理全零数组的情况：如果总和为 0，返回原数组不做修改。

    Args:
        probs: np.ndarray, 概率数组（原地修改）

    Returns:
        np.ndarray: 归一化后的 probs 数组
    """
    prob_sum = np.sum(probs)
    if prob_sum > 0:
        probs = probs / prob_sum
    return probs


# ================== P3.3C: Nova 阈值逻辑辅助函数（提取以便测试）==================

def evaluate_nova(hp_percent, triggered_novas=None, hp_initialized=False,
                  thresholds=None, action=-1, reset_actions=None):
    """评估 Nova（飞天火）预警状态——从当前 HP 和游戏状态纯函数计算。

    两个阶段：
      1. 初始化 (hp_initialized=False)：扫描已越过的阈值，填充已触发集合
      2. 持续检测：当 HP 跨过新阈值时触发 warning
      3. 重置：特定动作 (197/167/179) 清除 warning

    Args:
        hp_percent: 当前血量百分比 (0.0 ~ 1.0)
        triggered_novas: 已触发过的 Nova 阈值集合（None 则初始化为空集）
        hp_initialized: 是否已完成首次 HP 初始化
        thresholds: Nova 阈值列表（降序排列，默认为 NOVA_THRESHOLDS）
        action: 当前怪物动作 ID
        reset_actions: 重置 Nova warning 的动作 ID 集合（默认 {197, 167, 179}）

    Returns:
        (triggered_novas: set, nova_warning: bool, hp_initialized: bool)
    """
    if triggered_novas is None:
        triggered_novas = set()
    if thresholds is None:
        from src.config.actions import NOVA_THRESHOLDS as thresholds
    if reset_actions is None:
        reset_actions = {197, 167, 179}

    nova_warning = False

    # 阶段 1：首次初始化——标记所有已越过的阈值
    if not hp_initialized:
        for t in thresholds:
            if hp_percent <= t:
                triggered_novas.add(t)
        hp_initialized = True

    # 阶段 2：持续检测——发现新越过的阈值
    for t in thresholds:
        if hp_percent <= t and t not in triggered_novas:
            triggered_novas.add(t)
            nova_warning = True

    # 阶段 3：重置——特定动作清除 warning
    if action in reset_actions:
        nova_warning = False

    return triggered_novas, nova_warning, hp_initialized


def get_ptr(pm, base, offsets):
    try:
        addr = pm.read_longlong(base)
        for o in offsets[:-1]: addr = pm.read_longlong(addr + o)
        return addr + offsets[-1]
    except Exception:
        return 0


def find_monster(pm, base):
    for i in range(OFFSETS.MONSTER_MAX_SLOTS):
        ptr = get_ptr(pm, base, [
            OFFSETS.MONSTER_LIST_FIRST,
            i * OFFSETS.MONSTER_LIST_STRIDE,
            OFFSETS.MONSTER_LIST_NEXT,
            OFFSETS.MONSTER_LIST_TERMINAL,
        ])
        if ptr:
            try:
                hp = pm.read_longlong(ptr + OFFSETS.MONSTER_HP_BASE)
                if pm.read_float(hp + OFFSETS.HP_MAX) > OFFSETS.MONSTER_MIN_HP:
                    return ptr
            except Exception:
                pass


def data_logger_thread(pm, p_base, m_base, zone_base):
    filename = f"data/fatalis_combat_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    file_created = False
    while True:
        if not shared_state['is_recording']:
            time.sleep(1);
            continue
        try:
            zone_addr = get_ptr(pm, zone_base, [OFFSETS.ZONE_OFFSET])
            if zone_addr == 0 or pm.read_int(zone_addr) != OFFSETS.ZONE_FATALIS:
                time.sleep(1);
                continue

            player = get_ptr(pm, p_base, [
                OFFSETS.PLAYER_CHAIN_1, OFFSETS.PLAYER_CHAIN_2, OFFSETS.PLAYER_COORDS,
            ])
            monster = find_monster(pm, m_base)
            if not player or not monster: continue

            if not file_created:
                with open(filename, 'w', newline='') as f:
                    csv.writer(f).writerow(
                        ["timestamp", "hp_percent", "phase", "is_enraged", "distance", "relative_angle", "posture",
                         "action_id"])
                file_created = True

            p_coords = [pm.read_float(player + i * 4) for i in range(3)]
            m_coords = [pm.read_float(monster + OFFSETS.MONSTER_COORDS + i * 4) for i in range(3)]
            m_quat = [pm.read_float(monster + OFFSETS.MONSTER_QUAT + i * 4) for i in range(4)]
            hp_ptr = pm.read_longlong(monster + OFFSETS.MONSTER_HP_BASE)
            hp_percent = pm.read_float(hp_ptr + OFFSETS.HP_CURRENT) / pm.read_float(hp_ptr + OFFSETS.HP_MAX)

            action_id = pm.read_int(monster + OFFSETS.MONSTER_ACTION_ID)
            with lock:
                action_buffer.append(action_id)

            dist = calc_distance_2d(p_coords, m_coords)
            rel_angle = calc_relative_angle(p_coords, m_coords, m_quat)

            with open(filename, 'a', newline='') as f:
                csv.writer(f).writerow(
                    [time.time(), hp_percent, shared_state['phase'], shared_state['is_enraged'], dist, rel_angle,
                     shared_state['posture'], action_id])
        except Exception:
            logger.warning(f"录制线程异常:\n{traceback.format_exc()}")
        time.sleep(0.1)


class Ultimate_Radar_UI:
    def __init__(self, pm, p_base, m_base, zone_base):
        self.pm, self.p_base, self.m_base, self.zone_base = pm, p_base, m_base, zone_base
        self.last_action, self.last_ai_time = -1, 0
        try:
            self.ai_model = joblib.load("models/fatalis_ai_model.pkl")
            logger.info("成功加载 AI 预测模型")
            print("✅ 成功加载 AI 预测模型！")
        except Exception:
            logger.error(f"模型加载失败:\n{traceback.format_exc()}")
            self.ai_model = None

        dpg.create_context()
        with dpg.font_registry():
            try:
                with dpg.font("C:/Windows/Fonts/msyh.ttc", 20) as font:
                    pass  # 字符范围现已自动处理，不再需要 add_font_range_hint
                dpg.bind_font(font)
            except Exception:
                logger.warning(f"字体加载异常:\n{traceback.format_exc()}")
                print("⚠️ 中文字体加载异常")

        with dpg.window(label="Fatalis_God_Radar", width=420, height=350, no_title_bar=True, no_resize=True,
                        no_move=True, no_scrollbar=True, no_background=True):
            dpg.add_checkbox(label="录制实战数据", default_value=True,
                             callback=lambda s, a: shared_state.update({'is_recording': a}))
            self.text_state = dpg.add_text("等待接敌...")
            self.text_ai = dpg.add_text("")

        dpg.create_viewport(title="overlay", width=420, height=350, decorated=False, always_on_top=True,
                            clear_color=[0, 0, 0, 0])
        dpg.setup_dearpygui()
        dpg.show_viewport()
        hwnd = ctypes.windll.user32.FindWindowW(None, "overlay")
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, ctypes.windll.user32.GetWindowLongW(hwnd, -20) | 0x80000 | 0x20)
        ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x2)
        dpg.set_viewport_pos(
            (ctypes.windll.user32.GetSystemMetrics(0) - 440, int(ctypes.windll.user32.GetSystemMetrics(1) * 0.25)))

    def update_logic(self):
        try:
            zone_addr = get_ptr(self.pm, self.zone_base, [OFFSETS.ZONE_OFFSET])

            # 🌟 核心防污染逻辑：回集会所彻底清除内存数据
            if zone_addr == 0 or self.pm.read_int(zone_addr) != OFFSETS.ZONE_FATALIS:
                shared_state.update(
                    {'posture': 1, 'phase': 1, 'is_enraged': 0, 'hp_initialized': False,
                     'nova_warning': False})
                shared_state['triggered_novas'].clear()
                self.last_action = -1
                with lock: action_buffer.clear()
                dpg.set_value(self.text_state, "未在虚黑城，雷达已休眠...")
                dpg.configure_item(self.text_state, color=[255, 255, 255, 255])
                dpg.set_value(self.text_ai, "")
                return

            monster = find_monster(self.pm, self.m_base)
            player = get_ptr(self.pm, self.p_base, [
                OFFSETS.PLAYER_CHAIN_1, OFFSETS.PLAYER_CHAIN_2, OFFSETS.PLAYER_COORDS,
            ])
            if not monster or not player: return

            p_coords = [self.pm.read_float(player + i * 4) for i in range(3)]
            m_coords = [self.pm.read_float(monster + OFFSETS.MONSTER_COORDS + i * 4) for i in range(3)]
            m_quat = [self.pm.read_float(monster + OFFSETS.MONSTER_QUAT + i * 4) for i in range(4)]
            dist = calc_distance_2d(p_coords, m_coords)
            rel_angle = calc_relative_angle(p_coords, m_coords, m_quat)

            raw_action = action_buffer[-1] if action_buffer else -1
            action = ACTION_MAPPING.get(raw_action, raw_action)

            hp_ptr = self.pm.read_longlong(monster + OFFSETS.MONSTER_HP_BASE)
            hp_percent = self.pm.read_float(hp_ptr + OFFSETS.HP_CURRENT) / self.pm.read_float(hp_ptr + OFFSETS.HP_MAX)
            shared_state['phase'] = 1 if hp_percent > 0.78 else (2 if hp_percent > 0.50 else 3)

            # ========================================================
            # 1. 🌟 物理级发怒硬读取 (精确对接怪猎底层引擎秒表)
            # ========================================================
            try:
                # 定位到发怒结构体并读取内部秒表和上限 (offsets from src/config/offsets.py)
                enrage_timer = self.pm.read_float(monster + OFFSETS.ENRAGE_STRUCT + OFFSETS.ENRAGE_TIMER)
                enrage_max = self.pm.read_float(monster + OFFSETS.ENRAGE_STRUCT + OFFSETS.ENRAGE_MAX)

                # 只要正向计时器 > 0 且未触及上限，即判定为绝对发怒状态
                shared_state['is_enraged'] = 1 if (0.0 < enrage_timer < enrage_max) else 0
            except Exception:
                shared_state['is_enraged'] = 0
            # ========================================================

            # 飞天火血线预警逻辑 — P3.3C 提取为独立函数
            triggered, warning, initialized = evaluate_nova(
                hp_percent,
                triggered_novas=shared_state['triggered_novas'],
                hp_initialized=shared_state['hp_initialized'],
                action=action,
            )
            shared_state['triggered_novas'] = triggered
            shared_state['nova_warning'] = warning
            shared_state['hp_initialized'] = initialized

            # 2. 绝对姿态状态机 (包含头硬修复)
            if action != self.last_action and action != -1:
                if action in POSTURE_STAND:
                    shared_state['posture'] = 1
                elif action in POSTURE_PRONE:
                    shared_state['posture'] = 0
                elif action in POSTURE_FLY:
                    shared_state['posture'] = 2

            dpg.set_value(self.text_state,
                          f"[动作]: {ACTION_DB.get(action, f'({action})')} | P{shared_state['phase']} {'[怒]' if shared_state['is_enraged'] else '[未怒]'}\n[状态]: 距:{dist:.0f} | 角:{rel_angle:.0f}° | 血:{hp_percent * 100:.1f}%")

            # 3. 🤖 纯粹 AI 预测
            if shared_state['nova_warning']:
                dpg.set_value(self.text_ai, "【飞天火预警】血线触发，请立刻准备规避！")
                dpg.configure_item(self.text_ai, color=[255, 100, 100, 255])

            elif self.ai_model and time.time() - self.last_ai_time > 0.5 and action != -1:
                input_dict = {
                    'distance': dist, 'relative_angle': rel_angle, 'posture': shared_state['posture'],
                    'previous_action': action, 'phase': shared_state['phase'], 'is_enraged': shared_state['is_enraged']
                }

                input_data = pd.DataFrame([input_dict])
                for col in ['posture', 'previous_action', 'phase', 'is_enraged']:
                    if col in input_data.columns: input_data[col] = input_data[col].astype('category')

                probs = self.ai_model.predict_proba(input_data)[0]
                classes = self.ai_model.classes_

                # 常规姿态与阶段隔离网 (物理过滤) — P3.3B 提取为独立函数
                probs = filter_probs_by_phase(probs, classes, shared_state['phase'])
                probs = filter_probs_by_posture(probs, classes, shared_state['posture'])
                probs = renormalize_probs(probs)

                dpg.configure_item(self.text_ai, color=[150, 255, 150, 255])
                ai_msg = "预测下一招:\n"
                for class_id, prob in select_top_k(probs, classes):
                    ai_msg += f"{ACTION_DB.get(class_id, class_id)}: {prob * 100:.1f}%\n"

                dpg.set_value(self.text_ai, ai_msg)
                self.last_ai_time = time.time()

            self.last_action = action

        except Exception:
            logger.error(f"UI 刷新异常:\n{traceback.format_exc()}")

    def run(self):
        while dpg.is_dearpygui_running(): self.update_logic(); dpg.render_dearpygui_frame()
        dpg.destroy_context()


def main():
    try:
        pm = pymem.Pymem("MonsterHunterWorld.exe")
    except Exception:
        logger.error(f"游戏进程连接失败:\n{traceback.format_exc()}")
        return print("未找到游戏进程")
    base = pymem.process.module_from_name(pm.process_handle, "MonsterHunterWorld.exe").lpBaseOfDll
    PLAYER, MONSTER, ZONE = base + OFFSETS.PLAYER_BASE, base + OFFSETS.MONSTER_BASE, base + OFFSETS.ZONE_BASE
    threading.Thread(target=data_logger_thread, args=(pm, PLAYER, MONSTER, ZONE), daemon=True).start()
    Ultimate_Radar_UI(pm, PLAYER, MONSTER, ZONE).run()


if __name__ == "__main__": main()