"""Điểm vào DUY NHẤT chạy toàn bộ drift-check — dùng cho hook + đầu phiên.

VÌ SAO file này (bản chất): hook runCommand chạy "A; B" bị mangle (`;` dán vào argv, không phải separator)
→ mọi lệnh nhiều-phần đều hỏng bất kể shell. Giải pháp gốc = MỘT script gọi cả 2 linter nội bộ → hook/đầu
phiên chỉ cần 1 lệnh `python tests/drift_check.py` (không separator, shell-agnostic) = một-nguồn-sự-thật.

Chạy: `py tests/drift_check.py`   (exit 0 = bản ghi nhất quán, 1 = có DRIFT → sửa trước khi tiếp).
Gồm: (1) nhất quán bộ nhớ (test_memory_consistency) + (2) RULES_VERSION sync (test_rules_sync).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_memory_consistency as mc   # noqa: E402
import test_rules_sync as rs           # noqa: E402


def main() -> int:
    print("=== [1/2] MEMORY CONSISTENCY (LOG/journal/INDEX/activeContext khớp thực tế) ===")
    mc_ok, mc_report = mc.check()
    for r in mc_report:
        print(r)

    print("\n=== [2/2] RULES_VERSION SYNC (4 mirror khớp) ===")
    rs_ok, rs_versions = rs.check()
    for f, ver in rs_versions.items():
        print(f"{ver if ver else 'MISSING':>8}  {f}")

    ok = mc_ok and rs_ok
    print("\nDRIFT-CHECK: " + ("PASS — bản ghi nhất quán." if ok
                               else "FAIL — có DRIFT, SỬA bản ghi cho khớp thực tế TRƯỚC khi làm tiếp."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
