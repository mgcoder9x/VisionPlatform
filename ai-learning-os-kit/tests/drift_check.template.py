"""TEMPLATE — Điểm vào DUY NHẤT chạy drift-check. Copy sang `tests/drift_check.py`.

VÌ SAO 1 script (bản chất): hook runCommand chạy "A; B" bị mangle (`;` dán vào argv, không phải separator)
→ dùng 1 script gọi cả 2 linter nội bộ → hook/đầu-phiên chỉ cần `python tests/drift_check.py` (shell-agnostic).

Chạy: `py tests/drift_check.py`  (exit 0 = nhất quán, 1 = có DRIFT).
Yêu cầu: `tests/test_memory_consistency.py` + `tests/test_rules_sync.py` (copy từ kit) cùng thư mục.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_memory_consistency as mc   # noqa: E402
import test_rules_sync as rs           # noqa: E402


def main() -> int:
    print("=== [1/2] MEMORY CONSISTENCY ===")
    mc_ok, mc_report = mc.check()
    for r in mc_report:
        print(r)
    print("\n=== [2/2] RULES_VERSION SYNC ===")
    rs_ok, rs_versions = rs.check()
    for f, ver in rs_versions.items():
        print(f"{ver if ver else 'MISSING':>8}  {f}")
    ok = mc_ok and rs_ok
    print("\nDRIFT-CHECK: " + ("PASS — bản ghi nhất quán." if ok
                               else "FAIL — có DRIFT, SỬA bản ghi TRƯỚC khi làm tiếp."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
