"""D-098/K-088: `ensure_cuda_dll_path` prepend thư mục DLL nvidia vào PATH (idempotent, no-op an toàn).

Test bằng fake nvidia root (KHÔNG cần GPU/nvidia thật, deterministic)."""
from __future__ import annotations

import os

from vision_platform.adapters import cuda_dll_path as C


def _make_fake_nvidia(tmp_path):
    binx = tmp_path / "nvidia" / "cu13" / "bin" / "x86_64"
    binx.mkdir(parents=True)
    (binx / "cudart64_13.dll").write_bytes(b"\x00")
    cudnn = tmp_path / "nvidia" / "cudnn" / "bin"
    cudnn.mkdir(parents=True)
    (cudnn / "cudnn64_9.dll").write_bytes(b"\x00")
    return str(tmp_path / "nvidia"), str(binx), str(cudnn)


def test_prepends_dll_dirs_to_path(monkeypatch, tmp_path):
    root, binx, cudnn = _make_fake_nvidia(tmp_path)
    monkeypatch.setenv("PATH", "C:\\existing")
    dirs = C.ensure_cuda_dll_path([root], force=True)
    assert binx in dirs and cudnn in dirs                      # tìm cả layout cu13/bin/x86_64 lẫn cudnn/bin
    parts = os.environ["PATH"].split(os.pathsep)
    assert binx in parts and cudnn in parts                    # đã vào PATH
    assert parts[-1] == "C:\\existing"                          # PATH cũ giữ ở cuối (prepend, không mất)


def test_idempotent_no_duplicate(monkeypatch, tmp_path):
    root, binx, _ = _make_fake_nvidia(tmp_path)
    monkeypatch.setenv("PATH", "C:\\existing")
    C.ensure_cuda_dll_path([root], force=True)
    C.ensure_cuda_dll_path([root], force=True)                 # gọi lại
    assert os.environ["PATH"].split(os.pathsep).count(binx) == 1   # KHÔNG nhân đôi


def test_noop_when_no_nvidia(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", "C:\\existing")
    before = os.environ["PATH"]
    dirs = C.ensure_cuda_dll_path([str(tmp_path / "khong-ton-tai")], force=True)
    assert dirs == ()                                          # không tìm thấy → rỗng
    assert os.environ["PATH"] == before                        # PATH KHÔNG đổi (no-op an toàn)
