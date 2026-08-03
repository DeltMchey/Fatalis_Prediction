"""P4 Step 4: CombatRecorder tests — mock MemoryReader/StateTracker 录制测试。

策略：
  - MemoryReader 用 unittest.mock.MagicMock(spec=MemoryReader) 模拟（无 pymem 依赖）
  - StateTracker 用真实 CombatStateTracker（纯逻辑）验证状态流；另有一组
    mock StateTracker 验证"只能通过 state 对象读取状态"的接口契约
  - CSV I/O 使用 pytest tmp_path，无需真实游戏内存
  - 线程测试使用真实 start()/stop()，join 等待退出，避免遗留 daemon 线程

覆盖：
  - 构造与默认参数
  - header 生成（_create_file）：列名、文件格式、嵌套目录
  - 门控（_should_pause）：is_recording 开关 / zone gating
  - 帧录制（_record_frame）：CSV 行内容、action_buffer 写入、数据不完整跳过
  - mock StateTracker：状态值流入 CSV
  - 生命周期（start/stop/run）：daemon 线程、幂等、退出、真实录制
  - 结构约束：无 pymem 直读、无 shared_state
"""

import csv
import threading
import time
from collections import deque
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.config.offsets import OFFSETS
from src.core.memory_reader import MemoryReader
from src.core.state_tracker import CombatStateTracker
from src.data.recorder import CombatRecorder

# CSV 列名单一数据源 = CombatRecorder._COLUMNS（测试直接引用，避免拷贝漂移）
EXPECTED_HEADER = list(CombatRecorder._COLUMNS)

FAKE_MONSTER_PTR = 0x30000000
FAKE_P_COORDS = [100.0, 0.0, 200.0]
FAKE_M_COORDS = [110.0, 0.0, 210.0]
FAKE_M_QUAT = [0.0, 1.0, 0.0, 0.0]

# 期望值（基于 FAKE_* 常量计算）：
#   dist = sqrt((100-110)^2 + (200-210)^2) = sqrt(200) ≈ 14.1421356
#   rel_angle：quat [w=0,x=1,y=0,z=0] → monster_yaw=180°，
#              target_yaw=atan2(-10,-10)=-135° → (-135-180+180)%360-180 = 45.0
EXPECTED_DIST = 14.142135623730951
EXPECTED_ANGLE = 45.0


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_reader():
    """返回模拟 MemoryReader，默认提供有效战斗数据。"""
    reader = MagicMock(spec=MemoryReader)
    reader.check_zone.return_value = OFFSETS.ZONE_FATALIS
    reader.find_monster.return_value = FAKE_MONSTER_PTR
    reader.read_player_coords.return_value = FAKE_P_COORDS
    reader.read_monster_coords.return_value = FAKE_M_COORDS
    reader.read_monster_quat.return_value = FAKE_M_QUAT
    reader.read_monster_hp.return_value = 0.65
    reader.read_monster_action.return_value = 42
    return reader


@pytest.fixture
def state():
    """真实 CombatStateTracker（is_recording=True 默认）。"""
    return CombatStateTracker(is_recording=True)


@pytest.fixture
def buffer():
    return deque(maxlen=100)


@pytest.fixture
def lock():
    return threading.Lock()


@pytest.fixture
def recorder(mock_reader, state, buffer, lock, tmp_path):
    return CombatRecorder(
        mock_reader, state, buffer, lock, data_dir=str(tmp_path)
    )


def read_csv_rows(filepath):
    with open(filepath, newline='') as f:
        return list(csv.reader(f))


# =============================================================================
# 1. 构造与属性
# =============================================================================

class TestInitialization:
    def test_stores_dependencies(self, mock_reader, state, buffer, lock):
        rec = CombatRecorder(mock_reader, state, buffer, lock, data_dir="custom")
        assert rec._reader is mock_reader
        assert rec._state is state
        assert rec._buffer is buffer
        assert rec._lock is lock
        assert rec._data_dir == "custom"

    def test_default_data_dir_is_data(self, mock_reader, state, buffer, lock):
        rec = CombatRecorder(mock_reader, state, buffer, lock)
        assert rec._data_dir == "data"

    def test_initial_state(self, recorder):
        assert recorder.is_running is False
        assert recorder._thread is None
        assert recorder._file_created is False
        assert recorder._filename is None


# =============================================================================
# 2. header 生成（_create_file）
# =============================================================================

class TestCreateFile:
    def test_creates_csv_with_header_only(self, recorder, tmp_path):
        path = recorder._create_file()
        assert Path(path).exists()
        rows = read_csv_rows(path)
        assert rows[0] == EXPECTED_HEADER
        assert len(rows) == 1  # 仅 header

    def test_returns_path_inside_data_dir(self, recorder, tmp_path):
        path = recorder._create_file()
        assert Path(path).parent == tmp_path
        assert str(path).startswith(str(tmp_path))

    def test_filename_format(self, recorder):
        path = recorder._create_file()
        name = Path(path).name
        assert name.startswith("fatalis_combat_data_")
        assert name.endswith(".csv")

    def test_creates_nested_data_dir(self, mock_reader, state, buffer, lock, tmp_path):
        rec = CombatRecorder(
            mock_reader, state, buffer, lock,
            data_dir=str(tmp_path / "nested" / "dir"),
        )
        path = rec._create_file()
        assert Path(path).parent.exists()


