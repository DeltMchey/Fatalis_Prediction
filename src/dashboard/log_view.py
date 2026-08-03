"""P5: LogView — 控制中心实时日志面板。

消费 src.logging_config.get_log_queue() 中的 LogRecord，
在 DPG 文本 widget 中滚动显示最近 N 行。
"""

import logging
from dearpygui import dearpygui as dpg

from src.logging_config import get_log_queue

# 显示的最大行数
_MAX_LINES = 30


class LogView:
    """日志面板。build() 创建 widgets，refresh() 从队列取消息刷新。"""

    def __init__(self, max_lines: int = _MAX_LINES):
        self._max_lines = max_lines
        self._text_tag = None
        self._buffer: list[str] = []

    def build(self) -> None:
        """创建日志文本 widget。"""
        self._text_tag = dpg.add_text("（无日志）", wrap=0)
        self._buffer = []

    def append(self, message: str) -> None:
        """追加一行日志到内部缓冲并刷新显示。"""
        self._buffer.append(message)
        if len(self._buffer) > self._max_lines:
            self._buffer = self._buffer[-self._max_lines:]
        self._render()

    def refresh(self) -> None:
        """从全局日志队列取所有待显示消息。"""
        queue = get_log_queue()
        messages = []
        while not queue.empty():
            try:
                record = queue.get_nowait()
            except Exception:
                break
            messages.append(self._format_record(record))
        if messages:
            self._buffer.extend(messages)
            if len(self._buffer) > self._max_lines:
                self._buffer = self._buffer[-self._max_lines:]
            self._render()

    def _render(self) -> None:
        """将缓冲区渲染到 DPG widget。"""
        if self._text_tag is not None:
            dpg.set_value(self._text_tag, "\n".join(self._buffer))

    @staticmethod
    def _format_record(record: logging.LogRecord) -> str:
        """将 LogRecord 格式化为单行文本。"""
        return f"[{record.levelname}] {record.getMessage()}"
