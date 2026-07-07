"""Test Task 1 (spec shm-production-hardening): định danh & liveness tiến trình.

Dùng fake `query` để giả lập PID reuse / AccessDenied / không tồn tại mà KHÔNG cần spawn process thật
(deterministic, không flaky, không phụ thuộc OS state). Một test happy-path chạy psutil thật trên chính
tiến trình test (chắc chắn ALIVE).

Chạy: ghi output ra file rồi đọc (terminal Windows nuốt output) — xem Task 1 / Requirement 12.5.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from vision_platform.runtime.ipc._process_identity import (
    Liveness,
    ProcessAccessUnknown,
    ProcessNotFound,
    _psutil_query,
    current_identity,
    owner_liveness,
)
import psutil


# ============ current_identity (real psutil) ============

def test_current_identity_returns_pid_and_create_time():
    pid, ct_ns = current_identity()
    assert pid == os.getpid()
    assert pid > 0
    assert ct_ns > 0


def test_self_is_alive_real_psutil():
    """Happy-path đường thật: chính tiến trình test phải ALIVE (psutil query mặc định)."""
    pid, ct_ns = current_identity()
    assert owner_liveness(pid, ct_ns) is Liveness.ALIVE


def test_self_with_wrong_create_time_is_dead_real_psutil():
    """PID đúng nhưng create_time lệch → DEAD (mô phỏng PID reuse trên đường psutil thật)."""
    pid, ct_ns = current_identity()
    assert owner_liveness(pid, ct_ns + 1) is Liveness.DEAD


# ============ owner_liveness với fake query (deterministic) ============

def test_nonexistent_pid_is_dead():
    def query(_pid):
        raise ProcessNotFound("no such process")
    assert owner_liveness(12345, 999, query=query) is Liveness.DEAD


def test_pid_reuse_different_create_time_is_dead():
    def query(_pid):
        return True, 7777  # còn chạy nhưng create_time KHÁC giá trị lưu (1111)
    assert owner_liveness(4242, 1111, query=query) is Liveness.DEAD


def test_not_running_is_dead():
    def query(_pid):
        return False, 1111  # create_time khớp nhưng is_running=False
    assert owner_liveness(4242, 1111, query=query) is Liveness.DEAD


def test_access_denied_is_unknown():
    def query(_pid):
        raise ProcessAccessUnknown("access denied")
    assert owner_liveness(4242, 1111, query=query) is Liveness.UNKNOWN


def test_matching_identity_is_alive():
    def query(_pid):
        return True, 1111  # is_running + create_time khớp
    assert owner_liveness(4242, 1111, query=query) is Liveness.ALIVE


@pytest.mark.parametrize("bad_pid", [0, -1, -999])
def test_nonpositive_pid_is_dead(bad_pid):
    called = False

    def query(_pid):  # KHÔNG được gọi khi pid <= 0
        nonlocal called
        called = True
        return True, 1111

    assert owner_liveness(bad_pid, 1111, query=query) is Liveness.DEAD
    assert called is False  # short-circuit trước khi hỏi OS


# ============ _psutil_query: map exception psutil THẬT (monkeypatch, deterministic) ============
# Phủ nhánh except của đường psutil thật mà KHÔNG phụ thuộc pid OS (chống flaky + chống PID reuse).

class _FakeProc:
    def __init__(self, running: bool, ct_seconds: float):
        self._running = running
        self._ct = ct_seconds

    def is_running(self) -> bool:
        return self._running

    def create_time(self) -> float:
        return self._ct


def test_psutil_query_happy_returns_tuple(monkeypatch):
    monkeypatch.setattr(psutil, "Process", lambda pid=None: _FakeProc(True, 1.5))
    is_running, ct_ns = _psutil_query(4242)
    assert is_running is True
    assert ct_ns == int(1.5 * 1_000_000_000)


def test_psutil_query_maps_nosuchprocess_to_notfound(monkeypatch):
    def boom(pid=None):
        raise psutil.NoSuchProcess(pid)
    monkeypatch.setattr(psutil, "Process", boom)
    with pytest.raises(ProcessNotFound):
        _psutil_query(4242)


def test_psutil_query_maps_accessdenied_to_unknown(monkeypatch):
    def boom(pid=None):
        raise psutil.AccessDenied(pid)
    monkeypatch.setattr(psutil, "Process", boom)
    with pytest.raises(ProcessAccessUnknown):
        _psutil_query(4242)


def test_psutil_query_maps_oserror_to_unknown(monkeypatch):
    def boom(pid=None):
        raise OSError("platform error")
    monkeypatch.setattr(psutil, "Process", boom)
    with pytest.raises(ProcessAccessUnknown):
        _psutil_query(4242)


def test_owner_liveness_default_query_dead_on_nosuchprocess(monkeypatch):
    """Tích hợp: owner_liveness KHÔNG truyền query → dùng _psutil_query thật → DEAD khi NoSuchProcess."""
    def boom(pid=None):
        raise psutil.NoSuchProcess(pid)
    monkeypatch.setattr(psutil, "Process", boom)
    assert owner_liveness(4242, 1111) is Liveness.DEAD


def test_owner_liveness_default_query_unknown_on_accessdenied(monkeypatch):
    """Tích hợp: owner_liveness mặc định → UNKNOWN khi AccessDenied (KHÔNG quarantine)."""
    def boom(pid=None):
        raise psutil.AccessDenied(pid)
    monkeypatch.setattr(psutil, "Process", boom)
    assert owner_liveness(4242, 1111) is Liveness.UNKNOWN


# ============ Guard kiến trúc: KHÔNG dùng os.kill (cạm bẫy Windows CTRL_C_EVENT) ============

def test_module_does_not_call_os_kill():
    """Requirement 2.7: KHÔNG GỌI os.kill(pid,0) — trên Windows = CTRL_C_EVENT (đã verify thật).

    Dùng AST để bắt LỜI GỌI thật `os.kill(...)`, bỏ qua docstring/comment (chỗ giải thích vì sao tránh nó).
    """
    import ast

    src = Path(__file__).resolve().parents[1] / "src" / "vision_platform" / "runtime" / "ipc" / "_process_identity.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))

    calls_os_kill = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "kill"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
        for node in ast.walk(tree)
    )
    assert calls_os_kill is False

    # Module cũng KHÔNG import `os` (không cần os-level signal; chỉ dùng psutil).
    imports_os = any(
        (isinstance(node, ast.Import) and any(a.name == "os" for a in node.names))
        or (isinstance(node, ast.ImportFrom) and node.module == "os")
        for node in ast.walk(tree)
    )
    assert imports_os is False
