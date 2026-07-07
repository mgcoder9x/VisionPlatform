# Implementation Plan

> **Trạng thái:** PHA 2 (implement) — theo `design.md` đã valid (0 diagnostic).
> **Nguyên tắc:** ADDITIVE thuần, TDD, chạy test THẬT mới đánh ✅. Kỳ vọng 365/1 · lint 5/0.
> **Cập nhật lúc:** 2026-07-06.

- [x] 1. Viết test TRƯỚC (`tests/test_media_ref_port.py`) — đỏ trước khi có port
  - Test P1 conformance: `isinstance(InMemoryArrayRef.from_copy(arr), IMediaRef) is True`.
  - Test P2 substitutability: `_FakeMediaRef` (impl khác) vào `MediaPacket` → `BrightnessStage` chạy đúng,
    `artifacts["brightness"]` khớp `frame.mean()`.
  - Test P3/P4 invariance + read-only: pickle round-trip `MediaPacket(InMemoryArrayRef)` → `array.flags.writeable is False` + dữ liệu bằng + vẫn `isinstance IMediaRef`.
  - _Validates: R1, R2, R3 · Property 1–4_

- [x] 2. Tạo port `kernel/media_ref.py` (`IMediaRef` Protocol, `@runtime_checkable`, `array: np.ndarray`)
  - Chỉ import numpy + typing. Docstring: contract read-only-by-convention.
  - _Validates: R1 (1.1, 1.2, 1.3)_

- [x] 3. Nới type hint `kernel/media_packet.py` (`media_ref: InMemoryArrayRef → IMediaRef`)
  - Import `IMediaRef`. KHÔNG đổi runtime/pickle/CoW. InMemoryArrayRef giữ nguyên.
  - _Validates: R2 (2.1, 2.2)_

- [x] 4. VERIFY thật — ĐÃ CHẠY, output thật:
  - `pytest -q` → **369 passed / 1 skipped** (364 cũ + 5 mới; "365" dự đoán trước là ước lượng sai số test).
  - `lint-imports` → **5 kept / 0 broken**.
  - `get_diagnostics` media_ref.py / media_packet.py / test = **0**.
  - _Validates: R2.3, R3 · Definition of Done — ĐẠT_

- [x] 5. Cập nhật journal + LOG #207 + activeContext + progress (per-turn)
