"""conftest — gate test theo NĂNG LỰC máy (spec capability-aware-execution).

Test đánh dấu `@pytest.mark.gpu` sẽ tự SKIP khi máy KHÔNG có CUDA khả dụng (probe 1 lần lúc collect) →
CI xanh trên MỌI máy (GPU/không) mà không xoá/không giảm phủ test. Trên máy GPU, các test đó chạy thật.

Probe qua adapter thật (`probe_capabilities`) — an toàn (máy no-torch → has_cuda=False, không raise).
"""
from vision_platform.adapters.capability_probe import probe_capabilities

_CAPS = probe_capabilities()


def pytest_collection_modifyitems(config, items):
    import pytest

    if _CAPS.has_cuda:
        return  # máy có GPU → để test gpu chạy thật
    skip_gpu = pytest.mark.skip(
        reason=f"cần CUDA (máy không có CUDA khả dụng: has_torch={_CAPS.has_torch}) — skip tự động"
    )
    for item in items:
        if "gpu" in item.keywords:
            item.add_marker(skip_gpu)
