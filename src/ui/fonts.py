"""P5.1.1: Shared CJK font loading for Dashboard + OverlayUI.

统一中文字体配置：
  - Windows: 微软雅黑 (msyh.ttc)
  - 其他平台: 尝试常见 CJK 字体，失败时使用 DPG 默认字体（不阻塞）

调用时机:
  - 必须在 dpg.create_context() 之后调用
  - Dashboard.run() 和 OverlayUI._setup_dpg() 各调用一次
"""

import logging

from dearpygui import dearpygui as dpg

logger = logging.getLogger("BlackDragon")

# Windows 微软雅黑（与 ai_engine.py 原 L334 一致）
_MSYH_PATH: str = "C:/Windows/Fonts/msyh.ttc"

# 跨平台候选字体（按顺序尝试）
_FONT_CANDIDATES: list[str] = [
    _MSYH_PATH,
    "C:/Windows/Fonts/msyh.ttc",          # Win10 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",        # 黑体（备选）
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",  # Linux 文泉驿
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",  # Linux Noto CJK
]


def setup_cjk_font(font_path: str | None = None,
                   font_size: int = 20) -> None:
    """加载并绑定 CJK 中文字体（幂等）。

    Args:
        font_path: 显式指定字体路径；None 则自动探测候选字体
        font_size: 字号（默认 20，与 ai_engine.py 一致）

    找不到可用中文字体时打印警告并使用 DPG 默认字体——不抛异常，
    保证 Dashboard 在字体缺失环境下仍可启动（Linux CI / 测试）。
    """
    path = font_path or _FONT_CANDIDATES[0]
    # 若显式指定路径不存在，回退到候选探测
    candidates = [path] if font_path else _FONT_CANDIDATES
    loaded_path = _find_existing(candidates)
    if loaded_path is None:
        logger.warning("未找到 CJK 字体，中文可能无法正常显示")
        return
    try:
        with dpg.font_registry():
            with dpg.font(loaded_path, font_size) as font:
                pass  # 字符范围自动处理（DPG 2.x 默认含 CJK 范围）
            dpg.bind_font(font)
    except Exception:
        logger.warning("字体加载异常，使用默认字体: %s", loaded_path)


def _find_existing(candidates: list[str]) -> str | None:
    """返回第一个存在的字体路径，否则 None。"""
    import os
    for path in candidates:
        if os.path.exists(path):
            return path
    return None
