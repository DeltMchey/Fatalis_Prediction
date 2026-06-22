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
)

# 🌟 剔除了废弃的 enrage_end_time
shared_state = {
    'action_id': -1, 'posture': 1, 'phase': 1, 'is_enraged': 0,
    'is_recording': True, 'nova_warning': False, 'hp_initialized': False, 'triggered_novas': set()
}

lock = threading.Lock()
action_buffer = deque(maxlen=100)


def get_ptr(pm, base, offsets):
    try:
        addr = pm.read_longlong(base)
        for o in offsets[:-1]: addr = pm.read_longlong(addr + o)
        return addr + offsets[-1]
    except Exception:
        return 0


def find_monster(pm, base):
    for i in range(10):
        ptr = get_ptr(pm, base, [0x698, i * 0x8, 0x138, 0])
        if ptr:
            try:
                hp = pm.read_longlong(ptr + 0x7670)
                if pm.read_float(hp + 0x60) > 500: return ptr
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
            zone_addr = get_ptr(pm, zone_base, [0xAED0])
            if zone_addr == 0 or pm.read_int(zone_addr) != 417:
                time.sleep(1);
                continue

            player = get_ptr(pm, p_base, [0x50, 0xC0, 0x670])
            monster = find_monster(pm, m_base)
            if not player or not monster: continue

            if not file_created:
                with open(filename, 'w', newline='') as f:
                    csv.writer(f).writerow(
                        ["timestamp", "hp_percent", "phase", "is_enraged", "distance", "relative_angle", "posture",
                         "action_id"])
                file_created = True

            p_coords = [pm.read_float(player + i * 4) for i in range(3)]
            m_coords = [pm.read_float(monster + 0x160 + i * 4) for i in range(3)]
            m_quat = [pm.read_float(monster + 0x170 + i * 4) for i in range(4)]
            hp_ptr = pm.read_longlong(monster + 0x7670)
            hp_percent = pm.read_float(hp_ptr + 0x64) / pm.read_float(hp_ptr + 0x60)

            action_id = pm.read_int(monster + 0x6278)
            with lock:
                action_buffer.append(action_id)

            dist = math.sqrt((p_coords[0] - m_coords[0]) ** 2 + (p_coords[2] - m_coords[2]) ** 2)
            monster_yaw = math.degrees(math.atan2(2.0 * (m_quat[1] * m_quat[3] + m_quat[0] * m_quat[2]),
                                                  1.0 - 2.0 * (m_quat[0] ** 2 + m_quat[1] ** 2)))
            target_yaw = math.degrees(math.atan2(p_coords[0] - m_coords[0], p_coords[2] - m_coords[2]))
            rel_angle = (target_yaw - monster_yaw + 180) % 360 - 180

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
                    dpg.add_font_range_hint(dpg.mvFontRangeHint_Chinese_Simplified_Common)
                    dpg.add_font_range_hint(dpg.mvFontRangeHint_Default)
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
            zone_addr = get_ptr(self.pm, self.zone_base, [0xAED0])

            # 🌟 核心防污染逻辑：回集会所彻底清除内存数据
            if zone_addr == 0 or self.pm.read_int(zone_addr) != 417:
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
            player = get_ptr(self.pm, self.p_base, [0x50, 0xC0, 0x670])
            if not monster or not player: return

            p_coords = [self.pm.read_float(player + i * 4) for i in range(3)]
            m_coords = [self.pm.read_float(monster + 0x160 + i * 4) for i in range(3)]
            m_quat = [self.pm.read_float(monster + 0x170 + i * 4) for i in range(4)]
            dist = math.sqrt((p_coords[0] - m_coords[0]) ** 2 + (p_coords[2] - m_coords[2]) ** 2)
            monster_yaw = math.degrees(math.atan2(2.0 * (m_quat[1] * m_quat[3] + m_quat[0] * m_quat[2]),
                                                  1.0 - 2.0 * (m_quat[0] ** 2 + m_quat[1] ** 2)))
            target_yaw = math.degrees(math.atan2(p_coords[0] - m_coords[0], p_coords[2] - m_coords[2]))
            rel_angle = (target_yaw - monster_yaw + 180) % 360 - 180

            raw_action = action_buffer[-1] if action_buffer else -1
            action = ACTION_MAPPING.get(raw_action, raw_action)

            hp_ptr = self.pm.read_longlong(monster + 0x7670)
            hp_percent = self.pm.read_float(hp_ptr + 0x64) / self.pm.read_float(hp_ptr + 0x60)
            shared_state['phase'] = 1 if hp_percent > 0.78 else (2 if hp_percent > 0.50 else 3)

            # ========================================================
            # 1. 🌟 物理级发怒硬读取 (精确对接怪猎底层引擎秒表)
            # ========================================================
            try:
                # 定位到发怒结构体 (+0x1BE30) 并读取内部秒表 (+0x24) 和 上限 (+0x28)
                enrage_timer = self.pm.read_float(monster + 0x1BE30 + 0x24)
                enrage_max = self.pm.read_float(monster + 0x1BE30 + 0x28)

                # 只要正向计时器 > 0 且未触及上限，即判定为绝对发怒状态
                shared_state['is_enraged'] = 1 if (0.0 < enrage_timer < enrage_max) else 0
            except Exception:
                shared_state['is_enraged'] = 0
            # ========================================================

            # 飞天火血线预警逻辑 (保留)
            if not shared_state['hp_initialized']:
                for t in NOVA_THRESHOLDS:
                    if hp_percent <= t: shared_state['triggered_novas'].add(t)
                shared_state['hp_initialized'] = True
            for t in NOVA_THRESHOLDS:
                if hp_percent <= t and t not in shared_state['triggered_novas']:
                    shared_state['triggered_novas'].add(t);
                    shared_state['nova_warning'] = True
            if action in {197, 167, 179}: shared_state['nova_warning'] = False

            # 2. 绝对姿态状态机 (包含头硬修复)
            if action != self.last_action and action != -1:
                if action in {115, 116, 121, 122, 129, 119, 98, 99, 68, 69, 70, 71, 72, 149, 150, 151, 32, 19, 197, 219,
                              222}:
                    shared_state['posture'] = 1
                elif action in {138, 49, 50, 51, 52, 73, 30, 74, 75}:
                    shared_state['posture'] = 0
                elif action in {107, 108, 167, 179}:
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

                # 常规姿态与阶段隔离网 (物理过滤)
                for i, class_id in enumerate(classes):
                    if shared_state['phase'] > 1 and class_id in P1_ONLY_IDS: probs[i] = 0.0
                    if shared_state['phase'] < 2 and class_id in P2_PLUS_IDS: probs[i] = 0.0
                    if shared_state['phase'] < 3 and class_id in P3_ONLY_IDS: probs[i] = 0.0
                    if shared_state['posture'] == 1 and class_id in {129, 119, 98, 99, 68, 69, 70, 71, 72, 149, 150,
                                                                     151, 152, 153, 93}:
                        probs[i] = 0.0
                    elif shared_state['posture'] == 0 and class_id in {138, 49, 50, 51, 52, 73, 107, 108, 136, 88, 91,
                                                                       92, 94, 95, 96, 97, 100, 101, 137, 154, 155, 156,
                                                                       37, 38, 39, 40, 131, 132, 133, 140, 141, 142,
                                                                       135, 134, 81, 82, 83}:
                        probs[i] = 0.0

                prob_sum = np.sum(probs)
                if prob_sum > 0: probs = probs / prob_sum

                dpg.configure_item(self.text_ai, color=[150, 255, 150, 255])
                ai_msg = "预测下一招:\n"
                for idx in np.argsort(probs)[-3:][::-1]:
                    if probs[
                        idx] > 0.03: ai_msg += f"{ACTION_DB.get(classes[idx], classes[idx])}: {probs[idx] * 100:.1f}%\n"

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
    PLAYER, MONSTER, ZONE = base + 0x050139A0, base + 0x051238C8, base + 0x0500ECA0
    threading.Thread(target=data_logger_thread, args=(pm, PLAYER, MONSTER, ZONE), daemon=True).start()
    Ultimate_Radar_UI(pm, PLAYER, MONSTER, ZONE).run()


if __name__ == "__main__": main()