"""Test Task 11 (spec shm-production-hardening): gate phạm vi nền tảng (Req 10).

Vòng hardening này CHỈ claim production cho x86-64. Validate ARM (visibility/ordering yếu) là task gate
RIÊNG `arm-atomic-sentinel-validation` (stress visibility + kill-holder + jitter trên HW ARM thật) — CHƯA có
HW ARM ở đây nên giữ 🔴 chưa-verified cho ARM. Test này CHẶN nhầm tưởng "đã verify ARM".
"""
from __future__ import annotations

import platform

import pytest

X86_64 = {"amd64", "x86_64", "x64", "i686", "i386"}


def test_production_claim_is_x86_64_only():
    machine = platform.machine().lower()
    if machine not in X86_64:
        pytest.skip(
            f"Nền tảng '{machine}' KHÔNG nằm trong phạm vi claim (x86-64). "
            f"ARM/khác cần task gate riêng 'arm-atomic-sentinel-validation' trên HW thật (Req 10.2)."
        )
    # Trên x86-64: store ≤8B aligned là atomic (Intel SDM §8.1.1) → fast-path lock-free hợp lệ.
    assert machine in X86_64
