import pymem
import pymem.process
import time
import math
import threading
import ctypes
from collections import deque
from dearpygui import dearpygui as dpg

# ================== 动作数据库 ==================
ACTION_DB = {
    306: "等待", 307: "等待", 308: "等待",
    309: "开场吼", 4: "怒吼", 5: "怒吼",30: "趴下",28:"转身后退",
    88: "单火球", 93: "单火球",
    91: "三连火球", 92: "三连火球",
    96:"三连火球",97:"三连火球",
    94:"三连火球",95:"三连火球",
    89: "三连火球", 90: "三连火球",
    103: "空中三连火球", 104: "空中三连火球",
    102:"空中单火球",
    110:"空中直线火",
    115:"俯冲",116:"俯冲",
    130: "蓄力火",129: "蓄力火", 119: "蓄力火",124: "蓄力火",
    126: "飞天俯冲",121: "飞天俯冲", 122: "飞天俯冲",127: "飞天俯冲",
    100: "三连蓄力火",101: "三连蓄力火", 98:"三连蓄力火",99:"三连蓄力火",
    137: "孕吐", 138: "孕吐",139:"空中孕吐",
    155: "360度扫火", 156: "360度扫火",
    37: "龙车", 38:"龙车",39: "龙车", 40: "龙车",
    49:"龙车",50: "龙车",51: "龙车",52: "龙车",
    153: "后退S火", 136: "前进S火", 109: "空中S火",152:"前进S火（趴下）",
    131: "地毯火", 132: "地毯火", 133: "地毯火",
    140: "地毯火", 141: "地毯火",142: "地毯火",
    143: "地毯火", 144: "地毯火", 145: "地毯火",
    87: "地毯火",84: "地毯火",85: "地毯火",86: "地毯火",
    78: "小咬", 79: "大咬",80: "大咬",
    53: "连咬", 54: "连咬", 55: "连咬", 56: "连咬",
    68: "连咬", 69: "连咬", 70: "连咬", 71: "连咬", 72: "连咬",
    154: "扇形火", 73: "下压", 74: "反击下压",
    34: "拍地",33:"拍地",36: "扫地",35: "扫地",  76:"扫尾",77:"尾砸",
    135: "直线火",134:"左右火",
    180:"飞天火",181: "飞天火", 186: "飞天火",187: "飞天火", 188: "飞天火",189: "飞天火",
    191: "飞天火", 192: "飞天火", 193: "飞天火", 194:"飞天火",195:"飞天火结束",196:"飞回场地",197: "落地",
    21: "索敌", 22: "索敌",
    149: "后撤", 150: "后撤", 151: "后撤",146: "后撤",147: "后撤",148: "后撤",
    81: "吐痰",82: "吐痰",  83: "吐痰",
    208:"捕食",209:"捕食",210:"捕食",214:"捕食",211:"捕食",213:"捕食",215:"捕食",212:"捕食",216:"捕食",
    107: "跳投", 108: "跳投",
    219: "头硬", 222: "头硬",
    217: "胸硬", 220: "胸硬",221:"破胸",
    295:"被拍",294:"被拍",296:"被拍",297:"被拍",
    241:"破头倒地",242:"破头倒地",
    249:"拘束",245:"拘束",246:"拘束",
    23:"转身",24:"转身",32:"站起",
    19:"准备落地",
    75:"器械反击",237:"器械倒地",236:"器械倒地",232:"击龙枪倒地",
    158:"1转2",159:"1转2",160:"1转2",161:"1转2",162:"1转2",163:"1转2",164:"1转2",165:"1转2",166:"1转2结束",167:"飞回场中",
    168:"2转3",170:"2转3",171:"2转3",173:"2转3",174:"2转3",175:"2转3",169:"2转3",172:"2转3",176:"2转3",177:"2转3结束",178:"飞回场中",179:"p3开场吼",
    278:"讨伐成功",
}
PREDICT_DB = {
}
# ================== 全局变量 & 锁 ==================
action_buffer = deque(maxlen=200)
lock = threading.Lock()

# ================== 内存读取辅助函数 ==================
def get_ptr(pm, base, offsets):
    try:
        addr = pm.read_longlong(base)
        for o in offsets[:-1]:
            addr = pm.read_longlong(addr + o)
        return addr + offsets[-1]
    except:
        return 0

def find_monster(pm, base):
    for i in range(10):
        ptr = get_ptr(pm, base, [0x698, i*0x8, 0x138, 0])
        if ptr:
            try:
                hp = pm.read_longlong(ptr+0x7670)
                if pm.read_float(hp+0x60) > 500:
                    return ptr
            except:
                pass
    return 0

def get_latest_action():
    with lock:
        if not action_buffer:
            return -1
        return action_buffer[-1][0]