# =============================================================================
# 3. 门控（_should_pause）
# =============================================================================

class TestShouldPause:
    def test_recording_on_in_fatalis_not_paused(self, recorder):
        assert recorder._should_pause() is False

    def test_recording_off_pauses(self, recorder):
        recorder._state.is_recording = False
        assert recorder._should_pause() is True

    def test_wrong_zone_pauses(self, recorder, mock_reader):
        mock_reader.check_zone.return_value = 123
        assert recorder._should_pause() is True

    def test_zone_read_failure_pauses(self, recorder, mock_reader):
        mock_reader.check_zone.return_value = None
        assert recorder._should_pause() is True

    def test_zone_zero_pauses(self, recorder, mock_reader):
        mock_reader.check_zone.return_value = 0
        assert recorder._should_pause() is True


# =============================================================================
# 4. 帧录制（_record_frame）
# =============================================================================

class TestRecordFrame:
    def test_writes_header_and_one_row(self, recorder, buffer):
        ok = recorder._record_frame()
        assert ok is True
        assert recorder._file_created is True
        assert buffer == deque([42])
        rows = read_csv_rows(Path(recorder._filename))
        assert len(rows) == 2  # header + 1 数据行
        assert rows[0] == EXPECTED_HEADER

    def test_data_row_content(self, recorder):
        recorder._record_frame()
        rows = read_csv_rows(Path(recorder._filename))
        data = rows[1]
        # [timestamp, hp_percent, phase, is_enraged, distance, relative_angle, posture, action_id]
        assert abs(float(data[0]) - time.time()) < 5.0   # 当前时间戳
        assert float(data[1]) == pytest.approx(0.65)      # hp_percent
        assert int(data[2]) == 1                          # phase
        assert int(data[3]) == 0                          # is_enraged
        assert float(data[4]) == pytest.approx(EXPECTED_DIST)   # distance
        assert float(data[5]) == pytest.approx(EXPECTED_ANGLE)  # relative_angle
        assert int(data[6]) == 1                          # posture
        assert int(data[7]) == 42                         # action_id

    def test_state_values_flow_into_row(self, recorder, state):
        state.update_phase(0.60)          # → phase=2
        state.update_enrage(5.0, 10.0)    # → is_enraged=1
        state.update_posture(49)          # 49 ∈ POSTURE_PRONE → posture=0
        recorder._record_frame()
        rows = read_csv_rows(Path(recorder._filename))
        data = rows[1]
        assert int(data[2]) == 2
        assert int(data[3]) == 1
        assert int(data[6]) == 0

    def test_appends_action_each_frame(self, recorder, buffer):
        recorder._record_frame()
        recorder._record_frame()
        assert buffer == deque([42, 42])

    def test_multiple_frames_append_rows(self, recorder):
        recorder._record_frame()
        recorder._record_frame()
        recorder._record_frame()
        rows = read_csv_rows(Path(recorder._filename))
        assert len(rows) == 4  # header + 3 数据行

    def test_header_written_only_once(self, recorder):
        recorder._record_frame()
        recorder._record_frame()
        rows = read_csv_rows(Path(recorder._filename))
        assert rows[0] == EXPECTED_HEADER
        assert rows[1][0] != "timestamp"  # 第二行是数据行

    def test_no_monster_skips_frame(self, recorder, buffer, mock_reader):
        mock_reader.find_monster.return_value = None
        ok = recorder._record_frame()
        assert ok is False
        assert recorder._file_created is False
        assert recorder._filename is None
        assert buffer == deque()

    def test_no_player_coords_skips_frame(self, recorder, mock_reader):
        mock_reader.read_player_coords.return_value = None
        assert recorder._record_frame() is False
        assert recorder._file_created is False

    def test_incomplete_monster_data_skips_frame(self, recorder, mock_reader):
        mock_reader.read_monster_hp.return_value = None
        assert recorder._record_frame() is False
        assert recorder._file_created is False

    def test_action_read_failure_skips_frame(self, recorder, mock_reader):
        mock_reader.read_monster_action.return_value = None
        assert recorder._record_frame() is False
        assert recorder._file_created is False

    def test_skipped_frame_leaves_buffer_untouched(self, recorder, buffer, mock_reader):
        mock_reader.read_monster_hp.return_value = None
        recorder._record_frame()
        assert buffer == deque()


# =============================================================================
# 5. mock StateTracker（接口契约：只能通过 state 对象读取状态）
# =============================================================================

