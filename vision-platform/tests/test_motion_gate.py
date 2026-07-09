"""Sub-spec motion-gate — test XÁC ĐỊNH (frame numpy dựng tay), không GPU.

Phủ: domain changed_ratio (underflow) · stage skip-tĩnh/pass-motion/first/shape/mixed-source · integration
(PipelineRunner: gate giảm số lần chạy stage sau).
"""
import numpy as np

from vision_platform.domain.motion import changed_ratio
from vision_platform.kernel.media_packet import MediaPacket, InMemoryArrayRef
from vision_platform.kernel.stage_contract import StageStatus
from vision_platform.runtime.base_stage import BaseStage
from vision_platform.runtime.pipeline_runner import PipelineRunner
from vision_platform.runtime.sync_linear_executor import SyncLinearExecutor
from vision_platform.runtime.composite_sink import CompositeSink
from vision_platform.runtime.stages.motion_gate_stage import MotionGateStage
from vision_platform.adapters.fake_frame_source import FakeFrameSource


def _frame(val, h=8, w=8):
    return np.full((h, w, 3), val, dtype=np.uint8)


def _packet(frame, source_id="cam0"):
    return MediaPacket(packet_id="p", source_id=source_id,
                       media_ref=InMemoryArrayRef.from_copy(frame), capture_time_ns=0)


# ================= domain: changed_ratio =================

def test_changed_ratio_identical_and_full():
    assert changed_ratio(_frame(100), _frame(100), 25) == 0.0     # giống hệt
    assert changed_ratio(_frame(100), _frame(200), 25) == 1.0     # đổi hết (|100|>25)


def test_changed_ratio_uint8_underflow_handled():
    # sáng→tối: |10-250|=240 > 25 → ĐỔI HẾT. Nếu KHÔNG cast int16, uint8 wrap = 16 < 25 → SAI (0.0).
    assert changed_ratio(_frame(250), _frame(10), 25) == 1.0


# ================= MotionGateStage =================

def test_first_frame_passes():  # P3
    st = MotionGateStage()
    r = st.process(_packet(_frame(100)))
    assert r.status == StageStatus.SUCCESS and r.packet.artifacts["motion_ratio"] == 1.0


def test_static_frame_skipped():  # P1
    st = MotionGateStage()
    st.process(_packet(_frame(100)))                 # frame đầu → pass
    r = st.process(_packet(_frame(100)))             # y hệt → tĩnh → SKIP
    assert r.status == StageStatus.SKIPPED and "motion" in r.skip_reason


def test_moving_frame_passes_with_ratio():  # P2
    st = MotionGateStage()
    st.process(_packet(_frame(100)))
    r = st.process(_packet(_frame(200)))             # đổi hết → đi tiếp
    assert r.status == StageStatus.SUCCESS and r.packet.artifacts["motion_ratio"] == 1.0


def test_shape_change_passes():  # P3
    st = MotionGateStage()
    st.process(_packet(_frame(100, 8, 8)))
    r = st.process(_packet(_frame(100, 4, 4)))       # khác shape → đi tiếp (không so được)
    assert r.status == StageStatus.SUCCESS


def test_mixed_source_errors():  # P5
    st = MotionGateStage()
    assert st.process(_packet(_frame(100), "cam0")).status == StageStatus.SUCCESS
    r = st.process(_packet(_frame(200), "cam9"))
    assert r.status == StageStatus.ERROR and r.error_type == "ValueError"


# ================= integration: gate giảm số lần chạy stage sau =================

class _CountStub(BaseStage):
    """Stage đếm số lần _do_process được gọi (đại diện detector đắt)."""
    def __init__(self):
        super().__init__("count_stub")
        self.calls = 0

    def _do_process(self, packet):
        self.calls += 1
        return packet


def test_gate_reduces_downstream_calls():  # integration
    # FakeFrameSource fill=count%256 → frame liên tiếp chênh 1/pixel (<25) → TĨNH → skip (trừ frame đầu).
    stub = _CountStub()
    runner = PipelineRunner(
        FakeFrameSource(max_frames=5),
        SyncLinearExecutor([MotionGateStage(), stub]),
        CompositeSink([]),
    )
    stats = runner.run(max_frames=5)
    assert stats.frames_read == 5
    assert stats.skipped >= 1                          # gate ĐÃ bỏ frame tĩnh
    assert stats.processed >= 1                        # ít nhất frame đầu đi tiếp
    assert stub.calls == stats.processed               # stage sau CHỈ chạy trên frame không-skip
    assert stub.calls < stats.frames_read              # < tổng frame = tiết kiệm thật
