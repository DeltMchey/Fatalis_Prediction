"""v3(事故修复 F3): 两代备份链轮换 + 同内容跳过 — 数据集/模型写盘共享实现。

背景（2026-09-16 用户实测事故，Reviewer 确认根因）：
  旧机制（单代 .bak + 无条件轮换）存在两个叠加缺陷：
  1. 发行包不带原始 CSV 时，data_cleaner 只从在场 CSV 重建数据集，
     出厂 19 会话数据集被单场会话静默替换（.bak 同步被覆盖，无回退）；
  2. 用户二次训练（数据未变，训练确定性 → 新旧模型 sha 相同）时，
     无条件轮换把当前模型推进 .bak，出厂备份被"自吞"。

本模块提供统一晋升语义，供 data_cleaner.py（数据集）与
src/model/production_backend.py（模型）共享，两处行为一致：

  promote_with_backup(tmp, target, generations=2):
    - sha(tmp) == sha(target)（target 存在时）→ 跳过轮换，仅原子替换
      （杜绝二次训练自吞备份；备份链保持指向真正的"上一版"）
    - 内容不同 → 推进两代链（target→.bak→.bak2，.bak2 溢出即弃）
      后原子替换
    - tmp 必须与 target 同目录（os.replace 跨分区非原子）

注意：models/factory_model.pkl（v3 起随包附带的出厂不可变副本）
不属于备份链——训练/轮换机制永不触碰它。
"""

import hashlib
import os
from pathlib import Path

# 晋升结果状态（sidecar / 调用方日志消费）
ROTATED = "rotated"                # 内容变化 → 备份链推进一代
SKIPPED_SAME_SHA = "skipped_same_sha"  # 内容相同 → 备份链不动（防自吞）
FIRST_WRITE = "first_write"        # target 原不存在（首次产出，无旧版可轮换）


def sha256_file(path) -> str:
    """流式计算文件 sha256（1 MiB 分块，大模型安全）。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def backup_suffix(generation: int) -> str:
    """第 N 代备份文件后缀：.bak / .bak2 / .bak3 ..."""
    return ".bak" if generation == 1 else f".bak{generation}"


def rotate_backup_chain(target, generations: int = 2) -> bool:
    """把 target 推进 N 代备份链：target→.bak→.bak2（末端溢出即被覆盖）。

    Args:
        target: 现行文件路径（将被移走，调用方随后写入新内容）
        generations: 链长（v3 默认 2：.bak + .bak2）

    Returns:
        bool: 是否发生轮换（target 不存在 → False）。
    """
    target = Path(target)
    if not os.path.exists(target):
        return False
    # 从最老一代开始搬，避免正向搬移时覆盖尚未后移的下一代
    for gen in range(generations, 1, -1):
        src = target.with_name(target.name + backup_suffix(gen - 1))
        if src.exists():
            os.replace(src, target.with_name(target.name + backup_suffix(gen)))
    os.replace(target, target.with_name(target.name + backup_suffix(1)))
    return True


def promote_with_backup(tmp_path, target_path, generations: int = 2) -> str:
    """tmp → target 原子晋升，带两代链轮换与同 sha 跳过。

    Args:
        tmp_path: 已写好的新内容临时文件（须与 target 同目录）
        target_path: 目标文件（如 data/ML_Ready_Dataset.csv、
                     models/fatalis_ai_model.pkl）
        generations: 备份链长度（默认 2 = .bak + .bak2）

    Returns:
        ROTATED / SKIPPED_SAME_SHA / FIRST_WRITE 之一。
    """
    tmp, target = Path(tmp_path), Path(target_path)
    if os.path.exists(target):
        if sha256_file(tmp) == sha256_file(target):
            # 同内容：绝不推进备份链——这是"二次训练自吞出厂备份"的
            # 根因修复点。仍执行原子替换（内容相同，无观测差异）。
            os.replace(tmp, target)
            return SKIPPED_SAME_SHA
        rotate_backup_chain(target, generations)
        os.replace(tmp, target)
        return ROTATED
    os.replace(tmp, target)
    return FIRST_WRITE
