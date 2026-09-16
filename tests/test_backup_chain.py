"""v3(事故修复 F3): src/core/backup_chain.py 单元测试 — 两代备份链 + 同 sha 跳过。

锁定语义（data_cleaner 与 production_backend 共享，两处行为一致的前提）：
  - rotate_backup_chain: 两代链推进（.bak→.bak2→溢出丢弃，target→.bak）
  - promote_with_backup:
      * 首次写入 → FIRST_WRITE，不产生备份
      * 内容变化 → ROTATED，链推进一代
      * 内容相同（sha 一致）→ SKIPPED_SAME_SHA，备份链不动（防自吞）
  - 链长可参数化（generations=1 退化为旧单代行为）
"""

from src.core.backup_chain import (
    FIRST_WRITE,
    ROTATED,
    SKIPPED_SAME_SHA,
    backup_suffix,
    promote_with_backup,
    rotate_backup_chain,
    sha256_file,
)


class TestBackupSuffix:
    def test_suffix_naming(self):
        assert backup_suffix(1) == ".bak"
        assert backup_suffix(2) == ".bak2"
        assert backup_suffix(3) == ".bak3"


class TestSha256File:
    def test_known_digest(self, tmp_path):
        p = tmp_path / "f.bin"
        p.write_bytes(b"hello")
        # echo -n hello | sha256sum 的标准值
        assert sha256_file(p) == (
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        )


class TestRotateBackupChain:
    def test_two_generation_rotation(self, tmp_path):
        """v1 → v2 → v3 三次轮换：.bak=v2, .bak2=v1，v0 溢出被弃。"""
        t = tmp_path / "model.pkl"
        t.write_bytes(b"v0")
        rotate_backup_chain(t)          # .bak=v0
        t.write_bytes(b"v1")
        rotate_backup_chain(t)          # .bak=v1, .bak2=v0
        t.write_bytes(b"v2")
        rotate_backup_chain(t)          # .bak=v2, .bak2=v1（v0 溢出）

        # rotate 语义 = 移走 target（调用方随后写入新内容）
        assert not t.exists()
        assert (tmp_path / "model.pkl.bak").read_bytes() == b"v2"
        assert (tmp_path / "model.pkl.bak2").read_bytes() == b"v1"
        assert not (tmp_path / "model.pkl.bak3").exists()

    def test_missing_target_no_rotation(self, tmp_path):
        """target 不存在 → False，不产生任何备份文件。"""
        assert rotate_backup_chain(tmp_path / "nope.pkl") is False
        assert list(tmp_path.iterdir()) == []

    def test_single_generation_compat(self, tmp_path):
        """generations=1 → 旧单代行为（target→.bak，无 .bak2）。"""
        t = tmp_path / "model.pkl"
        t.write_bytes(b"a")
        (tmp_path / "model.pkl.bak").write_bytes(b"old")
        rotate_backup_chain(t, generations=1)
        assert (tmp_path / "model.pkl.bak").read_bytes() == b"a"
        assert not (tmp_path / "model.pkl.bak2").exists()


class TestPromoteWithBackup:
    def test_first_write(self, tmp_path):
        tmp, target = tmp_path / "x.new", tmp_path / "x.pkl"
        tmp.write_bytes(b"first")
        assert promote_with_backup(tmp, target) == FIRST_WRITE
        assert target.read_bytes() == b"first"
        assert not tmp.exists()                  # 已原子晋升
        assert not (tmp_path / "x.pkl.bak").exists()

    def test_rotated_on_change(self, tmp_path):
        target = tmp_path / "x.pkl"
        target.write_bytes(b"old")
        tmp = tmp_path / "x.new"
        tmp.write_bytes(b"new")
        assert promote_with_backup(tmp, target) == ROTATED
        assert target.read_bytes() == b"new"
        assert (tmp_path / "x.pkl.bak").read_bytes() == b"old"

    def test_same_sha_skips_rotation(self, tmp_path):
        """同内容晋升 → 备份链不动（二次训练自吞出厂备份的根因修复）。"""
        target = tmp_path / "x.pkl"
        target.write_bytes(b"current")
        (tmp_path / "x.pkl.bak").write_bytes(b"factory")
        (tmp_path / "x.pkl.bak2").write_bytes(b"ancient")

        tmp = tmp_path / "x.new"
        tmp.write_bytes(b"current")              # 与 target 逐字节相同
        assert promote_with_backup(tmp, target) == SKIPPED_SAME_SHA

        assert target.read_bytes() == b"current"
        # 备份链完全未动 —— 出厂备份存活
        assert (tmp_path / "x.pkl.bak").read_bytes() == b"factory"
        assert (tmp_path / "x.pkl.bak2").read_bytes() == b"ancient"
        assert not tmp.exists()

    def test_chain_progression_across_promotes(self, tmp_path):
        """端到端：v0 出厂 → 训练 v1 → 同内容重训（不推进）→ 训练 v2（推进）。"""
        target = tmp_path / "m.pkl"

        tmp = tmp_path / "m.new"; tmp.write_bytes(b"v0")
        promote_with_backup(tmp, target)                          # 首写
        tmp = tmp_path / "m.new"; tmp.write_bytes(b"v1")
        assert promote_with_backup(tmp, target) == ROTATED        # .bak=v0
        tmp = tmp_path / "m.new"; tmp.write_bytes(b"v1")
        assert promote_with_backup(tmp, target) == SKIPPED_SAME_SHA  # 链不动
        assert (tmp_path / "m.pkl.bak").read_bytes() == b"v0"

        tmp = tmp_path / "m.new"; tmp.write_bytes(b"v2")
        assert promote_with_backup(tmp, target) == ROTATED        # .bak=v1 .bak2=v0
        assert (tmp_path / "m.pkl.bak").read_bytes() == b"v1"
        assert (tmp_path / "m.pkl.bak2").read_bytes() == b"v0"
