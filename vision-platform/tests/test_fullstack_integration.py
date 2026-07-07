"""Full-stack integration test (sub-spec full-stack-integration-profile, capstone).

Spawn TOÀN HỆ qua `run_profile`: composition-root → Supervisor → 2 process (inference-server + camera,
bulkhead). Chứng minh frame chảy THẬT cross-process: camera → SHM → (ZMQ) inference → detections, rồi
shutdown sạch. Verify qua ARTIFACT FILE (design QĐ-4) — metrics per-process không gộp cross-process được.

Guard win32: SHM + ZMQ + spawn ĐÃ verify từng phần trên Windows (#05b T-B / zmq / #09); POSIX chưa verify.
Timeout rộng (Windows spawn chậm + ghép 3 hệ).
"""
from __future__ import annotations

import sys

import pytest

from vision_platform.profiles.vision_fullstack_profile import run_profile, parse_result

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="verify Windows (nền hiện tại); POSIX chưa verify",
)


def test_fullstack_end_to_end(tmp_path):
    """Property 1 + 2: frame chảy end-to-end (infer_ok>=1 THẬT cross-process) + shutdown sạch (run trả về)."""
    result_path = str(tmp_path / "result.txt")

    # Property 2: run_profile TRẢ VỀ (không hang) trong thời gian hợp lý.
    counts = run_profile(3.0, result_path=result_path)
    assert isinstance(counts, dict)
    assert set(counts.keys()) == {"inference", "camera"}

    # Property 1: đọc artifact camera ghi lúc shutdown → frame chảy end-to-end.
    data = parse_result(result_path)
    assert data["frames_ok"] >= 1, f"camera KHÔNG ghi được frame nào vào SHM: {data}"
    assert data["infer_ok"] >= 1, (
        f"KHÔNG có inference THÀNH CÔNG nào cross-process (camera→SHM→ZMQ→detector): {data}"
    )
