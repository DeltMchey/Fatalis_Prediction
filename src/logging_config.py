"""Unified logging configuration for BlackDragon.

Usage:
    from src.logging_config import setup_logging
    logger = setup_logging()

日志双路输出（P5）:
  - FileHandler  → blackdragon.log (保持不变)
  - QueueHandler → _log_queue (供 Dashboard 日志面板消费)

注意: QueueHandler 添加到返回的 logger（"BlackDragon"），而非 root logger——
  root 的 handler 数量保持 1 个 FileHandler（test_logging.py 约束）。
"""

import logging
import logging.handlers
import queue

# 全局日志队列 —— Dashboard 日志面板轮询消费
_log_queue: "queue.Queue[logging.LogRecord]" = queue.Queue()


def get_log_queue() -> "queue.Queue[logging.LogRecord]":
    """返回全局日志队列（Dashboard 日志面板消费）。"""
    return _log_queue


def _resolve_log_path() -> str:
    """日志文件路径（hotfix RC2: frozen-aware）。

    冻结模式下 CWD 不确定（双击/压缩软件内启动），写到 exe 目录
    保证用户总能找回 blackdragon.log；开发模式保持 CWD 相对路径不变。
    复用 src.app.config.resolve_runtime_path —— 与模型/数据路径同一解析器，
    避免 frozen 判定逻辑双实现漂移。
    """
    from src.app.config import resolve_runtime_path
    return str(resolve_runtime_path("blackdragon.log"))


def setup_logging(name: str = "BlackDragon") -> logging.Logger:
    """Configure and return a logger that writes to blackdragon.log + GUI queue.

    Log levels used across the project:
    - WARNING: Recoverable errors (recording thread glitch, font fallback)
    - ERROR:   Non-recoverable errors (model load failure, UI crash, process attach failure)
    """
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(_resolve_log_path(), encoding="utf-8"),
        ],
    )
    logger = logging.getLogger(name)
    # 幂等添加 QueueHandler —— 日志同时推送至 GUI 队列
    if not any(isinstance(h, logging.handlers.QueueHandler)
               for h in logger.handlers):
        logger.addHandler(logging.handlers.QueueHandler(_log_queue))
    return logger
