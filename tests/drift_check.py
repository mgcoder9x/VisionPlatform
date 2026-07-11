"""Điểm vào DUY NHẤT chạy toàn bộ drift-check — dùng cho hook + đầu phiên.

VÌ SAO file này (bản chất): hook runCommand chạy "A; B" bị mangle (`;` dán vào argv, không phải separator)
→ mọi lệnh nhiều-phần đều hỏng bất kể shell. Giải pháp gốc = MỘT script gọi cả 2 linter nội bộ → chỉ cần
1 lệnh (không separator, shell-agnostic) = một-nguồn-sự-thật.

CHẠY (chọn 1):
  - Hook/CI (portable, tự dò interpreter chạy được): `cmd /c tests\\drift_check.cmd`
  - Trực tiếp khi biết interpreter: `py tests/drift_check.py` (Windows python.org) hoặc `python3 tests/drift_check.py` (Linux).
Vì SAO có launcher `.cmd`: `python`/`py`/venv KHÁC nhau theo máy (python.org có `py`; scoop có `python`;
Windows Store-alias `python` tồn tại nhưng chạy lỗi 9009). Hook KHÔNG được hardcode 1 tên → launcher dò
theo KHẢ NĂNG (`--version` exit 0), dùng cái đầu tiên chạy được. Exit 0 = nhất quán · 1 = DRIFT → sửa trước.
Gồm: (1) nhất quán bộ nhớ (test_memory_consistency) + (2) RULES_VERSION sync (test_rules_sync).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_memory_consistency as mc   # noqa: E402
import test_rules_sync as rs           # noqa: E402


def main() -> int:
    print("=== [1/3] MEMORY CONSISTENCY (LOG/journal/INDEX/activeContext khớp thực tế) ===")
    mc_ok, mc_report = mc.check()
    for r in mc_report:
        print(r)

    print("\n=== [2/3] RULES_VERSION SYNC (mọi mirror + kit khớp) ===")
    rs_ok, rs_versions = rs.check()
    for f, ver in rs_versions.items():
        print(f"{ver if ver else 'MISSING':>8}  {f}")

    print("\n=== [3/3] SELF-TEST checker (guard chống regex-rot — checker phải BẮT được drift) ===")
    st_ok, st_report = mc.self_test()
    for r in st_report:
        print(r)

    ok = mc_ok and rs_ok and st_ok
    print("\nDRIFT-CHECK: " + ("PASS — bản ghi nhất quán." if ok
                               else "FAIL — có DRIFT, SỬA bản ghi cho khớp thực tế TRƯỚC khi làm tiếp."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
