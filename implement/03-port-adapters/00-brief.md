# Vấn đề #03 — IFrameSource port + 2 adapter + contract test

> Nguồn Design: `Design/module-03-build-along/step-03-first-port.md`. (Brief backfill — chọn A.)

## Mục tiêu
1 driven port `IFrameSource` (Protocol) + 2 adapter (Fake, Noise) + 1 **contract test** parametrized
(1 suite, mọi adapter phải pass).

## File (4) — ở `vision-platform/`
- `kernel/ports/frame_source.py`, `adapters/fake_frame_source.py`, `adapters/noise_frame_source.py`,
  `tests/test_step_03_frame_source_contract.py`.

## Concept cốt lõi (để học/viết lại)
- **Driven port = Protocol** (structural typing) → adapter không cần inherit; mock dễ.
- **Contract test parametrized** (`pytest.fixture(params=[lambda:...])`): thêm adapter = thêm 1 dòng
  `pytest.param`. Builder-lambda → mỗi test 1 instance mới (isolation).
- **Lifecycle idempotent** (setup/teardown gọi nhiều lần an toàn).
- **is_finite** phân biệt batch (EOF=done) vs stream (EOF=bug).

## Findings (ERRATA) — phát hiện + xử lý
- **E-13 (Risk 3):** `source_id` default cố định ("fake_0"/"noise_0") → trùng, mâu thuẫn contract
  "unique" → đổi auto-unique (`itertools.count`). Vẫn cho truyền id tường minh.
- **Risk 1/2/4 (GHI NHẬN contract cho adapter THẬT):** thread-safety (bulkhead single-thread),
  timeout (RTSP phải trả TIMEOUT), setup nửa chừng (try/finally). Xem ERRATA E-13 + note step-03.

## Validate (thật)
- `pytest` → **51 passed, 1 skipped** (skip=fake_infinite eventually_eofs) · `lint-imports` → **5 kept/0 broken**.

## Trạng thái: ✅ XONG.
