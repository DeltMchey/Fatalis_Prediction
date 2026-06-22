import pymem
import pymem.process
import time
import os


def get_ptr(pm, base, offsets):
    try:
        addr = pm.read_longlong(base)
        for o in offsets[:-1]: addr = pm.read_longlong(addr + o)
        return addr + offsets[-1]
    except:
        return 0


def find_monster(pm, base):
    for i in range(10):
        ptr = get_ptr(pm, base, [0x698, i * 0x8, 0x138, 0])
        if ptr:
            try:
                hp = pm.read_longlong(ptr + 0x7670)
                if pm.read_float(hp + 0x60) > 500: return ptr
            except:
                pass
    return 0


def scan_enrage_structure():
    try:
        pm = pymem.Pymem("MonsterHunterWorld.exe")
        print("✅ 成功连接到游戏进程！")
    except Exception as e:
        print("❌ 未找到游戏进程，请先启动游戏。")
        return

    base = pymem.process.module_from_name(pm.process_handle, "MonsterHunterWorld.exe").lpBaseOfDll
    MONSTER_BASE = base + 0x051238C8

    # 我们要扫描的内部偏移量列表 (每 4 个字节是一个 Float)
    # 扫描从 0x0 到 0x28 的所有抽屉
    offsets_to_test = [0x0, 0x4, 0x8, 0xC, 0x10, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x28]

    print("🚀 正在监听怪物的发怒结构体...")
    print("⚠️ 请进图并找到黑龙，然后用钩爪拍脸将它激怒！\n")

    while True:
        monster_ptr = find_monster(pm, MONSTER_BASE)

        if monster_ptr != 0:
            # 定位到发怒状态的绝对地址
            enrage_struct_addr = monster_ptr + 0x1BE30

            # 清屏，让数据在原地刷新，方便肉眼观察
            os.system('cls' if os.name == 'nt' else 'clear')
            print("=========================================")
            print("👁️  实时发怒内存剖析器 (Enrage Memory Scanner)")
            print("=========================================")

            # 遍历所有抽屉并打印浮点数
            for offset in offsets_to_test:
                try:
                    val = pm.read_float(enrage_struct_addr + offset)
                    # 格式化输出，对齐方便看
                    print(f" 偏移量 +0x{offset:02X} :  {val:10.3f}")
                except:
                    print(f" 偏移量 +0x{offset:02X} :  [读取错误]")

            print("=========================================")
            print("💡 提示：")
            print("- 找那个【激怒瞬间变成一百多，并且正在匀速减少】的数字！")
            print("- 找那个【你打他时会增加，满了就归零】的数字 (积蓄值)！")

        else:
            os.system('cls' if os.name == 'nt' else 'clear')
            print("🏠 未找到怪物，请进入狩猎地图...")

        # 每 0.2 秒刷新一次
        time.sleep(0.2)


if __name__ == "__main__":
    scan_enrage_structure()