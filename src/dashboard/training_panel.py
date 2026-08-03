"""P5: TrainingPanel — 模型训练控制面板。

提供:
  - 开始/取消训练按钮（经 AppController 调 train_lgbm.py 子进程）
  - 训练输出实时显示
  - 训练状态指示
"""

from dearpygui import dearpygui as dpg


class TrainingPanel:
    """训练面板。build() 创建 widgets，refresh() 轮询训练输出。"""

    _MAX_LINES = 30

    def __init__(self, controller):
        """注入 AppController。

        Args:
            controller: AppController — start_training/cancel_training/
                        get_training_output/is_training
        """
        self._controller = controller
        self._widgets: dict = {}
        self._buffer: list[str] = []

    def build(self) -> None:
        """创建训练面板 widgets。"""
        with dpg.group():
            with dpg.group(horizontal=True):
                self._widgets["start_btn"] = dpg.add_button(
                    label="开始训练", callback=self._on_start)
                self._widgets["cancel_btn"] = dpg.add_button(
                    label="取消训练", callback=self._on_cancel)
            self._widgets["status"] = dpg.add_text("训练状态: 空闲")
            self._widgets["output"] = dpg.add_text("", wrap=0)

    def refresh(self) -> None:
        """轮询训练输出并刷新显示。"""
        lines = self._controller.get_training_output()
        if lines:
            self._buffer.extend(lines)
            if len(self._buffer) > self._MAX_LINES:
                self._buffer = self._buffer[-self._MAX_LINES:]
            dpg.set_value(self._widgets["output"], "\n".join(self._buffer))
        # 刷新状态行
        status = "训练状态: 进行中" if self._controller.is_training else "训练状态: 空闲"
        dpg.set_value(self._widgets["status"], status)

    # ================= 回调 =================

    def _on_start(self, sender=None, app_data=None) -> None:
        """开始训练按钮回调。"""
        ok = self._controller.start_training()
        if not ok:
            self._buffer.append("[提示] 训练已在运行或启动失败")

    def _on_cancel(self, sender=None, app_data=None) -> None:
        """取消训练按钮回调。"""
        self._controller.cancel_training()
        self._buffer.append("[提示] 已请求取消训练")
