"""P5: StatusBar — 控制中心状态指示灯栏。

显示:
  - 游戏连接状态 (🟢/🔴)
  - 模型加载状态 (🟢/🔴)
  - 录制状态 (🟢/🟡/⬛)
  - 覆盖层状态 (🟢/⬛)
"""

from dearpygui import dearpygui as dpg


class StatusBar:
    """状态栏 widget 集合。build() 创建 widgets，update() 刷新值。"""

    _GAME_ON = "游戏: 🟢 已连接"
    _GAME_OFF = "游戏: 🔴 未连接"
    _MODEL_ON = "模型: 🟢 已加载"
    _MODEL_OFF = "模型: 🔴 未加载"
    _REC_ON = "录制: 🟢 进行中"
    _REC_OFF = "录制: ⬛ 停止"
    _OVL_ON = "覆盖层: 🟢 显示"
    _OVL_OFF = "覆盖层: ⬛ 隐藏"

    def __init__(self):
        self._game_text = None
        self._model_text = None
        self._rec_text = None
        self._ovl_text = None

    def build(self) -> None:
        """创建状态栏 widgets（须在 DPG context 创建后调用）。"""
        with dpg.group(horizontal=True):
            self._game_text = dpg.add_text(self._GAME_OFF)
            dpg.add_spacer(width=20)
            self._model_text = dpg.add_text(self._MODEL_OFF)
            dpg.add_spacer(width=20)
            self._rec_text = dpg.add_text(self._REC_OFF)
            dpg.add_spacer(width=20)
            self._ovl_text = dpg.add_text(self._OVL_OFF)

    def update(self, game: bool, model: bool, recording: bool,
               overlay: bool) -> None:
        """刷新状态显示。"""
        if self._game_text is not None:
            dpg.set_value(self._game_text,
                          self._GAME_ON if game else self._GAME_OFF)
        if self._model_text is not None:
            dpg.set_value(self._model_text,
                          self._MODEL_ON if model else self._MODEL_OFF)
        if self._rec_text is not None:
            value = self._REC_ON if recording else self._REC_OFF
            dpg.set_value(self._rec_text, value)
        if self._ovl_text is not None:
            dpg.set_value(self._ovl_text,
                          self._OVL_ON if overlay else self._OVL_OFF)