# ================== UI 类 ==================
class UI:
    def __init__(self, pm, p_base, m_base):
        self.pm = pm
        self.p_base = p_base
        self.m_base = m_base
        self.last_action = -1
        self.last_show_time = 0

        dpg.create_context()

        # 强制设置组件背景完全透明
        with dpg.theme() as transparent_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, [0, 0, 0, 0], category=dpg.mvThemeCat_Core)
        dpg.bind_theme(transparent_theme)

        # 字体加载
        with dpg.font_registry():
            try:
                font = dpg.add_font("C:/Windows/Fonts/msyh.ttc", 26)
            except:
                try:
                    font = dpg.add_font("C:/Windows/Fonts/simhei.ttf", 26)
                except:
                    print("⚠️ 未找到中文字体，可能显示乱码")

        # 👇 修改点 1：在这里显式地将窗口大小撑大到 500x200
        with dpg.window(
                label="overlay",
                width=500,  # <--- 新增：设定内部窗口宽度
                height=200,  # <--- 新增：设定内部窗口高度
                no_title_bar=True,
                no_resize=True,
                no_move=True,
                no_scrollbar=True,
                no_background=True
        ):
            self.text = dpg.add_text("等待接敌...")
            dpg.configure_item(self.text, color=[255, 255, 255, 255])

        # 👇 修改点 2：将底层系统视口也同步撑大到 500x200
        dpg.create_viewport(
            title="overlay",
            width=500,  # <--- 修改：从 350 扩大到 500
            height=200,  # <--- 修改：从 150 扩大到 200
            decorated=False,
            always_on_top=True,
            clear_color=[0, 0, 0, 0]
        )

        dpg.setup_dearpygui()
        dpg.show_viewport()
        if 'font' in locals():
            dpg.bind_font(font)

        # Windows 底层 API 透明及鼠标穿透
        hwnd = ctypes.windll.user32.FindWindowW(None, "overlay")
        if hwnd:
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20)
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x2)

        self.set_pos()

    def set_pos(self):
        w = ctypes.windll.user32.GetSystemMetrics(0)
        h = ctypes.windll.user32.GetSystemMetrics(1)
        # 👇 修改点 3：由于窗口变宽了，我们把它往左边再挪一点，防止右侧超出屏幕边缘
        dpg.set_viewport_pos((w - 520, int(h * 0.3)))  # 从 360 改为 520

    def update_logic(self):
        try:
            player = get_ptr(self.pm, self.p_base, [0x50, 0xC0, 0x670])
            monster = find_monster(self.pm, self.m_base)

            # 如果没进地图或者没找到怪，就跳过不更新 UI
            if not player or not monster:
                return

            px = self.pm.read_float(player)
            pz = self.pm.read_float(player + 8)
            mx = self.pm.read_float(monster + 0x160)
            mz = self.pm.read_float(monster + 0x168)

            dist = math.sqrt((px - mx)**2 + (pz - mz)**2)
            action = get_latest_action()
            now = time.time()

            # 动作改变，或者每 0.3 秒刷新一次距离
            if action != self.last_action or now - self.last_show_time > 0.3:
                name = ACTION_DB.get(action, f"未知({action})")

                # 注意：这里配置颜色必须是 [R, G, B, 255] 格式
                if action in PREDICT_DB:
                    txt = f"{PREDICT_DB[action]}\n{name}\n距离: {dist:.1f}"
                    dpg.set_value(self.text, txt)
                    dpg.configure_item(self.text, color=[255, 80, 80, 255])
                else:
                    txt = f"{name}\n距离: {dist:.1f}"
                    dpg.set_value(self.text, txt)
                    dpg.configure_item(self.text, color=[255, 255, 255, 255])

                self.last_action = action
                self.last_show_time = now

        except Exception as e:
            # 💡 关键：不再使用 pass 静默隐藏错误。这里会告诉你哪里出错了
            print(f"[!] UI 刷新发生错误: {e}")

    def run(self):
        print("✅ 正在运行透明悬浮窗模块...")
        while dpg.is_dearpygui_running():
            self.update_logic()
            dpg.render_dearpygui_frame()
        dpg.destroy_context()

# ================== 主函数 ==================
def main():
    try:
        pm = pymem.Pymem("MonsterHunterWorld.exe")
        base = pymem.process.module_from_name(
            pm.process_handle, "MonsterHunterWorld.exe"
        ).lpBaseOfDll
        print("✅ 成功连接游戏进程！")
    except Exception:
        print("❌ 错误：未找到怪物猎人世界游戏进程，请先打开游戏。")
        return

    PLAYER = base + 0x050139A0
    MONSTER = base + 0x051238C8

    # 定义独立的后台采样子线程
    def sampler_optimized(pm_instance, monster_base):
        while True:
            try:
                m = find_monster(pm_instance, monster_base)
                if m:
                    a = pm_instance.read_int(m + 0x6278)
                    with lock:
                        action_buffer.append((a, time.time()))
            except Exception as e:
                pass
            time.sleep(0.01)

    # 启动后台动作采样
    sampler_thread = threading.Thread(target=sampler_optimized, args=(pm, MONSTER), daemon=True)
    sampler_thread.start()

    # 启动 UI 主循环 (会接管当前线程)
    ui = UI(pm, PLAYER, MONSTER)
    ui.run()

if __name__ == "__main__":
    main()