class TestMockStateTracker:
    def test_state_values_flow_via_object_interface(self, mock_reader, tmp_path):
        mock_state = MagicMock(spec=CombatStateTracker)
        mock_state.is_recording = True
        mock_state.phase = 3
        mock_state.is_enraged = 1
        mock_state.posture = 2
        mock_state.calc_distance_2d.return_value = 7.5
        mock_state.calc_relative_angle.return_value = -30.0
        rec = CombatRecorder(
            mock_reader, mock_state, deque(), threading.Lock(),
            data_dir=str(tmp_path),
        )
        assert rec._should_pause() is False
        assert rec._record_frame() is True
        rows = read_csv_rows(Path(rec._filename))
        data = rows[1]
        assert float(data[4]) == pytest.approx(7.5)
        assert float(data[5]) == pytest.approx(-30.0)
        assert int(data[2]) == 3
        assert int(data[3]) == 1
        assert int(data[6]) == 2

    def test_mock_state_recording_off_pauses(self, mock_reader):
        mock_state = MagicMock(spec=CombatStateTracker)
        mock_state.is_recording = False
        rec = CombatRecorder(mock_reader, mock_state, deque(), threading.Lock())
        assert rec._should_pause() is True


# =============================================================================
# 6. 生命周期（start / stop / run）
# =============================================================================

class TestLifecycle:
    def test_start_spawns_daemon_thread(self, recorder):
        recorder.start()
        assert recorder.is_running is True
        assert recorder._thread is not None
        assert recorder._thread.is_alive() is True
        assert recorder._thread.daemon is True
        recorder.stop()
        recorder._thread.join(timeout=5)

    def test_start_twice_single_thread(self, recorder):
        recorder.start()
        first = recorder._thread
        recorder.start()  # 幂等
        assert recorder._thread is first
        recorder.stop()
        recorder._thread.join(timeout=5)

    def test_stop_ends_thread(self, recorder):
        recorder.start()
        assert recorder._thread.is_alive()
        recorder.stop()
        recorder._thread.join(timeout=5)
        assert recorder._thread.is_alive() is False
        assert recorder.is_running is False

    def test_stop_idempotent(self, recorder):
        recorder.start()
        recorder.stop()
        recorder.stop()  # 重复 stop 不抛异常
        recorder._thread.join(timeout=5)

    def test_stop_before_start_noop(self, recorder):
        recorder.stop()  # 未 start 也能安全调用
        assert recorder.is_running is False
        assert recorder._thread is None

    def test_thread_records_frames_until_stop(self, recorder, buffer, tmp_path):
        recorder.start()
        time.sleep(0.5)  # 约 5 帧（每帧 0.1s）
        recorder.stop()
        recorder._thread.join(timeout=5)
        csv_files = list(tmp_path.glob("fatalis_combat_data_*.csv"))
        assert len(csv_files) == 1
        rows = read_csv_rows(csv_files[0])
        assert rows[0] == EXPECTED_HEADER
        assert len(rows) >= 2          # header + ≥1 数据行
        assert len(buffer) >= 1        # action 已写入共享 buffer

    def test_thread_pauses_when_recording_off(self, recorder, buffer, tmp_path):
        recorder._state.is_recording = False
        recorder.start()
        time.sleep(0.35)
        recorder.stop()
        recorder._thread.join(timeout=5)
        assert list(tmp_path.glob("fatalis_combat_data_*.csv")) == []
        assert buffer == deque()

    def test_thread_survives_frame_exception(self, recorder, mock_reader, tmp_path):
        """D3: 单帧异常 → logger.warning → 继续循环，线程不被杀死。"""
        mock_reader.find_monster.side_effect = RuntimeError("memory read failed")
        recorder.start()
        time.sleep(0.35)  # 经历多次异常帧
        assert recorder._thread.is_alive() is True  # 异常未终止线程
        recorder.stop()
        recorder._thread.join(timeout=5)
        assert recorder._thread.is_alive() is False
        # 帧读取失败 → 没有产生 CSV 文件
        assert list(tmp_path.glob("fatalis_combat_data_*.csv")) == []


# =============================================================================
# 7. 结构约束（无 pymem 直读 / 无 shared_state）
# =============================================================================

class TestStructuralConstraints:
    def test_no_direct_pymem_or_shared_state(self):
        import inspect
        import re
        import src.data.recorder as recorder_module
        src = inspect.getsource(recorder_module)
        # 禁止 import pymem（直接进程内存访问依赖）
        assert not re.search(r"^\s*(?:import|from)\s+pymem", src, re.MULTILINE)
        # 禁止直接调用 pm.read_*（MemoryReader 是唯一内存读取入口）
        assert not re.search(
            r"\.read_(?:int|float|longlong|ulonglong|string|bytes)\(", src)
        # 禁止读写 shared_state 全局 dict（CombatStateTracker 是唯一状态入口）
        assert not re.search(r"\bshared_state\s*[\[.=]", src)
