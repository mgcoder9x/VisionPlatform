"""Step 03: contract test - mọi IFrameSource adapter PHẢI pass cùng test."""
import numpy as np
import pytest
from vision_platform.kernel.read_result import ReadStatus
from vision_platform.adapters.fake_frame_source import FakeFrameSource
from vision_platform.adapters.noise_frame_source import NoiseFrameSource


@pytest.fixture(params=[
    pytest.param(
        lambda: FakeFrameSource(width=320, height=240, max_frames=5),
        id="fake_finite_5",
    ),
    pytest.param(
        lambda: FakeFrameSource(width=160, height=120, max_frames=None),
        id="fake_infinite",
    ),
    pytest.param(
        lambda: NoiseFrameSource(width=320, height=240, max_frames=5),
        id="noise_finite_5",
    ),
])
def source(request):
    """Builder fixture - tạo adapter mới mỗi test (isolation)."""
    src = request.param()
    src.setup()
    yield src
    src.teardown()


class TestFrameSourceContract:
    """Mọi IFrameSource impl PHẢI thỏa các contract sau."""

    def test_read_returns_readresult(self, source):
        result = source.read(timeout_ms=100)
        assert hasattr(result, "status")

    def test_first_read_returns_valid_status(self, source):
        result = source.read(timeout_ms=100)
        assert result.status in {
            ReadStatus.FRAME, ReadStatus.EOF, ReadStatus.TIMEOUT,
            ReadStatus.RECONNECTING, ReadStatus.DROPPED, ReadStatus.ERROR,
        }

    def test_frame_status_implies_data(self, source):
        result = source.read(timeout_ms=100)
        if result.status == ReadStatus.FRAME:
            assert result.data is not None
            assert isinstance(result.data, np.ndarray)
            assert result.data.ndim == 3
            assert result.has_data

    def test_non_frame_status_no_data(self, source):
        for _ in range(20):
            result = source.read(timeout_ms=10)
            if result.status != ReadStatus.FRAME:
                assert result.data is None

    def test_source_id_is_str(self, source):
        assert isinstance(source.source_id, str)
        assert len(source.source_id) > 0

    def test_is_finite_is_bool(self, source):
        assert isinstance(source.is_finite, bool)

    def test_setup_idempotent(self, source):
        source.setup()  # already setup in fixture
        source.setup()  # 2nd call must not raise

    def test_teardown_idempotent(self, source):
        source.teardown()
        source.teardown()  # 2nd call must not raise

    def test_finite_source_eventually_eofs(self, source):
        if not source.is_finite:
            pytest.skip("Source is infinite")
        seen_eof = False
        for _ in range(1000):
            r = source.read(timeout_ms=10)
            if r.status == ReadStatus.EOF:
                seen_eof = True
                break
        assert seen_eof


# ============ Adapter-specific tests ============

def test_fake_frame_content_predictable():
    """Fake source dùng frame_count % 256 — verify."""
    src = FakeFrameSource(width=10, height=10, max_frames=None)
    src.setup()

    r0 = src.read()
    assert r0.data[0, 0, 0] == 0

    r1 = src.read()
    assert r1.data[0, 0, 0] == 1

    src.teardown()


def test_fake_inject_error():
    src = FakeFrameSource(max_frames=10, inject_error_at=2)
    src.setup()

    assert src.read().status == ReadStatus.FRAME
    assert src.read().status == ReadStatus.FRAME
    r = src.read()
    assert r.status == ReadStatus.ERROR
    assert "Injected" in str(r.error)
    assert src.read().status == ReadStatus.FRAME

    src.teardown()


def test_noise_seed_reproducible():
    """Same seed → same frames."""
    a = NoiseFrameSource(seed=42, max_frames=3)
    b = NoiseFrameSource(seed=42, max_frames=3)
    a.setup(); b.setup()

    fa = a.read().data
    fb = b.read().data
    assert np.array_equal(fa, fb)

    a.teardown(); b.teardown()


def test_source_id_unique_by_default():
    """ERRATA E-13 (Risk 3): 2 instance không truyền id → source_id KHÁC nhau
    (port contract yêu cầu unique). Vẫn cho phép truyền id tường minh."""
    a = FakeFrameSource()
    b = FakeFrameSource()
    assert a.source_id != b.source_id
    n1 = NoiseFrameSource()
    n2 = NoiseFrameSource()
    assert n1.source_id != n2.source_id
    # explicit id vẫn giữ nguyên:
    assert FakeFrameSource(_source_id="cam1").source_id == "cam1"


@pytest.mark.parametrize("builder", [
    lambda: FakeFrameSource(max_frames=3),
    lambda: NoiseFrameSource(max_frames=3),
])
def test_source_context_manager(builder):
    """R2#04 (ERRATA E-16): adapter là context manager — vào setup, ra teardown (kể cả khi raise).
    Đồng bộ vòng đời tài nguyên với SyncLinearExecutor → dùng được `with source, executor:`."""
    src = builder()
    with src as s:
        assert s is src
        assert s.read().status == ReadStatus.FRAME   # đã setup -> read không raise
    with pytest.raises(RuntimeError):
        src.read()   # ra khỏi with -> teardown -> read raise (chưa setup)

    # teardown vẫn chạy khi thân with raise:
    src2 = builder()
    with pytest.raises(ValueError):
        with src2:
            raise ValueError("boom")
    with pytest.raises(RuntimeError):
        src2.read()   # đã teardown
